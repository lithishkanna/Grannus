"""
Acceptance tests for Block H4: Audio Retention (24 Hours) & Deletion.

Verifies:
  - H4.1: Audio files are scheduled with 24-hour expiration by default.
  - H4.2 & H4.3: Retention sweep purges expired audio files and logs immutable deletion events to deletion_log.
  - H4.4: Text clinical transcripts and summaries are preserved after audio purge.
  - H4.7: Stream requests for purged audio files return 404.
"""
import os
import time
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.security.data_retention import get_retention_manager
from app.auth import generate_signed_url
from app.db import (
    save_consultation,
    get_consultation,
    get_deletion_logs,
)

client = TestClient(app)


def test_h4_advance_clock_25_hours_purges_audio_and_preserves_text(tmp_path):
    """H4.1, H4.3, H4.4: 25h clock advance deletes audio file, preserves consultation text, logs deletion."""
    # 1. Create a dummy audio file
    test_audio = tmp_path / "patient_rec_24h.wav"
    test_audio.write_bytes(b"RIFF....WAVEfmt ....data....")
    file_str = str(test_audio)
    assert Path(file_str).exists()

    # 2. Save consultation text in DB
    cid = "consult_audio_retention_01"
    save_consultation(cid, {
        "id": cid,
        "transcript_original": "தலைவலி மற்றும் காய்ச்சல்",
        "transcript_english": "Headache and fever",
        "chief_complaint": "Acute headache with mild fever",
        "urgency_tier": "doctor_soon",
        "audio_file": file_str,
    })

    # 3. Schedule 24-hour deletion
    retention_mgr = get_retention_manager()
    record = retention_mgr.schedule_audio_deletion(file_str, hours=24)
    assert "delete_after" in record

    # 4. Simulate clock advance of 25 hours (set expiry_ts to past)
    retention_mgr._scheduled_deletions[file_str]["expiry_ts"] = time.time() - 3600

    # 5. Run deletion sweep
    purged = retention_mgr.execute_retention_sweep()
    assert file_str in purged
    assert not Path(file_str).exists()

    # 6. Verify consultation text remains fully preserved
    c_after = get_consultation(cid)
    assert c_after is not None
    assert c_after["transcript_english"] == "Headache and fever"
    assert c_after["chief_complaint"] == "Acute headache with mild fever"

    # 7. Verify deletion event logged in deletion_log
    d_logs = get_deletion_logs()
    assert any(log["resource_id"] == file_str for log in d_logs)


def test_h4_deleted_audio_stream_returns_404(tmp_path):
    """H4.7: Stream request for an expired or purged audio URL returns 404."""
    purged_path = str(tmp_path / "expired_audio.wav")
    retention_mgr = get_retention_manager()
    retention_mgr._purged_files.add(purged_path)

    # Generate a signed URL for this purged file
    signed_url = generate_signed_url(purged_path, expires_in_seconds=3600)

    # Calling the media stream endpoint
    res = client.get(signed_url)
    assert res.status_code == 404
    assert "expired" in res.json()["detail"].lower() or "deleted" in res.json()["detail"].lower()
