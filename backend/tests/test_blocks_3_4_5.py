"""
Tests for Clinical Urgency Tiers, Approved Home Remedy Library, Follow-Up Loop,
One-Tap Escalation, and Translation Safety / Voice Threads.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    UrgencyTier,
    PriorityLevel,
    StructuredMedicalSummary,
    Symptom,
    SafetyScreening,
    SafetyRedFlag,
    ClinicalSummary,
)
from app.priority import determine_urgency_tier, assess_priority
from app.remedy_library import (
    APPROVED_REMEDY_LIBRARY,
    find_approved_remedy,
    get_approved_home_remedy_guidance,
)
from app.follow_up import FollowUpManager, get_follow_up_manager
from app.voice_threads import VoiceThreadManager, get_voice_thread_manager


@pytest.fixture
def client():
    return TestClient(app)


# -----------------------------------------------------------------------------
# Block 3: Urgency Tiers & Approved Remedy Library Tests
# -----------------------------------------------------------------------------

def test_urgency_tier_emergency_on_critical_flags():
    """Critical safety red flags must map strictly to UrgencyTier.EMERGENCY."""
    safety = SafetyScreening(
        red_flags=[
            SafetyRedFlag(
                potential_red_flag=True,
                symptom="chest pain",
                reason="Chest pain reported",
                severity="critical",
            )
        ],
        has_critical_flags=True,
        override_priority=True,
    )
    tier, fu_days = determine_urgency_tier(
        PriorityLevel.HIGH,
        emergency_override=True,
        safety_screening=safety,
    )
    assert tier == UrgencyTier.EMERGENCY
    assert fu_days == 0


def test_urgency_tier_doctor_today_on_high():
    """Non-critical HIGH priority cases must yield DOCTOR_TODAY."""
    tier, fu_days = determine_urgency_tier(
        PriorityLevel.HIGH,
        emergency_override=False,
    )
    assert tier == UrgencyTier.DOCTOR_TODAY
    assert fu_days == 1


def test_urgency_tier_doctor_soon_on_medium():
    """MEDIUM priority cases must yield DOCTOR_SOON with 2-day follow-up."""
    tier, fu_days = determine_urgency_tier(
        PriorityLevel.MEDIUM,
        emergency_override=False,
        score=20.0,
    )
    assert tier == UrgencyTier.DOCTOR_SOON
    assert fu_days == 2


def test_urgency_tier_self_care_on_low():
    """LOW priority cases must yield SELF_CARE with 3-day follow-up."""
    tier, fu_days = determine_urgency_tier(
        PriorityLevel.LOW,
        emergency_override=False,
        score=2.0,
    )
    assert tier == UrgencyTier.SELF_CARE
    assert fu_days == 3


def test_approved_remedy_library_completeness():
    """Every approved remedy in the library must have explicit seek_doctor_if criteria."""
    assert len(APPROVED_REMEDY_LIBRARY) >= 5
    for key, remedy in APPROVED_REMEDY_LIBRARY.items():
        assert len(remedy.care_steps) >= 3
        assert len(remedy.monitoring_signs) >= 2
        assert len(remedy.seek_doctor_if) >= 3, f"Remedy {key} missing mandatory escalation triggers"
        # Check translated criteria existence
        assert "ta-IN" in remedy.translations
        assert "hi-IN" in remedy.translations
        assert "te-IN" in remedy.translations


def test_approved_remedy_lookup_and_translation():
    """Symptoms matching approved categories return localized guidance without LLM hallucination."""
    summary = ClinicalSummary(
        chief_complaint="mild cough and throat irritation",
        symptoms=[
            Symptom(name="cough"),
            Symptom(name="sore throat"),
        ],
    )
    # Test Tamil translation delivery
    guidance = get_approved_home_remedy_guidance(summary, patient_language="ta-IN")
    assert guidance is not None
    assert len(guidance.care_steps) >= 3
    assert len(guidance.seek_doctor_if) >= 3
    # Check that Tamil text is populated in care steps and doctor triggers
    tamil_care = any(step.translated_step for step in guidance.care_steps if step.translated_step)
    assert tamil_care is True
    assert guidance.translated_seek_doctor_if is not None
    assert len(guidance.translated_seek_doctor_if) >= 3


# -----------------------------------------------------------------------------
# Block 4: Follow-up Check-in & One-Tap Escalation Tests
# -----------------------------------------------------------------------------

def test_follow_up_progression_ladder():
    """
    Test exact one-tap 'I feel worse' escalation sequence:
    self_care -> doctor_soon -> doctor_today -> emergency
    """
    mgr = FollowUpManager()
    cid = "test-consult-escalate-001"
    mgr.register_consultation(cid, urgency_tier=UrgencyTier.SELF_CARE, follow_up_days=3)

    # Escalation 1: self_care -> doctor_soon
    resp1 = mgr.escalate_tier(cid)
    assert resp1.previous_tier == UrgencyTier.SELF_CARE
    assert resp1.new_tier == UrgencyTier.DOCTOR_SOON
    assert resp1.is_escalated is True

    # Escalation 2: doctor_soon -> doctor_today
    resp2 = mgr.escalate_tier(cid)
    assert resp2.previous_tier == UrgencyTier.DOCTOR_SOON
    assert resp2.new_tier == UrgencyTier.DOCTOR_TODAY
    assert resp2.is_escalated is True

    # Escalation 3: doctor_today -> emergency
    resp3 = mgr.escalate_tier(cid)
    assert resp3.previous_tier == UrgencyTier.DOCTOR_TODAY
    assert resp3.new_tier == UrgencyTier.EMERGENCY
    assert resp3.is_escalated is True
    assert "108" in resp3.emergency_call_numbers

    # Escalation 4: emergency -> stays emergency with immediate instructions
    resp4 = mgr.escalate_tier(cid)
    assert resp4.new_tier == UrgencyTier.EMERGENCY


def test_follow_up_check_in_reporting_worse():
    """A scheduled check-in with status 'worse' automatically triggers tier escalation."""
    mgr = FollowUpManager()
    cid = "test-consult-checkin-002"
    mgr.register_consultation(cid, urgency_tier=UrgencyTier.SELF_CARE)

    resp = mgr.record_check_in(cid, status="worse", notes="Fever increased and breathing is uncomfortable")
    assert resp.is_escalated is True
    assert resp.new_tier == UrgencyTier.DOCTOR_SOON


def test_follow_up_check_in_improving_or_same():
    """A check-in with 'improving' or 'same' retains the current tier without escalation."""
    mgr = FollowUpManager()
    cid = "test-consult-checkin-003"
    mgr.register_consultation(cid, urgency_tier=UrgencyTier.DOCTOR_SOON)

    resp_same = mgr.record_check_in(cid, status="same")
    assert resp_same.is_escalated is False
    assert resp_same.new_tier == UrgencyTier.DOCTOR_SOON

    resp_imp = mgr.record_check_in(cid, status="improving")
    assert resp_imp.is_escalated is False
    assert resp_imp.new_tier == UrgencyTier.DOCTOR_SOON


# -----------------------------------------------------------------------------
# Block 5: Voice Threads & Translation Safety Tests
# -----------------------------------------------------------------------------

def test_voice_threads_and_back_translation():
    """Verify bilingual voice thread messaging and back-translation preservation."""
    vt_mgr = VoiceThreadManager()
    cid = "test-consult-thread-004"

    # 1. Doctor sends message in English with Tamil translation & back-translation
    doc_msg = vt_mgr.add_message(
        consultation_id=cid,
        sender="doctor",
        original_text="Take plenty of fluids and rest. Avoid spicy food.",
        translated_text="நிறைய திரவங்களை குடித்து ஓய்வெடுக்கவும். காரமான உணவைத் தவிர்க்கவும்.",
        original_language="en-IN",
        target_language="ta-IN",
        back_translated_text="Drink plenty of fluids and rest. Avoid spicy food.",
    )
    assert doc_msg.sender == "doctor"
    assert doc_msg.back_translated_text is not None

    # 2. Patient replies in Tamil with English translation
    pat_msg = vt_mgr.add_message(
        consultation_id=cid,
        sender="patient",
        original_text="எனக்கு தலைவலி அதிகமாக உள்ளது.",
        translated_text="I have a severe headache.",
        original_language="ta-IN",
        target_language="en-IN",
        back_translated_text="எனக்கு கடுமையான தலைவலி உள்ளது.",
    )
    assert pat_msg.sender == "patient"

    # 3. Retrieve thread
    thread = vt_mgr.get_thread(cid)
    assert thread is not None
    assert len(thread.messages) == 2
    assert thread.messages[0].sender == "doctor"
    assert thread.messages[1].sender == "patient"


# -----------------------------------------------------------------------------
# End-to-End API Endpoints Tests
# -----------------------------------------------------------------------------

def test_api_check_in_endpoint(client):
    """Test POST /api/v1/consultations/{id}/check-in endpoint."""
    from app.auth import create_token, UserRole
    token = create_token("test_pat_01", UserRole.PATIENT, phone_number="+919876543210")
    headers = {"Authorization": f"Bearer {token}"}
    cid = "api-consult-001"
    # Call check-in with 'worse'
    response = client.post(
        f"/api/v1/consultations/{cid}/check-in",
        json={"status": "worse", "notes": "Cough has become more severe"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["consultation_id"] == cid
    assert data["status"] == "worse"
    assert data["is_escalated"] is True
    assert data["new_tier"] == "doctor_soon"


def test_api_one_tap_escalate_endpoint(client):
    """Test POST /api/v1/consultations/{id}/escalate endpoint."""
    from app.auth import create_token, UserRole
    token = create_token("test_pat_01", UserRole.PATIENT, phone_number="+919876543210")
    headers = {"Authorization": f"Bearer {token}"}
    cid = "api-consult-002"
    # Call escalate
    response = client.post(
        f"/api/v1/consultations/{cid}/escalate",
        json={"reason": "Patient tapped 'I Feel Worse'"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_escalated"] is True
    assert data["previous_tier"] == "self_care"
    assert data["new_tier"] == "doctor_soon"


def test_api_voice_thread_endpoint(client):
    """Test GET /api/v1/consultations/{id}/thread endpoint."""
    from app.auth import create_token, UserRole
    token = create_token("test_pat_01", UserRole.PATIENT, phone_number="+919876543210")
    headers = {"Authorization": f"Bearer {token}"}
    cid = "api-consult-003"
    response = client.get(f"/api/v1/consultations/{cid}/thread", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["consultation_id"] == cid
    assert isinstance(data["messages"], list)
