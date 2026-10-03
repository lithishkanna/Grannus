"""
Complete AI Processing Pipeline for RuralCare AI:

1. Audio Preprocessing / Noise Reduction (audio_preprocessing.py)
2. Speech-to-Text via Sarvam API (services/sarvam_stt.py)
3. Medical Information Extraction / Structuring via Gemini (services/gemini_extract.py)
4. Safety / Red-Flag Detection (safety.py)
5. Feature Extraction (feature_extraction.py)
6. Priority Prediction via ML Model / Rule Fallback (priority.py)
7. Missing Info & Translated Follow-Up Questions (missing_info.py & services/translation.py)
8a. LOW priority  → Home Remedy Guidance (services/gemini_home_remedies.py) [Gated]
8b. MED/HIGH      → Doctor-Preferred Language Translation (services/translation.py)
9. Final Structured Output (PipelineResult)
"""
import asyncio
import io
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import soundfile as sf

from app.audio_preprocessing import (
    AudioFormatError,
    AudioPreprocessingError,
    AudioTooLongError,
    AudioTooShortError,
    preprocess_audio,
)
from app.acoustic_biomarkers import analyze_audio
from app.config import get_settings
from app.feature_extraction import extract_features
from app.missing_info import generate_missing_information, get_follow_up_questions
from app.priority import assess_priority
from app.safety import screen_safety
from app.schemas import (
    ClinicalSummary,
    DoctorTranslatedSummary,
    PatientInput,
    PipelineResult,
    PriorityAssessment,
    PriorityLevel,
    SafetyScreening,
    SafetyScreeningOutput,
    StructuredMedicalSummary,
    TranscriptionResult,
)
from app.services import gemini_extract, sarvam_stt
from app.services.gemini_home_remedies import generate_home_remedies
from app.services.translation import translate_clinical_summary_for_doctor, translate_text

logger = logging.getLogger("rural_care.pipeline")


def check_home_remedy_gate(
    patient_context: dict,
    summary: StructuredMedicalSummary,
    safety_screening: SafetyScreening,
    transcription: TranscriptionResult,
    priority: PriorityAssessment,
    language_verification_required: bool,
    stt_failed: bool,
    extraction_failed: bool,
) -> Tuple[bool, Optional[str]]:
    """
    0.5: Gate home remedies. Strictly exclude:
      - Age < 5 or > 65
      - Pregnancy
      - Comorbidities
      - Missing critical info
      - Low confidence or service failures
    Returns: (is_allowed, exclusion_reason)
    """
    if stt_failed or extraction_failed:
        return False, "Service failure: automated processing incomplete"

    if priority.level != PriorityLevel.LOW:
        return False, f"Priority level is {priority.level.value} (home remedies permitted only for LOW)"

    # 1. Age gating: exclude <5 or >65
    age_raw = patient_context.get("age") or patient_context.get("patient_age")
    if age_raw is not None:
        age_str = str(age_raw).strip().lower()
        if any(unit in age_str for unit in ["month", "week", "day", "mth"]):
            return False, "Age exclusion: infant or young child (<5 years) requires clinician consultation"
        digits = re.findall(r"\d+", age_str)
        if digits:
            try:
                age_val = float(digits[0])
                if age_val < 5:
                    return False, f"Age exclusion: patient age {age_val:g} < 5 requires clinician consultation"
                if age_val > 65:
                    return False, f"Age exclusion: elderly patient age {age_val:g} > 65 requires clinician consultation"
            except ValueError:
                pass

    # 2. Pregnancy gating
    if str(patient_context.get("is_pregnant", "")).strip().lower() in ("yes", "true", "1") or \
       str(patient_context.get("pregnancy", "")).strip().lower() in ("yes", "true", "1"):
        return False, "Pregnancy exclusion: pregnant patients require clinician consultation"

    context_str = " ".join(f"{k} {v}".lower() for k, v in patient_context.items())
    summary_conditions = " ".join((summary.existing_conditions or [])).lower()
    summary_history = (summary.relevant_history or "").lower()
    complaint = (summary.chief_complaint or "").lower()
    combined_clinical_text = f"{context_str} {summary_conditions} {summary_history} {complaint}"

    if any(pw in combined_clinical_text for pw in ["pregnant", "pregnancy", "trimester", "gestation", "maternity", "கருவுற்ற"]):
        return False, "Pregnancy exclusion: pregnant patients require clinician consultation"

    # 3. Comorbidities gating
    known_cond = patient_context.get("known_conditions")
    if known_cond and str(known_cond).strip().lower() not in ("none", "nil", "no", "na", "n/a"):
        return False, f"Comorbidity exclusion: pre-existing conditions ({known_cond}) require clinician consultation"
    if summary.existing_conditions:
        real_conditions = [c for c in summary.existing_conditions if c.strip().lower() not in ("none", "nil", "no", "na", "n/a")]
        if real_conditions:
            return False, f"Comorbidity exclusion: pre-existing conditions ({', '.join(real_conditions)}) require clinician consultation"

    # 4. Missing critical info gating
    if safety_screening.missing_critical_info:
        return False, f"Missing critical info: {'; '.join(safety_screening.missing_critical_info)}"

    # 5. Low confidence gating
    if priority.confidence < 0.70:
        return False, f"Low priority confidence ({priority.confidence:.2f} < 0.70)"
    if language_verification_required:
        return False, "Language verification required (low STT language confidence)"
    if transcription.language_probability is not None and transcription.language_probability < 0.80:
        return False, f"Low STT language confidence ({transcription.language_probability:.2f} < 0.80)"

    for sym in summary.symptoms:
        if not sym.negated and sym.confidence < 0.50:
            return False, f"Low extraction confidence for '{sym.name}' ({sym.confidence:.2f} < 0.50)"

    return True, None


async def run_pipeline(
    audio_bytes: bytes,
    filename: str,
    language_code: str = "unknown",
    patient_context: Optional[dict] = None,
    doctor_preferred_language: str = "en-IN",
) -> PipelineResult:
    """
    Run the complete GRANNUS triage pipeline.

    Args:
        audio_bytes: Raw audio from the patient.
        filename: Original filename (used for format detection).
        language_code: BCP-47 code for patient language, or "unknown" for auto-detect.
        patient_context: Optional dict with age, gender, known_conditions, etc.
        doctor_preferred_language: BCP-47 code for doctor's preferred language.
    """
    settings = get_settings()
    request_id = str(uuid.uuid4())
    logger.info(
        "pipeline start request_id=%s raw_bytes=%d lang=%s doctor_lang=%s",
        request_id, len(audio_bytes), language_code, doctor_preferred_language,
    )

    pipeline_stages: Dict[str, Any] = {}
    patient_context = patient_context or {}

    # -------------------------------------------------------------------------
    # Stage 1: Audio Preprocessing / Noise Reduction
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    try:
        clean_bytes, prep_result = preprocess_audio(audio_bytes, filename)
        pipeline_stages["audio_preprocessing"] = {
            "status": "success",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
            "original_duration_s": prep_result.original_duration_seconds,
            "processed_duration_s": prep_result.processed_duration_seconds,
            "noise_reduced": prep_result.noise_reduced,
            "quality_warning": prep_result.quality_warning,
        }
    except (AudioTooShortError, AudioTooLongError, AudioFormatError):
        # Validation errors raise to main.py to yield HTTP 400
        pipeline_stages["audio_preprocessing"] = {
            "status": "error",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
        raise
    except AudioPreprocessingError as exc:
        logger.warning("Audio preprocessing warning (using raw bytes): %s", exc)
        clean_bytes = audio_bytes
        prep_result = None
        pipeline_stages["audio_preprocessing"] = {
            "status": "warning",
            "error": str(exc),
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
    except Exception as exc:
        logger.warning("Unexpected audio preprocessing error (using raw bytes): %s", exc)
        clean_bytes = audio_bytes
        prep_result = None
        pipeline_stages["audio_preprocessing"] = {
            "status": "warning",
            "error": str(exc),
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        }

    safe_filename = Path(filename).stem + ".wav"
    content_type = "audio/wav"
    if prep_result is None:
        ext = Path(filename).suffix.lstrip('.')
        if ext:
            content_type = f"audio/{ext}"

    # -------------------------------------------------------------------------
    # Stage 1.5: Acoustic Biomarkers
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    biomarker_result = None
    try:
        audio_array, sample_rate = sf.read(io.BytesIO(clean_bytes))
        biomarker_result = analyze_audio(audio_array, sample_rate)
        pipeline_stages["acoustic_biomarkers"] = {
            "status": "success",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
            "score": biomarker_result.respiratory_distress_score,
            "distress_level": biomarker_result.distress_level,
        }
    except Exception as exc:
        logger.warning("Acoustic biomarker analysis failed: %s", exc)
        pipeline_stages["acoustic_biomarkers"] = {
            "status": "error",
            "error": str(exc),
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        }

    # -------------------------------------------------------------------------
    # Stage 2: Speech-to-Text (Sarvam API) with 0.4 fail-to-review try/except
    # -------------------------------------------------------------------------
    stt_failed = False
    stt_error_msg = None
    t0 = time.perf_counter()
    try:
        transcription = await sarvam_stt.transcribe_and_translate(
            audio_bytes=clean_bytes,
            filename=safe_filename,
            language_code=language_code,
            content_type=content_type,
        )
        language_verification_required = (
            transcription.language_probability is not None
            and transcription.language_probability < settings.language_confidence_threshold
        )
        pipeline_stages["stt"] = {
            "status": "success",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
            "language_code": transcription.language_code,
            "language_probability": transcription.language_probability,
            "original_chars": len(transcription.transcript_original),
            "english_chars": len(transcription.transcript_english),
        }
    except Exception as exc:
        logger.error("STT stage failed: %s", exc)
        stt_failed = True
        stt_error_msg = str(exc)
        pipeline_stages["stt"] = {
            "status": "error",
            "error": str(exc),
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
        transcription = TranscriptionResult(
            transcript_original="[Audio transcription unavailable - audio requires human review]",
            transcript_english="[Audio transcription unavailable - audio requires human review]",
            language_code=language_code if language_code != "unknown" else None,
            language_probability=0.0,
        )
        language_verification_required = True

    effective_lang = (
        language_code if language_code != "unknown"
        else (transcription.language_code or "en-IN")
    )

    # -------------------------------------------------------------------------
    # Stage 3: Medical Information Extraction (LLM) with 0.4 fail-to-review
    # -------------------------------------------------------------------------
    extraction_failed = False
    extraction_error_msg = None
    t0 = time.perf_counter()
    if stt_failed:
        structured_summary = StructuredMedicalSummary(
            chief_complaint="Unspecified - transcription failed",
            symptoms=[],
            red_flags=[],
            extraction_notes=f"STT failure: {stt_error_msg}. Audio must be reviewed directly by clinician.",
        )
        pipeline_stages["extraction"] = {
            "status": "skipped",
            "reason": "stt_failed",
            "duration_ms": 0.0,
            "symptoms_extracted": 0,
            "red_flags_extracted": 0,
        }
    else:
        try:
            structured_summary = await gemini_extract.extract_structured_summary(
                transcript_english=transcription.transcript_english,
                patient_context=patient_context,
            )
            pipeline_stages["extraction"] = {
                "status": "success",
                "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "symptoms_extracted": len(structured_summary.symptoms),
                "red_flags_extracted": len(structured_summary.red_flags),
            }
        except Exception as exc:
            logger.error("Gemini extraction failed: %s", exc)
            extraction_failed = True
            extraction_error_msg = str(exc)
            structured_summary = StructuredMedicalSummary(
                chief_complaint="Extraction failed - manual review required",
                symptoms=[],
                red_flags=[],
                extraction_notes=f"Extraction failure: {exc}. Review audio and transcripts directly.",
            )
            pipeline_stages["extraction"] = {
                "status": "error",
                "error": str(exc),
                "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "symptoms_extracted": 0,
                "red_flags_extracted": 0,
            }

    # -------------------------------------------------------------------------
    # Stage 4: Safety / Red-Flag Engine (Deterministic) + 0.2 Independent Raw Scan
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    safety_screening = screen_safety(
        summary=structured_summary,
        biomarkers=biomarker_result,
        transcript_english=transcription.transcript_english if not stt_failed else None,
        transcript_original=transcription.transcript_original if not stt_failed else None,
        language_code=effective_lang,
    )
    pipeline_stages["safety"] = {
        "status": "success",
        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        "red_flags_found": len(safety_screening.red_flags),
        "has_critical_flags": safety_screening.has_critical_flags,
        "override_priority": safety_screening.override_priority,
    }

    # -------------------------------------------------------------------------
    # Stage 5: Feature Extraction (for ML model)
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    features = extract_features(structured_summary, patient_context)
    pipeline_stages["feature_extraction"] = {
        "status": "success",
        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        "feature_count": len(features),
        "num_symptoms": features.get("num_symptoms", 0),
        "max_severity": features.get("max_severity", 0),
    }

    # -------------------------------------------------------------------------
    # Stage 6: Priority Prediction & 0.3/0.4 Insufficient Input Gating
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    priority = assess_priority(
        summary=structured_summary,
        patient_context=patient_context,
        safety_screening=safety_screening,
        features=features,
    )

    # 0.3 & 0.4: Insufficient input or service failure never yields LOW -> floor to at least MEDIUM
    raw_eng = (transcription.transcript_english or "").strip()
    raw_orig = (transcription.transcript_original or "").strip()
    non_negated_symptoms = [s for s in structured_summary.symptoms if not s.negated]

    is_insufficient_input = (
        stt_failed
        or extraction_failed
        or language_verification_required
        or (transcription.language_probability is not None and transcription.language_probability < settings.language_confidence_threshold)
        or len(raw_eng.split()) < 3
        or len(raw_eng) < 10
        or len(non_negated_symptoms) == 0
    )

    if is_insufficient_input and priority.level == PriorityLevel.LOW:
        logger.warning(
            "Insufficient input floor applied: elevating priority from LOW to MEDIUM "
            "(stt_fail=%s, ext_fail=%s, lang_verif=%s, word_count=%d, symptoms=%d)",
            stt_failed, extraction_failed, language_verification_required, len(raw_eng.split()), len(non_negated_symptoms)
        )
        priority.level = PriorityLevel.MEDIUM
        priority.confidence = max(priority.confidence, 0.6)
        insufficient_reason = (
            "Fail-to-review floor: automated transcription or extraction unavailable; requires human review"
            if (stt_failed or extraction_failed)
            else "Insufficient input: empty extraction, low STT confidence, or very short transcript routed to clinician review"
        )
        priority.reasons = [insufficient_reason] + priority.reasons
        priority.triggered_rules.append("insufficient_input_floor")
        if stt_failed or extraction_failed:
            priority.model_used = "fail_to_review"

    pipeline_stages["priority"] = {
        "status": "success",
        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        "level": priority.level.value,
        "confidence": priority.confidence,
        "model_used": priority.model_used,
        "emergency_override": priority.emergency_override,
    }

    # Build ClinicalSummary once to be reused
    clinical_summary = ClinicalSummary(
        chief_complaint=structured_summary.chief_complaint,
        symptoms=structured_summary.symptoms,
        existing_conditions=structured_summary.existing_conditions,
        medications=structured_summary.medications,
        allergies=structured_summary.allergies,
        relevant_history=structured_summary.relevant_history,
        field_confidence=structured_summary.field_confidence,
        extraction_notes=structured_summary.extraction_notes,
    )

    allowed, gate_reason = check_home_remedy_gate(
        patient_context=patient_context,
        summary=structured_summary,
        safety_screening=safety_screening,
        transcription=transcription,
        priority=priority,
        language_verification_required=language_verification_required,
        stt_failed=stt_failed,
        extraction_failed=extraction_failed,
    )

    # -------------------------------------------------------------------------
    # Concurrent Execution: Stages 7, 8a, 8b
    # -------------------------------------------------------------------------
    async def run_stage_7():
        t0_7 = time.perf_counter()
        m_items = generate_missing_information(structured_summary, patient_context)
        r_questions = get_follow_up_questions(m_items, max_questions=3)
        t_follow_ups = list(r_questions)

        needs_translation = bool(effective_lang and not effective_lang.lower().startswith("en"))
        if needs_translation:
            try:
                i_questions = [item.question for item in m_items]
                all_texts = i_questions + r_questions
                translated_all = await asyncio.gather(
                    *[translate_text(t, target_language=effective_lang) for t in all_texts],
                    return_exceptions=True,
                )
                for i, item in enumerate(m_items):
                    res = translated_all[i]
                    if not isinstance(res, Exception) and res != item.question:
                        item.translated_question = res

                t_follow_ups = []
                for i, q in enumerate(r_questions):
                    res = translated_all[len(i_questions) + i]
                    t_follow_ups.append(res if not isinstance(res, Exception) else q)
            except Exception as exc:
                logger.warning("Follow-up question translation failed: %s", exc)

        stage_data = {
            "status": "success",
            "duration_ms": round((time.perf_counter() - t0_7) * 1000, 2),
            "missing_items_count": len(m_items),
            "questions_generated": len(t_follow_ups),
        }
        return m_items, t_follow_ups, stage_data

    async def run_stage_8a():
        if allowed and priority.level == PriorityLevel.LOW:
            t0_8a = time.perf_counter()
            try:
                guidance = await generate_home_remedies(
                    summary=clinical_summary,
                    patient_language=effective_lang,
                )
                stage_data = {
                    "status": "success" if guidance else "skipped",
                    "duration_ms": round((time.perf_counter() - t0_8a) * 1000, 2),
                    "steps_generated": len(guidance.care_steps) if guidance else 0,
                    "translated": bool(guidance and guidance.translated_care_steps),
                }
                return guidance, stage_data
            except Exception as exc:
                logger.warning("Home remedy generation failed: %s", exc)
                return None, {
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": round((time.perf_counter() - t0_8a) * 1000, 2),
                }
        else:
            return None, {
                "status": "gated" if priority.level == PriorityLevel.LOW else "skipped",
                "reason": gate_reason,
            }

    async def run_stage_8b():
        if priority.level in (PriorityLevel.MEDIUM, PriorityLevel.HIGH):
            t0_8b = time.perf_counter()
            try:
                translated_dict = await translate_clinical_summary_for_doctor(
                    chief_complaint=structured_summary.chief_complaint,
                    symptoms=structured_summary.symptoms,
                    red_flags=safety_screening.red_flags,
                    doctor_language=doctor_preferred_language,
                )
                doc_summary = DoctorTranslatedSummary(**translated_dict) if translated_dict else None
                stage_data = {
                    "status": "success" if doc_summary else "skipped",
                    "duration_ms": round((time.perf_counter() - t0_8b) * 1000, 2),
                    "doctor_language": doctor_preferred_language,
                }
                return doc_summary, stage_data
            except Exception as exc:
                logger.warning("Doctor summary translation failed: %s", exc)
                return None, {
                    "status": "error",
                    "error": str(exc),
                    "duration_ms": round((time.perf_counter() - t0_8b) * 1000, 2),
                }
        return None, {"status": "skipped", "duration_ms": 0.0}

    res7, res8a, res8b = await asyncio.gather(
        run_stage_7(), run_stage_8a(), run_stage_8b()
    )

    missing_items, translated_follow_ups, pipeline_stages["follow_up"] = res7
    home_remedy_guidance, pipeline_stages["home_remedies"] = res8a
    doctor_translated_summary, pipeline_stages["doctor_translation"] = res8b

    # -------------------------------------------------------------------------
    # Stage 9: Assemble Final Structured Output
    # -------------------------------------------------------------------------
    patient_input = PatientInput(
        language=effective_lang,
        transcript_original=transcription.transcript_original,
        transcript_english=transcription.transcript_english,
        language_confidence=transcription.language_probability,
        language_verification_required=language_verification_required,
    )

    safety_output = SafetyScreeningOutput(
        red_flags=safety_screening.red_flags,
        missing_information=missing_items,
        follow_up_questions=translated_follow_ups,
    )

    return PipelineResult(
        request_id=request_id,
        patient_input=patient_input,
        clinical_summary=clinical_summary,
        safety_screening=safety_output,
        priority=priority,
        clinician_review_required=True,
        diagnosis=None,
        home_remedy_guidance=home_remedy_guidance,
        doctor_translated_summary=doctor_translated_summary,
        audio_preprocessing=prep_result,
        pipeline_stages=pipeline_stages,
        acoustic_biomarkers=biomarker_result,
    )
