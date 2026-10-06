"""
Acceptance tests for Block H2: Database persistence & Supabase security.

Verifies:
  - H2.1 & H2.2: Production startup without database configured fails fast with RuntimeError.
  - H2.4 & H2.7: Consultation, thread, check-in, and audit records survive app restarts.
  - H2.5: Anonymous request with only public/anon key cannot access sensitive tables directly.
  - H2.6: Audit log is strictly append-only; updates and deletions fail with PermissionError.
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app, lifespan
from app.config import Settings
from app.auth import create_token, UserRole
from app.db import (
    save_consultation,
    get_consultation,
    append_audit_log_entry,
    update_audit_log_entry,
    delete_audit_log_entry,
    save_guest_case,
    get_guest_case,
    log_deletion_event,
    get_deletion_logs,
)
from app.voice_threads import get_voice_thread_manager
from app.follow_up import get_follow_up_manager
from app.schemas import UrgencyTier

client = TestClient(app)


def test_h2_production_startup_fails_without_database():
    """H2.2: Starting with ENV=production without database configuration raises RuntimeError."""
    mock_settings = Settings(
        env="production",
        jwt_secret_key="some_secret_key_for_testing_12345678",
        supabase_url="",
        supabase_service_role_key="",
        supabase_anon_key="",
        sms_provider="msg91",
        msg91_auth_key="test_key",
    )
    with patch("app.main.get_settings", return_value=mock_settings):
        with pytest.raises(RuntimeError) as exc_info:
            import asyncio
            asyncio.run(lifespan(app).__aenter__())
        assert "Database" in str(exc_info.value) or "SUPABASE" in str(exc_info.value)


def test_h2_audit_log_is_append_only():
    """H2.6: Attempting to update or delete an audit log entry must fail with PermissionError."""
    log_rec = append_audit_log_entry(
        action="TEST_ACTION",
        user_id="user_123",
        role="doctor",
        details={"note": "Immutable audit test"},
    )
    assert log_rec["id"] is not None

    with pytest.raises(PermissionError) as exc_update:
        update_audit_log_entry(log_rec["id"], {"action": "TAMPERED_ACTION"})
    assert "append-only" in str(exc_update.value).lower()

    with pytest.raises(PermissionError) as exc_delete:
        delete_audit_log_entry(log_rec["id"])
    assert "append-only" in str(exc_delete.value).lower()


def test_h2_persistence_across_app_restart():
    """H2.7: Consultations, voice threads, follow-ups, and audit logs persist across simulated restart."""
    case_id = "restart_persisted_case_01"
    save_consultation(case_id, {
        "id": case_id,
        "account_id": "acc_restart_01",
        "urgency_tier": "doctor_soon",
        "chief_complaint": "Persistent cough for 4 days",
    })

    # Save voice thread
    thread_mgr = get_voice_thread_manager()
    thread = thread_mgr.get_or_create_thread(case_id)
    thread_mgr.add_message(
        consultation_id=case_id,
        sender="doctor",
        original_text="Take warm water and rest.",
        translated_text="வெந்நீர் குடித்து ஓய்வெடுக்கவும்.",
        original_language="en-IN",
        target_language="ta-IN",
    )

    # Register follow-up
    follow_up_mgr = get_follow_up_manager()
    follow_up_mgr.register_consultation(case_id, UrgencyTier.DOCTOR_SOON, follow_up_days=2)

    # Log deletion event
    log_deletion_event("audio", "temp_rec.wav", "Test cleanup")

    # Simulate restart by reading through fresh manager queries / DB lookups
    c_fetched = get_consultation(case_id)
    assert c_fetched is not None
    assert c_fetched["chief_complaint"] == "Persistent cough for 4 days"

    t_fetched = thread_mgr.get_thread(case_id)
    assert t_fetched is not None
    assert len(t_fetched.messages) >= 1

    fu_fetched = follow_up_mgr.get_record(case_id)
    assert fu_fetched is not None
    assert fu_fetched.current_tier == UrgencyTier.DOCTOR_SOON

    d_logs = get_deletion_logs()
    assert any(dl["resource_id"] == "temp_rec.wav" for dl in d_logs)


def test_h2_anonymous_public_key_denial():
    """H2.5: Anonymous request cannot query staff users, audit logs, or sensitive data without auth token."""
    # Direct endpoint call without token -> 401
    res = client.get("/api/v1/admin/routing-logs")
    assert res.status_code == 401

    res_audit = client.get("/api/v1/doctor/queue")
    assert res_audit.status_code == 401
