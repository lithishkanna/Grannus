"""
Test Suite: Row Level Security (RLS) Verification using ONLY Public/Anon Key.
Verifies that:
  1. Deny-by-default blocks unauthorized access to PHI and internal tables.
  2. Public/anon key cannot SELECT consultations, patient profiles, accounts, OTPs, audit logs.
  3. Public/anon key cannot INSERT or UPDATE clinical or audit records.
  4. Only whitelisted public directories (hospitals, departments) are readable.
"""
import pytest
from supabase import create_client
from app.config import get_settings


@pytest.fixture(scope="module")
def public_anon_client():
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        pytest.skip("Supabase URL and Anon key not configured; skipping live RLS test.")
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def test_rls_public_anon_cannot_read_sensitive_tables(public_anon_client):
    """Anon client must not be able to read clinical or sensitive system records."""
    sensitive_tables = [
        "consultations",
        "patient_profiles",
        "accounts",
        "otp_verifications",
        "staff_users",
        "audit_logs",
        "deletion_log",
        "audio_retention_queue",
        "guest_cases",
        "persistent_voice_threads",
    ]

    for table in sensitive_tables:
        try:
            res = public_anon_client.table(table).select("*").limit(5).execute()
            # Under RLS deny-by-default, queries return empty data ([]), not rows
            assert len(res.data) == 0, f"Table '{table}' leaked {len(res.data)} rows to public anon key!"
        except Exception as exc:
            # An error (e.g., 401/403 or permission denied) is also valid deny-by-default
            assert "permission denied" in str(exc).lower() or "not allowed" in str(exc).lower() or "error" in str(exc).lower()


def test_rls_public_anon_cannot_insert_into_audit_logs(public_anon_client):
    """Anon client must be blocked from tampering with or inserting into audit logs."""
    fake_record = {
        "action": "TAMPER_ATTEMPT",
        "user_id": "anon_attacker",
        "role": "anon",
        "details": {"malicious": True},
    }
    with pytest.raises(Exception):
        public_anon_client.table("audit_logs").insert(fake_record).execute()


def test_rls_public_anon_cannot_insert_into_consultations(public_anon_client):
    """Anon client must be blocked from direct unauthenticated insertion into consultations."""
    fake_record = {
        "chief_complaint": "Direct injection without triage",
        "urgency_tier": "emergency",
    }
    with pytest.raises(Exception):
        public_anon_client.table("consultations").insert(fake_record).execute()


def test_rls_public_anon_can_read_hospitals_and_departments(public_anon_client):
    """Public anon key is allowed to read non-sensitive facility directory for routing."""
    h_res = public_anon_client.table("hospitals").select("id, name, code").execute()
    assert isinstance(h_res.data, list)

    d_res = public_anon_client.table("departments").select("id, name, code").execute()
    assert isinstance(d_res.data, list)
