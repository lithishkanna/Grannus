"""
Database persistence and multi-tenancy layer for Grannus RuralCare AI.

Provides persistent access to:
  - Hospitals & Departments (Multi-tenancy)
  - Phone Accounts & OTP Verification (B2.2)
  - Patient Profiles (Multi-profile per phone B4.1)
  - Staff Users (Doctors, Nurses, Admins B2.3)
  - Pipeline Jobs (Persistent job queue B3.1)
  - Voice Threads (Persistent 2-way threads B3.1)
  - Follow-up Records (Persistent check-ins B3.1)
  - Audit Log (Append-only security log B3.5)
"""
import os
import hmac
import hashlib
import logging
import random
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple

from app.config import get_settings

logger = logging.getLogger("rural_care.db")

_supabase_client = None


def get_supabase_client():
    """Lazy initialize Supabase client if configured."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    settings = get_settings()
    if settings.supabase_url and settings.supabase_anon_key:
        try:
            from supabase import create_client, Client
            _supabase_client = create_client(settings.supabase_url, settings.supabase_anon_key)
            logger.info("Supabase client initialized successfully")
        except Exception as exc:
            logger.warning("Could not initialize Supabase client: %s. Using in-memory fallback store.", exc)
            _supabase_client = None
    return _supabase_client


# -----------------------------------------------------------------------------
# In-Memory Fallback Stores (used if DB connection fails or during unit tests)
# -----------------------------------------------------------------------------
_MEM_HOSPITALS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "District Hospital Rural Outreach",
        "code": "DHRO-01",
        "location": "Tamil Nadu, India",
        "emergency_phone": "108",
    }
]

_MEM_DEPARTMENTS = [
    {"id": "d1", "hospital_id": "11111111-1111-1111-1111-111111111111", "name": "Emergency Medicine", "code": "EMERGENCY"},
    {"id": "d2", "hospital_id": "11111111-1111-1111-1111-111111111111", "name": "General Medicine", "code": "GEN_MED"},
    {"id": "d3", "hospital_id": "11111111-1111-1111-1111-111111111111", "name": "Pediatrics", "code": "PEDIATRICS"},
    {"id": "d4", "hospital_id": "11111111-1111-1111-1111-111111111111", "name": "Obstetrics & Gynecology", "code": "OBGYN"},
    {"id": "d5", "hospital_id": "11111111-1111-1111-1111-111111111111", "name": "Cardiology", "code": "CARDIOLOGY"},
]

_MEM_ACCOUNTS: Dict[str, dict] = {}
_MEM_OTPS: Dict[str, list] = {}
_MEM_PROFILES: Dict[str, dict] = {}
_MEM_STAFF: Dict[str, dict] = {}
_MEM_JOBS: Dict[str, dict] = {}
_MEM_THREADS: Dict[str, dict] = {}
_MEM_FOLLOW_UPS: Dict[str, dict] = {}
_MEM_CONSULTATIONS: Dict[str, dict] = {}
_MEM_ASSIGNMENTS: Dict[str, dict] = {}
_MEM_AUDIT_LOGS: List[dict] = []

# Rate limiter for OTP requests: phone -> timestamp
_OTP_COOLDOWNS: Dict[str, float] = {}


# -----------------------------------------------------------------------------
# Password & OTP Cryptographic Hashing
# -----------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash password with PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}:{dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against stored PBKDF2 hash."""
    try:
        parts = hashed.split(":")
        if len(parts) != 2:
            return False
        salt = bytes.fromhex(parts[0])
        expected_dk = bytes.fromhex(parts[1])
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(dk, expected_dk)
    except Exception:
        return False


def _hash_otp(otp_code: str, salt: str = "grannus_otp_salt_2026") -> str:
    return hashlib.sha256(f"{otp_code}:{salt}".encode("utf-8")).hexdigest()


def _safe_uuid_or_none(val: Any) -> Optional[str]:
    if not val:
        return None
    val_str = str(val).strip()
    try:
        uuid.UUID(val_str)
        return val_str
    except (ValueError, AttributeError):
        return None


# -----------------------------------------------------------------------------
# Hospital & Department Operations (B3.2)
# -----------------------------------------------------------------------------
def get_hospitals() -> List[dict]:
    client = get_supabase_client()
    if client:
        try:
            res = client.table("hospitals").select("*").execute()
            if res.data:
                return res.data
        except Exception as exc:
            logger.error("Supabase get_hospitals error: %s", exc)
    return _MEM_HOSPITALS


def get_departments(hospital_id: Optional[str] = None) -> List[dict]:
    client = get_supabase_client()
    if client:
        try:
            query = client.table("departments").select("*")
            if hospital_id:
                query = query.eq("hospital_id", hospital_id)
            res = query.execute()
            if res.data:
                return res.data
        except Exception as exc:
            logger.error("Supabase get_departments error: %s", exc)
    if hospital_id:
        return [d for d in _MEM_DEPARTMENTS if d["hospital_id"] == hospital_id]
    return _MEM_DEPARTMENTS


# -----------------------------------------------------------------------------
# Patient Account & Phone OTP (B2.2, B4.1)
# -----------------------------------------------------------------------------
# Demo / Development test numbers that bypass external SMS network
DEV_TEST_NUMBERS = {
    "+919876543210": "123456",
    "+919999999999": "654321",
    "9876543210": "123456",
}


def normalize_phone(phone: str) -> str:
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    if not cleaned.startswith("+"):
        if len(cleaned) == 10:
            cleaned = f"+91{cleaned}"
        elif cleaned.startswith("91") and len(cleaned) == 12:
            cleaned = f"+{cleaned}"
    return cleaned


def request_phone_otp(phone: str) -> Tuple[bool, str, Optional[str]]:
    """
    Generate 6-digit OTP for patient phone login.
    Enforces 60-second resend cooldown and 5-minute expiration.
    Returns: (success, message, dev_otp_hint_if_dev)
    """
    phone_norm = normalize_phone(phone)
    now = time.time()

    # Cooldown check
    last_req = _OTP_COOLDOWNS.get(phone_norm, 0)
    if now - last_req < 60:
        remaining = int(60 - (now - last_req))
        return False, f"Please wait {remaining} seconds before requesting a new code.", None

    _OTP_COOLDOWNS[phone_norm] = now

    # Determine OTP code
    if phone_norm in DEV_TEST_NUMBERS or phone in DEV_TEST_NUMBERS:
        otp_code = DEV_TEST_NUMBERS.get(phone_norm) or DEV_TEST_NUMBERS.get(phone)
    else:
        otp_code = f"{random.randint(100000, 999999):06d}"

    otp_hash = _hash_otp(otp_code)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    otp_id = str(uuid.uuid4())

    record = {
        "id": otp_id,
        "phone_number": phone_norm,
        "otp_hash": otp_hash,
        "attempts": 0,
        "max_attempts": 5,
        "expires_at": expires_at.isoformat(),
        "is_used": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    client = get_supabase_client()
    if client:
        try:
            client.table("otp_verifications").insert(record).execute()
        except Exception as exc:
            logger.error("Supabase insert OTP error: %s", exc)

    # In-memory record
    if phone_norm not in _MEM_OTPS:
        _MEM_OTPS[phone_norm] = []
    _MEM_OTPS[phone_norm].append(record)

    # Dev hint only provided in development/test
    dev_hint = otp_code if (phone_norm in DEV_TEST_NUMBERS or phone in DEV_TEST_NUMBERS or os.getenv("ENV") != "production") else None

    logger.info("OTP requested for patient phone=%s (expires in 5m)", phone_norm[:5] + "****" + phone_norm[-2:])
    return True, "Verification code sent to your phone.", dev_hint


def verify_phone_otp(phone: str, otp_code: str) -> Tuple[bool, str, Optional[dict]]:
    """
    Verify single-use phone OTP.
    Max 5 attempts, expires in 5 minutes.
    Returns: (success, message, account_dict)
    """
    phone_norm = normalize_phone(phone)
    code_clean = otp_code.strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    client = get_supabase_client()
    latest_record = None

    if client:
        try:
            res = (
                client.table("otp_verifications")
                .select("*")
                .eq("phone_number", phone_norm)
                .eq("is_used", False)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if res.data:
                latest_record = res.data[0]
        except Exception as exc:
            logger.error("Supabase get OTP error: %s", exc)

    if not latest_record:
        user_otps = _MEM_OTPS.get(phone_norm, [])
        for r in reversed(user_otps):
            if not r["is_used"]:
                latest_record = r
                break

    if not latest_record:
        return False, "No active verification code found. Please request a new code.", None

    if latest_record["attempts"] >= latest_record.get("max_attempts", 5):
        return False, "Maximum verification attempts exceeded. Please request a new code.", None

    if latest_record["expires_at"] < now_iso:
        return False, "Verification code has expired. Please request a new code.", None

    # Check hash
    expected_hash = latest_record["otp_hash"]
    given_hash = _hash_otp(code_clean)

    if not hmac.compare_digest(given_hash, expected_hash):
        latest_record["attempts"] += 1
        for r in _MEM_OTPS.get(phone_norm, []):
            if r.get("id") == latest_record.get("id"):
                r["attempts"] = latest_record["attempts"]
        if client:
            try:
                client.table("otp_verifications").update({"attempts": latest_record["attempts"]}).eq("id", latest_record["id"]).execute()
            except Exception:
                pass
        remaining = latest_record["max_attempts"] - latest_record["attempts"]
        return False, f"Invalid verification code. {remaining} attempts remaining.", None

    # Success: Mark used
    latest_record["is_used"] = True
    for r in _MEM_OTPS.get(phone_norm, []):
        if r.get("id") == latest_record.get("id"):
            r["is_used"] = True
    if client:
        try:
            client.table("otp_verifications").update({"is_used": True}).eq("id", latest_record["id"]).execute()
        except Exception:
            pass

    # Get or create account
    account = _get_or_create_account_db(phone_norm)
    return True, "Phone number verified successfully.", account


def _get_or_create_account_db(phone_norm: str) -> dict:
    client = get_supabase_client()
    if client:
        try:
            res = client.table("accounts").select("*").eq("phone_number", phone_norm).execute()
            if res.data:
                return res.data[0]
            new_acc = {
                "id": str(uuid.uuid4()),
                "phone_number": phone_norm,
                "is_verified": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            ins = client.table("accounts").insert(new_acc).execute()
            if ins.data:
                return ins.data[0]
        except Exception as exc:
            logger.error("Supabase account error: %s", exc)

    if phone_norm in _MEM_ACCOUNTS:
        return _MEM_ACCOUNTS[phone_norm]

    new_acc = {
        "id": str(uuid.uuid4()),
        "phone_number": phone_norm,
        "is_verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _MEM_ACCOUNTS[phone_norm] = new_acc
    return new_acc


# -----------------------------------------------------------------------------
# Patient Profiles (B4.1 - Multi-profile per phone account)
# -----------------------------------------------------------------------------
def get_profiles_for_account(account_id: str) -> List[dict]:
    client = get_supabase_client()
    if client:
        try:
            res = client.table("patient_profiles").select("*").eq("account_id", account_id).execute()
            if res.data:
                return res.data
        except Exception as exc:
            logger.error("Supabase get_profiles error: %s", exc)
    return [p for p in _MEM_PROFILES.values() if p.get("account_id") == account_id]


def create_patient_profile(account_id: str, profile_data: dict) -> dict:
    profile_id = profile_data.get("id") or str(uuid.uuid4())
    record = {
        "id": profile_id,
        "account_id": account_id,
        "hospital_id": profile_data.get("hospital_id"),
        "full_name": profile_data.get("full_name", "Family Member"),
        "age": str(profile_data.get("age", "")),
        "gender": profile_data.get("gender", ""),
        "relation": profile_data.get("relation", "self"),
        "preferred_language": profile_data.get("preferred_language", "ta-IN"),
        "allergies": profile_data.get("allergies", []),
        "medications": profile_data.get("medications", []),
        "known_conditions": profile_data.get("known_conditions", []),
        "pin_hash": profile_data.get("pin_hash"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    client = get_supabase_client()
    if client:
        try:
            res = client.table("patient_profiles").insert(record).execute()
            if res.data:
                return res.data[0]
        except Exception as exc:
            logger.error("Supabase create_profile error: %s", exc)

    _MEM_PROFILES[profile_id] = record
    return record


def get_patient_profile(profile_id: str) -> Optional[dict]:
    client = get_supabase_client()
    if client:
        try:
            res = client.table("patient_profiles").select("*").eq("id", profile_id).execute()
            if res.data:
                return res.data[0]
        except Exception as exc:
            logger.error("Supabase get_profile error: %s", exc)
    return _MEM_PROFILES.get(profile_id)


# -----------------------------------------------------------------------------
# Staff Authentication (B2.3 - Doctors, Nurses, Admins)
# -----------------------------------------------------------------------------
# Seed fallback staff credentials (8 doctors B5.1 + admin + nurse)
_FALLBACK_STAFF = {
    "dr.rajan@hospital.in": {
        "id": "11111111-0001-0000-0000-000000000001",
        "email": "dr.rajan@hospital.in",
        "password_hash": hash_password("grannus_secure_doctor_2026"),
        "role": "doctor",
        "full_name": "Dr. Rajan K., MD",
        "doctor_registration_number": "TNMC-48291",
        "state_council": "Tamil Nadu Medical Council",
        "specialty": "General Medicine",
        "department_code": "GEN_MED",
        "languages": ["ta", "en", "hi"],
        "is_active": True,
        "is_on_duty": True,
        "active_case_load": 0,
        "max_capacity": 20,
        "weekly_schedule": {"mon_fri": "09:00-17:00", "sat": "09:00-13:00"},
        "is_verified_doctor": True,
    },
    "dr.priya@hospital.in": {
        "id": "11111111-0002-0000-0000-000000000002",
        "email": "dr.priya@hospital.in",
        "password_hash": hash_password("grannus_secure_doctor_2026"),
        "role": "doctor",
        "full_name": "Dr. Priya Sundaram, DM",
        "doctor_registration_number": "TNMC-54321",
        "state_council": "Tamil Nadu Medical Council",
        "specialty": "Cardiology",
        "department_code": "CARDIOLOGY",
        "languages": ["ta", "en"],
        "is_active": True,
        "is_on_duty": True,
        "active_case_load": 0,
        "max_capacity": 10,
        "weekly_schedule": {"mon_fri": "08:00-16:00"},
        "is_verified_doctor": True,
    },
    "dr.vikram@hospital.in": {
        "id": "11111111-0003-0000-0000-000000000003",
        "email": "dr.vikram@hospital.in",
        "password_hash": hash_password("grannus_secure_doctor_2026"),
        "role": "doctor",
        "full_name": "Dr. Vikram Patel, MD",
        "doctor_registration_number": "GMC-39104",
        "state_council": "Gujarat Medical Council",
        "specialty": "Pediatrics",
        "department_code": "PEDIATRICS",
        "languages": ["hi", "en", "te"],
        "is_active": True,
        "is_on_duty": True,
        "active_case_load": 0,
        "max_capacity": 15,
        "weekly_schedule": {"mon_sat": "10:00-18:00"},
        "is_verified_doctor": True,
    },
    "dr.shalini@hospital.in": {
        "id": "11111111-0004-0000-0000-000000000004",
        "email": "dr.shalini@hospital.in",
        "password_hash": hash_password("grannus_secure_doctor_2026"),
        "role": "doctor",
        "full_name": "Dr. Shalini Reddy, MD",
        "doctor_registration_number": "APMC-28491",
        "state_council": "Andhra Pradesh Medical Council",
        "specialty": "Dermatology",
        "department_code": "GEN_MED",
        "languages": ["te", "en"],
        "is_active": True,
        "is_on_duty": True,
        "active_case_load": 0,
        "max_capacity": 15,
        "weekly_schedule": {"tue_sat": "09:00-17:00"},
        "is_verified_doctor": True,
    },
    "dr.meenakshi@hospital.in": {
        "id": "11111111-0005-0000-0000-000000000005",
        "email": "dr.meenakshi@hospital.in",
        "password_hash": hash_password("grannus_secure_doctor_2026"),
        "role": "doctor",
        "full_name": "Dr. Meenakshi Iyer, MS",
        "doctor_registration_number": "TNMC-61245",
        "state_council": "Tamil Nadu Medical Council",
        "specialty": "Obstetrics & Gynecology",
        "department_code": "OBGYN",
        "languages": ["ta", "en"],
        "is_active": True,
        "is_on_duty": True,
        "active_case_load": 0,
        "max_capacity": 12,
        "weekly_schedule": {"mon_fri": "09:00-17:00"},
        "is_verified_doctor": True,
    },
    "dr.arvind@hospital.in": {
        "id": "11111111-0006-0000-0000-000000000006",
        "email": "dr.arvind@hospital.in",
        "password_hash": hash_password("grannus_secure_doctor_2026"),
        "role": "doctor",
        "full_name": "Dr. Arvind Kumar, MS",
        "doctor_registration_number": "DMC-50123",
        "state_council": "Delhi Medical Council",
        "specialty": "Orthopaedics",
        "department_code": "GEN_MED",
        "languages": ["hi", "ta", "en"],
        "is_active": True,
        "is_on_duty": True,
        "active_case_load": 0,
        "max_capacity": 15,
        "weekly_schedule": {"mon_fri": "10:00-18:00"},
        "is_verified_doctor": True,
    },
    "dr.suresh@hospital.in": {
        "id": "11111111-0007-0000-0000-000000000007",
        "email": "dr.suresh@hospital.in",
        "password_hash": hash_password("grannus_secure_doctor_2026"),
        "role": "doctor",
        "full_name": "Dr. Suresh Varma, MS",
        "doctor_registration_number": "TSMC-33109",
        "state_council": "Telangana State Medical Council",
        "specialty": "ENT",
        "department_code": "GEN_MED",
        "languages": ["te", "ta", "en"],
        "is_active": True,
        "is_on_duty": True,
        "active_case_load": 0,
        "max_capacity": 15,
        "weekly_schedule": {"mon_fri": "09:00-17:00"},
        "is_verified_doctor": True,
    },
    "dr.harish@hospital.in": {
        "id": "11111111-0008-0000-0000-000000000008",
        "email": "dr.harish@hospital.in",
        "password_hash": hash_password("grannus_secure_doctor_2026"),
        "role": "doctor",
        "full_name": "Dr. Harish Naidu, MBBS",
        "doctor_registration_number": "TNMC-72019",
        "state_council": "Tamil Nadu Medical Council",
        "specialty": "Emergency & Acute Care",
        "department_code": "EMERGENCY",
        "languages": ["ta", "hi", "te", "en"],
        "is_active": True,
        "is_on_duty": True,
        "active_case_load": 0,
        "max_capacity": 25,
        "weekly_schedule": {"all_week": "24_hours"},
        "is_verified_doctor": True,
    },
    "dr_clinician": {
        "id": "doc_clinician_002",
        "email": "dr.rajan@hospital.in",
        "password_hash": hash_password("grannus_secure_doctor_2026"),
        "role": "doctor",
        "full_name": "Dr. Rajan K., MD",
        "doctor_registration_number": "TNMC-48291",
        "state_council": "Tamil Nadu Medical Council",
        "specialty": "General Medicine",
        "department_code": "GEN_MED",
        "languages": ["ta", "en", "hi"],
        "is_active": True,
        "is_on_duty": True,
        "active_case_load": 0,
        "max_capacity": 20,
        "weekly_schedule": {"mon_fri": "09:00-17:00"},
        "is_verified_doctor": True,
    },
    "admin@hospital.in": {
        "id": "admin_sys_001",
        "email": "admin@hospital.in",
        "password_hash": hash_password("grannus_admin_2026"),
        "role": "admin",
        "full_name": "Medical Superintendent",
        "is_active": True,
        "is_on_duty": True,
    },
    "nurse.mary@hospital.in": {
        "id": "nurse_mary_001",
        "email": "nurse.mary@hospital.in",
        "password_hash": hash_password("grannus_nurse_2026"),
        "role": "nurse",
        "full_name": "Staff Nurse Deepa R.",
        "is_active": True,
        "is_on_duty": True,
    },
}


def find_staff_user(email: str) -> Optional[dict]:
    """Find staff user record by email or identifier."""
    email_clean = email.strip().lower()
    client = get_supabase_client()
    if client:
        try:
            res = client.table("staff_users").select("*").eq("email", email_clean).execute()
            if res.data:
                return res.data[0]
        except Exception:
            pass

    for user_key, user in _FALLBACK_STAFF.items():
        if user["email"].lower() == email_clean or user_key.lower() == email_clean:
            return user
    return None


def authenticate_staff_user(email: str, password: str) -> Optional[dict]:
    """Verify staff login with email and password."""
    email_clean = email.strip().lower()

    client = get_supabase_client()
    if client:
        try:
            res = client.table("staff_users").select("*").eq("email", email_clean).eq("is_active", True).execute()
            if res.data:
                user = res.data[0]
                if verify_password(password, user["password_hash"]):
                    return user
        except Exception as exc:
            logger.error("Supabase staff auth error: %s", exc)

    # Check fallback / seed in-memory users
    for user_key, user in _FALLBACK_STAFF.items():
        if user["email"].lower() == email_clean or user_key.lower() == email_clean:
            if verify_password(password, user["password_hash"]):
                return user

    return None


# -----------------------------------------------------------------------------
# Persistent Pipeline Jobs (B3.1)
# -----------------------------------------------------------------------------
def save_pipeline_job(job_id: str, job_data: dict) -> dict:
    record = {
        "id": job_id,
        "hospital_id": job_data.get("hospital_id"),
        "account_id": job_data.get("account_id"),
        "profile_id": job_data.get("profile_id"),
        "status": job_data.get("status", "QUEUED"),
        "stage": job_data.get("stage", "QUEUED"),
        "progress": job_data.get("progress", 0),
        "message": job_data.get("message", ""),
        "result": job_data.get("result"),
        "error_message": job_data.get("error_message"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client = get_supabase_client()
    if client:
        try:
            client.table("pipeline_jobs").upsert(record).execute()
        except Exception as exc:
            logger.error("Supabase save_job error: %s", exc)

    _MEM_JOBS[job_id] = record
    return record


def get_pipeline_job(job_id: str) -> Optional[dict]:
    client = get_supabase_client()
    if client:
        try:
            res = client.table("pipeline_jobs").select("*").eq("id", job_id).execute()
            if res.data:
                return res.data[0]
        except Exception as exc:
            logger.error("Supabase get_job error: %s", exc)
    return _MEM_JOBS.get(job_id)


# -----------------------------------------------------------------------------
# Persistent Voice Threads (B3.1)
# -----------------------------------------------------------------------------
def save_voice_thread(thread_id: str, thread_data: dict) -> dict:
    record = {
        "id": thread_id,
        "consultation_id": thread_data.get("consultation_id"),
        "hospital_id": thread_data.get("hospital_id"),
        "patient_profile_id": thread_data.get("patient_profile_id"),
        "doctor_id": thread_data.get("doctor_id"),
        "status": thread_data.get("status", "open"),
        "messages": thread_data.get("messages", []),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client = get_supabase_client()
    if client:
        try:
            client.table("persistent_voice_threads").upsert(record).execute()
        except Exception as exc:
            logger.error("Supabase save_thread error: %s", exc)

    _MEM_THREADS[thread_id] = record
    return record


def get_voice_thread(thread_id: str) -> Optional[dict]:
    client = get_supabase_client()
    if client:
        try:
            res = client.table("persistent_voice_threads").select("*").eq("id", thread_id).execute()
            if res.data:
                return res.data[0]
        except Exception as exc:
            logger.error("Supabase get_thread error: %s", exc)
    return _MEM_THREADS.get(thread_id)


# -----------------------------------------------------------------------------
# Persistent Follow-ups (B3.1, B6.5)
# -----------------------------------------------------------------------------
def save_follow_up_record(follow_up_id: str, data: dict) -> dict:
    record = {
        "id": follow_up_id,
        "consultation_id": data.get("consultation_id"),
        "hospital_id": data.get("hospital_id"),
        "profile_id": data.get("profile_id"),
        "urgency_tier": data.get("urgency_tier", "self_care"),
        "scheduled_for": data.get("scheduled_for", datetime.now(timezone.utc).isoformat()),
        "status": data.get("status", "PENDING"),
        "patient_status": data.get("patient_status"),
        "patient_feedback": data.get("patient_feedback"),
        "checked_in_at": data.get("checked_in_at"),
        "created_at": data.get("created_at", datetime.now(timezone.utc).isoformat()),
    }
    client = get_supabase_client()
    if client:
        try:
            client.table("persistent_follow_ups").upsert(record).execute()
        except Exception as exc:
            logger.error("Supabase save_follow_up error: %s", exc)

    _MEM_FOLLOW_UPS[follow_up_id] = record
    return record


def get_follow_up_record(follow_up_id: str) -> Optional[dict]:
    client = get_supabase_client()
    if client:
        try:
            res = client.table("persistent_follow_ups").select("*").eq("id", follow_up_id).execute()
            if res.data:
                return res.data[0]
        except Exception as exc:
            logger.error("Supabase get_follow_up error: %s", exc)
    return _MEM_FOLLOW_UPS.get(follow_up_id)


# -----------------------------------------------------------------------------
# Append-Only Audit Logging (B3.5)
# -----------------------------------------------------------------------------
def append_audit_log_entry(
    action: str,
    user_id: str,
    role: str,
    hospital_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> dict:
    record = {
        "id": str(uuid.uuid4()),
        "hospital_id": hospital_id,
        "action": action,
        "user_id": user_id,
        "role": role,
        "resource_id": resource_id,
        "details": details or {},
        "ip_address": ip_address,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    client = get_supabase_client()
    if client:
        try:
            client.table("audit_logs").insert(record).execute()
        except Exception as exc:
            logger.error("Supabase audit log insert error: %s", exc)

    _MEM_AUDIT_LOGS.append(record)
    return record


# -----------------------------------------------------------------------------
# Block C: Consent, PIN, Data Export & Statutory Erasure (B4.3, B4.4, B4.5, B4.6)
# -----------------------------------------------------------------------------

_MEM_CONSENTS: List[dict] = []


def save_consent_record(data: dict) -> dict:
    """Save versioned patient consent record to database (B4.5)."""
    record = {
        "id": data.get("id") or str(uuid.uuid4()),
        "patient_id": data.get("patient_id"),
        "consent_type": data.get("consent_type", "TELEMEDICINE_TRIAGE"),
        "version": data.get("version", "2023.1-DPDP"),
        "language_code": data.get("language_code", "en-IN"),
        "ip_hash": data.get("ip_hash"),
        "profile_id": data.get("profile_id"),
        "is_granted": data.get("is_granted", True),
        "granted_at": data.get("granted_at") or datetime.now(timezone.utc).isoformat(),
    }
    client = get_supabase_client()
    if client:
        try:
            client.table("consents").insert(record).execute()
        except Exception as exc:
            logger.error("Supabase insert consent error: %s", exc)

    _MEM_CONSENTS.append(record)
    return record


def verify_profile_pin(profile_id: str, pin: str) -> bool:
    """Verify 4-digit PIN for private patient profile (B4.3)."""
    profile = get_patient_profile(profile_id)
    if not profile or not profile.get("pin_hash"):
        return True  # No PIN protection set
    return verify_password(pin.strip(), profile["pin_hash"])


def export_account_data(account_id: str) -> dict:
    """Export all profiles, consultations, follow-ups, and consents for an account (B4.6)."""
    profiles = get_profiles_for_account(account_id)
    profile_ids = [p["id"] for p in profiles]

    consultations: List[dict] = []
    follow_ups: List[dict] = []
    consents: List[dict] = []

    client = get_supabase_client()
    if client and profile_ids:
        try:
            res_c = client.table("consultations").select("*").in_("profile_id", profile_ids).execute()
            if res_c.data:
                consultations = res_c.data
        except Exception:
            pass

        try:
            res_fu = client.table("persistent_follow_ups").select("*").in_("profile_id", profile_ids).execute()
            if res_fu.data:
                follow_ups = res_fu.data
        except Exception:
            pass

    if not follow_ups:
        follow_ups = [fu for fu in _MEM_FOLLOW_UPS.values() if fu.get("profile_id") in profile_ids]

    consents = [c for c in _MEM_CONSENTS if c.get("profile_id") in profile_ids or c.get("patient_id") == account_id]

    return {
        "account_id": account_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profiles": profiles,
        "consultations": consultations,
        "follow_ups": follow_ups,
        "consents": consents,
    }


def erase_account_data(account_id: str, reason: str = "Statutory erasure under DPDP Act 2023") -> bool:
    """Statutory erasure: anonymize profiles and remove clinical history (B4.6)."""
    profiles = get_profiles_for_account(account_id)
    client = get_supabase_client()

    for p in profiles:
        anonymized = {
            "full_name": "ANONYMIZED_PATIENT",
            "allergies": [],
            "medications": [],
            "known_conditions": [],
            "pin_hash": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if client:
            try:
                client.table("patient_profiles").update(anonymized).eq("id", p["id"]).execute()
            except Exception:
                pass
        if p["id"] in _MEM_PROFILES:
            _MEM_PROFILES[p["id"]].update(anonymized)

    # Anonymize account
    if client:
        try:
            client.table("accounts").update({"is_active": False}).eq("id", account_id).execute()
        except Exception:
            pass

    append_audit_log_entry(
        action="DATA_ERASURE_COMPLETED",
        user_id=account_id,
        role="patient",
        resource_id=account_id,
        details={"reason": reason},
    )
    return True


def reset_recycled_phone_number(account_id: str) -> bool:
    """Disassociate all prior profiles from recycled phone number (B4.4)."""
    client = get_supabase_client()
    if client:
        try:
            client.table("patient_profiles").delete().eq("account_id", account_id).execute()
        except Exception:
            pass

    # In-memory reset
    to_delete = [pid for pid, p in _MEM_PROFILES.items() if p.get("account_id") == account_id]
    for pid in to_delete:
        del _MEM_PROFILES[pid]

    append_audit_log_entry(
        action="RECYCLED_NUMBER_RESET",
        user_id=account_id,
        role="patient",
        resource_id=account_id,
        details={"message": "All prior profiles cleared for recycled phone number."},
    )
    return True


# -----------------------------------------------------------------------------
# Consultations & Queue Management (B3.1, B5.1 - B5.8, F1.1)
# -----------------------------------------------------------------------------
TIER_PRIORITY_ORDER = {
    "emergency": 0,
    "doctor_today": 1,
    "doctor_soon": 2,
    "self_care": 3,
}


def save_consultation(consultation_id: str, data: dict) -> dict:
    """Save consultation record with full triage results and department mapping (B3.1, B5.3)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "id": consultation_id,
        "hospital_id": data.get("hospital_id", "c5b971d1-fe39-40bf-a5cb-539f1a98059f"),
        "account_id": data.get("account_id"),
        "profile_id": data.get("profile_id"),
        "patient_id": data.get("patient_id"),
        "status": data.get("status", "triage"),
        "patient_language": data.get("patient_language", "en-IN"),
        "urgency_tier": data.get("urgency_tier", "doctor_soon"),
        "department_id": _safe_uuid_or_none(data.get("department_id")),
        "assigned_doctor_id": _safe_uuid_or_none(data.get("assigned_doctor_id")),
        "original_transcript": data.get("original_transcript", ""),
        "english_transcript": data.get("english_transcript", ""),
        "audio_url": data.get("audio_url", ""),
        "complaint_category": data.get("complaint_category"),
        "chief_complaint": data.get("chief_complaint"),
        "full_result": data.get("full_result"),
        "created_at": data.get("created_at", now_iso),
        "updated_at": now_iso,
    }

    client = get_supabase_client()
    if client:
        try:
            client.table("consultations").upsert(record).execute()
        except Exception as exc:
            logger.error("Supabase save_consultation error: %s", exc)

    _MEM_CONSULTATIONS[consultation_id] = record
    return record


def get_consultation(consultation_id: str) -> Optional[dict]:
    """Retrieve consultation record by ID."""
    client = get_supabase_client()
    if client:
        try:
            res = client.table("consultations").select("*").eq("id", consultation_id).execute()
            if res.data:
                return res.data[0]
        except Exception as exc:
            logger.error("Supabase get_consultation error: %s", exc)
    return _MEM_CONSULTATIONS.get(consultation_id)


def list_consultations_for_queue(
    department_code: Optional[str] = None,
    tier: Optional[str] = None,
    doctor_id: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> List[dict]:
    """
    List consultations for doctor dashboard queue, sorted urgent-first (F3.2).
    Emergency (0) -> Doctor Today (1) -> Doctor Soon (2) -> Self Care (3).
    """
    results: List[dict] = []
    client = get_supabase_client()
    if client:
        try:
            query = client.table("consultations").select("*")
            if status:
                query = query.eq("status", status)
            if tier and tier.lower() != "all":
                query = query.eq("urgency_tier", tier)
            if doctor_id:
                query = query.eq("assigned_doctor_id", doctor_id)
            res = query.order("created_at", desc=True).execute()
            if res.data:
                results = res.data
        except Exception as exc:
            logger.error("Supabase list_queue error: %s", exc)

    seen_ids = {c["id"] for c in results}
    for mem_c in _MEM_CONSULTATIONS.values():
        if mem_c.get("id") not in seen_ids:
            if status and mem_c.get("status") != status:
                continue
            if tier and tier.lower() != "all" and mem_c.get("urgency_tier") != tier:
                continue
            if doctor_id and mem_c.get("assigned_doctor_id") != doctor_id:
                continue
            results.append(mem_c)
            seen_ids.add(mem_c.get("id"))

    if search:
        q = search.lower()
        results = [
            c for c in results
            if q in (c.get("chief_complaint") or "").lower()
            or q in (c.get("patient_language") or "").lower()
            or q in (c.get("original_transcript") or "").lower()
            or q in (c.get("english_transcript") or "").lower()
        ]

    # Attach current assignment lock status for each case
    for c in results:
        cid = c["id"]
        assignment = get_assignment_for_consultation(cid)
        if assignment:
            c["assignment"] = assignment
            c["is_claimed"] = assignment.get("status") == "claimed"
            c["claimed_by_id"] = assignment.get("doctor_id")
            c["claimed_by_name"] = assignment.get("locked_by_name")
            c["lock_expires_at"] = assignment.get("lock_expires_at")
        else:
            c["assignment"] = None
            c["is_claimed"] = False
            c["claimed_by_id"] = None
            c["claimed_by_name"] = None
            c["lock_expires_at"] = None

    # Sort urgent-first: emergency (0) > doctor_today (1) > doctor_soon (2) > self_care (3)
    results.sort(
        key=lambda c: (
            TIER_PRIORITY_ORDER.get(c.get("urgency_tier", "self_care"), 4),
            c.get("created_at", "")
        )
    )
    return results


def save_assignment(
    consultation_id: str,
    doctor_id: str,
    assigned_by: str = "system",
    status: str = "assigned",
    reassignment_reason: Optional[str] = None,
    locked_by_name: Optional[str] = None,
    lock_ttl_minutes: int = 15,
) -> dict:
    """Save or update consultation doctor assignment (B5.3, B5.4)."""
    now = datetime.now(timezone.utc)
    lock_expires = (now + timedelta(minutes=lock_ttl_minutes)).isoformat() if status == "claimed" else None
    assignment_id = f"asgn_{consultation_id[:8]}_{int(time.time())}"
    rec = {
        "id": assignment_id,
        "consultation_id": consultation_id,
        "doctor_id": doctor_id,
        "assigned_by": assigned_by,
        "status": status,
        "reassignment_reason": reassignment_reason,
        "claimed_at": now.isoformat() if status == "claimed" else None,
        "released_at": None,
        "lock_expires_at": lock_expires,
        "locked_by_name": locked_by_name,
    }

    client = get_supabase_client()
    if client:
        try:
            client.table("consultation_assignments").insert(rec).execute()
        except Exception as exc:
            logger.error("Supabase save_assignment error: %s", exc)

    _MEM_ASSIGNMENTS[consultation_id] = rec
    return rec


def get_assignment_for_consultation(consultation_id: str) -> Optional[dict]:
    """Get active assignment for consultation."""
    client = get_supabase_client()
    if client:
        try:
            res = (
                client.table("consultation_assignments")
                .select("*")
                .eq("consultation_id", consultation_id)
                .order("claimed_at", desc=True)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
        except Exception as exc:
            logger.error("Supabase get_assignment error: %s", exc)
    return _MEM_ASSIGNMENTS.get(consultation_id)


def claim_consultation_lock(
    consultation_id: str,
    doctor_id: str,
    doctor_name: str,
    lock_ttl_minutes: int = 15,
) -> Tuple[bool, str, Optional[dict]]:
    """
    Atomic claim locking (B5.4) so two doctors cannot claim the same case.
    Prevents race condition and enforces active lock timeouts.
    """
    now = datetime.now(timezone.utc)
    assignment = get_assignment_for_consultation(consultation_id)

    if assignment and assignment.get("status") == "claimed":
        current_claimant = assignment.get("doctor_id")
        lock_expires_at_str = assignment.get("lock_expires_at")
        is_lock_active = True
        if lock_expires_at_str:
            try:
                exp_dt = datetime.fromisoformat(lock_expires_at_str)
                if exp_dt < now:
                    is_lock_active = False
            except Exception:
                pass

        if is_lock_active and current_claimant != doctor_id:
            claimant_name = assignment.get("locked_by_name", "another clinician")
            return False, f"Case already locked and claimed by {claimant_name}. Lock expires at {lock_expires_at_str}.", assignment

    # Lock acquired or refreshed
    new_assignment = save_assignment(
        consultation_id=consultation_id,
        doctor_id=doctor_id,
        assigned_by=doctor_name,
        status="claimed",
        locked_by_name=doctor_name,
        lock_ttl_minutes=lock_ttl_minutes,
    )

    # Update consultation status
    consultation = get_consultation(consultation_id)
    if consultation:
        consultation["assigned_doctor_id"] = doctor_id
        consultation["status"] = "in_review"
        save_consultation(consultation_id, consultation)

    append_audit_log_entry(
        action="CONSULTATION_CLAIMED",
        user_id=doctor_id,
        role="doctor",
        resource_id=consultation_id,
        details={"locked_by_name": doctor_name, "lock_ttl_minutes": lock_ttl_minutes},
    )
    return True, "Consultation case successfully claimed and locked.", new_assignment


def release_consultation_lock(
    consultation_id: str,
    doctor_id: str,
) -> Tuple[bool, str]:
    """Release claim lock on consultation so other clinicians can claim (B5.4)."""
    assignment = get_assignment_for_consultation(consultation_id)
    if not assignment or assignment.get("doctor_id") != doctor_id:
        return False, "You do not currently hold the claim lock for this consultation."

    assignment["status"] = "released"
    assignment["released_at"] = datetime.now(timezone.utc).isoformat()
    assignment["lock_expires_at"] = None

    client = get_supabase_client()
    if client:
        try:
            client.table("consultation_assignments").update({
                "status": "released",
                "released_at": assignment["released_at"],
                "lock_expires_at": None,
            }).eq("id", assignment["id"]).execute()
        except Exception:
            pass

    _MEM_ASSIGNMENTS[consultation_id] = assignment

    consultation = get_consultation(consultation_id)
    if consultation:
        consultation["status"] = "triage"
        consultation["assigned_doctor_id"] = None
        save_consultation(consultation_id, consultation)

    append_audit_log_entry(
        action="CONSULTATION_RELEASED",
        user_id=doctor_id,
        role="doctor",
        resource_id=consultation_id,
        details={"consultation_id": consultation_id},
    )
    return True, "Claim lock released. Case returned to active department queue."


def reassign_consultation(
    consultation_id: str,
    reassigning_doctor_id: str,
    target_doctor_id: str,
    target_department_code: Optional[str],
    reason: str,
) -> Tuple[bool, str, Optional[dict]]:
    """Reassign case with mandatory clinical reason logged to audit trail (B5.6, B5.7)."""
    if not reason or len(reason.strip()) < 5:
        return False, "A mandatory clinical rationale of at least 5 characters is required for reassignment.", None

    target_doctor = find_staff_user(target_doctor_id)
    target_name = target_doctor.get("full_name", target_doctor_id) if target_doctor else target_doctor_id

    new_assignment = save_assignment(
        consultation_id=consultation_id,
        doctor_id=target_doctor_id,
        assigned_by=reassigning_doctor_id,
        status="assigned",
        reassignment_reason=reason.strip(),
        locked_by_name=target_name,
    )

    consultation = get_consultation(consultation_id)
    if consultation:
        consultation["assigned_doctor_id"] = target_doctor_id
        if target_department_code:
            consultation["department_id"] = target_department_code
        save_consultation(consultation_id, consultation)

    append_audit_log_entry(
        action="CONSULTATION_REASSIGNED",
        user_id=reassigning_doctor_id,
        role="doctor",
        resource_id=consultation_id,
        details={
            "target_doctor_id": target_doctor_id,
            "target_doctor_name": target_name,
            "target_department": target_department_code,
            "reason": reason.strip(),
        },
    )
    return True, f"Case successfully reassigned to {target_name}.", new_assignment


def override_urgency_tier(
    consultation_id: str,
    doctor_id: str,
    doctor_reg_no: Optional[str],
    new_tier: str,
    reason: str,
) -> Tuple[bool, str, Optional[dict]]:
    """Override AI urgency tier with mandatory clinical reason (B5.6, B5.7)."""
    valid_tiers = ["emergency", "doctor_today", "doctor_soon", "self_care"]
    if new_tier not in valid_tiers:
        return False, f"Invalid urgency tier '{new_tier}'. Must be one of {valid_tiers}.", None

    if not reason or len(reason.strip()) < 5:
        return False, "A mandatory clinical rationale of at least 5 characters is required to override urgency tier.", None

    consultation = get_consultation(consultation_id)
    if not consultation:
        return False, f"Consultation '{consultation_id}' not found.", None

    old_tier = consultation.get("urgency_tier", "unknown")
    consultation["urgency_tier"] = new_tier
    save_consultation(consultation_id, consultation)

    # Sync follow-up record if exists
    follow_up = get_follow_up_record(consultation_id)
    if follow_up:
        follow_up["urgency_tier"] = new_tier
        save_follow_up_record(consultation_id, follow_up)

    append_audit_log_entry(
        action="URGENCY_TIER_OVERRIDDEN",
        user_id=doctor_id,
        role="doctor",
        resource_id=consultation_id,
        details={
            "old_tier": old_tier,
            "new_tier": new_tier,
            "doctor_reg_no": doctor_reg_no,
            "clinical_reason": reason.strip(),
        },
    )
    return True, f"Urgency tier overridden from '{old_tier}' to '{new_tier}'.", consultation


def update_doctor_availability(doctor_id: str, is_on_duty: bool) -> bool:
    """Doctor availability toggle (B5.1, F3.6)."""
    client = get_supabase_client()
    if client:
        try:
            client.table("staff_users").update({"is_on_duty": is_on_duty}).eq("id", doctor_id).execute()
        except Exception as exc:
            logger.error("Supabase update_duty error: %s", exc)

    # Update fallback in-memory doctor if matching
    for d in _FALLBACK_STAFF.values():
        if d.get("id") == doctor_id or d.get("email") == doctor_id:
            d["is_on_duty"] = is_on_duty

    append_audit_log_entry(
        action="DOCTOR_AVAILABILITY_CHANGED",
        user_id=doctor_id,
        role="doctor",
        resource_id=doctor_id,
        details={"is_on_duty": is_on_duty},
    )
    return True


def verify_doctor_registration_by_admin(doctor_id: str, admin_user_id: str) -> bool:
    """Administrative verification of doctor registration number (B5.2, F4.2)."""
    client = get_supabase_client()
    if client:
        try:
            client.table("staff_users").update({"is_verified_doctor": True}).eq("id", doctor_id).execute()
        except Exception as exc:
            logger.error("Supabase admin_verify_doc error: %s", exc)

    for d in _FALLBACK_STAFF.values():
        if d.get("id") == doctor_id or d.get("email") == doctor_id:
            d["is_verified_doctor"] = True

    append_audit_log_entry(
        action="DOCTOR_REGISTRATION_ADMIN_VERIFIED",
        user_id=admin_user_id,
        role="admin",
        resource_id=doctor_id,
        details={"verified_doctor_id": doctor_id},
    )
    return True


def get_staff_doctors(department_code: Optional[str] = None, on_duty_only: bool = False) -> List[dict]:
    """Retrieve doctor roster with specialty, schedule, capacity and status (B5.1, F4.2)."""
    docs: List[dict] = []
    client = get_supabase_client()
    if client:
        try:
            q = client.table("staff_users").select("*").eq("role", "doctor")
            if on_duty_only:
                q = q.eq("is_on_duty", True)
            res = q.execute()
            if res.data:
                docs = res.data
        except Exception as exc:
            logger.error("Supabase get_staff_doctors error: %s", exc)

    if not docs:
        docs = [s for s in _FALLBACK_STAFF.values() if s.get("role") == "doctor"]
        if on_duty_only:
            docs = [s for s in docs if s.get("is_on_duty", True)]

    if department_code:
        docs = [d for d in docs if d.get("department_code") == department_code or d.get("specialty", "").upper() == department_code]

    return docs


def get_unclaimed_consultations_for_escalation() -> List[dict]:
    """
    Check unclaimed-case timers per tier and trigger automatic escalation (B5.5).
      - Emergency > 5 min -> raise critical ER alert flag
      - Doctor Today > 2 hours -> escalate to duty doctor
      - Doctor Soon > 24 hours -> escalate to Doctor Today
    """
    now = datetime.now(timezone.utc)
    escalations = []
    consultations = list_consultations_for_queue(status="triage")

    for c in consultations:
        if c.get("is_claimed"):
            continue

        created_str = c.get("created_at")
        if not created_str:
            continue

        try:
            created_dt = datetime.fromisoformat(created_str)
            elapsed_seconds = (now - created_dt).total_seconds()
            tier = c.get("urgency_tier", "self_care")
            cid = c["id"]

            if tier == "emergency" and elapsed_seconds > 300: # > 5 min
                escalations.append({
                    "consultation_id": cid,
                    "tier": tier,
                    "action": "ER_ALERT_ESCALATION",
                    "reason": f"Emergency case unclaimed for {int(elapsed_seconds/60)} minutes. Hospital ER and duty doctor alerted.",
                })
            elif tier == "doctor_today" and elapsed_seconds > 7200: # > 2 hours
                c["assigned_doctor_id"] = "11111111-0008-0000-0000-000000000008" # Duty Doctor
                save_consultation(cid, c)
                escalations.append({
                    "consultation_id": cid,
                    "tier": tier,
                    "action": "DUTY_DOCTOR_DISPATCH",
                    "reason": f"Doctor Today case unclaimed for {int(elapsed_seconds/3600)} hours. Automatically routed to Duty Doctor.",
                })
            elif tier == "doctor_soon" and elapsed_seconds > 86400: # > 24 hours
                c["urgency_tier"] = "doctor_today"
                save_consultation(cid, c)
                escalations.append({
                    "consultation_id": cid,
                    "tier": "doctor_today",
                    "action": "TIER_ESCALATED",
                    "reason": "Doctor Soon case unclaimed for > 24 hours. Escalated to Doctor Today tier.",
                })
        except Exception:
            continue

    return escalations


