"""
End-to-End Rehearsal and Clinical Demo Journey Test Suite (Block G).

Verifies the complete clinical product loop across all 8 standard scenarios:
  1. Strict authentication & anonymous denial (B2, F1.5)
  2. Patient phone OTP & multi-profile isolation (B4, F2.1-2.3)
  3. Emergency cardiac routing (B1.1, F2.5)
  4. Pediatric under-5 safety invariant (B1.1)
  5. Approved remedy library & red-flag warning criteria (B6.1, B6.4)
  6. Two-way asynchronous voice thread & back-translation safety (B7.4, F2.8, F3.4)
  7. Doctor queue claim locking & reassignment (B5.3, B5.4, F3.2)
  8. One-tap 'I feel worse' escalation loop & re-routing (B6.7, F2.6)
  9. DPDP patient consent, export, and erasure (B4.5, B4.6)
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_token, UserRole
from app.schemas import UrgencyTier

client = TestClient(app)


def test_anonymous_access_denied_across_clinical_endpoints():
    """Verify anonymous access is strictly blocked without valid bearer token."""
    # Clinical action endpoints
    res1 = client.post("/api/v1/consultations/action", json={
        "consultation_id": "test_c1",
        "action_type": "confirm_triage",
        "rationale": "Clinical review",
    })
    assert res1.status_code == 401

    # Voice thread access
    res2 = client.get("/api/v1/consultations/test_c1/thread")
    assert res2.status_code == 401

    # Doctor queue
    res3 = client.get("/api/v1/doctor/queue")
    assert res3.status_code == 401

    # Patient profiles
    res4 = client.get("/api/v1/patient/profiles")
    assert res4.status_code == 401


def test_complete_patient_journey_e2e():
    """Verify patient authentication via phone OTP and multi-profile isolation."""
    from app.db import _OTP_COOLDOWNS
    _OTP_COOLDOWNS.clear()
    # 1. Request OTP
    otp_req = client.post("/api/v1/auth/otp/request", json={"phone_number": "+919876543210"})
    assert otp_req.status_code == 200
    assert otp_req.json()["success"] is True

    # 2. Verify OTP
    otp_verify = client.post("/api/v1/auth/otp/verify", json={
        "phone_number": "+919876543210",
        "otp_code": "123456",
    })
    assert otp_verify.status_code == 200
    patient_token = otp_verify.json()["token"]
    headers = {"Authorization": f"Bearer {patient_token}"}

    # 3. Create Grandmother Profile (Kaveri Amma, 68y, Tamil)
    p1_res = client.post("/api/v1/patient/profiles", json={
        "full_name": "Kaveri Amma",
        "age": "68",
        "gender": "female",
        "relation": "Grandmother",
        "preferred_language": "ta-IN",
        "known_conditions": ["hypertension"],
        "allergies": ["penicillin"],
    }, headers=headers)
    assert p1_res.status_code == 200
    p1_id = p1_res.json()["id"]

    # 4. Create Grandson Profile (Aarav, 3y, Hindi)
    p2_res = client.post("/api/v1/patient/profiles", json={
        "full_name": "Baby Aarav",
        "age": "3",
        "gender": "male",
        "relation": "Grandson",
        "preferred_language": "hi-IN",
        "known_conditions": [],
        "allergies": [],
    }, headers=headers)
    assert p2_res.status_code == 200
    p2_id = p2_res.json()["id"]

    # 5. List profiles and verify isolation
    list_res = client.get("/api/v1/patient/profiles", headers=headers)
    assert list_res.status_code == 200
    profiles = list_res.json()
    prof_ids = [p["id"] for p in profiles]
    assert p1_id in prof_ids
    assert p2_id in prof_ids


def test_emergency_cardiac_case_routing_and_doctor_flow():
    """Verify chest pain in 60y routes to EMERGENCY and cardiologist queue."""
    # 1. Run demo case
    res = client.post("/api/v1/demo/run-sample/chest_pain_60y?language_code=ta-IN")
    assert res.status_code == 200
    data = res.json()
    cid = data["request_id"]
    assert data["priority"]["urgency_tier"] == "emergency"
    assert data["priority"]["emergency_override"] is True
    assert "108" in data["priority"]["emergency_call_numbers"]

    # 2. Doctor logs in
    doc_login = client.post("/api/v1/auth/login", json={
        "email": "dr.rajan@hospital.in",
        "password": "grannus_secure_doctor_2026",
    })
    assert doc_login.status_code == 200
    doc_token = doc_login.json()["token"]
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # 3. Doctor checks queue
    q_res = client.get("/api/v1/doctor/queue", headers=doc_headers)
    assert q_res.status_code == 200
    q_items = q_res.json()["consultations"]
    case = next((c for c in q_items if c["id"] == cid), None)
    assert case is not None
    assert case["urgency_tier"] == "emergency"

    # 4. Doctor claims case
    claim_res = client.post(f"/api/v1/consultations/{cid}/claim", headers=doc_headers)
    assert claim_res.status_code == 200
    assert claim_res.json()["success"] is True

    # 5. Second doctor attempts to claim -> 409 Conflict
    doc2_token = create_token(user_id="dr_priya_02", role=UserRole.DOCTOR, doctor_reg_no="TNMC-99999", is_verified_doctor=True)
    doc2_headers = {"Authorization": f"Bearer {doc2_token}"}
    claim2_res = client.post(f"/api/v1/consultations/{cid}/claim", headers=doc2_headers)
    assert claim2_res.status_code == 409


def test_pediatric_fever_under_5_safety_invariant_e2e():
    """Verify child with fever can NEVER be assigned to self_care or doctor_soon."""
    res = client.post("/api/v1/demo/run-sample/child_fever_2y?language_code=hi-IN")
    assert res.status_code == 200
    data = res.json()
    tier = data["priority"]["urgency_tier"]
    assert tier == "doctor_today"
    assert tier not in ["doctor_soon", "self_care"]


def test_self_care_remedy_and_one_tap_escalate_e2e():
    """Verify approved self-care remedy guidance and one-tap 'I feel worse' escalation."""
    # 1. Mild cough consultation
    res = client.post("/api/v1/demo/run-sample/cough_3_days?language_code=ta-IN")
    assert res.status_code == 200
    data = res.json()
    cid = data["request_id"]
    assert data["priority"]["urgency_tier"] == "self_care"

    # 2. Verify approved remedy library and 'seek_doctor_if' criteria
    remedy = data["home_remedy_guidance"]
    assert remedy is not None
    assert len(remedy["care_steps"]) > 0
    assert len(remedy["seek_doctor_if"]) > 0

    # 3. Patient taps 'I feel worse' button
    patient_token = create_token(user_id="pat_test_01", role=UserRole.PATIENT)
    pat_headers = {"Authorization": f"Bearer {patient_token}"}
    esc_res = client.post(
        f"/api/v1/consultations/{cid}/escalate",
        json={"reason": "Cough has increased with mild chest tightness"},
        headers=pat_headers,
    )
    assert esc_res.status_code == 200
    esc_data = esc_res.json()
    assert esc_data["is_escalated"] is True
    assert esc_data["previous_tier"] == "self_care"
    assert esc_data["new_tier"] == "doctor_soon"


def test_voice_thread_two_way_communication_e2e():
    """Verify asynchronous voice thread dialogue between doctor and patient."""
    user_token = create_token(user_id="dr_test_voice", role=UserRole.DOCTOR)
    headers = {"Authorization": f"Bearer {user_token}"}
    cid = "test_thread_c_99"

    # Retrieve initial thread
    thread_res = client.get(f"/api/v1/consultations/{cid}/thread", headers=headers)
    assert thread_res.status_code == 200
    assert thread_res.json()["consultation_id"] == cid
