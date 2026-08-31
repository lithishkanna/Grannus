"""
Complete AI Processing Pipeline for RuralCare AI:

1. Audio Preprocessing / Noise Reduction (audio_preprocessing.py)
2. Speech-to-Text via Sarvam API (services/sarvam_stt.py)
3. Medical Information Extraction / Structuring via Gemini (services/gemini_extract.py)
4. Safety / Red-Flag Detection (safety.py)
5. Feature Extraction (feature_extraction.py)
6. Priority Prediction via ML Model / Rule Fallback (priority.py)
7. Missing Info & Translated Follow-Up Questions (missing_info.py & services/translation.py)
8a. LOW priority  → Home Remedy Guidance (services/gemini_home_remedies.py)
8b. MED/HIGH      → Doctor-Preferred Language Translation (services/translation.py)
9. Final Structured Output (PipelineResult)
"""
import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from app.audio_preprocessing import (
    AudioFormatError,
    AudioPreprocessingError,
    AudioTooLongError,
    AudioTooShortError,
    preprocess_audio,
)
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
    PriorityLevel,
    SafetyScreeningOutput,
)
from app.services import gemini_extract, sarvam_stt
from app.services.gemini_home_remedies import generate_home_remedies
from app.services.translation import translate_clinical_summary_for_doctor, translate_text

logger = logging.getLogger("rural_care.pipeline")


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
        doctor_preferred_language: BCP-47 code for doctor's preferred language
            (used to translate the clinical summary for MEDIUM/HIGH priority cases).
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
        # Re-raise validation errors so main.py can return correct 400 status.
        pipeline_stages["audio_preprocessing"] = {
            "status": "error",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
        raise
    except AudioPreprocessingError as exc:
        # Other preprocessing errors: fall back to raw bytes rather than failing.
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

    # Fix: use Path().stem + ".wav" to avoid "sample.mp3.wav" style appends
    safe_filename = Path(filename).stem + ".wav"

    # -------------------------------------------------------------------------
    # Stage 2: Speech-to-Text (Sarvam API)
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    transcription = await sarvam_stt.transcribe_and_translate(
        audio_bytes=clean_bytes,
        filename=safe_filename,
        language_code=language_code,
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

    # Determine effective patient language — default to "en-IN", not Tamil,
    # when language is unknown and STT couldn't detect it.
    effective_lang = (
        language_code if language_code != "unknown"
        else (transcription.language_code or "en-IN")
    )

    # -------------------------------------------------------------------------
    # Stage 3: Medical Information Extraction (LLM / Gemini)
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
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

    # -------------------------------------------------------------------------
    # Stage 4: Safety / Red-Flag Engine (Deterministic)
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    safety_screening = screen_safety(structured_summary)
    pipeline_stages["safety"] = {
        "status": "success",
        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        "red_flags_found": len(safety_screening.red_flags),
        "has_critical_flags": safety_screening.has_critical_flags,
        "override_priority": safety_screening.override_priority,
    }

    # -------------------------------------------------------------------------
    # Stage 5: Feature Extraction (for ML model) — extracted ONCE, reused
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
    # Stage 6: Priority Prediction — passes pre-computed features to avoid
    # redundant extraction inside assess_priority()
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    priority = assess_priority(
        summary=structured_summary,
        patient_context=patient_context,
        safety_screening=safety_screening,
        features=features,          # pass pre-computed; avoids double extraction
    )
    pipeline_stages["priority"] = {
        "status": "success",
        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        "level": priority.level,
        "confidence": priority.confidence,
        "model_used": priority.model_used,
        "emergency_override": priority.emergency_override,
    }

    # -------------------------------------------------------------------------
    # Stage 7: Follow-up Question Generation & Translation (concurrent)
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    missing_items = generate_missing_information(structured_summary, patient_context)
    raw_questions = get_follow_up_questions(missing_items, max_questions=3)

    # Translate missing_items questions and raw_questions concurrently
    # instead of sequentially to reduce latency.
    needs_translation = bool(
        effective_lang and not effective_lang.lower().startswith("en")
    )

    if needs_translation:
        # Build one flat list of all texts to translate, then dispatch them all
        # in a single asyncio.gather call.
        item_questions = [item.question for item in missing_items]
        all_texts = item_questions + raw_questions

        translated_all = await asyncio.gather(
            *[translate_text(t, target_language=effective_lang) for t in all_texts],
            return_exceptions=True,
        )

        # Assign translations back to missing_items
        for i, item in enumerate(missing_items):
            result = translated_all[i]
            if not isinstance(result, Exception) and result != item.question:
                item.translated_question = result

        # Build translated follow-up questions list
        translated_follow_ups = []
        for i, q in enumerate(raw_questions):
            result = translated_all[len(item_questions) + i]
            translated_follow_ups.append(
                result if not isinstance(result, Exception) else q
            )
    else:
        translated_follow_ups = list(raw_questions)

    pipeline_stages["follow_up"] = {
        "status": "success",
        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        "missing_items_count": len(missing_items),
        "questions_generated": len(translated_follow_ups),
    }

    # -------------------------------------------------------------------------
    # Stage 8a: LOW Priority → Home Remedy Guidance (Gemini, safety-constrained)
    # -------------------------------------------------------------------------
    home_remedy_guidance = None
    if priority.level == PriorityLevel.LOW:
        t0 = time.perf_counter()
        clinical_for_remedies = ClinicalSummary(
            chief_complaint=structured_summary.chief_complaint,
            symptoms=structured_summary.symptoms,
            existing_conditions=structured_summary.existing_conditions,
            medications=structured_summary.medications,
            allergies=structured_summary.allergies,
            relevant_history=structured_summary.relevant_history,
            field_confidence=structured_summary.field_confidence,
            extraction_notes=structured_summary.extraction_notes,
        )
        home_remedy_guidance = await generate_home_remedies(
            summary=clinical_for_remedies,
            patient_language=effective_lang,
        )
        pipeline_stages["home_remedies"] = {
            "status": "success" if home_remedy_guidance else "skipped",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
            "steps_generated": len(home_remedy_guidance.care_steps) if home_remedy_guidance else 0,
            "translated": bool(
                home_remedy_guidance and home_remedy_guidance.translated_care_steps
            ),
        }

    # -------------------------------------------------------------------------
    # Stage 8b: MEDIUM/HIGH Priority → Translate summary for doctor language
    # -------------------------------------------------------------------------
    doctor_translated_summary = None
    if priority.level in (PriorityLevel.MEDIUM, PriorityLevel.HIGH):
        t0 = time.perf_counter()
        translated_dict = await translate_clinical_summary_for_doctor(
            chief_complaint=structured_summary.chief_complaint,
            symptoms=structured_summary.symptoms,
            red_flags=safety_screening.red_flags,
            doctor_language=doctor_preferred_language,
        )
        if translated_dict:
            doctor_translated_summary = DoctorTranslatedSummary(**translated_dict)
        pipeline_stages["doctor_translation"] = {
            "status": "success" if doctor_translated_summary else "skipped",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
            "doctor_language": doctor_preferred_language,
        }

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
    )
