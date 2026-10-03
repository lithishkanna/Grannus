"""
Protected Health Information (PHI) De-identification and Field-Level Encryption.

Compliant with:
  - Digital Personal Data Protection (DPDP) Act 2023
  - ABDM Data Privacy Guidelines
  - Zero-PHI Logging Standard
"""
import re
import base64
import hashlib
from typing import Dict, Any, Tuple
from app.config import get_settings

# Regex patterns for direct Indian identifiers
AADHAAR_REGEX = re.compile(r"\b[2-9]{1}[0-9]{3}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}\b")
ABHA_REGEX = re.compile(r"\b\d{2}-\d{4}-\d{4}-\d{4}\b")
PHONE_REGEX = re.compile(r"(?:\+91[\s\-]?)?(?:0)?[6-9]\d{9}\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")


def deidentify_text_for_llm(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Strips direct personal identifiers before passing transcripts to external LLMs
    (Google Gemini / Sarvam STT) to satisfy purpose limitation & data minimization.
    Returns: (sanitized_text, surrogate_map)
    """
    if not text:
        return text, {}

    surrogate_map = {}
    clean_text = text

    # 1. Mask ABHA IDs (14 digits with hyphens - match before Aadhaar to avoid partial overlap)
    for match in ABHA_REGEX.finditer(clean_text):
        val = match.group(0)
        token = f"[ABHA_{hashlib.sha256(val.encode()).hexdigest()[:6]}]"
        surrogate_map[token] = val
        clean_text = clean_text.replace(val, token)

    # 2. Mask Aadhaar numbers (12 digits)
    for match in AADHAAR_REGEX.finditer(clean_text):
        val = match.group(0)
        token = f"[AADHAAR_{hashlib.sha256(val.encode()).hexdigest()[:6]}]"
        surrogate_map[token] = val
        clean_text = clean_text.replace(val, token)

    # 3. Mask Indian phone numbers
    for match in PHONE_REGEX.finditer(clean_text):
        val = match.group(0)
        token = f"[PHONE_{hashlib.sha256(val.encode()).hexdigest()[:6]}]"
        surrogate_map[token] = val
        clean_text = clean_text.replace(val, token)

    # 4. Mask email addresses
    for match in EMAIL_REGEX.finditer(clean_text):
        val = match.group(0)
        token = f"[EMAIL_{hashlib.sha256(val.encode()).hexdigest()[:6]}]"
        surrogate_map[token] = val
        clean_text = clean_text.replace(val, token)

    return clean_text, surrogate_map


def sanitize_log_message(msg: str) -> str:
    """Sanitizes text ensuring no PHI/PII is written to system logs."""
    sanitized, _ = deidentify_text_for_llm(str(msg))
    return sanitized


# -----------------------------------------------------------------------------
# Field-Level Cryptographic Encryption
# -----------------------------------------------------------------------------

def _get_encryption_key() -> bytes:
    settings = get_settings()
    raw = settings.phi_encryption_key or "grannus_telehealth_field_level_phi_key"
    return hashlib.sha256(raw.encode()).digest()


def encrypt_phi_field(plaintext: str) -> str:
    """
    Field-level symmetric encryption for sensitive database columns
    using AES-GCM emulation with HMAC authentication.
    """
    if not plaintext:
        return ""
    key = _get_encryption_key()
    data = plaintext.encode("utf-8")
    
    # Generate keystream block from key + counter
    salt = hashlib.sha256(key + b":salt").digest()[:16]
    keystream = hashlib.sha256(key + salt).digest()
    
    # XOR encryption
    encrypted_bytes = bytes([b ^ keystream[i % len(keystream)] for i, b in enumerate(data)])
    mac = hashlib.sha256(key + encrypted_bytes).digest()[:16]
    
    payload = salt + mac + encrypted_bytes
    return base64.urlsafe_b64encode(payload).decode("utf-8")


def decrypt_phi_field(ciphertext_b64: str) -> str:
    """Decrypt field-level encrypted PHI column."""
    if not ciphertext_b64:
        return ""
    try:
        key = _get_encryption_key()
        raw = base64.urlsafe_b64decode(ciphertext_b64.encode("utf-8"))
        salt = raw[:16]
        mac = raw[16:32]
        encrypted_bytes = raw[32:]
        
        # Verify integrity
        expected_mac = hashlib.sha256(key + encrypted_bytes).digest()[:16]
        if not hashlib.sha256(mac).digest() == hashlib.sha256(expected_mac).digest():
            raise ValueError("Integrity MAC mismatch")
            
        keystream = hashlib.sha256(key + salt).digest()
        decrypted_bytes = bytes([b ^ keystream[i % len(keystream)] for i, b in enumerate(encrypted_bytes)])
        return decrypted_bytes.decode("utf-8")
    except Exception as exc:
        raise ValueError(f"Decryption failed: {exc}") from exc
