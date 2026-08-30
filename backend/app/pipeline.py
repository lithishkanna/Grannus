"""
Complete AI Processing Pipeline for RuralCare AI:

1. Audio Preprocessing / Noise Reduction (audio_preprocessing.py)
2. Speech-to-Text via Sarvam API (services/sarvam_stt.py)
3. Medical Information Extraction / Structuring via Gemini (services/gemini_extract.py)
4. Safety / Red-Flag Detection (safety.py)
5. Feature Extraction (feature_extraction.py)
6. Priority Prediction via ML Model / Rule Fallback (priority.py)
7. Missing Info & Translated Follow-Up Questions (missing_info.py & services/translation.py)
8. Final Structured Output (PipelineResult)
"""
import logging
import time
import uuid
from typing import Any, Dict, Optional

from app.audio_preprocessing import preprocess_audio
from app.config import get_settings
from app.feature_extraction import extract_features
from app.missing_info import generate_missing_information, get_follow_up_questions
from app.priority import assess_priority
from app.safety import screen_safety
from app.schemas import (
    ClinicalSummary,
    PatientInput,
    PipelineResult,
    SafetyScreeningOutput,
)
from app.services import gemini_extract, sarvam_stt
from app.services.translation import translate_text

logger = logging.getLogger("rural_care.pipeline")


async def run_pipeline(
    audio_bytes: bytes,
    filename: str,
    language_code: str = "unknown",
    patient_context: Optional[dict] = None,
) -> PipelineResult:
    settings = get_settings()
    request_id = str(uuid.uuid4())
    logger.info("pipeline start request_id=%s raw_bytes=%d lang=%s", request_id, len(audio_bytes), language_code)

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
    except Exception as exc:
        logger.warning("Audio preprocessing warning (using raw bytes): %s", exc)
        clean_bytes = audio_bytes
        prep_result = None
        pipeline_stages["audio_preprocessing"] = {
            "status": "warning",
            "error": str(exc),
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        }

    # -------------------------------------------------------------------------
    # Stage 2: Speech-to-Text (Sarvam API)
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    transcription = await sarvam_stt.transcribe_and_translate(
        audio_bytes=clean_bytes,
        filename=filename if filename.endswith(".wav") else f"{filename}.wav",
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

    # Determine effective patient language
    effective_lang = (
        language_code if language_code != "unknown"
        else (transcription.language_code or "ta-IN")
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
    # Stage 6: Priority Prediction (ML Model / Safety Override)
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    priority = assess_priority(
        summary=structured_summary,
        patient_context=patient_context,
        safety_screening=safety_screening,
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
    # Stage 7: Follow-up Question Generation & Translation
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    missing_items = generate_missing_information(structured_summary, patient_context)

    # Translate questions to patient language if needed
    for item in missing_items:
        if effective_lang and not effective_lang.lower().startswith("en"):
            translated_q = await translate_text(item.question, target_language=effective_lang)
            if translated_q != item.question:
                item.translated_question = translated_q

    raw_questions = get_follow_up_questions(missing_items, max_questions=3)
    translated_follow_ups = []
    for q in raw_questions:
        if effective_lang and not effective_lang.lower().startswith("en"):
            t_q = await translate_text(q, target_language=effective_lang)
            translated_follow_ups.append(t_q)
        else:
            translated_follow_ups.append(q)

    pipeline_stages["follow_up"] = {
        "status": "success",
        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        "missing_items_count": len(missing_items),
        "questions_generated": len(translated_follow_ups),
    }

    # -------------------------------------------------------------------------
    # Stage 8: Assemble Final Structured Output
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
        audio_preprocessing=prep_result,
        pipeline_stages=pipeline_stages,
    )
