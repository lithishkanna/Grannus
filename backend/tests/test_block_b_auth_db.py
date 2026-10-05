"""
Tests for Block B: Real Authentication, Phone OTP, Staff Logins, Role Enforcement,
Token Revocation, and Persistence Layer (B2, B3).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import create_token, UserRole, revoke_token, is_token_revoked
from app.db import (
    request_phone_otp,
    verify_phone_otp,
    authenticate_staff_user,
    save_pipeline_job,
    get_pipeline_job,
    save_voice_thread,
    get_voice_thread,
    save_follow_up_record,
    get_follow_up_record,
    append_audit_log_entry,
)


@pytest.fixture
def client():
    return TestClient(app)


# -----------------------------------------------------------------------------
# B2.2 Phone OTP Flow Tests
# -----------------------------------------------------------------------------

def test_otp_request_and_verify_dev_number(client):
    """Test OTP request and verification with dev test number +919876543210."""
    from app.db import _OTP_COOLDOWNS
    _OTP_COOLDOWNS.clear()
    phone = "+919876543210"

    # 1. Request OTP
    req_res = client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert req_res.status_code == 200
    data = req_res.json()
    assert data["success"] is True
    assert "dev_otp_hint" not in data  # H1.2: OTPs never appear in API responses

    # 2. Verify with wrong code
    bad_res = client.post("/api/v1/auth/otp/verify", json={"phone_number": phone, "otp_code": "000000"})
    assert bad_res.status_code == 401
    assert "Invalid verification code" in bad_res.json()["detail"]

    # 3. Verify with correct code
    good_res = client.post("/api/v1/auth/otp/verify", json={"phone_number": phone, "otp_code": "123456"})
    assert good_res.status_code == 200
    auth_data = good_res.json()
    assert "token" in auth_data
    assert auth_data["role"] == "patient"
    assert auth_data["phone_number"] == phone
    assert auth_data["account_id"] is not None

    # 4. Attempt to reuse same OTP (single-use enforcement)
    reuse_res = client.post("/api/v1/auth/otp/verify", json={"phone_number": phone, "otp_code": "123456"})
    assert reuse_res.status_code == 401


def test_otp_cooldown_rate_limit(client):
    """Calling OTP request twice within 60s should trigger 429 Too Many Requests."""
    phone = "+919999999999"
    # First request
    res1 = client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert res1.status_code == 200

    # Immediate second request
    res2 = client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert res2.status_code == 429
    assert "Please wait" in res2.json()["detail"]


# -----------------------------------------------------------------------------
# B2.3 Staff Authentication Tests (Email & Password)
# -----------------------------------------------------------------------------

def test_staff_doctor_login_success(client):
    """Doctor login with valid email and password."""
    res = client.post("/api/v1/auth/login", json={
        "email": "dr.rajan@hospital.in",
        "password": "grannus_secure_doctor_2026",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "doctor"
    assert data["is_verified_doctor"] is True
    assert "DEMO-NMC" in data["doctor_registration_number"] or "TNMC" in data["doctor_registration_number"]
    assert "Dr. Rajan K." in data["full_name"]
    assert "token" in data


def test_staff_nurse_and_admin_login(client):
    """Nurse and Admin login with valid credentials."""
    # Nurse login
    nurse_res = client.post("/api/v1/auth/login", json={
        "email": "nurse.mary@hospital.in",
        "password": "grannus_nurse_2026",
    })
    assert nurse_res.status_code == 200
    assert nurse_res.json()["role"] == "nurse"

    # Admin login
    admin_res = client.post("/api/v1/auth/login", json={
        "email": "admin@hospital.in",
        "password": "grannus_admin_2026",
    })
    assert admin_res.status_code == 200
    assert admin_res.json()["role"] == "admin"


def test_staff_login_invalid_password(client):
    """Staff login with wrong password is rejected with 401."""
    res = client.post("/api/v1/auth/login", json={
        "email": "dr.rajan@hospital.in",
        "password": "wrong_password_123",
    })
    assert res.status_code == 401
    assert "Invalid credentials" in res.json()["detail"]


# -----------------------------------------------------------------------------
# B2.5 Token Revocation and Logout Tests
# -----------------------------------------------------------------------------

def test_logout_and_token_revocation(client):
    """After calling logout, the token is revoked and cannot access protected endpoints."""
    # 1. Log in as doctor
    login_res = client.post("/api/v1/auth/login", json={
        "email": "dr.rajan@hospital.in",
        "password": "grannus_secure_doctor_2026",
    })
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Access /api/v1/auth/me -> success
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "doctor"

    # 3. Log out
    logout_res = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # 4. Access /api/v1/auth/me again -> 401 Revoked
    revoked_res = client.get("/api/v1/auth/me", headers=headers)
    assert revoked_res.status_code == 401
    assert "revoked" in revoked_res.json()["detail"].lower()


# -----------------------------------------------------------------------------
# B2.7 Endpoint Protection Tests (Formerly open endpoints now require auth)
# -----------------------------------------------------------------------------

def test_unauthenticated_requests_return_401(client):
    """Ensure all protected endpoints strictly return 401 when accessed without token."""
    # Job status
    r1 = client.get("/api/v1/pipeline/job-status/test-job-123")
    assert r1.status_code == 401

    # Check-in
    r2 = client.post("/api/v1/consultations/test-c-1/check-in", json={"status": "same"})
    assert r2.status_code == 401

    # Escalate
    r3 = client.post("/api/v1/consultations/test-c-1/escalate", json={"reason": "worse"})
    assert r3.status_code == 401

    # Voice Thread GET
    r4 = client.get("/api/v1/consultations/test-c-1/thread")
    assert r4.status_code == 401

    # Patient profiles
    r5 = client.get("/api/v1/patient/profiles")
    assert r5.status_code == 401


# -----------------------------------------------------------------------------
# B2.8 & B4.1 Patient Profiles & Account Isolation Tests
# -----------------------------------------------------------------------------

def test_patient_profiles_creation_and_isolation(client):
    """Patient can create profiles under their phone account, with PIN protection."""
    # Create two different patient tokens
    token_a = create_token("pat_a", UserRole.PATIENT, phone_number="+919876543210", account_id="acc_user_a")
    token_b = create_token("pat_b", UserRole.PATIENT, phone_number="+919876543211", account_id="acc_user_b")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates a profile for self and for a child
    p1 = client.post("/api/v1/patient/profiles", json={
        "full_name": "Ramesh Kumar",
        "age": "45",
        "gender": "male",
        "relation": "self",
        "preferred_language": "ta-IN",
        "pin": "1234",
    }, headers=headers_a)
    assert p1.status_code == 200
    assert p1.json()["full_name"] == "Ramesh Kumar"

    p2 = client.post("/api/v1/patient/profiles", json={
        "full_name": "Ananya Kumar",
        "age": "8",
        "gender": "female",
        "relation": "child",
        "preferred_language": "ta-IN",
    }, headers=headers_a)
    assert p2.status_code == 200

    # User A lists profiles -> sees 2 profiles
    list_a = client.get("/api/v1/patient/profiles", headers=headers_a)
    assert list_a.status_code == 200
    profiles_a = list_a.json()
    assert len(profiles_a) == 2
    assert any(p["full_name"] == "Ramesh Kumar" for p in profiles_a)
    assert any(p["full_name"] == "Ananya Kumar" for p in profiles_a)

    # User B lists profiles -> sees 0 profiles (Account isolation B2.8)
    list_b = client.get("/api/v1/patient/profiles", headers=headers_b)
    assert list_b.status_code == 200
    profiles_b = list_b.json()
    assert len(profiles_b) == 0


# -----------------------------------------------------------------------------
# B3 Persistence & Append-Only Audit Log Tests
# -----------------------------------------------------------------------------

def test_pipeline_job_persistence():
    """Job records are saved and retrievable via db layer."""
    job_id = "test_persist_job_001"
    save_pipeline_job(job_id, {
        "status": "EXTRACTING",
        "stage": "Extracting clinical symptoms",
        "progress": 60,
    })

    retrieved = get_pipeline_job(job_id)
    assert retrieved is not None
    assert retrieved["id"] == job_id
    assert retrieved["status"] == "EXTRACTING"
    assert retrieved["progress"] == 60


def test_follow_up_record_persistence():
    """Follow-up check-in records are saved and retrievable via db layer."""
    cid = "test_persist_consult_001"
    save_follow_up_record(cid, {
        "consultation_id": cid,
        "urgency_tier": "doctor_today",
        "status": "ESCALATED",
        "patient_status": "worse",
    })

    retrieved = get_follow_up_record(cid)
    assert retrieved is not None
    assert retrieved["consultation_id"] == cid
    assert retrieved["urgency_tier"] == "doctor_today"
    assert retrieved["status"] == "ESCALATED"


def test_audit_log_append_only():
    """Audit logs append correctly and preserve action details."""
    log_entry = append_audit_log_entry(
        action="TEST_SECURITY_EVENT",
        user_id="test_admin_01",
        role="admin",
        details={"ip": "127.0.0.1", "action_type": "security_check"},
    )
    assert log_entry is not None
    assert log_entry["action"] == "TEST_SECURITY_EVENT"
    assert log_entry["user_id"] == "test_admin_01"
    assert "id" in log_entry
