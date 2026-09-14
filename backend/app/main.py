"""
RuralCare AI — FastAPI Application

Endpoints:
- GET  /health — Health check & configuration status
- POST /api/v1/pipeline/process-audio — Audio triage pipeline
"""
import logging
from typing import Optional

from dotenv import load_dotenv

load_dotenv()  # populate os.environ from .env before Settings() reads it

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.audio_preprocessing import (
    AudioFormatError,
    AudioPreprocessingError,
    AudioTooLongError,
    AudioTooShortError,
)
from app.config import get_settings
from app.ml_model import get_model
from app.pipeline import run_pipeline
from app.schemas import PipelineResult, VoicePrescriptionResponse
from app.services.gemini_extract import GeminiExtractionError
from app.services.sarvam_stt import SarvamSTTError, transcribe_and_translate
from app.services.translation import translate_text
from app.services.sarvam_tts import text_to_speech

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rural_care.api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load ML model at startup."""
    try:
        model = get_model()
        if model.is_available():
            logger.info("ML priority model pre-loaded successfully at startup.")
        else:
            logger.warning("ML priority model not available at startup. Will use rule engine.")
    except Exception as exc:
        logger.warning("Failed to initialize ML model at startup: %s", exc)
    yield

app = FastAPI(
    title="RuralCare AI — Medical Triage & Information Pipeline",
    description=(
        "AI processing engine: Audio Preprocessing -> Speech-to-Text (Sarvam) -> "
        "Medical Information Extraction (Gemini) -> Safety Engine -> ML Priority Prediction"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# -- CORS: allow frontend origins to access the API --
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    model = get_model()
    return {
        "status": "ok",
        "sarvam_key_configured": bool(settings.sarvam_api_key),
        "gemini_key_configured": bool(settings.gemini_api_key),
        "audio_preprocessing_enabled": settings.enable_audio_preprocessing,
        "ml_model_loaded": model.is_available(),
    }


@app.post("/api/v1/pipeline/process-audio", response_model=PipelineResult)
async def process_audio(
    audio: UploadFile = File(..., description="Patient's voice recording (WAV, MP3, WEBM, etc.)"),
    language_code: str = Form(
        "unknown", description="BCP-47 code e.g. 'ta-IN', 'hi-IN', or 'unknown' to auto-detect"
    ),
    doctor_preferred_language: str = Form(
        "en-IN", description="BCP-47 code for the doctor's interface language"
    ),
    age: str = Form(None, description="Optional patient age"),
    gender: str = Form(None, description="Optional patient gender"),
    reported_duration: str = Form(None, description="Optional reported duration"),
    known_conditions: str = Form(None, description="Optional pre-existing medical conditions"),
    current_medications: str = Form(None, description="Optional current medications"),
) -> PipelineResult:
    """
    Process patient voice recording through the complete AI triage pipeline.
    """
    settings = get_settings()
    if not settings.sarvam_api_key or not settings.gemini_api_key:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: missing SARVAM_API_KEY / GEMINI_API_KEY.",
        )

    audio_bytes = await audio.read()

    if not audio_bytes or len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file uploaded.")

    if len(audio_bytes) > settings.max_audio_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large ({len(audio_bytes)} bytes). Max allowed is {settings.max_audio_bytes} bytes.",
        )

    patient_context = {
        "age": age,
        "gender": gender,
        "reported_duration": reported_duration,
        "known_conditions": known_conditions,
        "current_medications": current_medications,
    }

    try:
        result = await run_pipeline(
            audio_bytes=audio_bytes,
            filename=audio.filename or "patient_audio.wav",
            language_code=language_code,
            patient_context=patient_context,
            doctor_preferred_language=doctor_preferred_language,
        )
        return result

    except AudioTooShortError as exc:
        logger.warning("Audio too short: %s", exc)
        raise HTTPException(status_code=400, detail=f"Audio recording too short: {exc}") from exc

    except AudioTooLongError as exc:
        logger.warning("Audio too long: %s", exc)
        raise HTTPException(status_code=400, detail=f"Audio recording too long: {exc}") from exc

    except AudioFormatError as exc:
        logger.warning("Audio format error: %s", exc)
        raise HTTPException(status_code=400, detail=f"Unsupported or corrupted audio format: {exc}") from exc

    except SarvamSTTError as exc:
        logger.error("Speech-to-text failure: %s", exc)
        raise HTTPException(status_code=502, detail=f"Speech-to-Text service error: {exc}") from exc

    except GeminiExtractionError as exc:
        logger.error("Medical extraction failure: %s", exc)
        raise HTTPException(status_code=502, detail=f"Medical extraction service error: {exc}") from exc

    except Exception as exc:
        logger.exception("Unexpected pipeline failure")
        raise HTTPException(status_code=500, detail=f"Pipeline processing failed: {exc}") from exc


@app.post("/api/v1/doctor/voice-prescription", response_model=VoicePrescriptionResponse)
async def voice_prescription(
    audio: UploadFile = File(..., description="Doctor's spoken advice recording (WAV/WEBM)"),
    patient_language: str = Form(..., description="The patient's language BCP-47 code (e.g., 'ta-IN', 'hi-IN')"),
    consultation_id: Optional[str] = Form(None, description="Optional consultation ID to link this to")
) -> VoicePrescriptionResponse:
    """
    Process doctor's voice prescription.
    """
    settings = get_settings()
    if not settings.sarvam_api_key:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: missing SARVAM_API_KEY.",
        )

    audio_bytes = await audio.read()

    if not audio_bytes or len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file uploaded.")

    try:
        # 1. Transcribe doctor's English audio -> get English text
        transcription_result = await transcribe_and_translate(
            audio_bytes=audio_bytes,
            filename=audio.filename or "doctor_audio.wav",
            language_code="en-IN"
        )
        english_text = transcription_result.transcript_english
        
        if not english_text:
            raise HTTPException(status_code=400, detail="Could not transcribe audio to text.")

        # 2. Translate English text -> patient's language text
        translated_text = await translate_text(
            text=english_text,
            target_language=patient_language,
            source_language="en-IN"
        )

        # 3. Synthesize the translated text -> base64 WAV audio in patient's language
        patient_audio_base64 = await text_to_speech(
            text=translated_text,
            target_language_code=patient_language,
            speaker="kavya"
        )

        return VoicePrescriptionResponse(
            english_text=english_text,
            translated_text=translated_text,
            patient_audio_base64=patient_audio_base64,
            patient_language=patient_language,
            consultation_id=consultation_id
        )

    except SarvamSTTError as exc:
        logger.error("Speech-to-text failure: %s", exc)
        raise HTTPException(status_code=502, detail=f"Speech-to-Text service error: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected voice prescription failure")
        raise HTTPException(status_code=500, detail=f"Voice prescription processing failed: {exc}") from exc


@app.post("/api/v1/export/fhir")
async def export_fhir(result: PipelineResult) -> dict:
    from app.fhir_bundle import generate_fhir_bundle
    try:
        bundle = generate_fhir_bundle(
            request_id=result.request_id,
            patient_input=result.patient_input,
            clinical_summary=result.clinical_summary,
            safety_screening=result.safety_screening,
            priority=result.priority,
        )
        return bundle
    except Exception as exc:
        logger.exception("Failed to generate FHIR bundle")
        raise HTTPException(status_code=500, detail=f"Failed to generate FHIR bundle: {exc}") from exc
