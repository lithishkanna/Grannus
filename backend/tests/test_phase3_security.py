"""
Unit and Integration Tests for Phase 3: Security, Privacy, and Compliance.

Covers:
  - Role-Based Access Control (RBAC) & Doctor Registration Verification (NMC/State Council)
  - Cryptographic JWT Creation & Tamper Detection
  - Signed Short-Lived Media Streaming URLs
  - Binary Magic Byte Header Inspection & Polyglot/Malware Rejection
  - Path Traversal Filename Sanitization
  - Sliding Window In-Memory Rate Limiter
  - DPDP Act 2023 Multilingual Consent Notices & Explicit Consent Recording
  - PHI De-identification (Aadhaar, ABHA, Phone, Email) for LLM Safe Dispatch
  - Field-Level Symmetric Encryption/Decryption Roundtrip
  - Zero-PHI Log Sanitization
  - 72-Hour Data Retention & Section 12 Statutory Right-to-Erasure
  - CDSCO SaMD Non-Device Declaration & 108/112 Emergency Disclaimers
  - ABDM FHIR R4 Bundle Profile Conformance
  - FastAPI Endpoint Security (Login, Doctor Guard, FHIR Export, Erasure)
"""
import time
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.auth import (
    UserRole,
    AuthenticatedUser,
    validate_doctor_registration,
    create_token,
    verify_token,
    generate_signed_url,
    verify_signed_url,
)
from app.security.input_validation import (
    validate_audio_upload,
    sanitize_filename,
    SecurityValidationError,
)
from app.security.rate_limiter import SlidingWindowRateLimiter
from app.security.phi_protection import (
    deidentify_text_for_llm,
    encrypt_phi_field,
    decrypt_phi_field,
    sanitize_log_message,
)
from app.consent import get_consent_notice, record_patient_consent
from app.security.data_retention import get_retention_manager
from app.regulatory import (
    CDSCO_SAMD_DECLARATION,
    EMERGENCY_DISCLAIMER_TEXT,
    validate_abdm_fhir_bundle,
)

client = TestClient(app)


# -----------------------------------------------------------------------------
# 1. Doctor Registration & Authentication
# -----------------------------------------------------------------------------

def test_doctor_registration_validation():
    # Valid Indian Medical Registration formats
    assert validate_doctor_registration("NMC-123456") is True
    assert validate_doctor_registration("TNMC-98765") is True
    assert validate_doctor_registration("KMC-45678") is True
    assert validate_doctor_registration("MMC-112233") is True
    assert validate_doctor_registration("DMC-99999") is True
    assert validate_doctor_registration("123456") is True

    # Invalid registration formats
    assert validate_doctor_registration("") is False
    assert validate_doctor_registration("   ") is False
    assert validate_doctor_registration("123") is False
    assert validate_doctor_registration("DOC-BAD") is False
    assert validate_doctor_registration("NMC") is False


def test_jwt_creation_verification_and_tamper_detection():
    # Valid doctor token
    token = create_token(
        user_id="doc_001",
        role=UserRole.DOCTOR,
        doctor_reg_no="NMC-123456",
        state_council="Tamil Nadu Medical Council",
    )
    assert isinstance(token, str)
    assert "." in token

    user = verify_token(token)
    assert user.user_id == "doc_001"
    assert user.role == UserRole.DOCTOR
    assert user.is_verified_doctor is True
    assert user.doctor_registration_number == "NMC-123456"

    # Patient token
    pat_token = create_token(user_id="pat_999", role=UserRole.PATIENT)
    pat_user = verify_token(pat_token)
    assert pat_user.user_id == "pat_999"
    assert pat_user.role == UserRole.PATIENT
    assert pat_user.is_verified_doctor is False

    # Tampered token signature
    parts = token.split(".")
    tampered_token = f"{parts[0]}.badsignature123456"
    with pytest.raises(HTTPException) as exc_info:
        verify_token(tampered_token)
    assert exc_info.value.status_code == 401

    # Expired token
    expired_token = create_token(
        user_id="doc_expired",
        role=UserRole.DOCTOR,
        doctor_reg_no="NMC-123456",
        expires_in_seconds=-10,  # Already expired
    )
    with pytest.raises(HTTPException) as exc_info:
        verify_token(expired_token)
    assert exc_info.value.status_code == 401


def test_signed_media_urls():
    file_path = "/recordings/patient_123.wav"
    signed_url = generate_signed_url(file_path, expires_in_seconds=60)
    assert "/api/v1/media/stream" in signed_url
    assert f"file={file_path}" in signed_url
    assert "sig=" in signed_url

    # Parse query params
    import urllib.parse
    parsed = urllib.parse.urlparse(signed_url)
    params = dict(urllib.parse.parse_qsl(parsed.query))

    # Verification passes
    assert verify_signed_url(params["file"], int(params["expires"]), params["sig"]) is True

    # Tampered path fails
    assert verify_signed_url("/recordings/other_patient.wav", int(params["expires"]), params["sig"]) is False

    # Tampered signature fails
    assert verify_signed_url(params["file"], int(params["expires"]), "forged_sig") is False

    # Expired timestamp fails
    assert verify_signed_url(params["file"], int(time.time()) - 100, params["sig"]) is False


# -----------------------------------------------------------------------------
# 2. Input Validation, Magic Bytes, Malware Defense & Filename Sanitization
# -----------------------------------------------------------------------------

def test_input_validation_valid_audio_magic_bytes():
    # Valid WAV container (RIFF....WAVE)
    wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00" + b"\x00" * 100
    valid, fmt = validate_audio_upload(wav_header, "audio.wav")
    assert valid is True
    assert fmt == "wav"

    # Valid WebM container
    webm_header = b"\x1a\x45\xdf\xa3" + b"\x00" * 120
    valid, fmt = validate_audio_upload(webm_header, "voice.webm")
    assert valid is True
    assert fmt == "webm"

    # Valid MP3 container (ID3 tag)
    mp3_header = b"ID3\x03\x00\x00\x00\x00\x00\x76" + b"\x00" * 120
    valid, fmt = validate_audio_upload(mp3_header, "speech.mp3")
    assert valid is True
    assert fmt == "mp3"

    # Valid OGG container
    ogg_header = b"OggS\x00\x02\x00\x00" + b"\x00" * 120
    valid, fmt = validate_audio_upload(ogg_header, "recording.ogg")
    assert valid is True
    assert fmt == "ogg"


def test_input_validation_malicious_binaries_and_scripts():
    # Windows PE executable (MZ header) disguised as WAV
    pe_file = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 120
    with pytest.raises(SecurityValidationError) as exc:
        validate_audio_upload(pe_file, "trojan.wav")
    assert "Malicious file signature detected" in exc.value.detail

    # Linux ELF executable
    elf_file = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 120
    with pytest.raises(SecurityValidationError) as exc:
        validate_audio_upload(elf_file, "exploit.wav")
    assert "Malicious file signature detected" in exc.value.detail

    # Shell script disguised as MP3
    sh_file = b"#!/bin/bash\nrm -rf /" + b"\x00" * 120
    with pytest.raises(SecurityValidationError) as exc:
        validate_audio_upload(sh_file, "script.mp3")
    assert "Malicious file signature detected" in exc.value.detail

    # PHP script
    php_file = b"<?php phpinfo(); ?>" + b"\x00" * 120
    with pytest.raises(SecurityValidationError) as exc:
        validate_audio_upload(php_file, "webshell.ogg")
    assert "Malicious file signature detected" in exc.value.detail

    # Embedded Script
    html_file = b"<script>alert('xss')</script>" + b"\x00" * 120
    with pytest.raises(SecurityValidationError) as exc:
        validate_audio_upload(html_file, "xss.webm")
    assert "Malicious file signature detected" in exc.value.detail

    # Truncated file (<100 bytes)
    with pytest.raises(SecurityValidationError) as exc:
        validate_audio_upload(b"RIFFWAVE", "tiny.wav")
    assert "empty or corrupted" in exc.value.detail

    # File exceeding max_bytes
    with pytest.raises(HTTPException) as exc:
        validate_audio_upload(b"RIFF" + b"WAVE" + b"\x00" * 200, "large.wav", max_bytes=150)
    assert exc.value.status_code == 413


def test_sanitize_filename_path_traversal():
    assert sanitize_filename("../../etc/passwd.wav") == "passwd.wav"
    assert sanitize_filename("..\\..\\windows\\system32\\cmd.wav") == "cmd.wav"
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("normal_audio.wav") == "normal_audio.wav"
    assert sanitize_filename("") == "patient_audio.wav"
    assert sanitize_filename(None) == "patient_audio.wav"


# -----------------------------------------------------------------------------
# 3. Rate Limiting
# -----------------------------------------------------------------------------

def test_sliding_window_rate_limiter():
    limiter = SlidingWindowRateLimiter(requests_per_minute=5, burst_limit=3)

    # 3 requests allowed (within burst limit)
    for _ in range(3):
        allowed, remaining, _ = limiter.is_allowed("127.0.0.1")
        assert allowed is True

    # 4th burst request in rapid succession rejected
    allowed, remaining, retry_after = limiter.is_allowed("127.0.0.1")
    assert allowed is False
    assert retry_after > 0


# -----------------------------------------------------------------------------
# 4. PHI Protection & Field-Level Encryption
# -----------------------------------------------------------------------------

def test_phi_deidentification_indian_identifiers():
    raw_text = (
        "Patient Ramesh, Aadhaar 2345 6789 0123, ABHA 12-3456-7890-1234, "
        "phone +91 9876543210, email ramesh@example.com reports severe chest pain."
    )
    sanitized, surrogates = deidentify_text_for_llm(raw_text)

    # Identifiers must be removed
    assert "2345 6789 0123" not in sanitized
    assert "12-3456-7890-1234" not in sanitized
    assert "+91 9876543210" not in sanitized
    assert "ramesh@example.com" not in sanitized

    # Medical context must remain intact
    assert "severe chest pain" in sanitized
    assert "[AADHAAR_" in sanitized
    assert "[ABHA_" in sanitized
    assert "[PHONE_" in sanitized
    assert "[EMAIL_" in sanitized
    assert len(surrogates) == 4


def test_phi_field_level_encryption_roundtrip():
    original_phi = "Aadhaar: 4567 8901 2345, Diagnosis: Acute Myocardial Infarction"
    ciphertext = encrypt_phi_field(original_phi)
    assert ciphertext != original_phi
    assert isinstance(ciphertext, str)

    decrypted = decrypt_phi_field(ciphertext)
    assert decrypted == original_phi

    # Tampered ciphertext fails decryption
    tampered = ciphertext[:-4] + "AAAA"
    with pytest.raises(ValueError):
        decrypt_phi_field(tampered)


def test_zero_phi_log_sanitization():
    raw_log = "Processing consultation for user with phone 9876543210 and Aadhaar 9876 5432 1098"
    safe_log = sanitize_log_message(raw_log)
    assert "9876543210" not in safe_log
    assert "9876 5432 1098" not in safe_log
    assert "[PHONE_" in safe_log
    assert "[AADHAAR_" in safe_log


# -----------------------------------------------------------------------------
# 5. Consent & Data Retention
# -----------------------------------------------------------------------------

def test_multilingual_dpdp_consent_notices():
    languages = ["en-IN", "ta-IN", "hi-IN", "te-IN"]
    for lang in languages:
        notice_data = get_consent_notice(lang)
        assert notice_data["version"] == "2023.1-DPDP"
        notice = notice_data["notice"]
        assert "purpose" in notice
        assert "retention" in notice
        assert "72" in notice["retention"]
        assert "rights" in notice
        assert "emergency_disclaimer" in notice
        assert "108" in notice["emergency_disclaimer"]


def test_patient_consent_recording():
    record = record_patient_consent(
        patient_id="patient_abc_123",
        language_code="ta-IN",
        client_ip="192.168.1.50",
        explicit_consent=True,
    )
    assert record.patient_id == "patient_abc_123"
    assert record.explicit_consent_granted is True
    assert record.language_code == "ta-IN"
    assert record.retention_period_hours == 72
    assert record.consent_id.startswith("CONSENT-")

    # Reject without explicit affirmation
    with pytest.raises(ValueError):
        record_patient_consent(
            patient_id="patient_abc_123",
            language_code="ta-IN",
            client_ip="192.168.1.50",
            explicit_consent=False,
        )


def test_data_retention_and_statutory_erasure():
    retention_mgr = get_retention_manager()
    retention_mgr.schedule_audio_deletion("test_audio_path.wav", hours=72)
    assert "test_audio_path.wav" in retention_mgr._scheduled_deletions

    # Execute statutory Right to Erasure under Section 12 DPDP Act
    erasure_res = retention_mgr.process_patient_erasure(
        patient_id="pat_delete_me",
        reason="Patient withdrew consent",
    )
    assert erasure_res["status"] == "erasure_complete"
    assert erasure_res["statutory_act"] == "Digital Personal Data Protection Act 2023 (Section 12)"
    assert retention_mgr.is_patient_erased("pat_delete_me") is True


# -----------------------------------------------------------------------------
# 6. Regulatory Positioning & ABDM FHIR Profile
# -----------------------------------------------------------------------------

def test_regulatory_samd_and_emergency_disclaimers():
    assert CDSCO_SAMD_DECLARATION["classification"] == "Non-Device Clinical Decision Support (CDS) Software"
    assert "CDSCO Medical Device Rules 2017" in CDSCO_SAMD_DECLARATION["regulatory_basis"]
    assert "108" in EMERGENCY_DISCLAIMER_TEXT
    assert "112" in EMERGENCY_DISCLAIMER_TEXT


def test_abdm_fhir_r4_bundle_validation():
    # Valid ABDM bundle
    valid_bundle = {
        "resourceType": "Bundle",
        "type": "document",
        "entry": [
            {"resource": {"resourceType": "Composition", "title": "Clinical Summary"}},
            {"resource": {"resourceType": "Patient", "id": "p1"}},
            {"resource": {"resourceType": "Condition", "clinicalStatus": "active"}},
        ],
    }
    is_valid, errors = validate_abdm_fhir_bundle(valid_bundle)
    assert is_valid is True
    assert len(errors) == 0

    # Non-compliant bundle missing Composition
    bad_bundle = {
        "resourceType": "Bundle",
        "type": "document",
        "entry": [{"resource": {"resourceType": "Patient"}}],
    }
    is_valid, errors = validate_abdm_fhir_bundle(bad_bundle)
    assert is_valid is False
    assert any("Composition" in e for e in errors)


# -----------------------------------------------------------------------------
# 7. FastAPI Endpoint Security & Auth Integration
# -----------------------------------------------------------------------------

def test_auth_login_endpoint():
    # Valid doctor login
    res = client.post("/api/v1/auth/login", json={
        "user_id": "doc_rajan",
        "role": "doctor",
        "doctor_registration_number": "TNMC-54321",
        "state_medical_council": "Tamil Nadu Medical Council",
    })
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["role"] == "doctor"
    assert data["is_verified_doctor"] is True

    # Doctor login with invalid registration rejected
    res_bad = client.post("/api/v1/auth/login", json={
        "user_id": "fake_doc",
        "role": "doctor",
        "doctor_registration_number": "BAD",
    })
    assert res_bad.status_code == 400


def test_consent_api_endpoints():
    # Fetch notice
    res = client.get("/api/v1/consent/notice?language_code=hi-IN")
    assert res.status_code == 200
    data = res.json()
    assert data["language"] == "hi-IN"
    assert "मरीज सहमति" in data["notice"]["title"]

    # Record consent
    res = client.post("/api/v1/consent/record", json={
        "patient_id": "pat_hi_1",
        "language_code": "hi-IN",
        "explicit_consent": True,
    })
    assert res.status_code == 200
    resp_data = res.json()
    assert resp_data["consent_id"].startswith("CONSENT-")
    assert resp_data["explicit_consent_granted"] is True


def test_protected_doctor_endpoints():
    # Unauthenticated voice-prescription call -> 401
    res = client.post("/api/v1/doctor/voice-prescription")
    assert res.status_code == 401

    # Patient token calling doctor voice-prescription -> 403 Forbidden
    pat_token = create_token(user_id="pat_1", role=UserRole.PATIENT)
    res = client.post(
        "/api/v1/doctor/voice-prescription",
        headers={"Authorization": f"Bearer {pat_token}"},
    )
    assert res.status_code == 403

    # Sample pipeline result payload for FHIR export
    sample_pipeline_payload = {
        "request_id": "req_fhir_001",
        "patient_input": {
            "language": "hi-IN",
            "transcript_original": "गंभीर छाती में दर्द",
            "transcript_english": "severe chest pain",
            "confidence": 0.95,
        },
        "clinical_summary": {
            "chief_complaint": "chest pain",
            "symptoms": [
                {
                    "name": "chest pain",
                    "raw_text": "गंभीर छाती में दर्द",
                    "severity": "severe",
                    "negated": False,
                    "confidence": 0.95,
                }
            ],
            "red_flags": [],
        },
        "safety_screening": {
            "emergency_triggered": True,
            "red_flags": [
                {
                    "symptom": "chest pain",
                    "severity": "critical",
                    "reason": "Cardiac emergency risk",
                    "action": "Immediate ECG & emergency referral",
                    "triggered_by": "deterministic_rule",
                }
            ],
            "contradictions": [],
        },
        "priority": {
            "level": "HIGH",
            "confidence": 0.99,
            "rationale": "Critical cardiac red flag",
            "action": "Immediate hospital transfer",
        },
        "clinician_review_required": True,
        "disclaimer": "AI-generated structured summary",
    }

    # Unauthenticated FHIR export -> 401
    res_fhir_unauth = client.post("/api/v1/export/fhir", json=sample_pipeline_payload)
    assert res_fhir_unauth.status_code == 401

    # Patient token calling FHIR export -> 403
    res_fhir_pat = client.post(
        "/api/v1/export/fhir",
        headers={"Authorization": f"Bearer {pat_token}"},
        json=sample_pipeline_payload,
    )
    assert res_fhir_pat.status_code == 403

    # Doctor token calling FHIR export -> 200
    doc_token = create_token(
        user_id="doc_rajan",
        role=UserRole.DOCTOR,
        doctor_reg_no="TNMC-54321",
    )
    res_fhir_doc = client.post(
        "/api/v1/export/fhir",
        headers={"Authorization": f"Bearer {doc_token}"},
        json=sample_pipeline_payload,
    )
    assert res_fhir_doc.status_code == 200
    bundle = res_fhir_doc.json()
    assert bundle["resourceType"] == "Bundle"
    assert any(e.get("resource", {}).get("resourceType") == "Composition" for e in bundle.get("entry", []))


def test_statutory_erasure_endpoint():
    pat_token = create_token(user_id="pat_test_erase", role=UserRole.PATIENT)
    
    # Unauthenticated -> 401
    res_unauth = client.post("/api/v1/patient/request-erasure", json={
        "patient_id": "pat_test_erase",
        "reason": "Revoking consent",
    })
    assert res_unauth.status_code == 401

    # Authenticated -> 200
    res = client.post(
        "/api/v1/patient/request-erasure",
        headers={"Authorization": f"Bearer {pat_token}"},
        json={
            "patient_id": "pat_test_erase",
            "reason": "Revoking consent under DPDP Act 2023",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "erasure_complete"
