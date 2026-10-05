"""
Unit tests for MSG91 SMS gateway integration and patient consultation history retrieval.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_token, UserRole
from app.sms import send_sms_otp, normalize_mobile_for_india, SANDBOX_TEST_NUMBERS
from app.db import save_consultation, get_consultations_for_patient

client = TestClient(app)


def test_normalize_mobile_for_india():
    assert normalize_mobile_for_india("9876543210") == "919876543210"
    assert normalize_mobile_for_india("+919876543210") == "919876543210"
    assert normalize_mobile_for_india("09876543210") == "919876543210"
    assert normalize_mobile_for_india("919876543210") == "919876543210"


def test_send_sms_otp_sandbox_preserves_credits():
    # Sandbox numbers should return instantly without consuming external API credits
    ok, msg = send_sms_otp("+919876543210", "123456")
    assert ok is True
    assert "Sandbox" in msg or "active" in msg


def test_patient_consultations_endpoint_requires_auth():
    # Unauthorized request must return 401
    res = client.get("/api/v1/patient/consultations")
    assert res.status_code == 401


def test_patient_consultations_endpoint_retrieves_records():
    account_id = "test_acc_9999"
    profile_id = "test_prof_8888"
    token = create_token(
        user_id="pat_test_9999",
        role=UserRole.PATIENT,
        account_id=account_id,
        phone_number="+919876543210",
    )

    # Save a consultation linked to this profile and account
    cid = "test_consult_report_123"
    save_consultation(cid, {
        "account_id": account_id,
        "profile_id": profile_id,
        "patient_language": "ta-IN",
        "urgency_tier": "doctor_today",
        "original_transcript": "நெஞ்சு வலி",
        "english_transcript": "Chest pain",
        "chief_complaint": "Chest pain radiating to left arm",
    })

    # Retrieve via API with Bearer token
    res = client.get(
        f"/api/v1/patient/consultations?profile_id={profile_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "consultations" in data
    assert data["count"] >= 1
    found = any(c.get("id") == cid for c in data["consultations"])
    assert found is True
