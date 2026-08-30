"""
Wrapper around Sarvam AI's Speech-to-Text REST endpoint (Saaras model).

Docs: https://docs.sarvam.ai/api-reference/speech-to-text/transcribe

We call the endpoint twice with the same audio bytes:
  1. mode="transcribe" -> native-language transcript (for the doctor to
     verify against what the patient actually said)
  2. mode="translate"  -> English transcript (fed into Gemini extraction)

This keeps the provider swap-out point (Sarvam -> Whisper/IndicConformer
later) isolated to this single file. Nothing outside this module should
know Sarvam's request/response shape.
"""
import asyncio
import httpx
import logging

from app.config import get_settings
from app.schemas import TranscriptionResult

logger = logging.getLogger('rural_care.sarvam_stt')

STT_ENDPOINT = "/speech-to-text"


class SarvamSTTError(RuntimeError):
    """Raised when Sarvam's STT API returns an error or unusable response."""


async def _call_sarvam_stt(
    client: httpx.AsyncClient,
    audio_bytes: bytes,
    filename: str,
    mode: str,
    language_code: str,
) -> dict:
    settings = get_settings()

    files = {"file": (filename, audio_bytes)}
    data = {
        "model": settings.sarvam_stt_model,
        "mode": mode,  # "transcribe" | "translate"
        "language_code": language_code,  # "unknown" lets Sarvam auto-detect
    }
    headers = {"api-subscription-key": settings.sarvam_api_key}

    max_attempts = settings.sarvam_retry_attempts
    for attempt in range(max_attempts):
        try:
            response = await client.post(
                f"{settings.sarvam_base_url}{STT_ENDPOINT}",
                files=files,
                data=data,
                headers=headers,
                timeout=settings.sarvam_timeout_seconds,
            )

            if response.status_code in (429, 500, 503):
                if attempt < max_attempts - 1:
                    logger.warning(f"Sarvam STT {mode} failed with status {response.status_code}. Retrying ({attempt + 1}/{max_attempts})...")
                    await asyncio.sleep(2 ** attempt)
                    continue
                
            if response.status_code != 200:
                raise SarvamSTTError(
                    f"Sarvam STT failed ({response.status_code}) mode={mode}: {response.text}"
                )

            return response.json()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt < max_attempts - 1:
                logger.warning(f"Sarvam STT {mode} connection error ({e}). Retrying ({attempt + 1}/{max_attempts})...")
                await asyncio.sleep(2 ** attempt)
            else:
                raise SarvamSTTError(f"Sarvam STT failed after {max_attempts} attempts due to network errors: {e}")
    raise SarvamSTTError(f"Sarvam STT failed after {max_attempts} attempts.")


async def transcribe_and_translate(
    audio_bytes: bytes,
    filename: str,
    language_code: str = "unknown",
) -> TranscriptionResult:
    """
    Run the patient's audio through Sarvam Saaras twice (native + English)
    and return both, plus the detected language.

    language_code: BCP-47 code (e.g. "ta-IN") if the patient selected a
    language in the UI, or "unknown" to let Sarvam auto-detect.
    """
    if not audio_bytes:
        raise SarvamSTTError("No audio bytes received.")

    async with httpx.AsyncClient() as client:
        native = await _call_sarvam_stt(
            client, audio_bytes, filename, mode="transcribe", language_code=language_code
        )
        
        native_transcript = native.get("transcript", "")
        if not native_transcript.strip():
            raise SarvamSTTError("No speech detected in audio — transcript is empty.")
        if len(native_transcript.strip()) < 5:
            logger.warning(f"Native transcript is suspiciously short: '{native_transcript}'")

        # Re-use the detected language for the translate call so both
        # requests agree on what language was actually spoken.
        if language_code == "unknown":
            translate_lang = native.get("language_code") or "unknown"
        else:
            translate_lang = language_code
            
        english = await _call_sarvam_stt(
            client, audio_bytes, filename, mode="translate", language_code=translate_lang
        )
        
        english_transcript = english.get("transcript", "")
        if not english_transcript.strip() and native_transcript.strip():
            logger.warning("English transcript is empty but native transcript is not.")
        elif english_transcript.strip() and len(english_transcript.strip()) < 5:
            logger.warning(f"English transcript is suspiciously short: '{english_transcript}'")

    return TranscriptionResult(
        transcript_original=native_transcript,
        transcript_english=english_transcript,
        language_code=native.get("language_code"),
        language_probability=native.get("language_probability"),
    )
