"""
Test suite for Phase 0: Stop-ship safety fixes.

Exit criteria: a test suite where chest pain, breathing difficulty, mumbled audio,
and "Gemini returns nothing" all yield MEDIUM or HIGH, never LOW.
"""
import io
import numpy as np
import pytest
import scipy.io.wavfile as wavfile
from unittest.mock import AsyncMock, patch

from app.priority import apply_floor, assess_priority, _score_symptom
from app.safety import (
    screen_safety,
    scan_raw_transcript,
    _matches_keyword,
    is_negated_match,
    is_text_negated,
)
from app.pipeline import check_home_remedy_gate, run_pipeline
from app.schemas import (
    AcousticBiomarkerResult,
    Duration,
    DurationUnit,
    FieldConfidence,
    PriorityAssessment,
    PriorityLevel,
    RedFlag,
    SafetyRedFlag,
    SafetyScreening,
    Severity,
    StructuredMedicalSummary,
    Symptom,
    TranscriptionResult,
)
from app.services.sarvam_stt import SarvamSTTError
from app.services.gemini_extract import GeminiExtractionError


def _make_valid_wav(duration_s: float = 2.0, sample_rate: int = 16000) -> bytes:
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    signal = 0.5 * np.sin(2 * np.pi * 440 * t)
    signal_int16 = (signal * 32767).astype(np.int16)
    out = io.BytesIO()
    wavfile.write(out, sample_rate, signal_int16)
    return out.getvalue()



# =============================================================================
# 0.1: apply_floor tests
# =============================================================================

def test_apply_floor_critical_flag_elevates_to_high():
    """Any critical deterministic flag must floor final priority to HIGH."""
    screening = SafetyScreening(
        red_flags=[
            SafetyRedFlag(
                potential_red_flag=True,
                symptom="chest pain",
                reason="Severe chest pain reported",
                action="emergency_referral",
                severity="critical",
            )
        ]
    )
    assert apply_floor(PriorityLevel.LOW, screening) == PriorityLevel.HIGH
    assert apply_floor(PriorityLevel.MEDIUM, screening) == PriorityLevel.HIGH
    assert apply_floor(PriorityLevel.HIGH, screening) == PriorityLevel.HIGH


def test_apply_floor_high_flag_elevates_to_medium():
    """Any high deterministic flag must floor final priority to at least MEDIUM."""
    screening = SafetyScreening(
        red_flags=[
            SafetyRedFlag(
                potential_red_flag=True,
                symptom="chest pain",
                reason="Chest pain reported",
                action="clinician_review",
                severity="high",
            )
        ]
    )
    assert apply_floor(PriorityLevel.LOW, screening) == PriorityLevel.MEDIUM
    assert apply_floor(PriorityLevel.MEDIUM, screening) == PriorityLevel.MEDIUM
    assert apply_floor(PriorityLevel.HIGH, screening) == PriorityLevel.HIGH


def test_apply_floor_no_flags():
    """Without flags, apply_floor returns candidate level unchanged."""
    screening = SafetyScreening(red_flags=[])
    assert apply_floor(PriorityLevel.LOW, screening) == PriorityLevel.LOW
    assert apply_floor(PriorityLevel.MEDIUM, screening) == PriorityLevel.MEDIUM
    assert apply_floor(PriorityLevel.HIGH, screening) == PriorityLevel.HIGH
    assert apply_floor(PriorityLevel.LOW, None) == PriorityLevel.LOW


# =============================================================================
# 0.9: Word-boundary regex matching ("fits" substring bug)
# =============================================================================

def test_fits_word_boundary_regex_no_false_positives():
    """'fits' keyword matching must not trigger on 'benefits', 'fitness', or 'outfits'."""
    assert len(_matches_keyword("fits", "Taking this medication has many benefits for health.")) == 0
    assert len(_matches_keyword("fits", "The patient is improving physical fitness.")) == 0
    assert len(_matches_keyword("fits", "Patient bought new outfits.")) == 0
    assert len(_matches_keyword("fits", "The profit margins are good.")) == 0


def test_fits_word_boundary_regex_matches_actual_fits():
    """'fits' should match standalone word forms indicating seizures."""
    assert len(_matches_keyword("fits", "Patient had sudden fits.")) > 0
    assert len(_matches_keyword("fits", "History of fits and seizure.")) > 0
    assert len(_matches_keyword("fits", "fits")) > 0

    # Test via screen_safety
    summary = StructuredMedicalSummary(
        chief_complaint="Patient discussion",
        symptoms=[Symptom(name="benefits from medication", confidence=1.0)],
        red_flags=[],
    )
    screening = screen_safety(summary)
    assert not any("Seizure" in f.reason for f in screening.red_flags)

    # Actual fits
    summary_fits = StructuredMedicalSummary(
        chief_complaint="Convulsions",
        symptoms=[Symptom(name="fits", confidence=1.0)],
        red_flags=[],
    )
    screening_fits = screen_safety(summary_fits)
    assert any("Seizure or convulsions reported" in f.reason for f in screening_fits.red_flags)


# =============================================================================
# 0.6: Remove confidence discount on high-risk symptoms
# =============================================================================

def test_uncertain_chest_pain_no_confidence_discount():
    """High-risk symptoms like chest pain must not be discounted by low confidence."""
    symptom_low_conf = Symptom(name="chest pain", confidence=0.2)
    symptom_high_conf = Symptom(name="chest pain", confidence=1.0)

    score_low = _score_symptom(symptom_low_conf)
    score_high = _score_symptom(symptom_high_conf)
    # Uncertain chest pain retains full 3.0 base score
    assert score_low == pytest.approx(3.0)
    assert score_high == pytest.approx(3.0)

    # In contrast, non-high-risk symptom (e.g., headache) DOES scale with confidence
    headache_low = Symptom(name="headache", confidence=0.2)
    headache_high = Symptom(name="headache", confidence=1.0)
    assert _score_symptom(headache_low) < _score_symptom(headache_high)


def test_uncertain_chest_pain_escalates_to_at_least_medium():
    """Uncertain chest pain (confidence=0.2) must never yield LOW."""
    summary = StructuredMedicalSummary(
        chief_complaint="chest discomfort",
        symptoms=[Symptom(name="chest pain", confidence=0.2)],
        red_flags=[],
    )
    screening = screen_safety(summary)
    assessment = assess_priority(summary, safety_screening=screening)
    assert assessment.level in (PriorityLevel.MEDIUM, PriorityLevel.HIGH)
    assert assessment.level != PriorityLevel.LOW


# =============================================================================
# 0.7: Acoustic biomarkers capped at 'high' and advisory
# =============================================================================

def test_biomarker_flags_capped_at_high_and_advisory():
    biomarkers = AcousticBiomarkerResult(
        cough_count=12,
        cough_rate=12.0,
        wheeze_detected=True,
        wheeze_ratio=0.75,
        breathlessness_pauses=6,
        speech_dyspnea_index=0.8,
        respiratory_distress_score=0.92,
        distress_level="severe",
    )
    summary = StructuredMedicalSummary(
        chief_complaint="mild cough",
        symptoms=[Symptom(name="cough", severity=Severity.MILD, confidence=1.0)],
        red_flags=[],
    )
    screening = screen_safety(summary, biomarkers=biomarkers)

    bio_flags = [f for f in screening.red_flags if f.symptom == "respiratory_distress_acoustic"]
    assert len(bio_flags) == 1
    assert bio_flags[0].severity == "high"  # Capped at high, NOT critical
    assert bio_flags[0].action == "clinician_review"
    assert screening.has_critical_flags is False
    assert screening.override_priority is False

    # Priority assessment with this advisory flag floors to MEDIUM, not emergency HIGH override
    assessment = assess_priority(summary, safety_screening=screening)
    assert assessment.level == PriorityLevel.MEDIUM
    assert assessment.emergency_override is False


# =============================================================================
# 0.8: Negation handling on Gemini red flags and breathing unknown logic
# =============================================================================

def test_gemini_red_flags_negation_handling():
    """Negated red flags from Gemini should not generate safety red flags."""
    summary = StructuredMedicalSummary(
        chief_complaint="Cough and cold",
        symptoms=[Symptom(name="cough", confidence=1.0)],
        red_flags=[
            RedFlag(phrase="no chest pain", related_symptom="chest pain"),
            RedFlag(phrase="patient denies shortness of breath", related_symptom="difficulty breathing"),
        ],
    )
    screening = screen_safety(summary)
    assert not any("chest pain" in f.reason.lower() for f in screening.red_flags)
    assert not any("breathing" in f.reason.lower() for f in screening.red_flags)


def test_breathing_unknown_logic_with_negation():
    """
    If patient reports chest pain, but explicitly denies breathing difficulty:
    breathing status IS known, so 'Breathing status is unknown' must NOT be raised.
    """
    summary_known = StructuredMedicalSummary(
        chief_complaint="Chest pain",
        symptoms=[
            Symptom(name="chest pain", severity=Severity.MODERATE, confidence=1.0),
            Symptom(name="difficulty breathing", negated=True, confidence=1.0),
        ],
        red_flags=[],
    )
    screening_known = screen_safety(summary_known)
    assert not any("Breathing status is unknown" in msg for msg in screening_known.missing_critical_info)

    # But if breathing was never mentioned, breathing status IS unknown
    summary_unknown = StructuredMedicalSummary(
        chief_complaint="Chest pain",
        symptoms=[Symptom(name="chest pain", severity=Severity.MODERATE, confidence=1.0)],
        red_flags=[],
    )
    screening_unknown = screen_safety(summary_unknown)
    assert any("Breathing status is unknown" in msg for msg in screening_unknown.missing_critical_info)


# =============================================================================
# 0.2: Independent safety scan of raw English and Indic transcripts
# =============================================================================

def test_independent_raw_transcript_scan_english():
    """Safety scan must catch red flags in raw English text even if Gemini returns empty summary."""
    empty_summary = StructuredMedicalSummary(
        chief_complaint="",
        symptoms=[],
        red_flags=[],
    )
    raw_eng = "I am having severe chest pain since morning."
    screening = screen_safety(summary=empty_summary, transcript_english=raw_eng)

    assert any("chest pain" in f.reason.lower() for f in screening.red_flags)
    assert screening.has_critical_flags is True
    assert screening.override_priority is True


def test_independent_raw_transcript_scan_indic_tamil():
    """Safety scan must catch red flags in raw Tamil transcript."""
    empty_summary = StructuredMedicalSummary(
        chief_complaint="",
        symptoms=[],
        red_flags=[],
    )
    raw_tamil = "எனக்கு நெஞ்சு வலி கடுமையாக உள்ளது மற்றும் மூச்சு திணறல் இருக்கிறது"
    screening = screen_safety(summary=empty_summary, transcript_original=raw_tamil)

    assert len(screening.red_flags) >= 1
    assert any("chest pain" in f.reason.lower() for f in screening.red_flags)
    assert any("breathing" in f.reason.lower() for f in screening.red_flags)
    assert screening.has_critical_flags is True


def test_independent_raw_transcript_scan_indic_hindi():
    """Safety scan must catch red flags in raw Hindi transcript."""
    empty_summary = StructuredMedicalSummary(chief_complaint="", symptoms=[], red_flags=[])
    raw_hindi = "सीने में तेज दर्द है और सांस लेने में तकलीफ हो रही है"
    screening = screen_safety(summary=empty_summary, transcript_original=raw_hindi)

    assert any("chest pain" in f.reason.lower() for f in screening.red_flags)
    assert any("breathing" in f.reason.lower() for f in screening.red_flags)
    assert screening.has_critical_flags is True


def test_independent_raw_transcript_scan_indic_negation():
    """Negated red flag in raw Indic transcript should not trigger positive red flag."""
    raw_tamil_neg = "எனக்கு நெஞ்சு வலி இல்லை, வெறும் தலைவலி தான்"
    flags, has_cp, has_br = scan_raw_transcript(transcript_original=raw_tamil_neg)
    assert not any("chest pain" in f.reason.lower() for f in flags)
    assert has_cp is False


# =============================================================================
# 0.3: Insufficient input never yields LOW
# =============================================================================

def test_empty_extraction_never_yields_low():
    """Empty extraction in assess_priority must elevate to MEDIUM, never LOW."""
    empty_summary = StructuredMedicalSummary(
        chief_complaint="",
        symptoms=[],
        red_flags=[],
    )
    screening = screen_safety(empty_summary)
    assessment = assess_priority(empty_summary, safety_screening=screening)

    assert assessment.level in (PriorityLevel.MEDIUM, PriorityLevel.HIGH)
    assert assessment.level != PriorityLevel.LOW
    assert any("empty extraction" in r.lower() for r in assessment.reasons)


# =============================================================================
# 0.5: Gate home remedies
# =============================================================================

def test_home_remedies_gating_scenarios():
    """Test all exclusion gates for home remedies."""
    base_summary = StructuredMedicalSummary(
        chief_complaint="Mild runny nose",
        symptoms=[Symptom(name="cold-like symptoms", severity=Severity.MILD, confidence=0.9)],
        red_flags=[],
    )
    base_screening = SafetyScreening(red_flags=[])
    base_transcription = TranscriptionResult(
        transcript_original="I have a slight cold",
        transcript_english="I have a slight cold",
        language_code="en-IN",
        language_probability=0.95,
    )
    base_priority = PriorityAssessment(
        level=PriorityLevel.LOW,
        confidence=0.85,
    )

    # 1. Healthy adult -> Allowed
    allowed, reason = check_home_remedy_gate(
        patient_context={"age": "30"},
        summary=base_summary,
        safety_screening=base_screening,
        transcription=base_transcription,
        priority=base_priority,
        language_verification_required=False,
        stt_failed=False,
        extraction_failed=False,
    )
    assert allowed is True
    assert reason is None

    # 2. Child under 5 -> Excluded
    allowed, reason = check_home_remedy_gate(
        patient_context={"age": "3"},
        summary=base_summary,
        safety_screening=base_screening,
        transcription=base_transcription,
        priority=base_priority,
        language_verification_required=False,
        stt_failed=False,
        extraction_failed=False,
    )
    assert allowed is False
    assert "age exclusion" in reason.lower()

    # 3. Elderly over 65 -> Excluded
    allowed, reason = check_home_remedy_gate(
        patient_context={"age": "72"},
        summary=base_summary,
        safety_screening=base_screening,
        transcription=base_transcription,
        priority=base_priority,
        language_verification_required=False,
        stt_failed=False,
        extraction_failed=False,
    )
    assert allowed is False
    assert "age exclusion" in reason.lower()

    # 4. Pregnancy -> Excluded
    allowed, reason = check_home_remedy_gate(
        patient_context={"age": "28", "is_pregnant": "yes"},
        summary=base_summary,
        safety_screening=base_screening,
        transcription=base_transcription,
        priority=base_priority,
        language_verification_required=False,
        stt_failed=False,
        extraction_failed=False,
    )
    assert allowed is False
    assert "pregnancy exclusion" in reason.lower()

    # 5. Comorbidities -> Excluded
    allowed, reason = check_home_remedy_gate(
        patient_context={"age": "45", "known_conditions": "type 2 diabetes, hypertension"},
        summary=base_summary,
        safety_screening=base_screening,
        transcription=base_transcription,
        priority=base_priority,
        language_verification_required=False,
        stt_failed=False,
        extraction_failed=False,
    )
    assert allowed is False
    assert "comorbidity exclusion" in reason.lower()

    # 6. Missing critical info -> Excluded
    screening_with_missing = SafetyScreening(
        red_flags=[],
        missing_critical_info=["Breathing status is unknown for patient with chest pain."],
    )
    allowed, reason = check_home_remedy_gate(
        patient_context={"age": "35"},
        summary=base_summary,
        safety_screening=screening_with_missing,
        transcription=base_transcription,
        priority=base_priority,
        language_verification_required=False,
        stt_failed=False,
        extraction_failed=False,
    )
    assert allowed is False
    assert "missing critical info" in reason.lower()

    # 7. Low priority confidence -> Excluded
    low_conf_priority = PriorityAssessment(level=PriorityLevel.LOW, confidence=0.55)
    allowed, reason = check_home_remedy_gate(
        patient_context={"age": "30"},
        summary=base_summary,
        safety_screening=base_screening,
        transcription=base_transcription,
        priority=low_conf_priority,
        language_verification_required=False,
        stt_failed=False,
        extraction_failed=False,
    )
    assert allowed is False
    assert "low priority confidence" in reason.lower()


# =============================================================================
# 0.4: STT & Gemini Fail-to-Review (Never 500, Never LOW)
# =============================================================================

@pytest.mark.asyncio
async def test_stt_failure_yields_fail_to_review_never_low():
    """When Sarvam STT fails, pipeline must return fail-to-review result at MEDIUM, never 500 or LOW."""
    with patch("app.pipeline.sarvam_stt.transcribe_and_translate", side_effect=SarvamSTTError("Connection timed out")):
        result = await run_pipeline(
            audio_bytes=_make_valid_wav(),
            filename="test.wav",
            language_code="ta-IN",
        )
        assert result.priority.level in (PriorityLevel.MEDIUM, PriorityLevel.HIGH)
        assert result.priority.level != PriorityLevel.LOW
        assert result.clinician_review_required is True
        assert result.home_remedy_guidance is None
        assert result.pipeline_stages["stt"]["status"] == "error"


@pytest.mark.asyncio
async def test_gemini_failure_yields_fail_to_review_never_low():
    """When Gemini extraction fails, pipeline must return fail-to-review result at MEDIUM/HIGH, never 500 or LOW."""
    mock_transcription = TranscriptionResult(
        transcript_original="I feel unwell",
        transcript_english="I feel unwell",
        language_code="en-IN",
        language_probability=0.95,
    )
    with patch("app.pipeline.sarvam_stt.transcribe_and_translate", AsyncMock(return_value=mock_transcription)):
        with patch("app.pipeline.gemini_extract.extract_structured_summary", side_effect=GeminiExtractionError("Quota exceeded")):
            result = await run_pipeline(
                audio_bytes=_make_valid_wav(),
                filename="test.wav",
                language_code="en-IN",
            )
            assert result.priority.level in (PriorityLevel.MEDIUM, PriorityLevel.HIGH)
            assert result.priority.level != PriorityLevel.LOW
            assert result.clinician_review_required is True
            assert result.home_remedy_guidance is None
            assert result.pipeline_stages["extraction"]["status"] == "error"


# =============================================================================
# Exit Criteria Stop-Ship Suite:
# Chest pain, breathing difficulty, mumbled audio, and "Gemini returns nothing"
# all yield MEDIUM or HIGH, never LOW.
# =============================================================================

@pytest.mark.asyncio
async def test_exit_criteria_chest_pain_never_low():
    """Chest pain must yield MEDIUM or HIGH, never LOW."""
    mock_transcription = TranscriptionResult(
        transcript_original="I have chest pain since yesterday",
        transcript_english="I have chest pain since yesterday",
        language_code="en-IN",
        language_probability=0.95,
    )
    mock_summary = StructuredMedicalSummary(
        chief_complaint="Chest pain",
        symptoms=[Symptom(name="chest pain", severity=Severity.MODERATE, confidence=0.4)],
        red_flags=[],
    )
    with patch("app.pipeline.sarvam_stt.transcribe_and_translate", AsyncMock(return_value=mock_transcription)):
        with patch("app.pipeline.gemini_extract.extract_structured_summary", AsyncMock(return_value=mock_summary)):
            result = await run_pipeline(
                audio_bytes=_make_valid_wav(),
                filename="test.wav",
            )
            assert result.priority.level in (PriorityLevel.MEDIUM, PriorityLevel.HIGH)
            assert result.priority.level != PriorityLevel.LOW


@pytest.mark.asyncio
async def test_exit_criteria_breathing_difficulty_yields_high():
    """Difficulty breathing must yield HIGH, never LOW."""
    mock_transcription = TranscriptionResult(
        transcript_original="I cannot breathe properly",
        transcript_english="I cannot breathe properly",
        language_code="en-IN",
        language_probability=0.95,
    )
    mock_summary = StructuredMedicalSummary(
        chief_complaint="Difficulty breathing",
        symptoms=[Symptom(name="difficulty breathing", severity=Severity.SEVERE, confidence=0.9)],
        red_flags=[RedFlag(phrase="cannot breathe properly")],
    )
    with patch("app.pipeline.sarvam_stt.transcribe_and_translate", AsyncMock(return_value=mock_transcription)):
        with patch("app.pipeline.gemini_extract.extract_structured_summary", AsyncMock(return_value=mock_summary)):
            result = await run_pipeline(
                audio_bytes=_make_valid_wav(),
                filename="test.wav",
            )
            assert result.priority.level == PriorityLevel.HIGH
            assert result.priority.level != PriorityLevel.LOW


@pytest.mark.asyncio
async def test_exit_criteria_mumbled_audio_never_low():
    """Mumbled audio (low STT confidence / short words) must yield MEDIUM or HIGH, never LOW."""
    mock_transcription = TranscriptionResult(
        transcript_original="mm... uh...",
        transcript_english="uh",
        language_code="unknown",
        language_probability=0.35,  # Low STT confidence
    )
    mock_summary = StructuredMedicalSummary(
        chief_complaint="unclear",
        symptoms=[],
        red_flags=[],
    )
    with patch("app.pipeline.sarvam_stt.transcribe_and_translate", AsyncMock(return_value=mock_transcription)):
        with patch("app.pipeline.gemini_extract.extract_structured_summary", AsyncMock(return_value=mock_summary)):
            result = await run_pipeline(
                audio_bytes=_make_valid_wav(),
                filename="test.wav",
            )
            assert result.priority.level in (PriorityLevel.MEDIUM, PriorityLevel.HIGH)
            assert result.priority.level != PriorityLevel.LOW
            assert result.clinician_review_required is True


@pytest.mark.asyncio
async def test_exit_criteria_gemini_returns_nothing_never_low():
    """'Gemini returns nothing' (0 symptoms extracted) must yield MEDIUM or HIGH, never LOW."""
    mock_transcription = TranscriptionResult(
        transcript_original="I have been feeling strange",
        transcript_english="I have been feeling strange",
        language_code="en-IN",
        language_probability=0.92,
    )
    # Gemini returned nothing
    mock_summary = StructuredMedicalSummary(
        chief_complaint="",
        symptoms=[],
        red_flags=[],
    )
    with patch("app.pipeline.sarvam_stt.transcribe_and_translate", AsyncMock(return_value=mock_transcription)):
        with patch("app.pipeline.gemini_extract.extract_structured_summary", AsyncMock(return_value=mock_summary)):
            result = await run_pipeline(
                audio_bytes=_make_valid_wav(),
                filename="test.wav",
            )
            assert result.priority.level in (PriorityLevel.MEDIUM, PriorityLevel.HIGH)
            assert result.priority.level != PriorityLevel.LOW
            assert result.clinician_review_required is True
