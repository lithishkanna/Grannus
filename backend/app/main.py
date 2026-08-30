"""
RuralCare AI — FastAPI Application

Endpoints:
- GET  /health — Health check & configuration status
- POST /api/v1/pipeline/process-audio — Audio triage pipeline
"""
import logging

from dotenv import load_dotenv

load_dotenv()  # populate os.environ from .env before Settings() reads it

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
from app.schemas import PipelineResult
from app.services.gemini_extract import GeminiExtractionError
from app.services.sarvam_stt import SarvamSTTError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rural_care.api")

app = FastAPI(
    title="RuralCare AI — Medical Triage & Information Pipeline",
    description=(
        "AI processing engine: Audio Preprocessing -> Speech-to-Text (Sarvam) -> "
        "Medical Information Extraction (Gemini) -> Safety Engine -> ML Priority Prediction"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """Pre-load ML model at startup."""
    try:
        model = get_model()
        if model.is_available():
            logger.info("ML priority model pre-loaded successfully at startup.")
        else:
            logger.warning("ML priority model not available at startup. Will use rule engine.")
    except Exception as exc:
        logger.warning("Failed to initialize ML model at startup: %s", exc)


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
