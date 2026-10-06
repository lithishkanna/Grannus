"""
Unit and Integration Tests for Phase 5: Field Pilot Readiness and Telehealth Orchestration.

Covers:
  - Asynchronous background job queue and stage progress polling
  - 202 Accepted intake decoupling on low-bandwidth / slow connections
  - Clinician telehealth decision loop (confirm triage, priority override, prescription, referral)
  - Medical registration audit logging on doctor actions
  - Official bilingual clinical referral slip generation for PHC/CHC handoffs
"""
import io
import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import UserRole, create_token
from app.jobs.job_manager import get_job_manager, JobStatus
from app.telehealth.clinical_actions import (
    get_clinical_action_manager,
    DoctorActionType,
    DoctorActionRequest,
    PrescriptionItem,
)
from app.telehealth.referral_slip import generate_referral_slip

client = TestClient(app)

SAMPLE_WAV_HEADER = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00" + b"\x00" * 120

SAMPLE_PIPELINE_RESULT = {
    "request_id": "req_pilot_001",
    "patient_input": {
        "language": "hi-IN",
        "transcript_original": "तीन दिनों से तेज बुखार और सांस लेने में कठिनाई है",
        "transcript_english": "high fever for three days and difficulty breathing",
        "confidence": 0.95,
    },
    "clinical_summary": {
        "chief_complaint": "difficulty breathing",
        "symptoms": [
            {
                "name": "difficulty breathing",
                "raw_text": "सांस लेने में कठिनाई",
                "severity": "severe",
                "negated": False,
                "confidence": 0.98,
            },
            {
                "name": "fever",
                "raw_text": "तेज बुखार",
                "severity": "moderate",
                "negated": False,
                "confidence": 0.95,
            }
        ],
        "red_flags": [
            {
                "phrase": "difficulty breathing",
                "related_symptom": "difficulty breathing",
                "confidence": 0.98,
            }
        ],
    },
    "safety_screening": {
        "emergency_triggered": True,
        "red_flags": [
            {
                "symptom": "difficulty breathing",
                "severity": "critical",
                "reason": "Respiratory distress risk",
                "action": "Immediate oxygenation & referral",
                "triggered_by": "deterministic_rule",
            }
        ],
        "contradictions": [],
    },
    "priority": {
        "level": "HIGH",
        "confidence": 0.99,
        "rationale": "Severe breathing difficulty detected",
        "action": "Immediate hospital referral",
    },
    "clinician_review_required": True,
    "disclaimer": "AI-generated structured summary",
}


# -----------------------------------------------------------------------------
# 1. Asynchronous Job Manager & Status Tracking
# -----------------------------------------------------------------------------

def test_job_manager_lifecycle():
    mgr = get_job_manager()
    job_id = mgr.create_job()
    assert job_id.startswith("job_")

    job = mgr.get_job(job_id)
    assert job is not None
    assert job.status == JobStatus.QUEUED
    assert job.progress_pct == 0

    # Advance stage
    job.update_stage(JobStatus.TRANSCRIBING, 40, "Processing audio speech")
    assert job.status == JobStatus.TRANSCRIBING
    assert job.progress_pct == 40

    resp = job.to_response()
    assert resp.job_id == job_id
    assert resp.status == JobStatus.TRANSCRIBING


def test_job_status_api_endpoints():
    mgr = get_job_manager()
    job_id = mgr.create_job()
    token = create_token("test_doc_01", UserRole.DOCTOR, doctor_reg_no="TNMC-54321")
    headers = {"Authorization": f"Bearer {token}"}

    # Query existing job
    res = client.get(f"/api/v1/pipeline/job-status/{job_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["job_id"] == job_id
    assert data["status"] == "QUEUED"

    # Query non-existent job -> 404
    res_404 = client.get("/api/v1/pipeline/job-status/non_existent_job_123", headers=headers)
    assert res_404.status_code == 404


def test_async_submit_audio_endpoint():
    # Submit valid WAV file asynchronously
    file_payload = {"audio": ("sample_consultation.wav", io.BytesIO(SAMPLE_WAV_HEADER), "audio/wav")}
    form_data = {
        "language_code": "hi-IN",
        "doctor_preferred_language": "en-IN",
        "age": "45",
        "gender": "female",
    }

    # H3.5: Unauthenticated submit-audio must return 401
    unauth_res = client.post("/api/v1/pipeline/submit-audio", files=file_payload, data=form_data)
    assert unauth_res.status_code == 401

    # Authenticated call
    patient_token = create_token("patient_test_01", UserRole.PATIENT, phone_number="+919876543210")
    headers = {"Authorization": f"Bearer {patient_token}"}
    file_payload_2 = {"audio": ("sample_consultation.wav", io.BytesIO(SAMPLE_WAV_HEADER), "audio/wav")}
    res = client.post("/api/v1/pipeline/submit-audio", files=file_payload_2, data=form_data, headers=headers)
    assert res.status_code == 202
    data = res.json()
    assert "job_id" in data
    assert data["status"] == "QUEUED"
    assert f"/api/v1/pipeline/job-status/{data['job_id']}" == data["poll_url"]


# -----------------------------------------------------------------------------
# 2. Clinician Telehealth Decisions & Actions
# -----------------------------------------------------------------------------

def test_telehealth_clinical_action_permissions():
    # Unauthenticated -> 401
    res = client.post("/api/v1/consultations/action", json={
        "consultation_id": "c_001",
        "action_type": "CONFIRM_TRIAGE",
        "clinical_notes": "Reviewed and verified triage",
    })
    assert res.status_code == 401

    # Patient token -> 403 Forbidden
    pat_token = create_token(user_id="pat_1", role=UserRole.PATIENT)
    res_pat = client.post(
        "/api/v1/consultations/action",
        headers={"Authorization": f"Bearer {pat_token}"},
        json={
            "consultation_id": "c_001",
            "action_type": "CONFIRM_TRIAGE",
            "clinical_notes": "Reviewed and verified triage",
        },
    )
    assert res_pat.status_code == 403


def test_telehealth_doctor_action_and_history():
    doc_token = create_token(
        user_id="dr_subramaniam",
        role=UserRole.DOCTOR,
        doctor_reg_no="TNMC-77889",
        state_council="Tamil Nadu Medical Council",
    )

    action_payload = {
        "consultation_id": "c_rural_42",
        "action_type": "REFER_TO_DISTRICT_HOSPITAL",
        "clinical_notes": "Severe respiratory distress, oxygen saturation 88%. Needs immediate admission.",
        "new_priority": "HIGH",
        "referral_hospital": "Tirunelveli Medical College Hospital",
        "referral_urgency": "IMMEDIATE",
        "prescriptions": [
            {
                "medication_name": "Salbutamol Nebulization",
                "dosage": "2.5mg",
                "frequency": "Stat",
                "duration": "1 dose",
                "instructions": "Administer oxygen via face mask during transit",
            }
        ],
    }

    # Record action
    res = client.post(
        "/api/v1/consultations/action",
        headers={"Authorization": f"Bearer {doc_token}"},
        json=action_payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["action_id"].startswith("ACT-")
    assert data["doctor_id"] == "dr_subramaniam"
    assert data["doctor_registration_number"] == "TNMC-77889"
    assert data["action_type"] == "REFER_TO_DISTRICT_HOSPITAL"
    assert len(data["prescriptions"]) == 1

    # Retrieve history
    res_hist = client.get(
        "/api/v1/consultations/c_rural_42/actions",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) >= 1
    assert history[0]["consultation_id"] == "c_rural_42"


# -----------------------------------------------------------------------------
# 3. Bilingual Clinical Referral Slip Generation
# -----------------------------------------------------------------------------

def test_clinical_referral_slip_generation():
    doc_token = create_token(
        user_id="dr_meenakshi",
        role=UserRole.DOCTOR,
        doctor_reg_no="KMC-99112",
        state_council="Karnataka Medical Council",
    )

    req_payload = {
        "result": SAMPLE_PIPELINE_RESULT,
        "clinical_notes": "Suspected acute bacterial pneumonia with severe wheeze. Refer to district hospital ICU.",
        "referral_facility": "Kolar District Hospital",
    }

    # Unauthenticated -> 401
    res_unauth = client.post("/api/v1/consultations/referral-slip", json=req_payload)
    assert res_unauth.status_code == 401

    # Doctor authenticated -> 200
    res = client.post(
        "/api/v1/consultations/referral-slip",
        headers={"Authorization": f"Bearer {doc_token}"},
        json=req_payload,
    )
    assert res.status_code == 200
    slip = res.json()
    assert slip["slip_id"].startswith("REF-")
    assert slip["consultation_id"] == "req_pilot_001"
    assert slip["triage_priority"] == "HIGH"
    assert slip["chief_complaint"] == "difficulty breathing"
    assert "difficulty breathing" in slip["symptoms"]
    assert slip["referring_doctor_name"] == "dr_meenakshi"
    assert slip["doctor_registration_number"] == "KMC-99112"
    assert slip["referral_destination"] == "Kolar District Hospital"
    assert "108" in slip["emergency_ambulance_protocol"]
    assert "108" in slip["statutory_disclaimer"]
