"""
Input Validation, Magic Byte Signature Inspection, and Malware Defense for Grannus.

Ensures uploads are legitimate audio files (WAV, MP3, WebM, OGG/Opus, M4A)
and prevents polyglot files, hidden executables, shell scripts, or path traversal attacks.
"""
import re
from pathlib import Path
from typing import Tuple, Optional
from fastapi import HTTPException, status

# Audio magic byte signatures
MAGIC_BYTES = {
    "wav": [b"RIFF"],                        # RIFF....WAVE
    "mp3": [b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID3"],
    "webm": [b"\x1a\x45\xdf\xa3"],           # EBML ID for WebM/MKV
    "ogg": [b"OggS"],                        # Ogg container
    "m4a": [b"ftypM4A", b"ftypmp42", b"ftypisom"],
}

# Dangerous executable / script magic signatures to immediately reject
MALICIOUS_SIGNATURES = [
    b"MZ",               # Windows PE executable / DLL
    b"\x7fELF",          # Linux ELF binary
    b"#!/bin/",         # Shell script
    b"<?php",            # PHP script
    b"<script",          # Embedded HTML script
    b"eval(",            # JavaScript/Python eval
]

SAFE_FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


class SecurityValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def sanitize_filename(filename: Optional[str]) -> str:
    """Sanitize filename to prevent directory traversal attacks."""
    if not filename:
        return "patient_audio.wav"
    
    clean_name = Path(filename).name.strip()
    if not SAFE_FILENAME_REGEX.match(clean_name) or ".." in clean_name:
        # Fallback to safe alphanumeric name
        stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", Path(clean_name).stem)
        ext = Path(clean_name).suffix.lower()
        if ext not in [".wav", ".mp3", ".webm", ".ogg", ".m4a"]:
            ext = ".wav"
        return f"{stem}{ext}"
    return clean_name


def validate_audio_upload(audio_bytes: bytes, filename: str, max_bytes: int = 25 * 1024 * 1024) -> Tuple[bool, str]:
    """
    Performs multi-layered security inspection on uploaded audio:
      1. Size checks (minimum 100 bytes, maximum max_bytes)
      2. Malware / executable header rejection
      3. Magic byte signature verification
    """
    if not audio_bytes or len(audio_bytes) < 100:
        raise SecurityValidationError("Upload rejected: Audio file is empty or corrupted (<100 bytes).")

    if len(audio_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload rejected: File size ({len(audio_bytes)} bytes) exceeds safety maximum ({max_bytes} bytes).",
        )

    # Check for known malicious signatures
    header_start = audio_bytes[:64]
    for mal_sig in MALICIOUS_SIGNATURES:
        if mal_sig in header_start:
            raise SecurityValidationError("Security Alert: Malicious file signature detected. Upload blocked.")

    # Validate audio magic bytes
    ext = Path(filename).suffix.lower().lstrip(".")
    is_valid_format = False
    detected_format = "unknown"

    # Check RIFF/WAV
    if audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        is_valid_format = True
        detected_format = "wav"
    # Check WebM
    elif audio_bytes[:4] == b"\x1a\x45\xdf\xa3":
        is_valid_format = True
        detected_format = "webm"
    # Check Ogg
    elif audio_bytes[:4] == b"OggS":
        is_valid_format = True
        detected_format = "ogg"
    # Check MP3
    elif any(audio_bytes.startswith(sig) for sig in MAGIC_BYTES["mp3"]):
        is_valid_format = True
        detected_format = "mp3"
    # Check M4A / MP4 container
    elif any(sig in audio_bytes[4:16] for sig in MAGIC_BYTES["m4a"]):
        is_valid_format = True
        detected_format = "m4a"

    if not is_valid_format:
        raise SecurityValidationError(
            f"Upload rejected: Unsupported audio container. Must be a valid WAV, MP3, WebM, or OGG file."
        )

    return True, detected_format
