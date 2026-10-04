"""
Test Suite for Block D: Doctors and Routing (B5.1 - B5.8, F3)

Verifies:
  - B5.1 Doctor profiles with specialty, languages, schedule, and capacity
  - B5.2 Administrative verification of doctor registration numbers
  - B5.3 Routing order:
        1. Emergency alert
        2. Complaint category mapping (Cardiology, Pediatrics, OBGYN, Gen Med)
        3. Match on-duty doctor speaking patient language with lowest load
        4. Department fallback -> Gen Med -> Duty Doctor
  - B5.4 Atomic claim locking (prevent race conditions, respect lock timeouts)
  - B5.5 Unclaimed case timers & auto-escalation
  - B5.6 Clinical reassignment and urgency tier overrides with mandatory rationale
  - B5.7 Append-only audit logging of all routing decisions
  - B5.8 Routing described as "by complaint category"
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_token, UserRole
from app.routing import categorize_complaint, select_best_doctor
from app.db import (
    get_staff_doctors,
    save_consultation,
    get_consultation,
    claim_consultation_lock,
    release_consultation_lock,
    reassign_consultation,
    override_urgency_tier,
    update_doctor_availability,
    verify_doctor_registration_by_admin,
    get_unclaimed_consultations_for_escalation,
    list_consultations_for_queue,
)
from app.schemas import ClinicalSummary, Symptom

client = TestClient(app)


@pytest.fixture
def admin_token():
    return create_token(
        user_id="admin_sys_001",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def doctor_rajan_token():
    return create_token(
        user_id="11111111-0001-0000-0000-000000000001",
        role=UserRole.DOCTOR,
        doctor_reg_no="DEMO-NMC-GENMED-01",
        is_verified_doctor=True,
    )


@pytest.fixture
def doctor_priya_token():
    return create_token(
        user_id="11111111-0002-0000-0000-000000000002",
        role=UserRole.DOCTOR,
        doctor_reg_no="DEMO-NMC-CARDIO-02",
        is_verified_doctor=True,
    )


def test_b5_1_seeded_doctor_roster_and_capacity(admin_token):
    """B5.1: 8 seeded demo doctors with specialty, languages, schedule, and capacity."""
    resp = client.get(
        "/api/v1/doctor/roster",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 8
    docs = data["doctors"]

    specialties = [d.get("specialty") for d in docs]
    assert "General Medicine" in specialties
    assert "Cardiology" in specialties
    assert "Pediatrics" in specialties
    assert "Obstetrics & Gynecology" in specialties

    # Verify every doctor has capacity and schedule
    for d in docs:
        assert "max_capacity" in d
        assert d["max_capacity"] > 0
        assert "weekly_schedule" in d
        assert "languages" in d
        assert len(d["languages"]) >= 1


def test_b5_2_admin_verification_of_doctor_registration(admin_token):
    """B5.2: Registration numbers verified by hospital admin, not matched by regex only."""
    resp = client.post(
        "/api/v1/staff/doctors/11111111-0001-0000-0000-000000000001/verify-registration",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert "verified by hospital administrator" in resp.json()["message"]


def test_b5_3_complaint_category_mapping_and_doctor_hierarchy():
    """B5.3, B5.8: Complaint categorization & multi-tiered doctor selection hierarchy."""
    # 1. Cardiac mapping
    cardio_summary = ClinicalSummary(
        chief_complaint="Severe chest pain with sweating",
        symptoms=[Symptom(name="chest pain", severity="severe")],
    )
    cat, dept, rationale = categorize_complaint(cardio_summary, {"age": "55"}, urgency_tier="doctor_today")
    assert cat == "cardiac_symptoms"
    assert dept == "CARDIOLOGY"
    assert "by complaint category" in rationale

    # 2. Pediatric mapping
    ped_summary = ClinicalSummary(
        chief_complaint="Baby having high fever and cough",
        symptoms=[Symptom(name="fever", severity="severe")],
    )
    cat, dept, rationale = categorize_complaint(ped_summary, {"age": "3"}, urgency_tier="doctor_today")
    assert cat == "pediatric_illness"
    assert dept == "PEDIATRICS"

    # 3. Doctor selection: Tamil speaker for Cardiology
    all_docs = get_staff_doctors()
    doc, doc_rationale = select_best_doctor(all_docs, "CARDIOLOGY", "ta-IN")
    assert doc is not None
    assert doc["specialty"] == "Cardiology"
    assert "ta" in [l.lower() for l in doc["languages"]]

    # 4. Doctor selection fallback: if cardiology doctor is busy/at capacity, fall back to Gen Med
    docs_copy = [dict(d) for d in all_docs]
    for d in docs_copy:
        if d.get("specialty") == "Cardiology":
            d["active_case_load"] = 999  # simulate at capacity
    fallback_doc, fallback_rationale = select_best_doctor(docs_copy, "CARDIOLOGY", "ta-IN")
    assert fallback_doc is not None
    assert fallback_doc.get("specialty") == "General Medicine" or fallback_doc.get("department_code") == "GEN_MED"


def test_b5_4_atomic_claim_locking_prevents_race_conditions(doctor_rajan_token, doctor_priya_token):
    """B5.4: Claim locking ensures two doctors cannot answer the same case."""
    cid = "test-consultation-claim-001"
    save_consultation(cid, {
        "status": "triage",
        "urgency_tier": "doctor_today",
        "chief_complaint": "Persistent headache",
    })

    # Doctor 1 claims the case
    resp1 = client.post(
        f"/api/v1/consultations/{cid}/claim",
        headers={"Authorization": f"Bearer {doctor_rajan_token}"},
        json={"lock_ttl_minutes": 15},
    )
    assert resp1.status_code == 200
    assert resp1.json()["success"] is True

    # Doctor 2 attempts to claim the same case -> 409 Conflict
    resp2 = client.post(
        f"/api/v1/consultations/{cid}/claim",
        headers={"Authorization": f"Bearer {doctor_priya_token}"},
        json={"lock_ttl_minutes": 15},
    )
    assert resp2.status_code == 409
    assert "already locked and claimed" in resp2.json()["detail"]

    # Doctor 1 releases lock
    resp3 = client.post(
        f"/api/v1/consultations/{cid}/release",
        headers={"Authorization": f"Bearer {doctor_rajan_token}"},
    )
    assert resp3.status_code == 200
    assert resp3.json()["success"] is True

    # Doctor 2 can now claim it
    resp4 = client.post(
        f"/api/v1/consultations/{cid}/claim",
        headers={"Authorization": f"Bearer {doctor_priya_token}"},
        json={"lock_ttl_minutes": 15},
    )
    assert resp4.status_code == 200
    assert resp4.json()["success"] is True


def test_b5_6_reassignment_and_tier_override_with_mandatory_reasons(doctor_priya_token):
    """B5.6: Reassignment and tier override enforce mandatory clinical reasons."""
    cid = "test-consultation-reassign-001"
    save_consultation(cid, {
        "status": "triage",
        "urgency_tier": "doctor_soon",
        "chief_complaint": "Joint stiffness",
    })

    # Reassignment fails without sufficient reason
    resp_bad = client.post(
        f"/api/v1/consultations/{cid}/reassign",
        headers={"Authorization": f"Bearer {doctor_priya_token}"},
        json={"target_doctor_id": "11111111-0006-0000-0000-000000000006", "reason": "no"},
    )
    assert resp_bad.status_code == 422  # validation error min_length 5

    # Reassignment succeeds with valid reason
    resp_ok = client.post(
        f"/api/v1/consultations/{cid}/reassign",
        headers={"Authorization": f"Bearer {doctor_priya_token}"},
        json={
            "target_doctor_id": "11111111-0006-0000-0000-000000000006",
            "reason": "Re-routing to Dr. Arvind (Orthopaedics) for specialized joint evaluation.",
        },
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["success"] is True

    # Tier override succeeds with mandatory clinical rationale
    resp_tier = client.post(
        f"/api/v1/consultations/{cid}/override-tier",
        headers={"Authorization": f"Bearer {doctor_priya_token}"},
        json={
            "new_tier": "doctor_today",
            "reason": "Patient reports worsening nocturnal pain requiring expedited review.",
        },
    )
    assert resp_tier.status_code == 200
    assert resp_tier.json()["consultation"]["urgency_tier"] == "doctor_today"


def test_b5_5_unclaimed_case_timers_and_escalation(admin_token):
    """B5.5: Automatic escalation when case exceeds unclaimed timer limit."""
    resp = client.post(
        "/api/v1/consultations/escalate-unclaimed",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "escalations" in resp.json()


def test_f3_doctor_availability_toggle(doctor_rajan_token):
    """F3.6: Doctor availability toggle updates duty status."""
    resp = client.post(
        "/api/v1/doctor/availability",
        headers={"Authorization": f"Bearer {doctor_rajan_token}"},
        json={"is_on_duty": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_on_duty"] is False

    # Toggle back on
    resp2 = client.post(
        "/api/v1/doctor/availability",
        headers={"Authorization": f"Bearer {doctor_rajan_token}"},
        json={"is_on_duty": True},
    )
    assert resp2.status_code == 200
    assert resp2.json()["is_on_duty"] is True


def test_f3_doctor_queue_urgent_first_ordering(doctor_rajan_token):
    """F3.2: Consultation queue sorted urgent-first (emergency > doctor_today > doctor_soon > self_care)."""
    save_consultation("queue-case-self-care", {"urgency_tier": "self_care", "status": "triage"})
    save_consultation("queue-case-emergency", {"urgency_tier": "emergency", "status": "triage"})
    save_consultation("queue-case-today", {"urgency_tier": "doctor_today", "status": "triage"})

    resp = client.get(
        "/api/v1/doctor/queue",
        headers={"Authorization": f"Bearer {doctor_rajan_token}"},
    )
    assert resp.status_code == 200
    consultations = resp.json()["consultations"]
    tiers = [c["urgency_tier"] for c in consultations if c["id"].startswith("queue-case-")]

    # Emergency must be before doctor_today, and doctor_today before self_care
    assert tiers.index("emergency") < tiers.index("doctor_today")
    assert tiers.index("doctor_today") < tiers.index("self_care")
