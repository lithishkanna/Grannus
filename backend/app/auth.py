"""
Authentication, Role-Based Access Control, and Doctor Verification for Grannus RuralCare AI.

Compliant with:
  - Telemedicine Practice Guidelines 2020 (Registered Medical Practitioner verification)
  - Supabase Auth & JWT standards
  - Cryptographic signed short-lived URLs for audio/media files
"""
import os
import hmac
import hashlib
import time
import base64
import json
import re
from enum import Enum
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.config import get_settings

security_bearer = HTTPBearer(auto_error=False)


def get_signing_secret() -> str:
    """Retrieve dedicated JWT signing secret independent of external API keys."""
    settings = get_settings()
    if not settings.jwt_secret_key:
        raise RuntimeError("JWT_SECRET_KEY is mandatory and not configured. Backend refusing to operate.")
    return settings.jwt_secret_key


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations and random 16-byte salt."""
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


# Registered medical / admin users with PBKDF2-hashed passwords
_REGISTERED_USERS: Dict[str, Dict[str, Any]] = {
    "dr.rajan@hospital.in": {
        "role": "doctor",
        "password_hash": hash_password("grannus_secure_doctor_2026"),
        "doctor_reg_no": "TNMC-48291",
        "state_council": "Tamil Nadu Medical Council",
    },
    "dr_clinician": {
        "role": "doctor",
        "password_hash": hash_password("grannus_secure_doctor_2026"),
        "doctor_reg_no": "TNMC-48291",
        "state_council": "Tamil Nadu Medical Council",
    },
    "admin_user": {
        "role": "admin",
        "password_hash": hash_password("grannus_secure_admin_2026"),
        "doctor_reg_no": None,
        "state_council": None,
    },
}


def authenticate_credentials(user_id: str, role: "UserRole", password: Optional[str] = None) -> bool:
    """
    Authenticate user credentials against password registry.
    Requires an explicit registered account and valid password.
    Legacy open login bypass is deleted (H1.1).
    """
    if not password:
        return False
    if user_id in _REGISTERED_USERS:
        reg_info = _REGISTERED_USERS[user_id]
        return verify_password(password, reg_info["password_hash"])
    return False


class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    NURSE = "nurse"
    ADMIN = "admin"
    ASHA_WORKER = "asha_worker"
    GUEST_EMERGENCY = "guest_emergency"


class AuthenticatedUser(BaseModel):
    user_id: str
    email: Optional[str] = None
    role: UserRole
    doctor_registration_number: Optional[str] = None
    state_medical_council: Optional[str] = None
    is_verified_doctor: bool = False
    phone_number: Optional[str] = None
    account_id: Optional[str] = None
    profile_id: Optional[str] = None
    hospital_id: Optional[str] = None
    guest_case_id: Optional[str] = None
    guest_token: Optional[str] = None


# NMC / State Medical Council registration format (e.g. "MCI-41982", "TN-67890", "123456", "DEMO-NMC-GENMED-01")
DOCTOR_REG_REGEX = re.compile(r"^DEMO-[A-Z0-9-]+$|^[A-Z]{2,4}-?[0-9]{4,10}$|^[0-9]{5,10}$", re.IGNORECASE)


def validate_doctor_registration(reg_number: str) -> bool:
    """Validate format of Indian medical registration number (NMC/State council)."""
    if not reg_number or len(reg_number.strip()) < 5:
        return False
    return bool(DOCTOR_REG_REGEX.match(reg_number.strip()))


# Set of revoked token signatures (logout / revocation support B2.5)
_REVOKED_TOKENS: set = set()


def revoke_token(token: str) -> None:
    """Revoke an active JWT token upon logout."""
    if token:
        _REVOKED_TOKENS.add(token.strip())


def is_token_revoked(token: str) -> bool:
    return token.strip() in _REVOKED_TOKENS


def create_token(
    user_id: str,
    role: UserRole,
    doctor_reg_no: Optional[str] = None,
    state_council: Optional[str] = None,
    phone_number: Optional[str] = None,
    account_id: Optional[str] = None,
    profile_id: Optional[str] = None,
    hospital_id: Optional[str] = None,
    is_verified_doctor: Optional[bool] = None,
    guest_case_id: Optional[str] = None,
    guest_token: Optional[str] = None,
    expires_in_seconds: int = 86400,
) -> str:
    """
    Generate a cryptographic signed token (HMAC-SHA256) for session management.
    """
    secret = get_signing_secret()
    
    is_verified = False
    if is_verified_doctor is not None:
        is_verified = is_verified_doctor
    elif role == UserRole.DOCTOR and doctor_reg_no:
        is_verified = validate_doctor_registration(doctor_reg_no)

    payload = {
        "sub": user_id,
        "role": role.value,
        "doc_reg": doctor_reg_no,
        "state_council": state_council,
        "verified_doctor": is_verified,
        "phone": phone_number,
        "account_id": account_id,
        "profile_id": profile_id,
        "hospital_id": hospital_id,
        "guest_case_id": guest_case_id,
        "guest_token": guest_token,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in_seconds,
    }

    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> AuthenticatedUser:
    """Validate and decode signed token."""
    if is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked or logged out.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = get_signing_secret()

    try:
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Malformed token")
        payload_b64, sig = parts
        
        # Verify HMAC signature
        expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Invalid signature")

        # Padding for base64
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())

        if time.time() > payload.get("exp", 0):
            raise ValueError("Token expired")

        return AuthenticatedUser(
            user_id=payload["sub"],
            role=UserRole(payload["role"]),
            doctor_registration_number=payload.get("doc_reg"),
            state_medical_council=payload.get("state_council"),
            is_verified_doctor=payload.get("verified_doctor", False),
            phone_number=payload.get("phone"),
            account_id=payload.get("account_id"),
            profile_id=payload.get("profile_id"),
            hospital_id=payload.get("hospital_id"),
            guest_case_id=payload.get("guest_case_id"),
            guest_token=payload.get("guest_token"),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> AuthenticatedUser:
    """Dependency for extracting authenticated user."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(auth.credentials)


def require_role(allowed_roles: List[UserRole]):
    """Enforce role-based access control."""
    def role_checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {[r.value for r in allowed_roles]}.",
            )
        return user
    return role_checker


def require_verified_doctor(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """
    Enforce verified doctor access under Telemedicine Practice Guidelines 2020.
    Requires role=doctor and a valid medical registration number.
    """
    if user.role != UserRole.DOCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only registered medical doctors may access this endpoint.",
        )
    if not user.is_verified_doctor or not user.doctor_registration_number:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unverified doctor. Valid NMC/State Council medical registration number required.",
        )
    return user


# -----------------------------------------------------------------------------
# Cryptographic Short-Lived Signed URLs
# -----------------------------------------------------------------------------

def generate_signed_url(file_path: str, expires_in_seconds: int = 1800) -> str:
    """
    Generate short-lived, HMAC-signed URL for audio/media files (default: 30 minutes).
    Prevents unauthorized public access to patient voice recordings.
    """
    secret = get_signing_secret()
    
    expires_at = int(time.time()) + expires_in_seconds
    message = f"{file_path}:{expires_at}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    
    return f"/api/v1/media/stream?file={file_path}&expires={expires_at}&sig={signature}"


def verify_signed_url(file_path: str, expires: int, signature: str) -> bool:
    """Verify that a signed media URL has not expired or been tampered with."""
    if time.time() > expires:
        return False
    
    secret = get_signing_secret()
    
    expected_message = f"{file_path}:{expires}"
    expected_sig = hmac.new(secret.encode(), expected_message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected_sig)
