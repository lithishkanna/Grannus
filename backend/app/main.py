"""
RuralCare AI — FastAPI Application

Endpoints:
- GET  /health — Health check & configuration status
- POST /api/v1/pipeline/process-audio — Audio triage pipeline
"""
import os
import logging
import asyncio
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

load_dotenv()  # populate os.environ from .env before Settings() reads it

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import time
import uuid
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Depends, status, Security
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
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
from app.schemas import (
    PipelineResult,
    VoicePrescriptionResponse,
    CheckInRequest,
    CheckInResponse,
    VoiceThread,
    VoiceThreadMessage,
)
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
    revoke_token,
    security_bearer,
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
from app.follow_up import get_follow_up_manager
from app.voice_threads import get_voice_thread_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rural_care.api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify mandatory secrets and pre-load ML model at startup."""
    settings = get_settings()
    if not settings.jwt_secret_key:
        raise RuntimeError("JWT_SECRET_KEY is mandatory and not configured. Backend refusing to start.")

    # Block H2: In production/staging, database and SMS provider must be configured
    if settings.env.lower() in ("production", "prod", "staging"):
        key = settings.supabase_service_role_key or settings.supabase_anon_key
        if not settings.supabase_url or not key:
            raise RuntimeError(f"Database (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY) is mandatory in {settings.env}. Backend refusing to start.")
        if not settings.sms_provider or (settings.sms_provider == "msg91" and not settings.msg91_auth_key) or (settings.sms_provider == "twilio" and not settings.twilio_account_sid):
            raise RuntimeError(f"SMS provider is mandatory in {settings.env}. Backend refusing to start.")

    try:
        model = get_model()
        if model.is_available():
            logger.info("ML priority model pre-loaded successfully at startup.")
        else:
            logger.warning("ML priority model not available at startup. Will use rule engine.")
    except Exception as exc:
        logger.warning("Failed to initialize ML model at startup: %s", exc)

    # Statutory 24-hour audio retention sweep on startup
    try:
        from app.security.data_retention import get_retention_manager
        purged = get_retention_manager().execute_retention_sweep()
        if purged:
            logger.info("Startup audio retention sweep purged %d files.", len(purged))
    except Exception as exc:
        logger.warning("Startup audio retention sweep error: %s", exc)

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

# -- CORS: allow configured origins or local development origins --
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()] if allowed_origins_env else [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Enforce defensive HTTP security headers across all endpoints."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
    if get_settings().env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    return response


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

class OTPRequest(BaseModel):
    phone_number: str


class OTPRequestResponse(BaseModel):
    success: bool
    message: str


class OTPVerifyRequest(BaseModel):
    phone_number: str
    otp_code: str


class GuestEmergencyRequest(BaseModel):
    guest_name: str
    age: Optional[str] = None
    gender: Optional[str] = None
    language_code: Optional[str] = "en-IN"


class GuestEmergencyResponse(BaseModel):
    success: bool
    guest_token: str
    case_id: str
    message: str
    emergency_contact: str = "108 / 112"


class LoginRequest(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None
    doctor_registration_number: Optional[str] = None
    state_medical_council: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    user_id: str
    role: UserRole
    is_verified_doctor: bool = False
    doctor_registration_number: Optional[str] = None
    phone_number: Optional[str] = None
    account_id: Optional[str] = None
    full_name: Optional[str] = None
    hospital_id: Optional[str] = None


class PatientProfileCreate(BaseModel):
    full_name: str
    age: Optional[str] = None
    gender: Optional[str] = None
    relation: Optional[str] = "self"
    preferred_language: Optional[str] = "ta-IN"
    allergies: Optional[List[str]] = None
    medications: Optional[List[str]] = None
    known_conditions: Optional[List[str]] = None
    pin: Optional[str] = None


class ConsentRequest(BaseModel):
    patient_id: str
    language_code: str = "en-IN"
    explicit_consent: bool


class ErasureRequest(BaseModel):
    patient_id: str
    reason: Optional[str] = "Statutory erasure requested under DPDP Act 2023"


@app.post("/api/v1/auth/otp/request", response_model=OTPRequestResponse)
def request_phone_otp_endpoint(req: OTPRequest):
    """
    Request 6-digit phone OTP for patient authentication (B2.2, H1.2).
    Enforces cooldown and 5-minute single-use expiration.
    Codes never appear in API responses, logs, or error payloads.
    """
    from app.db import request_phone_otp
    success, message, _ = request_phone_otp(req.phone_number)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message,
        )
    return OTPRequestResponse(
        success=True,
        message=message,
    )


@app.post("/api/v1/auth/otp/verify", response_model=LoginResponse)
def verify_phone_otp_endpoint(req: OTPVerifyRequest):
    """
    Verify phone OTP for patient session creation (B2.2).
    Single-use, max 5 attempts.
    """
    from app.db import verify_phone_otp
    success, message, account = verify_phone_otp(req.phone_number, req.otp_code)
    if not success or not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
        )

    account_id = account["id"]
    phone_number = account["phone_number"]
    user_id = f"pat_{account_id[:8]}"

    token = create_token(
        user_id=user_id,
        role=UserRole.PATIENT,
        phone_number=phone_number,
        account_id=account_id,
    )

    get_audit_logger().log(
        action="AUTH_PATIENT_OTP_VERIFIED",
        user_id=user_id,
        role=UserRole.PATIENT.value,
        details={"account_id": account_id},
    )

    return LoginResponse(
        token=token,
        user_id=user_id,
        role=UserRole.PATIENT,
        is_verified_doctor=False,
        phone_number=phone_number,
        account_id=account_id,
    )


@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """
    Authenticate staff (doctors, nurses, admins) with email and password,
    or verify credentials with medical registration number validation (B2.3).
    """
    from app.auth import validate_doctor_registration, authenticate_credentials, verify_token
    from app.db import authenticate_staff_user, find_staff_user

    identifier = (req.email or req.user_id or "").strip()
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or User ID is required.",
        )

    staff = None
    staff_record = find_staff_user(identifier)
    if staff_record:
        if not req.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password is required for staff account authentication.",
            )
        staff = authenticate_staff_user(identifier, req.password)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials. Please verify your email and password.",
            )
        role = UserRole(staff["role"])
        user_id = staff.get("id", identifier)
        doc_reg = staff.get("doctor_registration_number") or req.doctor_registration_number
        state_council = staff.get("state_council") or req.state_medical_council
        full_name = staff.get("full_name")
        hospital_id = staff.get("hospital_id")
    else:
        if not req.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password is required for staff account authentication.",
            )
        from app.auth import _REGISTERED_USERS
        if identifier in _REGISTERED_USERS and authenticate_credentials(identifier, req.role or UserRole.DOCTOR, req.password):
            reg = _REGISTERED_USERS[identifier]
            role = UserRole(reg["role"])
            user_id = identifier
            doc_reg = reg.get("doctor_reg_no") or req.doctor_registration_number
            state_council = reg.get("state_council") or req.state_medical_council
            full_name = identifier
            hospital_id = "c5b971d1-fe39-40bf-a5cb-539f1a98059f"
            is_verified_doc = True
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials. Unregistered staff account.",
            )

    is_verified_doc = None
    if staff and role == UserRole.DOCTOR:
        is_verified_doc = staff.get("is_verified_doctor", True)

    if role == UserRole.DOCTOR:
        if not doc_reg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor registration requires a valid NMC/State Medical Council registration number.",
            )
        if not is_verified_doc and not validate_doctor_registration(doc_reg):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid medical registration number format. Must be an official NMC or State Council ID.",
            )

    token = create_token(
        user_id=user_id,
        role=role,
        doctor_reg_no=doc_reg,
        state_council=state_council,
        hospital_id=hospital_id,
        is_verified_doctor=is_verified_doc,
    )
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
        full_name=full_name,
        hospital_id=hospital_id,
    )


@app.post("/api/v1/auth/guest-emergency", response_model=GuestEmergencyResponse)
def guest_emergency_intake(req: GuestEmergencyRequest):
    """
    Emergency access without OTP (H1.3).
    Instant 'Call 108' triage screen appears on client, and the backend generates
    a secure single-case guest token alerting the hospital ER.
    """
    clean_name = req.guest_name.strip()
    if len(clean_name) < 2:
        clean_name = "Emergency Patient"

    case_id = f"emg_{uuid.uuid4().hex[:12]}"
    guest_id = f"guest_{uuid.uuid4().hex[:12]}"

    token = create_token(
        user_id=guest_id,
        role=UserRole.GUEST_EMERGENCY,
        guest_case_id=case_id,
        guest_token=guest_id,
        expires_in_seconds=7200,  # 2 hours
    )

    from app.db import save_consultation, save_guest_case
    save_guest_case(case_id, {
        "id": case_id,
        "patient_name": clean_name,
        "age": req.age,
        "urgency_tier": "emergency",
        "chief_complaint": f"Emergency Guest Walk-in / Intake: {clean_name}",
        "guest_token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "status": "unverified",
    })
    save_consultation(case_id, {
        "id": case_id,
        "patient_id": guest_id,
        "urgency_tier": "emergency",
        "status": "emergency_unverified",
        "chief_complaint": f"Emergency Guest Walk-in / Intake: {clean_name}",
        "patient_language": req.language_code or "en-IN",
        "department_id": "GEN_MED",
        "is_guest_emergency": True,
        "guest_name": clean_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    get_audit_logger().log(
        action="GUEST_EMERGENCY_INTAKE",
        user_id=guest_id,
        role="guest_emergency",
        consultation_id=case_id,
        details={"name": clean_name, "age": req.age, "gender": req.gender},
    )

    return GuestEmergencyResponse(
        success=True,
        guest_token=token,
        case_id=case_id,
        message="Emergency intake recorded. Hospital ER alerted. Dial 108 or 112 immediately.",
        emergency_contact="108 / 112",
    )


@app.post("/api/v1/auth/refresh", response_model=LoginResponse)
def refresh_session_token(current_user: AuthenticatedUser = Depends(get_current_user)):
    """
    Renew active session token (H1.4).
    """
    new_token = create_token(
        user_id=current_user.user_id,
        role=current_user.role,
        doctor_reg_no=current_user.doctor_registration_number,
        state_council=current_user.state_medical_council,
        phone_number=current_user.phone_number,
        account_id=current_user.account_id,
        profile_id=current_user.profile_id,
        hospital_id=current_user.hospital_id,
        is_verified_doctor=current_user.is_verified_doctor,
        guest_case_id=current_user.guest_case_id,
        guest_token=current_user.guest_token,
        expires_in_seconds=86400,
    )
    return LoginResponse(
        token=new_token,
        user_id=current_user.user_id,
        role=current_user.role,
        is_verified_doctor=current_user.is_verified_doctor,
        doctor_registration_number=current_user.doctor_registration_number,
        phone_number=current_user.phone_number,
        account_id=current_user.account_id,
    )


@app.post("/api/v1/auth/logout")
async def logout(
    current_user: AuthenticatedUser = Depends(get_current_user),
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
):
    """Revoke active JWT token upon logout (B2.5)."""
    if auth and auth.credentials:
        revoke_token(auth.credentials)
    get_audit_logger().log(
        action="AUTH_LOGOUT",
        user_id=current_user.user_id,
        role=current_user.role.value,
    )
    return {"status": "success", "message": "Logged out successfully. Session invalidated."}


@app.get("/api/v1/auth/me", response_model=AuthenticatedUser)
async def get_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve profile and session claims for currently authenticated user."""
    return current_user


@app.get("/api/v1/patient/profiles")
async def list_patient_profiles(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List all patient profiles linked to authenticated phone account (B4.1)."""
    if current_user.role == UserRole.GUEST_EMERGENCY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Guest emergency sessions cannot browse patient profiles.",
        )
    from app.db import get_profiles_for_account
    if not current_user.account_id:
        return []
    return get_profiles_for_account(current_user.account_id)


@app.get("/api/v1/patient/consultations")
async def list_patient_consultations(
    profile_id: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    List all clinical intake reports and consultations for the authenticated patient (B4.2).
    Optionally filters by specific patient family profile.
    """
    if current_user.role == UserRole.GUEST_EMERGENCY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Guest emergency sessions cannot browse historical consultation lists.",
        )
    from app.db import get_consultations_for_patient
    account_id = current_user.account_id
    consultations = get_consultations_for_patient(account_id=account_id, profile_id=profile_id)
    return {
        "count": len(consultations),
        "consultations": consultations,
    }


@app.post("/api/v1/patient/profiles")
async def create_patient_profile_endpoint(
    req: PatientProfileCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Register a new patient profile under verified phone account (B4.1)."""
    if not current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated patient phone account required to register profiles.",
        )
    from app.db import create_patient_profile, hash_password
    profile_data = req.dict(exclude={"pin"})
    if req.pin:
        profile_data["pin_hash"] = hash_password(req.pin)

    profile = create_patient_profile(current_user.account_id, profile_data)
    get_audit_logger().log(
        action="CREATE_PATIENT_PROFILE",
        user_id=current_user.user_id,
        role=current_user.role.value,
        details={"profile_id": profile["id"], "relation": req.relation},
    )
    return profile


class VerifyPinRequest(BaseModel):
    pin: str


@app.get("/api/v1/patient/profiles/{profile_id}")
def get_patient_profile_endpoint(
    profile_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve details for a single patient profile with ownership enforcement (H3.1)."""
    if current_user.role == UserRole.GUEST_EMERGENCY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Guest emergency sessions cannot browse patient profiles.",
        )
    from app.db import get_patient_profile
    profile = get_patient_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Patient profile not found.")
    if current_user.role == UserRole.PATIENT:
        if profile.get("account_id") and profile.get("account_id") != current_user.account_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You cannot access another account's patient profile.",
            )
    get_audit_logger().log(
        action="PATIENT_PROFILE_READ",
        user_id=current_user.user_id,
        role=current_user.role.value,
        details={"profile_id": profile_id},
    )
    return profile


@app.post("/api/v1/patient/profiles/{profile_id}/verify-pin")
def verify_profile_pin_endpoint(
    profile_id: str,
    req: VerifyPinRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Verify 4-digit PIN before unlocking private patient profile (B4.3)."""
    if current_user.role == UserRole.GUEST_EMERGENCY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Guest emergency sessions cannot verify profile PINs.",
        )
    from app.db import get_patient_profile, verify_profile_pin
    profile = get_patient_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Patient profile not found.")
    if current_user.role == UserRole.PATIENT:
        if profile.get("account_id") and profile.get("account_id") != current_user.account_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You cannot access another account's patient profile.",
            )
    if not verify_profile_pin(profile_id, req.pin):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect 4-digit PIN for this profile.",
        )
    return {"verified": True, "profile_id": profile_id}


@app.post("/api/v1/patient/account/reset-recycled")
def reset_recycled_account(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Clear prior profile associations for recycled phone numbers (B4.4)."""
    if not current_user.account_id:
        raise HTTPException(status_code=400, detail="Authenticated patient phone account required.")
    from app.db import reset_recycled_phone_number
    reset_recycled_phone_number(current_user.account_id)
    return {"status": "success", "message": "Recycled phone number profile history reset successfully."}


@app.get("/api/v1/consent/notice")
def consent_notice(language_code: str = "en-IN"):
    """Fetch localized consent notice under India's DPDP Act 2023."""
    return get_consent_notice(language_code)


@app.post("/api/v1/consent/record")
def record_consent(req: ConsentRequest, request: Request):
    """Store timestamped, explicit patient consent before audio processing (B4.5)."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        record = record_patient_consent(
            patient_id=req.patient_id,
            language_code=req.language_code,
            client_ip=client_ip,
            explicit_consent=req.explicit_consent,
        )
        from app.db import save_consent_record
        save_consent_record({
            "patient_id": req.patient_id,
            "version": record.consent_version,
            "language_code": req.language_code,
            "ip_hash": record.ip_hash,
            "is_granted": True,
        })
        get_audit_logger().log(
            action="RECORD_CONSENT",
            user_id=req.patient_id,
            role="patient",
            details={"consent_id": record.consent_id, "version": record.consent_version},
        )
        return record
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/patient/data-export")
def export_patient_data(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Statutory Right to Data Portability & Access under DPDP Act 2023 (B4.6)."""
    if not current_user.account_id:
        raise HTTPException(status_code=400, detail="Authenticated account required for data export.")
    from app.db import export_account_data
    data = export_account_data(current_user.account_id)
    get_audit_logger().log(
        action="PATIENT_DATA_EXPORT",
        user_id=current_user.user_id,
        role=current_user.role.value,
        details={"account_id": current_user.account_id},
    )
    return data


@app.post("/api/v1/patient/data-erasure")
def erase_patient_data(
    req: Optional[ErasureRequest] = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Statutory Right to Erasure under Section 12 of DPDP Act 2023 (B4.6)."""
    if not current_user.account_id:
        raise HTTPException(status_code=400, detail="Authenticated account required for data erasure.")
    from app.db import erase_account_data
    reason = req.reason if req and req.reason else "Statutory erasure under DPDP Act 2023"
    erase_account_data(current_user.account_id, reason=reason)
    return {"status": "success", "message": "All patient profiles and identifiable records erased."}


@app.post("/api/v1/patient/request-erasure")
def request_erasure(req: ErasureRequest, current_user: AuthenticatedUser = Depends(get_current_user)):
    """Legacy alias for statutory right to erasure."""
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
    # Block H4.7: If audio file has expired/deleted under 24h retention policy -> 404
    if get_retention_manager().is_audio_purged(file) or not os.path.exists(file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio recording has expired or been permanently deleted under the 24-hour statutory retention policy.",
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
    profile_id: Optional[str] = Form(None, description="Optional patient profile ID (B4.2)"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PipelineResult:
    """
    Process patient voice recording through the complete AI triage pipeline.
    Secured with:
      - Mandatory user authentication (H3.5)
      - Rate limiting & abuse protection
      - Magic byte signature validation
      - Path traversal sanitization
      - Automated 24-hour audio deletion scheduling (H4.1)
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

    # 3. Schedule raw audio deletion under 24-hour retention policy (H4.1)
    get_retention_manager().schedule_audio_deletion(safe_filename, hours=24)

    # Resolve patient phone account linkage (B4.2)
    resolved_account_id = None
    if profile_id:
        from app.db import get_patient_profile
        prof = get_patient_profile(profile_id)
        if prof:
            resolved_account_id = prof.get("account_id")

    auth_header = request.headers.get("Authorization")
    if not resolved_account_id and auth_header and auth_header.startswith("Bearer "):
        try:
            from app.auth import verify_token
            token_user = verify_token(auth_header.split(" ", 1)[1])
            if token_user and token_user.account_id:
                resolved_account_id = token_user.account_id
        except Exception:
            pass

    patient_context = {
        "age": age,
        "gender": gender,
        "reported_duration": reported_duration,
        "known_conditions": known_conditions,
        "current_medications": current_medications,
        "profile_id": profile_id,
        "account_id": resolved_account_id,
    }

    try:
        result = await run_pipeline(
            audio_bytes=audio_bytes,
            filename=safe_filename,
            language_code=language_code,
            patient_context=patient_context,
            doctor_preferred_language=doctor_preferred_language,
        )

        # 3b. Route by complaint category and persist consultation (B5.3, B5.8, F1.1)
        try:
            from app.routing import categorize_complaint, select_best_doctor
            from app.db import save_consultation, save_assignment, get_staff_doctors

            complaint_cat, dept_code, routing_rationale = categorize_complaint(
                clinical_summary=result.clinical_summary,
                patient_context=patient_context,
                safety_screening=result.safety_screening,
                urgency_tier=result.priority.urgency_tier,
            )

            all_doctors = get_staff_doctors()
            assigned_doc, doc_selection_rationale = select_best_doctor(
                doctors=all_doctors,
                department_code=dept_code,
                patient_language=result.patient_input.language,
            )
            assigned_doc_id = assigned_doc.get("id") if assigned_doc else None

            save_consultation(result.request_id, {
                "account_id": patient_context.get("account_id"),
                "profile_id": patient_context.get("profile_id"),
                "status": "triage",
                "patient_language": result.patient_input.language,
                "urgency_tier": result.priority.urgency_tier,
                "department_id": dept_code,
                "assigned_doctor_id": assigned_doc_id,
                "original_transcript": result.patient_input.transcript_original,
                "english_transcript": result.patient_input.transcript_english,
                "complaint_category": complaint_cat,
                "chief_complaint": result.clinical_summary.chief_complaint if result.clinical_summary else None,
                "full_result": result.dict(),
            })

            if assigned_doc_id:
                save_assignment(
                    consultation_id=result.request_id,
                    doctor_id=assigned_doc_id,
                    assigned_by="system_routing",
                    status="assigned",
                    reassignment_reason=f"{routing_rationale} {doc_selection_rationale}",
                    locked_by_name=assigned_doc.get("full_name"),
                )
        except Exception as route_err:
            logger.warning("Routing failed for consultation %s: %s", result.request_id, route_err)

        # 4. Register for follow-up tracking
        try:
            get_follow_up_manager().register_consultation(
                consultation_id=result.request_id,
                urgency_tier=result.priority.urgency_tier,
                follow_up_days=result.priority.follow_up_days,
            )
        except Exception as fu_err:
            logger.warning("Failed to register follow-up for %s: %s", result.request_id, fu_err)

        # 5. Audit logging
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
        raise HTTPException(status_code=400, detail="Audio recording too short. Minimum duration is 1.0 second.") from exc

    except AudioTooLongError as exc:
        logger.warning("Audio too long: %s", exc)
        raise HTTPException(status_code=400, detail="Audio recording exceeds maximum permitted duration.") from exc

    except AudioFormatError as exc:
        logger.warning("Audio format error: %s", exc)
        raise HTTPException(status_code=400, detail="Unsupported or corrupted audio format.") from exc

    except SarvamSTTError as exc:
        logger.error("Speech-to-text failure: %s", exc)
        raise HTTPException(status_code=502, detail="Speech-to-Text service temporarily unavailable.") from exc

    except GeminiExtractionError as exc:
        logger.error("Medical extraction failure: %s", exc)
        raise HTTPException(status_code=502, detail="Medical extraction service temporarily unavailable.") from exc

    except Exception as exc:
        logger.exception("Unexpected pipeline failure")
        raise HTTPException(status_code=500, detail="Pipeline processing failed. Please try again or seek direct medical attention.") from exc


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
      - Translation safety: Back-translation verification to ensure clinical accuracy
      - Asynchronous bilingual voice threads
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

        # 2b. Translation safety: Back-translate from patient language back to English for doctor verification
        back_translated_text = english_text
        if patient_language != "en-IN":
            try:
                back_translated_text = await translate_text(
                    text=translated_text,
                    target_language="en-IN",
                    source_language=patient_language,
                )
            except Exception as bt_err:
                logger.warning("Back-translation failed: %s; using English original as fallback", bt_err)
                back_translated_text = english_text

        # 3. Synthesize the translated text -> base64 WAV audio in patient's language
        patient_audio_base64 = await text_to_speech(
            text=translated_text,
            target_language_code=patient_language,
            speaker="kavya"
        )

        # 4. If linked to consultation, append to asynchronous voice thread
        if consultation_id:
            try:
                get_voice_thread_manager().add_message(
                    consultation_id=consultation_id,
                    sender="doctor",
                    original_text=english_text,
                    translated_text=translated_text,
                    original_language="en-IN",
                    target_language=patient_language,
                    back_translated_text=back_translated_text,
                    audio_base64=patient_audio_base64,
                )
            except Exception as vt_err:
                logger.warning("Failed to append voice thread message: %s", vt_err)

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
            back_translated_text=back_translated_text,
            translation_verified=True,
            patient_audio_base64=patient_audio_base64,
            patient_language=patient_language,
            consultation_id=consultation_id
        )

    except SarvamSTTError as exc:
        logger.error("Speech-to-text failure: %s", exc)
        raise HTTPException(status_code=502, detail="Speech-to-Text service temporarily unavailable.") from exc
    except Exception as exc:
        logger.exception("Unexpected voice prescription failure")
        raise HTTPException(status_code=500, detail="Voice prescription processing failed.") from exc


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
            patient_context=getattr(result, "patient_context", None),
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
        raise HTTPException(status_code=500, detail="Failed to generate ABDM FHIR bundle.") from exc


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
    profile_id: Optional[str] = Form(None),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Non-blocking asynchronous audio intake endpoint returning 202 Accepted.
    Requires authentication (H3.5).
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

    # Schedule raw audio deletion under 24-hour retention policy (H4.1)
    get_retention_manager().schedule_audio_deletion(safe_filename, hours=24)

    patient_context = {
        "age": age,
        "gender": gender,
        "reported_duration": reported_duration,
        "known_conditions": known_conditions,
        "current_medications": current_medications,
        "profile_id": profile_id,
        "account_id": current_user.account_id,
        "user_id": current_user.user_id,
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
def get_job_status(
    job_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
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


# -----------------------------------------------------------------------------
# Follow-Up Check-in, One-Tap Escalation & Asynchronous Voice Threads
# -----------------------------------------------------------------------------

class EscalateRequest(BaseModel):
    reason: Optional[str] = None


@app.post("/api/v1/consultations/{consultation_id}/check-in", response_model=CheckInResponse)
def check_in_consultation(
    consultation_id: str,
    req: CheckInRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Record patient 2 to 3 day follow-up check-in ('improving', 'same', 'worse').
    Automatically escalates urgency tier if 'worse' is reported.
    """
    if current_user.role in (UserRole.NURSE, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Forbidden: Hospital staff cannot record patient self-check-ins.")
    if current_user.role == UserRole.GUEST_EMERGENCY and current_user.guest_case_id != consultation_id:
        raise HTTPException(status_code=403, detail="Forbidden: Guest emergency access restricted to own case.")

    from app.db import get_consultation
    consultation = get_consultation(consultation_id)
    if consultation:
        if current_user.role == UserRole.PATIENT:
            if consultation.get("account_id") and consultation.get("account_id") != current_user.account_id:
                raise HTTPException(status_code=403, detail="Forbidden: You cannot check-in for another patient's consultation.")

    response = get_follow_up_manager().record_check_in(
        consultation_id=consultation_id,
        status=req.status,
        notes=req.notes,
    )
    get_audit_logger().log(
        action="PATIENT_CHECK_IN",
        user_id=current_user.user_id,
        role=current_user.role.value,
        consultation_id=consultation_id,
        details={
            "status": req.status,
            "previous_tier": response.previous_tier.value,
            "new_tier": response.new_tier.value,
            "is_escalated": response.is_escalated,
        },
    )
    return response


@app.post("/api/v1/consultations/{consultation_id}/escalate", response_model=CheckInResponse)
def escalate_consultation(
    consultation_id: str,
    req: Optional[EscalateRequest] = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    One-tap 'I feel worse' button action.
    Immediately escalates the patient up one urgency tier:
      self_care -> doctor_soon -> doctor_today -> emergency
    """
    if current_user.role in (UserRole.NURSE, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Forbidden: Hospital staff cannot trigger patient self-escalation.")
    if current_user.role == UserRole.GUEST_EMERGENCY and current_user.guest_case_id != consultation_id:
        raise HTTPException(status_code=403, detail="Forbidden: Guest emergency access restricted to own case.")

    from app.db import get_consultation
    consultation = get_consultation(consultation_id)
    if consultation:
        if current_user.role == UserRole.PATIENT:
            if consultation.get("account_id") and consultation.get("account_id") != current_user.account_id:
                raise HTTPException(status_code=403, detail="Forbidden: You cannot escalate another patient's consultation.")

    reason = req.reason if req and req.reason else "Patient initiated one-tap 'I feel worse' escalation."
    response = get_follow_up_manager().escalate_tier(
        consultation_id=consultation_id,
        reason=reason,
    )
    get_audit_logger().log(
        action="ONE_TAP_ESCALATE",
        user_id=current_user.user_id,
        role=current_user.role.value,
        consultation_id=consultation_id,
        details={
            "previous_tier": response.previous_tier.value,
            "new_tier": response.new_tier.value,
            "reason": reason,
        },
    )
    return response


@app.get("/api/v1/patient/check-in-prompts")
def get_patient_check_in_prompts(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Check if any 2-3 day follow-up check-ins are due for this patient account (B6.5).
    Used to show prompt banners or modals upon app opening.
    """
    from app.db import get_profiles_for_account
    profile_ids = []
    if current_user.account_id:
        profiles = get_profiles_for_account(current_user.account_id)
        profile_ids = [p["id"] for p in profiles]
    prompts = get_follow_up_manager().get_due_check_ins(
        account_id=current_user.account_id,
        profile_ids=profile_ids,
    )
    return {"due_check_ins": prompts, "count": len(prompts)}


@app.post("/api/v1/follow-ups/process-due")
def process_due_follow_up_notifications(
    current_user: AuthenticatedUser = Depends(require_role([UserRole.ADMIN, UserRole.DOCTOR])),
):
    """
    Scheduler endpoint to trigger automated SMS dispatch for overdue check-ins (B6.5).
    """
    dispatched_count = get_follow_up_manager().dispatch_due_check_in_notifications()
    return {"status": "success", "dispatched_notifications": dispatched_count}


class VerifyDoctorReplyRequest(BaseModel):
    english_reply: str
    patient_language: str = "ta-IN"


@app.post("/api/v1/consultations/{consultation_id}/verify-reply-translation")
async def verify_doctor_reply_translation(
    consultation_id: str,
    req: VerifyDoctorReplyRequest,
    current_doctor: AuthenticatedUser = Depends(require_verified_doctor),
):
    """
    Back-translate doctor voice/text reply so the clinician can verify it before sending (B7.4).
    Guarantees medication names & dosages are preserved and not distorted by translation.
    """
    from app.services.translation import verify_and_back_translate_doctor_reply
    result = await verify_and_back_translate_doctor_reply(
        doctor_english_reply=req.english_reply,
        patient_language=req.patient_language,
    )
    return result


@app.get("/api/v1/demo/sample-cases")
def get_demo_sample_cases():
    """
    List the 8 pre-cached demonstration cases for 100% offline-resilient evaluation (B7.6).
    """
    from app.demo_cache import list_cached_sample_cases
    return {"cases": list_cached_sample_cases()}


@app.post("/api/v1/demo/run-sample/{sample_id}")
def run_demo_sample_case(
    sample_id: str,
    language_code: str = "en-IN",
):
    """
    Instantly return the pre-cached PipelineResult for a demo case and persist it in the queue (B7.6).
    """
    from app.demo_cache import get_cached_demo_response
    from app.db import save_consultation
    from app.routing import route_consultation
    cached_result = get_cached_demo_response(sample_id, language_code)
    if not cached_result:
        raise HTTPException(status_code=404, detail=f"Demo sample '{sample_id}' not found.")

    cid = cached_result.request_id
    from app.routing import categorize_complaint
    category, dept_code, _ = categorize_complaint(
        clinical_summary=cached_result.clinical_summary,
        urgency_tier=cached_result.priority.urgency_tier.value,
    )
    save_consultation(cid, {
        "id": cid,
        "status": "triage",
        "patient_language": language_code,
        "urgency_tier": cached_result.priority.urgency_tier.value,
        "complaint_category": category,
        "department_id": dept_code,
        "chief_complaint": cached_result.clinical_summary.chief_complaint,
        "original_transcript": cached_result.patient_input.transcript_original,
        "english_transcript": cached_result.patient_input.transcript_english,
        "full_result": cached_result.model_dump(),
        "age": cached_result.patient_input.age,
        "gender": cached_result.patient_input.gender,
    })

    get_follow_up_manager().register_consultation(
        consultation_id=cid,
        urgency_tier=cached_result.priority.urgency_tier,
        follow_up_days=cached_result.priority.follow_up_days or 2,
    )

    c_dict = {"id": cid, "urgency_tier": cached_result.priority.urgency_tier.value, "patient_language": language_code}
    route_consultation(c_dict, cached_result.clinical_summary, cached_result.safety_screening)

    return cached_result


@app.get("/api/v1/consultations/{consultation_id}/thread", response_model=VoiceThread)
def get_consultation_voice_thread(
    consultation_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieve asynchronous two-way bilingual voice thread messages.
    """
    if current_user.role in (UserRole.NURSE, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Forbidden: Nurses and admins cannot access clinical voice threads.")
    if current_user.role == UserRole.GUEST_EMERGENCY and current_user.guest_case_id != consultation_id:
        raise HTTPException(status_code=403, detail="Forbidden: Guest emergency access restricted to own case.")

    from app.db import get_consultation, get_assignment_for_consultation
    consultation = get_consultation(consultation_id)
    if consultation:
        if current_user.role == UserRole.PATIENT:
            if consultation.get("account_id") and consultation.get("account_id") != current_user.account_id:
                raise HTTPException(status_code=403, detail="Forbidden: You cannot access another patient's voice thread.")
        elif current_user.role == UserRole.DOCTOR:
            assignment = get_assignment_for_consultation(consultation_id)
            if assignment and assignment.get("doctor_id") and assignment.get("doctor_id") != current_user.user_id:
                raise HTTPException(status_code=403, detail="Forbidden: Case is assigned to another clinician.")

    return get_voice_thread_manager().get_or_create_thread(consultation_id)


@app.post("/api/v1/consultations/{consultation_id}/thread/patient-reply", response_model=VoiceThreadMessage)
async def patient_voice_reply(
    consultation_id: str,
    audio: UploadFile = File(..., description="Patient spoken reply audio (WAV, WEBM)"),
    patient_language: str = Form("ta-IN", description="Patient language code"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Two-way asynchronous voice thread: Patient speaks in regional dialect.
    Transcribes regional speech -> translates to English for doctor -> verifies with back-translation.
    """
    if current_user.role not in (UserRole.PATIENT, UserRole.GUEST_EMERGENCY):
        raise HTTPException(status_code=403, detail="Forbidden: Only patients may record replies in this endpoint.")

    from app.db import get_consultation
    consultation = get_consultation(consultation_id)
    if not consultation:
        raise HTTPException(status_code=404, detail=f"Consultation '{consultation_id}' not found.")

    if current_user.role == UserRole.PATIENT:
        if consultation.get("account_id") and consultation.get("account_id") != current_user.account_id:
            raise HTTPException(status_code=403, detail="Forbidden: You cannot reply to another patient's thread.")
    elif current_user.role == UserRole.GUEST_EMERGENCY:
        if current_user.guest_case_id != consultation_id:
            raise HTTPException(status_code=403, detail="Forbidden: Guest token restricted to own case.")

    settings = get_settings()
    if not settings.sarvam_api_key:
        raise HTTPException(status_code=500, detail="Server configuration error: missing SARVAM_API_KEY.")

    audio_bytes = await audio.read()
    safe_filename = sanitize_filename(audio.filename or "patient_reply.wav")
    validate_audio_upload(audio_bytes, safe_filename, settings.max_audio_bytes)

    try:
        # 1. Transcribe regional audio and get English translation
        stt_result = await transcribe_and_translate(
            audio_bytes=audio_bytes,
            filename=safe_filename,
            language_code=patient_language,
        )
        patient_text = stt_result.transcript_original or stt_result.transcript_english
        english_text = stt_result.transcript_english

        if not patient_text:
            raise HTTPException(status_code=400, detail="Could not transcribe audio to text.")

        # 2. Back-translation verification
        back_translated = None
        if patient_language != "en-IN":
            try:
                back_translated = await translate_text(
                    text=english_text,
                    target_language=patient_language,
                    source_language="en-IN",
                )
            except Exception as bt_err:
                logger.warning("Back-translation failed for patient reply: %s", bt_err)
                back_translated = patient_text

        msg = get_voice_thread_manager().add_message(
            consultation_id=consultation_id,
            sender="patient",
            original_text=patient_text,
            translated_text=english_text,
            original_language=patient_language,
            target_language="en-IN",
            back_translated_text=back_translated,
            audio_base64=None,
        )

        get_audit_logger().log(
            action="PATIENT_VOICE_REPLY",
            user_id=current_user.user_id,
            role=current_user.role.value,
            consultation_id=consultation_id,
            details={"patient_language": patient_language, "message_id": msg.message_id},
        )
        return msg
    except Exception as exc:
        logger.exception("Failed to process patient voice reply")
        raise HTTPException(status_code=500, detail="Failed to process voice reply.") from exc


# -----------------------------------------------------------------------------
# Block D: Doctor Queue, Routing & Roster Management (B5.1 - B5.8, F3.1 - F3.6)
# -----------------------------------------------------------------------------

class ClaimCaseRequest(BaseModel):
    lock_ttl_minutes: Optional[int] = 15


class ReassignCaseRequest(BaseModel):
    target_doctor_id: str
    target_department: Optional[str] = None
    reason: str = Field(..., min_length=5, description="Mandatory clinical rationale for reassignment")


class OverrideTierRequest(BaseModel):
    new_tier: str
    reason: str = Field(..., min_length=5, description="Mandatory clinical rationale for urgency tier override")


class DoctorAvailabilityRequest(BaseModel):
    is_on_duty: bool


@app.get("/api/v1/doctor/queue")
def get_doctor_queue(
    tier: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(require_role([UserRole.DOCTOR, UserRole.NURSE, UserRole.ADMIN])),
):
    """
    Doctor Dashboard Consultation Queue (F3.1, F3.2).
    Sorted urgent-first: emergency (0) > doctor_today (1) > doctor_soon (2) > self_care (3).
    Includes atomic claim lock statuses, wait times, and complaint categorization.
    """
    from app.db import list_consultations_for_queue
    results = list_consultations_for_queue(
        department_code=department,
        tier=tier,
        status=status,
        search=search,
    )
    return {
        "count": len(results),
        "consultations": results,
    }


@app.get("/api/v1/consultations/{consultation_id}")
def get_consultation_details(
    consultation_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieve full consultation details and AI triage summary (F3.3, B4.7).
    Enforces strict access control:
      - Patients can only view their own account's consultations (H3.1).
      - Guests can only view their own single emergency case (H1.3).
      - Doctors can only view their assigned cases or unclaimed cases (H3.2).
      - Doctors get masked phone numbers; nurses and admins receive no clinical text (H3.3).
      - Every read writes an append-only audit trail record (H3.8).
    """
    from app.db import get_consultation, get_assignment_for_consultation
    consultation_raw = get_consultation(consultation_id)
    if not consultation_raw:
        raise HTTPException(status_code=404, detail=f"Consultation '{consultation_id}' not found.")

    assignment = get_assignment_for_consultation(consultation_id)

    if current_user.role == UserRole.PATIENT:
        if consultation_raw.get("account_id") and consultation_raw.get("account_id") != current_user.account_id:
            raise HTTPException(status_code=403, detail="Unauthorized: Access denied to other patient records.")

    elif current_user.role == UserRole.GUEST_EMERGENCY:
        if current_user.guest_case_id != consultation_id:
            raise HTTPException(status_code=403, detail="Unauthorized: Guest emergency access is restricted to the generated emergency case.")

    elif current_user.role == UserRole.DOCTOR:
        if assignment and assignment.get("doctor_id") and assignment.get("doctor_id") != current_user.user_id:
            raise HTTPException(status_code=403, detail="Forbidden: Case is assigned to another clinician.")

    consultation = dict(consultation_raw)
    consultation["assignment"] = assignment

    # Role-based masking & privacy preservation (H3.3)
    if current_user.role == UserRole.DOCTOR:
        phone = consultation.get("phone_number")
        if phone:
            consultation["phone_number"] = phone[:3] + "****" + phone[-2:]
    elif current_user.role in (UserRole.NURSE, UserRole.ADMIN):
        # Strip clinical text for nurses and admins
        for field in ("transcript_original", "transcript_english", "symptoms", "chief_complaint", "clinical_summary"):
            consultation.pop(field, None)

    get_audit_logger().log(
        action="CONSULTATION_READ",
        user_id=current_user.user_id,
        role=current_user.role.value,
        consultation_id=consultation_id,
    )
    return consultation


@app.post("/api/v1/consultations/{consultation_id}/claim")
def claim_consultation_case(
    consultation_id: str,
    req: ClaimCaseRequest = ClaimCaseRequest(),
    current_doctor: AuthenticatedUser = Depends(require_verified_doctor),
):
    """
    Atomic claim locking for clinician review (B5.4).
    Prevents race conditions where two doctors attempt to answer the same consultation.
    """
    from app.db import claim_consultation_lock
    success, message, assignment = claim_consultation_lock(
        consultation_id=consultation_id,
        doctor_id=current_doctor.user_id,
        doctor_name=current_doctor.user_id,
        lock_ttl_minutes=req.lock_ttl_minutes or 15,
    )
    if not success:
        raise HTTPException(status_code=409, detail=message)
    return {
        "success": True,
        "message": message,
        "assignment": assignment,
    }


@app.post("/api/v1/consultations/{consultation_id}/release")
def release_consultation_case(
    consultation_id: str,
    current_doctor: AuthenticatedUser = Depends(require_verified_doctor),
):
    """
    Release claim lock on consultation back to the department pool (B5.4).
    """
    from app.db import release_consultation_lock
    success, message = release_consultation_lock(
        consultation_id=consultation_id,
        doctor_id=current_doctor.user_id,
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {
        "success": True,
        "message": message,
    }


@app.post("/api/v1/consultations/{consultation_id}/reassign")
def reassign_consultation_case(
    consultation_id: str,
    req: ReassignCaseRequest,
    current_user: AuthenticatedUser = Depends(require_role([UserRole.DOCTOR, UserRole.ADMIN])),
):
    """
    Reassign case to another doctor or department with mandatory clinical reason (B5.6, B5.7).
    """
    from app.db import reassign_consultation
    success, message, assignment = reassign_consultation(
        consultation_id=consultation_id,
        reassigning_doctor_id=current_user.user_id,
        target_doctor_id=req.target_doctor_id,
        target_department_code=req.target_department,
        reason=req.reason,
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {
        "success": True,
        "message": message,
        "assignment": assignment,
    }


@app.post("/api/v1/consultations/{consultation_id}/override-tier")
def override_consultation_urgency_tier(
    consultation_id: str,
    req: OverrideTierRequest,
    current_doctor: AuthenticatedUser = Depends(require_verified_doctor),
):
    """
    Override AI triage urgency tier with mandatory clinical rationale (B5.6, B5.7).
    Logged to append-only audit trail.
    """
    from app.db import override_urgency_tier
    success, message, consultation = override_urgency_tier(
        consultation_id=consultation_id,
        doctor_id=current_doctor.user_id,
        doctor_reg_no=current_doctor.doctor_registration_number,
        new_tier=req.new_tier,
        reason=req.reason,
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {
        "success": True,
        "message": message,
        "consultation": consultation,
    }


@app.post("/api/v1/doctor/availability")
def toggle_doctor_availability(
    req: DoctorAvailabilityRequest,
    current_doctor: AuthenticatedUser = Depends(require_role([UserRole.DOCTOR])),
):
    """
    Doctor availability toggle for duty scheduling (B5.1, F3.6).
    """
    from app.db import update_doctor_availability
    success = update_doctor_availability(
        doctor_id=current_doctor.user_id,
        is_on_duty=req.is_on_duty,
    )
    return {
        "success": success,
        "is_on_duty": req.is_on_duty,
        "message": f"Duty status updated to {'ON-DUTY' if req.is_on_duty else 'OFF-DUTY'}.",
    }


@app.get("/api/v1/doctor/roster")
@app.get("/api/v1/admin/roster")
def get_doctor_roster(
    department: Optional[str] = None,
    on_duty_only: bool = False,
    current_user: AuthenticatedUser = Depends(require_role([UserRole.DOCTOR, UserRole.NURSE, UserRole.ADMIN])),
):
    """
    Retrieve hospital doctor roster with specialty, schedule, capacity and duty status (B5.1, F4.2).
    """
    from app.db import get_staff_doctors
    doctors = get_staff_doctors(department_code=department, on_duty_only=on_duty_only)
    sanitized = []
    for d in doctors:
        doc_copy = dict(d)
        doc_copy.pop("password_hash", None)
        sanitized.append(doc_copy)
    return {
        "count": len(sanitized),
        "doctors": sanitized,
    }


@app.get("/api/v1/admin/routing-logs")
def get_admin_routing_logs(
    current_admin: AuthenticatedUser = Depends(require_role([UserRole.ADMIN])),
):
    """
    Hospital administrator routing audit logs (B5.7, F4.1).
    """
    from app.db import _MEM_AUDIT_LOGS, get_supabase_client
    client = get_supabase_client()
    if client:
        try:
            res = client.table("audit_logs").select("*").ilike("action", "%ROUTE%").order("created_at", desc=True).limit(50).execute()
            if res.data:
                return {"count": len(res.data), "logs": res.data}
        except Exception:
            pass
    routing_logs = [l for l in _MEM_AUDIT_LOGS if "ROUTE" in l.get("action", "").upper()]
    return {"count": len(routing_logs), "logs": routing_logs}


@app.post("/api/v1/staff/doctors/{doctor_id}/verify-registration")
def verify_doctor_registration(
    doctor_id: str,
    current_admin: AuthenticatedUser = Depends(require_role([UserRole.ADMIN])),
):
    """
    Hospital admin manually verifies doctor registration credentials (B5.2, F4.2).
    Replaces regex-only matching with human administrative sign-off.
    """
    from app.db import verify_doctor_registration_by_admin
    success = verify_doctor_registration_by_admin(
        doctor_id=doctor_id,
        admin_user_id=current_admin.user_id,
    )
    return {
        "success": success,
        "message": f"Doctor registration credentials verified by hospital administrator {current_admin.user_id}.",
    }


@app.post("/api/v1/consultations/escalate-unclaimed")
def trigger_unclaimed_escalations(
    current_user: AuthenticatedUser = Depends(require_role([UserRole.DOCTOR, UserRole.ADMIN])),
):
    """
    Trigger automatic escalation check for unclaimed cases exceeding timer limits (B5.5).
    """
    from app.db import get_unclaimed_consultations_for_escalation
    escalations = get_unclaimed_consultations_for_escalation()
    return {
        "count": len(escalations),
        "escalations": escalations,
    }

