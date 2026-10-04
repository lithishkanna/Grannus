"""
Tests for Block A: Safety and Honesty.

Covers:
- B1.1 & B1.2: Urgency tier invariants (chest pain 60y sweating, vomiting blood, 2yo fever,
  pregnancy with bleeding NEVER land in doctor_soon or self_care).
- B1.3: Raw-text-only emergency scans (Gemini returns nothing) across English, Hindi,
  Tamil, Telugu, Hinglish, Tanglish.
- B1.4: Negation tests ("chest pain and nausea", "severe chest pain, no fever",
  "pregnant with heavy bleeding", Hindi "पसीना" not falsely negated, true negations unflagged).
- B1.5: Unrated bleeding and vomiting blood escalation (never LOW or self_care).
- B1.6: Biomarker flags advisory only (no emergency override, labelled experimental).
- B1.7: Deterministic floor invariant (empty/insufficient input routes to doctor, never self_care).
- B2.4: Secret enforcement (missing JWT_SECRET_KEY raises RuntimeError).
- B9.4: FHIR Condition resource uses problem-list-item and includes demographics, meds, allergies.
"""
import pytest
from app.schemas import (
    UrgencyTier,
    PriorityLevel,
    StructuredMedicalSummary,
    Symptom,
    Severity,
    SafetyScreening,
    SafetyRedFlag,
    AcousticBiomarkerResult,
    PatientInput,
    ClinicalSummary,
    SafetyScreeningOutput,
    PriorityAssessment,
)
from app.safety import (
    screen_safety,
    scan_raw_transcript,
    is_text_negated,
    is_negated_match,
)
from app.priority import (
    determine_urgency_tier,
    assess_priority,
    apply_floor,
)
from app.auth import get_signing_secret
from app.config import get_settings
from app.fhir_bundle import generate_fhir_bundle


# =============================================================================
# B1.1 & B1.2: Urgency Tier Invariants
# =============================================================================

def test_chest_pain_elderly_sweating_always_emergency():
    """Chest pain with age 60 and sweating must ALWAYS map to EMERGENCY, never doctor_soon or self_care."""
    summary = StructuredMedicalSummary(
        chief_complaint="Chest pain and sweating",
        symptoms=[
            Symptom(name="chest pain", severity=Severity.MODERATE),
            Symptom(name="sweating", severity=Severity.MODERATE),
        ],
    )
    patient_context = {"age": "60", "gender": "male"}
    safety = screen_safety(summary)

    assessment = assess_priority(summary, patient_context=patient_context, safety_screening=safety)
    assert assessment.urgency_tier == UrgencyTier.EMERGENCY
    assert assessment.urgency_tier not in (UrgencyTier.DOCTOR_SOON, UrgencyTier.SELF_CARE)

    tier, fu_days = determine_urgency_tier(
        level=PriorityLevel.MEDIUM,
        safety_screening=safety,
        patient_context=patient_context,
        summary=summary,
    )
    assert tier == UrgencyTier.EMERGENCY
    assert fu_days == 0


def test_vomiting_blood_never_doctor_soon_or_self_care():
    """Vomiting blood must escalate to at least DOCTOR_TODAY, never doctor_soon or self_care."""
    summary = StructuredMedicalSummary(
        chief_complaint="vomited blood this morning",
        symptoms=[Symptom(name="vomiting blood")],
    )
    safety = screen_safety(summary)
    assert any(f.severity == "high" for f in safety.red_flags)

    tier, fu_days = determine_urgency_tier(
        level=PriorityLevel.LOW,
        safety_screening=safety,
        summary=summary,
    )
    assert tier == UrgencyTier.DOCTOR_TODAY
    assert tier not in (UrgencyTier.DOCTOR_SOON, UrgencyTier.SELF_CARE)

    assessment = assess_priority(summary, safety_screening=safety)
    assert assessment.urgency_tier in (UrgencyTier.DOCTOR_TODAY, UrgencyTier.EMERGENCY)
    assert assessment.urgency_tier not in (UrgencyTier.DOCTOR_SOON, UrgencyTier.SELF_CARE)


def test_two_year_old_high_fever_never_doctor_soon_or_self_care():
    """Child under 5 with high fever must map to at least DOCTOR_TODAY, never doctor_soon or self_care."""
    summary = StructuredMedicalSummary(
        chief_complaint="high fever in toddler",
        symptoms=[Symptom(name="fever", severity=Severity.HIGH if hasattr(Severity, "HIGH") else Severity.SEVERE)],
    )
    patient_context = {"age": "2", "gender": "female"}
    safety = screen_safety(summary)

    tier, fu_days = determine_urgency_tier(
        level=PriorityLevel.LOW,
        safety_screening=safety,
        patient_context=patient_context,
        summary=summary,
    )
    assert tier in (UrgencyTier.DOCTOR_TODAY, UrgencyTier.EMERGENCY)
    assert tier not in (UrgencyTier.DOCTOR_SOON, UrgencyTier.SELF_CARE)

    assessment = assess_priority(summary, patient_context=patient_context, safety_screening=safety)
    assert assessment.urgency_tier in (UrgencyTier.DOCTOR_TODAY, UrgencyTier.EMERGENCY)
    assert assessment.urgency_tier not in (UrgencyTier.DOCTOR_SOON, UrgencyTier.SELF_CARE)


def test_pregnancy_with_bleeding_always_emergency():
    """Pregnancy with bleeding must map strictly to EMERGENCY."""
    summary = StructuredMedicalSummary(
        chief_complaint="bleeding during pregnancy",
        symptoms=[Symptom(name="bleeding")],
    )
    patient_context = {"is_pregnant": "true", "age": "26"}
    safety = screen_safety(summary)

    tier, fu_days = determine_urgency_tier(
        level=PriorityLevel.MEDIUM,
        safety_screening=safety,
        patient_context=patient_context,
        summary=summary,
    )
    assert tier == UrgencyTier.EMERGENCY
    assert fu_days == 0

    assessment = assess_priority(summary, patient_context=patient_context, safety_screening=safety)
    assert assessment.urgency_tier == UrgencyTier.EMERGENCY


def test_infant_fever_under_one_year_escalates():
    """Infant fever (< 1 year) must map to at least DOCTOR_TODAY."""
    summary = StructuredMedicalSummary(
        chief_complaint="fever in 4-month baby",
        symptoms=[Symptom(name="fever")],
    )
    patient_context = {"age": "4 months"}
    safety = screen_safety(summary)

    tier, fu_days = determine_urgency_tier(
        level=PriorityLevel.LOW,
        safety_screening=safety,
        patient_context=patient_context,
        summary=summary,
    )
    assert tier in (UrgencyTier.DOCTOR_TODAY, UrgencyTier.EMERGENCY)
    assert tier not in (UrgencyTier.DOCTOR_SOON, UrgencyTier.SELF_CARE)


# =============================================================================
# B1.3: Raw-Text-Only Emergency Tests (Gemini Returns Nothing)
# =============================================================================

@pytest.mark.parametrize(
    "lang,raw_text",
    [
        ("en", "Severe chest pain and difficulty breathing"),
        ("hi", "सीने में बहुत तेज दर्द है और सांस लेने में तकलीफ हो रही है"),
        ("ta", "கடுமையான நெஞ்சு வலி மற்றும் மூச்சு திணறல்"),
        ("te", "తీవ్రమైన ఛాతీ నొప్పి మరియు శ్వాస తీసుకోవడంలో ఇబ్బంది"),
        ("hinglish", "seene me bahut tez dard hai aur saans lene me dikkat ho rahi hai"),
        ("tanglish", "nenju vali romba athigama irukku moochu thinaran"),
    ],
)
def test_raw_text_only_emergency_scans(lang, raw_text):
    """When Gemini returns nothing (empty summary), deterministic scan of raw text must trigger EMERGENCY."""
    empty_summary = StructuredMedicalSummary(chief_complaint="", symptoms=[])

    if lang in ("en", "hinglish", "tanglish"):
        safety = screen_safety(
            summary=empty_summary,
            transcript_english=raw_text,
            transcript_original=raw_text,
        )
    else:
        safety = screen_safety(
            summary=empty_summary,
            transcript_original=raw_text,
        )

    assert safety.has_critical_flags is True
    assert safety.override_priority is True
    assert len(safety.red_flags) >= 1

    tier, fu_days = determine_urgency_tier(
        level=PriorityLevel.LOW,
        emergency_override=safety.override_priority,
        safety_screening=safety,
    )
    assert tier == UrgencyTier.EMERGENCY
    assert fu_days == 0


# =============================================================================
# B1.4: Negation Regression Tests
# =============================================================================

def test_negation_chest_pain_and_nausea():
    """'chest pain and nausea' has no negation -> chest pain must be flagged."""
    summary = StructuredMedicalSummary(
        chief_complaint="chest pain and nausea",
        symptoms=[Symptom(name="chest pain"), Symptom(name="nausea")],
    )
    safety = screen_safety(summary)
    assert any("chest pain" in f.reason.lower() for f in safety.red_flags)


def test_negation_severe_chest_pain_no_fever():
    """'severe chest pain, no fever' -> chest pain flagged, fever must NOT be flagged."""
    summary = StructuredMedicalSummary(
        chief_complaint="severe chest pain, no fever",
        symptoms=[
            Symptom(name="chest pain", severity=Severity.SEVERE),
            Symptom(name="fever", negated=True),
        ],
    )
    safety = screen_safety(
        summary=summary,
        transcript_english="severe chest pain, but no fever",
    )
    has_cp = any("chest pain" in f.reason.lower() for f in safety.red_flags)
    has_fev = any("fever" in f.reason.lower() for f in safety.red_flags)
    assert has_cp is True
    assert has_fev is False


def test_negation_pregnant_with_heavy_bleeding():
    """'pregnant with heavy bleeding' -> must NOT be negated."""
    safety = screen_safety(transcript_english="pregnant with heavy bleeding")
    assert safety.has_critical_flags is True
    assert any("bleeding" in f.reason.lower() for f in safety.red_flags)


def test_negation_hindi_pasina_not_falsely_negated():
    """Hindi 'पसीना' contains 'ना' but must NOT be treated as a negation regex match."""
    text = "सीने में दर्द और पसीना"
    assert is_text_negated(text) is False

    safety = screen_safety(transcript_original=text)
    assert safety.has_sweating is True
    assert any("chest pain" in f.reason.lower() for f in safety.red_flags)


def test_true_negations_stay_unflagged():
    """True negations in English, Hindi, Tamil, Telugu must remain unflagged."""
    # English
    safety_en = screen_safety(transcript_english="I do not have chest pain")
    assert not any("chest pain" in f.reason.lower() for f in safety_en.red_flags)

    # Hindi
    safety_hi = screen_safety(transcript_original="सीने में दर्द नहीं है")
    assert not any("chest pain" in f.reason.lower() for f in safety_hi.red_flags)

    # Tamil
    safety_ta = screen_safety(transcript_original="nenju vali illa")
    assert not any("chest pain" in f.reason.lower() for f in safety_ta.red_flags)

    # Telugu
    safety_te = screen_safety(transcript_original="chati noppi ledu")
    assert not any("chest pain" in f.reason.lower() for f in safety_te.red_flags)


# =============================================================================
# B1.5: Unrated Bleeding and Vomiting Blood Escalation
# =============================================================================

def test_unrated_generic_bleeding_escalates_not_low():
    """Unrated 'bleeding from leg' must trigger HIGH safety flag and DOCTOR_TODAY, not LOW or self_care."""
    summary = StructuredMedicalSummary(
        chief_complaint="bleeding from cut on leg",
        symptoms=[Symptom(name="bleeding", raw_text="bleeding from leg")],
    )
    safety = screen_safety(summary)
    assert any(f.severity == "high" and "bleeding" in f.reason.lower() for f in safety.red_flags)

    tier, _ = determine_urgency_tier(
        level=PriorityLevel.LOW,
        safety_screening=safety,
        summary=summary,
    )
    assert tier == UrgencyTier.DOCTOR_TODAY


def test_vomited_and_there_was_blood_escalates():
    """'vomited and there was blood' must escalate to high flag and DOCTOR_TODAY."""
    safety = screen_safety(transcript_english="patient vomited and there was blood")
    assert any(f.severity == "high" for f in safety.red_flags)

    tier, _ = determine_urgency_tier(
        level=PriorityLevel.LOW,
        safety_screening=safety,
    )
    assert tier == UrgencyTier.DOCTOR_TODAY


# =============================================================================
# B1.6: Biomarker Flags Advisory Only
# =============================================================================

def test_biomarker_flags_advisory_experimental_no_emergency_override():
    """Acoustic biomarker flags are labelled [Advisory - Experimental] and never cause emergency override."""
    biomarkers = AcousticBiomarkerResult(
        cough_count=5,
        cough_rate=12.0,
        wheeze_detected=True,
        wheeze_ratio=0.4,
        breathlessness_pauses=4,
        speech_dyspnea_index=0.7,
        respiratory_distress_score=0.85,
        distress_level="SEVERE",
    )
    summary = StructuredMedicalSummary(
        chief_complaint="mild cough",
        symptoms=[Symptom(name="cough", severity=Severity.MILD)],
    )
    safety = screen_safety(summary=summary, biomarkers=biomarkers)

    bio_flags = [f for f in safety.red_flags if f.symptom == "respiratory_distress_acoustic"]
    assert len(bio_flags) == 1
    assert "[Advisory - Experimental]" in bio_flags[0].reason
    assert bio_flags[0].severity == "high"

    # Acoustic flag must NOT trigger emergency override
    assert safety.has_critical_flags is False
    assert safety.override_priority is False


# =============================================================================
# B1.7: Invariants: Empty/Insufficient Input Routes to Doctor, Never Self-Care
# =============================================================================

def test_empty_input_never_yields_self_care():
    """Empty extraction or missing critical info must route to clinician, never self_care."""
    empty_summary = StructuredMedicalSummary(chief_complaint="", symptoms=[])
    assessment = assess_priority(empty_summary)
    assert assessment.urgency_tier in (UrgencyTier.DOCTOR_SOON, UrgencyTier.DOCTOR_TODAY)
    assert assessment.urgency_tier != UrgencyTier.SELF_CARE


def test_missing_critical_info_floor():
    """Chest pain with unknown breathing status routes to doctor, never self_care."""
    summary = StructuredMedicalSummary(
        chief_complaint="chest pain",
        symptoms=[Symptom(name="chest pain")],
    )
    safety = screen_safety(summary)
    assert len(safety.missing_critical_info) >= 1

    tier, _ = determine_urgency_tier(
        level=PriorityLevel.LOW,
        safety_screening=safety,
        summary=summary,
    )
    assert tier in (UrgencyTier.DOCTOR_TODAY, UrgencyTier.DOCTOR_SOON)
    assert tier != UrgencyTier.SELF_CARE


# =============================================================================
# B2.4: Secret Enforcement
# =============================================================================

def test_missing_jwt_secret_fails_startup(monkeypatch):
    """Backend must raise RuntimeError if JWT_SECRET_KEY is empty."""
    settings = get_settings()
    original_key = settings.jwt_secret_key
    try:
        settings.jwt_secret_key = ""
        with pytest.raises(RuntimeError) as exc_info:
            get_signing_secret()
        assert "JWT_SECRET_KEY" in str(exc_info.value)
    finally:
        settings.jwt_secret_key = original_key


# =============================================================================
# B9.4: FHIR Bundle Conformance
# =============================================================================

def test_fhir_bundle_uses_problem_list_item_and_includes_demographics():
    """FHIR Condition resource must use problem-list-item and include demographics, meds, allergies."""
    patient_input = PatientInput(
        language="ta-IN",
        transcript_original="எனக்கு தலைவலி மற்றும் காய்ச்சல்",
        transcript_english="I have headache and fever",
        age=35,
        gender="female",
    )
    clinical_summary = ClinicalSummary(
        chief_complaint="headache and fever",
        symptoms=[Symptom(name="headache"), Symptom(name="fever")],
        medications=["Paracetamol 500mg"],
        allergies=["Penicillin"],
    )
    safety_screening = SafetyScreeningOutput(red_flags=[])
    priority = PriorityAssessment(level=PriorityLevel.LOW, urgency_tier=UrgencyTier.SELF_CARE)

    bundle = generate_fhir_bundle(
        request_id="test_req_001",
        patient_input=patient_input,
        clinical_summary=clinical_summary,
        safety_screening=safety_screening,
        priority=priority,
    )

    resources = [e["resource"] for e in bundle["entry"]]

    # 1. Condition category must be problem-list-item, not encounter-diagnosis
    conditions = [r for r in resources if r["resourceType"] == "Condition"]
    assert len(conditions) >= 1
    for cond in conditions:
        codings = cond.get("category", [{}])[0].get("coding", [])
        codes = [c.get("code") for c in codings]
        assert "problem-list-item" in codes
        assert "encounter-diagnosis" not in codes
        assert "Triage complaint category" in cond["code"]["text"]

    # 2. Patient demographics
    patients = [r for r in resources if r["resourceType"] == "Patient"]
    assert len(patients) == 1
    assert patients[0].get("gender") == "female"
    assert any(ext.get("valueString") == "35" for ext in patients[0].get("extension", []))
    assert any(c.get("language", {}).get("text") == "ta-IN" for c in patients[0].get("communication", []))

    # 3. Medications & Allergies
    med_stmts = [r for r in resources if r["resourceType"] == "MedicationStatement"]
    assert len(med_stmts) == 1
    assert med_stmts[0]["medicationCodeableConcept"]["text"] == "Paracetamol 500mg"

    allergy_intol = [r for r in resources if r["resourceType"] == "AllergyIntolerance"]
    assert len(allergy_intol) == 1
    assert allergy_intol[0]["code"]["text"] == "Penicillin"
