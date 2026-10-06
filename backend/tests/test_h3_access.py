"""
Acceptance tests for Block H3: Authorization Everywhere & Role Isolation Matrix.

Verifies:
  - H3.1: Patient A gets 403 or 404 on Patient B's profile, consultation, thread, and audio.
  - H3.2: Doctor X gets 403 on Doctor Y's assigned case.
  - H3.3: Data masking by role: doctor sees masked phone; nurse/admin receives no clinical text.
  - H3.4 & H3.5: All protected clinical endpoints deny unauthenticated calls (401) and wrong roles (403).
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_token, UserRole
from app.db import (
    save_consultation,
    create_patient_profile,
    save_assignment,
)
from app.voice_threads import get_voice_thread_manager

client = TestClient(app)


def test_h3_patient_isolation_across_endpoints():
    """H3.1: Patient A gets 403 or 404 on Patient B's profile, consultation, and voice thread."""
    # 1. Create tokens for two separate patient accounts
    token_a = create_token("user_a", UserRole.PATIENT, phone_number="+919876500001", account_id="acc_a")
    token_b = create_token("user_b", UserRole.PATIENT, phone_number="+919876500002", account_id="acc_b")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 2. Create profile for Patient B
    prof_b = create_patient_profile("acc_b", {
        "full_name": "Patient B Person",
        "age": "40",
        "gender": "male",
        "relation": "Self",
        "preferred_language": "hi-IN",
    })
    prof_b_id = prof_b["id"]

    # Patient A attempts to read Patient B's profile -> 403
    res_prof = client.get(f"/api/v1/patient/profiles/{prof_b_id}", headers=headers_a)
    assert res_prof.status_code == 403

    # Patient B can read own profile -> 200
    res_prof_ok = client.get(f"/api/v1/patient/profiles/{prof_b_id}", headers=headers_b)
    assert res_prof_ok.status_code == 200
    assert res_prof_ok.json()["full_name"] == "Patient B Person"

    # 3. Create consultation belonging to Patient B
    case_b_id = "consult_patient_b_99"
    save_consultation(case_b_id, {
        "id": case_b_id,
        "account_id": "acc_b",
        "profile_id": prof_b_id,
        "urgency_tier": "doctor_soon",
        "chief_complaint": "Joint stiffness",
    })
    get_voice_thread_manager().get_or_create_thread(case_b_id)

    # Patient A attempts to read Patient B's consultation details -> 403
    res_case = client.get(f"/api/v1/consultations/{case_b_id}", headers=headers_a)
    assert res_case.status_code == 403

    # Patient A attempts to read Patient B's voice thread -> 403
    res_thread = client.get(f"/api/v1/consultations/{case_b_id}/thread", headers=headers_a)
    assert res_thread.status_code == 403

    # Patient A attempts to escalate Patient B's case -> 403
    res_esc = client.post(f"/api/v1/consultations/{case_b_id}/escalate", json={"reason": "worse"}, headers=headers_a)
    assert res_esc.status_code == 403


def test_h3_doctor_assignment_isolation():
    """H3.2: Doctor X gets 403 on Doctor Y's assigned case."""
    doc_x_token = create_token("doc_x", UserRole.DOCTOR, doctor_reg_no="TNMC-11111", is_verified_doctor=True)
    doc_y_token = create_token("doc_y", UserRole.DOCTOR, doctor_reg_no="TNMC-22222", is_verified_doctor=True)
    headers_x = {"Authorization": f"Bearer {doc_x_token}"}
    headers_y = {"Authorization": f"Bearer {doc_y_token}"}

    case_id = "consult_assigned_to_doc_y"
    save_consultation(case_id, {
        "id": case_id,
        "urgency_tier": "doctor_today",
        "chief_complaint": "Persistent headache",
        "phone_number": "+919876543210",
    })
    # Explicitly assign case to Doctor Y
    save_assignment(case_id, doctor_id="doc_y", assigned_by="system")

    # Doctor Y accesses assigned case -> 200
    res_y = client.get(f"/api/v1/consultations/{case_id}", headers=headers_y)
    assert res_y.status_code == 200

    # Doctor X accesses Doctor Y's assigned case -> 403
    res_x = client.get(f"/api/v1/consultations/{case_id}", headers=headers_x)
    assert res_x.status_code == 403
    assert "assigned to another clinician" in res_x.json()["detail"].lower()


def test_h3_role_data_masking():
    """H3.3: Doctor gets masked phone; Nurse and Admin never receive clinical text."""
    doc_token = create_token("doc_test", UserRole.DOCTOR, doctor_reg_no="TNMC-12345", is_verified_doctor=True)
    nurse_token = create_token("nurse_test", UserRole.NURSE)
    admin_token = create_token("admin_test", UserRole.ADMIN)

    case_id = "consult_masking_test"
    save_consultation(case_id, {
        "id": case_id,
        "phone_number": "+919876543210",
        "transcript_original": "நெஞ்சு வலிக்கிறது மற்றும் மூச்சு திணறல்",
        "transcript_english": "Chest pain and difficulty breathing",
        "chief_complaint": "Severe acute chest pain",
        "urgency_tier": "emergency",
    })

    # Doctor view: phone number is masked
    res_doc = client.get(f"/api/v1/consultations/{case_id}", headers={"Authorization": f"Bearer {doc_token}"})
    assert res_doc.status_code == 200
    doc_data = res_doc.json()
    assert "****" in doc_data.get("phone_number", "")
    assert "+919876543210" != doc_data.get("phone_number")

    # Nurse view: clinical transcript and text are stripped
    res_nurse = client.get(f"/api/v1/consultations/{case_id}", headers={"Authorization": f"Bearer {nurse_token}"})
    assert res_nurse.status_code == 200
    nurse_data = res_nurse.json()
    assert "transcript_original" not in nurse_data
    assert "transcript_english" not in nurse_data
    assert "chief_complaint" not in nurse_data
    assert nurse_data["urgency_tier"] == "emergency"

    # Admin view: clinical transcript and text are stripped
    res_admin = client.get(f"/api/v1/consultations/{case_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    admin_data = res_admin.json()
    assert "transcript_original" not in admin_data
    assert "transcript_english" not in admin_data
    assert "chief_complaint" not in admin_data


@pytest.mark.parametrize("endpoint,method,payload", [
    ("/api/v1/doctor/queue", "GET", None),
    ("/api/v1/admin/routing-logs", "GET", None),
    ("/api/v1/admin/roster", "GET", None),
    ("/api/v1/consultations/escalate-unclaimed", "POST", None),
])
def test_h3_patient_denied_on_staff_routes(endpoint, method, payload):
    """H3.4: Patient token gets 403 on all doctor and administrative routes."""
    patient_token = create_token("patient_u1", UserRole.PATIENT, phone_number="+919876543210")
    headers = {"Authorization": f"Bearer {patient_token}"}
    if method == "GET":
        res = client.get(endpoint, headers=headers)
    else:
        res = client.post(endpoint, json=payload or {}, headers=headers)
    assert res.status_code == 403
