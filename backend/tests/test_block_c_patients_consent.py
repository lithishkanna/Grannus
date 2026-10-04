"""
Tests for Block C: Patient Accounts, Profiles, PIN Protection, Recycled Numbers,
Consent Recording, Data Export, and Statutory Erasure (B4.1 - B4.7).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import create_token, UserRole
from app.db import (
    create_patient_profile,
    get_patient_profile,
    get_profiles_for_account,
    verify_profile_pin,
    export_account_data,
    erase_account_data,
    reset_recycled_phone_number,
    save_consent_record,
)


@pytest.fixture
def client():
    return TestClient(app)


# -----------------------------------------------------------------------------
# B4.1 & B4.2 Multi-Profile per Phone and Profile Attachment
# -----------------------------------------------------------------------------

def test_multi_profile_creation_and_retrieval(client):
    """One phone account holds multiple family profiles (self, child, parent)."""
    token = create_token("pat_fam_01", UserRole.PATIENT, phone_number="+919876543210", account_id="acc_family_01")
    headers = {"Authorization": f"Bearer {token}"}

    # Create self profile
    res1 = client.post("/api/v1/patient/profiles", json={
        "full_name": "Suresh Raina",
        "age": "36",
        "gender": "male",
        "relation": "self",
        "preferred_language": "ta-IN",
        "allergies": ["Penicillin"],
        "medications": ["Antihistamine"],
    }, headers=headers)
    assert res1.status_code == 200
    p1 = res1.json()
    assert p1["full_name"] == "Suresh Raina"
    assert p1["allergies"] == ["Penicillin"]

    # Create child profile with PIN
    res2 = client.post("/api/v1/patient/profiles", json={
        "full_name": "Gracia Raina",
        "age": "6",
        "gender": "female",
        "relation": "child",
        "preferred_language": "ta-IN",
        "pin": "9988",
    }, headers=headers)
    assert res2.status_code == 200
    p2 = res2.json()
    assert p2["full_name"] == "Gracia Raina"
    assert p2["pin_hash"] is not None

    # Retrieve all profiles for account
    list_res = client.get("/api/v1/patient/profiles", headers=headers)
    assert list_res.status_code == 200
    profiles = list_res.json()
    assert len(profiles) >= 2


# -----------------------------------------------------------------------------
# B4.3 Profile 4-Digit PIN Verification
# -----------------------------------------------------------------------------

def test_profile_pin_verification(client):
    """Test 4-digit PIN verification before accessing private profile."""
    token = create_token("pat_pin_user", UserRole.PATIENT, phone_number="+919876543212", account_id="acc_pin_01")
    headers = {"Authorization": f"Bearer {token}"}

    # Create profile with PIN
    p_res = client.post("/api/v1/patient/profiles", json={
        "full_name": "Private User",
        "relation": "self",
        "pin": "4321",
    }, headers=headers)
    profile_id = p_res.json()["id"]

    # Verify wrong PIN -> 401
    bad_pin = client.post(f"/api/v1/patient/profiles/{profile_id}/verify-pin", json={"pin": "0000"}, headers=headers)
    assert bad_pin.status_code == 401
    assert "Incorrect" in bad_pin.json()["detail"]

    # Verify correct PIN -> 200
    good_pin = client.post(f"/api/v1/patient/profiles/{profile_id}/verify-pin", json={"pin": "4321"}, headers=headers)
    assert good_pin.status_code == 200
    assert good_pin.json()["verified"] is True


# -----------------------------------------------------------------------------
# B4.4 Recycled Phone Number Reset
# -----------------------------------------------------------------------------

def test_recycled_phone_number_reset(client):
    """New owner of recycled phone number can wipe prior profile history."""
    acc_id = "acc_recycled_99"
    token = create_token("pat_recycled", UserRole.PATIENT, phone_number="+919876500099", account_id=acc_id)
    headers = {"Authorization": f"Bearer {token}"}

    # Add old profile
    client.post("/api/v1/patient/profiles", json={"full_name": "Prior Owner"}, headers=headers)
    assert len(get_profiles_for_account(acc_id)) >= 1

    # Call reset recycled account
    reset_res = client.post("/api/v1/patient/account/reset-recycled", headers=headers)
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "success"

    # Confirm prior profiles removed
    assert len(get_profiles_for_account(acc_id)) == 0


# -----------------------------------------------------------------------------
# B4.5 Versioned Timestamped Patient Consent
# -----------------------------------------------------------------------------

def test_versioned_patient_consent_flow(client):
    """Test localized consent notice and timestamped consent recording."""
    # 1. Fetch notice in Tamil
    notice_res = client.get("/api/v1/consent/notice?language_code=ta-IN")
    assert notice_res.status_code == 200
    n_data = notice_res.json()
    assert n_data["version"] == "2023.1-DPDP"
    assert "நோயாளி ஒப்புதல்" in n_data["notice"]["title"]

    # 2. Record consent
    rec_res = client.post("/api/v1/consent/record", json={
        "patient_id": "pat_consent_001",
        "language_code": "ta-IN",
        "explicit_consent": True,
    })
    assert rec_res.status_code == 200
    c_data = rec_res.json()
    assert c_data["explicit_consent_granted"] is True
    assert c_data["consent_version"] == "2023.1-DPDP"
    assert "CONSENT-" in c_data["consent_id"]


# -----------------------------------------------------------------------------
# B4.6 Data Portability Export & Statutory Erasure (DPDP Act 2023)
# -----------------------------------------------------------------------------

def test_patient_data_export_and_erasure(client):
    """Test complete account data export and DPDP statutory erasure."""
    acc_id = "acc_export_erasure_01"
    token = create_token("pat_export_user", UserRole.PATIENT, phone_number="+919876543255", account_id=acc_id)
    headers = {"Authorization": f"Bearer {token}"}

    # Create profile
    client.post("/api/v1/patient/profiles", json={
        "full_name": "Export Candidate",
        "age": "50",
        "relation": "self",
    }, headers=headers)

    # 1. Export patient data
    export_res = client.get("/api/v1/patient/data-export", headers=headers)
    assert export_res.status_code == 200
    exp = export_res.json()
    assert exp["account_id"] == acc_id
    assert len(exp["profiles"]) >= 1
    assert exp["profiles"][0]["full_name"] == "Export Candidate"

    # 2. Execute statutory erasure
    erase_res = client.post("/api/v1/patient/data-erasure", json={
        "patient_id": acc_id,
        "reason": "Patient requested complete account erasure under DPDP Act 2023",
    }, headers=headers)
    assert erase_res.status_code == 200
    assert erase_res.json()["status"] == "success"

    # 3. Confirm profile is now anonymized
    post_export = client.get("/api/v1/patient/data-export", headers=headers)
    assert post_export.status_code == 200
    anonymized_profiles = post_export.json()["profiles"]
    assert any(p["full_name"] == "ANONYMIZED_PATIENT" for p in anonymized_profiles)
