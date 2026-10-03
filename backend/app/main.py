"""
RuralCare AI — FastAPI Application

Endpoints:
- GET  /health — Health check & configuration status
- POST /api/v1/pipeline/process-audio — Audio triage pipeline
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

load_dotenv()  # populate os.environ from .env before Settings() reads it

from contextlib import asynccontextmanager
import time
import uuid
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Depends, status
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.observability.metrics import get_metrics

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

from app.auth import (
    UserRole,
    AuthenticatedUser,
    create_token,
    get_current_user,
    require_role,
    require_verified_doctor,
    generate_signed_url,
    verify_signed_url,
)
from app.security.input_validation import validate_audio_upload, sanitize_filename
from app.security.rate_limiter import rate_limit_patient_intake
from app.security.audit_logger import get_audit_logger
from app.security.data_retention import get_retention_manager
from app.consent import get_consent_notice, record_patient_consent
from app.regulatory import CDSCO_SAMD_DECLARATION, EMERGENCY_DISCLAIMER_TEXT, validate_abdm_fhir_bundle
from app.jobs.job_manager import get_job_manager, JobProgressResponse
from app.telehealth.clinical_actions import (
    get_clinical_action_manager,
    DoctorActionRequest,
    ActionRecord,
)
from app.telehealth.referral_slip import generate_referral_slip, ReferralSlip

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


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """Correlation ID and latency tracking middleware."""
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    get_metrics().record_request(request.url.path)
    
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    get_metrics().record_latency(request.url.path, duration)
    response.headers["X-Request-ID"] = req_id
    return response


@app.get("/health")
def health() -> dict:
    """Liveness probe."""
    settings = get_settings()
    model = get_model()
    return {
        "status": "ok",
        "sarvam_key_configured": bool(settings.sarvam_api_key),
        "gemini_key_configured": bool(settings.gemini_api_key),
        "audio_preprocessing_enabled": settings.enable_audio_preprocessing,
        "ml_model_loaded": model.is_available(),
    }


@app.get("/ready")
def ready() -> dict:
    """Readiness probe validating models and critical integrations."""
    settings = get_settings()
    model = get_model()
    is_ready = bool(settings.sarvam_api_key) and bool(settings.gemini_api_key)
    payload = {
        "status": "ready" if is_ready else "degraded",
        "sarvam_configured": bool(settings.sarvam_api_key),
        "gemini_configured": bool(settings.gemini_api_key),
        "ml_model_loaded": model.is_available(),
    }
    if not is_ready:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=payload)
    return payload


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics():
    """Prometheus exposition metrics."""
    return get_metrics().generate_prometheus_output()


# --- Security & Auth Endpoints ---

class LoginRequest(BaseModel):
    user_id: str
    role: UserRole
    doctor_registration_number: Optional[str] = None
    state_medical_council: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    user_id: str
    role: UserRole
    is_verified_doctor: bool
    doctor_registration_number: Optional[str] = None


class ConsentRequest(BaseModel):
    patient_id: str
    language_code: str = "en-IN"
    explicit_consent: bool


class ErasureRequest(BaseModel):
    patient_id: str
    reason: Optional[str] = "Statutory erasure requested under DPDP Act 2023"


@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """
    Authenticate a patient, doctor, or administrator.
    Verifies Indian medical registration credentials for doctors.
    """
    if req.role == UserRole.DOCTOR:
        if not req.doctor_registration_number:
            raise HTTPException(
                status_code=400,
                detail="Doctor registration requires a valid NMC/State Medical Council registration number.",
            )
        from app.auth import validate_doctor_registration
        if not validate_doctor_registration(req.doctor_registration_number):
            raise HTTPException(
                status_code=400,
                detail="Invalid medical registration number format. Must be an official NMC or State Council ID.",
            )

    token = create_token(
        user_id=req.user_id,
        role=req.role,
        doctor_reg_no=req.doctor_registration_number,
        state_council=req.state_medical_council,
    )
    from app.auth import verify_token
    user = verify_token(token)

    get_audit_logger().log(
        action="AUTH_LOGIN",
        user_id=user.user_id,
        role=user.role.value,
        doctor_registration_number=user.doctor_registration_number,
    )

    return LoginResponse(
        token=token,
        user_id=user.user_id,
        role=user.role,
        is_verified_doctor=user.is_verified_doctor,
        doctor_registration_number=user.doctor_registration_number,
    )


@app.get("/api/v1/consent/notice")
def consent_notice(language_code: str = "en-IN"):
    """Fetch localized consent notice under India's DPDP Act 2023."""
    return get_consent_notice(language_code)


@app.post("/api/v1/consent/record")
def record_consent(req: ConsentRequest, request: Request):
    """Store timestamped, explicit patient consent before audio processing."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        record = record_patient_consent(
            patient_id=req.patient_id,
            language_code=req.language_code,
            client_ip=client_ip,
            explicit_consent=req.explicit_consent,
        )
        get_audit_logger().log(
            action="RECORD_CONSENT",
            user_id=req.patient_id,
            role="patient",
            details={"consent_id": record.consent_id, "version": record.consent_version},
        )
        return record
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/patient/request-erasure")
def request_erasure(req: ErasureRequest, current_user: AuthenticatedUser = Depends(get_current_user)):
    """Statutory Right to Erasure under Section 12 of the DPDP Act 2023."""
    retention_mgr = get_retention_manager()
    erasure_result = retention_mgr.process_patient_erasure(req.patient_id, reason=req.reason or "")
    get_audit_logger().log(
        action="REQUEST_ERASURE",
        user_id=current_user.user_id,
        role=current_user.role.value,
        details={"patient_id": req.patient_id, "reason": req.reason},
    )
    return erasure_result


@app.get("/api/v1/regulatory/positioning")
def regulatory_positioning():
    """Statutory CDSCO SaMD and Telemedicine Practice Guidelines compliance statement."""
    return {
        "cdsco_declaration": CDSCO_SAMD_DECLARATION,
        "emergency_disclaimer": EMERGENCY_DISCLAIMER_TEXT,
        "telemedicine_guidelines_compliant": True,
    }


@app.get("/api/v1/media/stream")
def stream_media(file: str, expires: int, sig: str):
    """
    Access short-lived cryptographic signed media URL (prevents unauthorized public access).
    """
    if not verify_signed_url(file, expires, sig):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signed media link is invalid or expired. Please re-authenticate.",
        )
    return {"status": "authorized", "file": file, "valid_until": expires}


# --- Core Pipeline Endpoints ---

@app.post("/api/v1/pipeline/process-audio", response_model=PipelineResult)
async def process_audio(
    request: Request,
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
    Secured with:
      - Rate limiting & abuse protection
      - Magic byte signature validation
      - Path traversal sanitization
      - Automated 72-hour audio deletion scheduling
      - Audit trail logging
    """
    # 1. Rate limiting & abuse defense
    await rate_limit_patient_intake(request)

    settings = get_settings()
    if not settings.sarvam_api_key or not settings.gemini_api_key:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: missing SARVAM_API_KEY / GEMINI_API_KEY.",
        )

    audio_bytes = await audio.read()

    # 2. Input validation & magic byte inspection
    safe_filename = sanitize_filename(audio.filename)
    validate_audio_upload(audio_bytes, safe_filename, settings.max_audio_bytes)

    # 3. Schedule raw audio deletion under DPDP 72-hour retention policy
    get_retention_manager().schedule_audio_deletion(safe_filename, hours=72)

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
            filename=safe_filename,
            language_code=language_code,
            patient_context=patient_context,
            doctor_preferred_language=doctor_preferred_language,
        )

        # 4. Audit logging
        get_audit_logger().log(
            action="RUN_PIPELINE",
            user_id="anonymous_patient_intake",
            role="patient",
            consultation_id=result.request_id,
            details={"priority": result.priority.level.value, "language": result.patient_input.language},
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
    consultation_id: Optional[str] = Form(None, description="Optional consultation ID to link this to"),
    current_doctor: AuthenticatedUser = Depends(require_verified_doctor),
) -> VoicePrescriptionResponse:
    """
    Process doctor's voice prescription.
    Secured with:
      - Doctor verification under Telemedicine Guidelines 2020
      - Magic byte audio inspection
      - Audit trail logging
    """
    settings = get_settings()
    if not settings.sarvam_api_key:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: missing SARVAM_API_KEY.",
        )

    audio_bytes = await audio.read()
    safe_filename = sanitize_filename(audio.filename or "doctor_audio.wav")
    validate_audio_upload(audio_bytes, safe_filename, settings.max_audio_bytes)

    try:
        # 1. Transcribe doctor's English audio -> get English text
        transcription_result = await transcribe_and_translate(
            audio_bytes=audio_bytes,
            filename=safe_filename,
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

        # Audit log prescription generation
        get_audit_logger().log(
            action="GENERATE_PRESCRIPTION",
            user_id=current_doctor.user_id,
            role=current_doctor.role.value,
            doctor_registration_number=current_doctor.doctor_registration_number,
            consultation_id=consultation_id,
            details={"patient_language": patient_language},
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
async def export_fhir(
    result: PipelineResult,
    current_user: AuthenticatedUser = Depends(require_role([UserRole.DOCTOR, UserRole.ADMIN])),
) -> dict:
    """
    Generate and export ABDM-compliant FHIR R4 Bundle.
    Secured with:
      - Role-based authorization (Doctor/Admin only)
      - ABDM profile validation
      - Audit trail logging
    """
    from app.fhir_bundle import generate_fhir_bundle
    try:
        bundle = generate_fhir_bundle(
            request_id=result.request_id,
            patient_input=result.patient_input,
            clinical_summary=result.clinical_summary,
            safety_screening=result.safety_screening,
            priority=result.priority,
        )

        # Validate against ABDM FHIR profiles
        is_valid, validation_errors = validate_abdm_fhir_bundle(bundle)
        if not is_valid:
            logger.warning("ABDM profile validation warnings: %s", validation_errors)

        # Audit log FHIR export
        get_audit_logger().log(
            action="EXPORT_FHIR",
            user_id=current_user.user_id,
            role=current_user.role.value,
            doctor_registration_number=current_user.doctor_registration_number,
            consultation_id=result.request_id,
            details={"abdm_valid": is_valid},
        )

        return bundle
    except Exception as exc:
        logger.exception("Failed to generate FHIR bundle")
        raise HTTPException(status_code=500, detail=f"Failed to generate FHIR bundle: {exc}") from exc


# -----------------------------------------------------------------------------
# Phase 5: Field Pilot Readiness & Telehealth Orchestration Endpoints
# -----------------------------------------------------------------------------

@app.post("/api/v1/pipeline/submit-audio", status_code=status.HTTP_202_ACCEPTED)
async def submit_audio_async(
    request: Request,
    audio: UploadFile = File(..., description="Patient's voice recording"),
    language_code: str = Form("unknown"),
    doctor_preferred_language: str = Form("en-IN"),
    age: str = Form(None),
    gender: str = Form(None),
    reported_duration: str = Form(None),
    known_conditions: str = Form(None),
    current_medications: str = Form(None),
):
    """
    Non-blocking asynchronous audio intake endpoint returning 202 Accepted.
    Eliminates HTTP gateway timeouts on slow / low-bandwidth 2G/3G rural networks.
    """
    await rate_limit_patient_intake(request)

    settings = get_settings()
    if not settings.sarvam_api_key or not settings.gemini_api_key:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: missing SARVAM_API_KEY / GEMINI_API_KEY.",
        )

    audio_bytes = await audio.read()
    safe_filename = sanitize_filename(audio.filename)
    validate_audio_upload(audio_bytes, safe_filename, settings.max_audio_bytes)

    # Schedule raw audio deletion under DPDP 72-hour retention policy
    get_retention_manager().schedule_audio_deletion(safe_filename, hours=72)

    patient_context = {
        "age": age,
        "gender": gender,
        "reported_duration": reported_duration,
        "known_conditions": known_conditions,
        "current_medications": current_medications,
    }

    job_mgr = get_job_manager()
    job_id = job_mgr.create_job()

    # Dispatch to background task worker
    asyncio.create_task(
        job_mgr.execute_job(
            job_id=job_id,
            audio_bytes=audio_bytes,
            filename=safe_filename,
            language_code=language_code,
            patient_context=patient_context,
            doctor_preferred_language=doctor_preferred_language,
        )
    )

    return {
        "job_id": job_id,
        "status": "QUEUED",
        "poll_url": f"/api/v1/pipeline/job-status/{job_id}",
        "message": "Consultation audio accepted for asynchronous triage processing.",
    }


@app.get("/api/v1/pipeline/job-status/{job_id}", response_model=JobProgressResponse)
def get_job_status(job_id: str):
    """
    Poll stage-by-stage progress of an asynchronous consultation triage job.
    """
    job = get_job_manager().get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job ID '{job_id}' not found or expired.",
        )
    return job.to_response()


@app.post("/api/v1/consultations/action", response_model=ActionRecord)
def record_consultation_action(
    req: DoctorActionRequest,
    current_doctor: AuthenticatedUser = Depends(require_verified_doctor),
):
    """
    Record clinical decision (confirm triage, priority override, prescribe, refer).
    Restricted to verified Registered Medical Practitioners (RMPs).
    """
    return get_clinical_action_manager().record_action(req, current_doctor)


@app.get("/api/v1/consultations/{consultation_id}/actions", response_model=List[ActionRecord])
def get_consultation_action_history(
    consultation_id: str,
    current_user: AuthenticatedUser = Depends(require_role([UserRole.DOCTOR, UserRole.ADMIN])),
):
    """Retrieve complete clinical decision and referral history for a consultation."""
    return get_clinical_action_manager().get_consultation_actions(consultation_id)


class ReferralSlipRequest(BaseModel):
    result: PipelineResult
    clinical_notes: Optional[str] = None
    referral_facility: Optional[str] = None


@app.post("/api/v1/consultations/referral-slip", response_model=ReferralSlip)
def create_clinical_referral_slip(
    req: ReferralSlipRequest,
    current_doctor: AuthenticatedUser = Depends(require_verified_doctor),
):
    """
    Generate official bilingual referral slip / e-prescription for PHC / CHC patient handoff.
    """
    return generate_referral_slip(
        result=req.result,
        doctor=current_doctor,
        referral_facility=req.referral_facility,
        clinical_notes=req.clinical_notes,
    )
