"""
Text-to-Speech (TTS) service using Sarvam AI (bulbul:v1 model).

Converts clinical summary text into spoken audio in the target language
(e.g., doctor's preferred language or patient's native language).
"""
import asyncio
import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger("rural_care.sarvam_tts")

TTS_ENDPOINT = "/text-to-speech"

# Default speakers available per language in Sarvam bulbul:v1
DEFAULT_SPEAKER = "kavya"

class SarvamTTSError(RuntimeError):
    """Raised when Sarvam TTS fails."""


async def text_to_speech(
    text: str,
    target_language_code: str,
    speaker: str = DEFAULT_SPEAKER,
) -> Optional[str]:
    """
    Generate audio for given text in target language using Sarvam TTS.

    Args:
        text: Text to convert to speech.
        target_language_code: BCP-47 language code (e.g., 'ta-IN', 'hi-IN', 'en-IN').
        speaker: Voice speaker name (default 'kavya').

    Returns:
        Base64-encoded WAV audio string, or None if TTS fails/unsupported.
    """
    if not text or not text.strip():
        return None

    settings = get_settings()
    if not settings.sarvam_api_key:
        logger.warning("tts_skipped reason=no_api_key")
        return None

    # Sanitize language code (e.g. en-IN, ta-IN, hi-IN)
    lang = target_language_code if target_language_code else "en-IN"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.sarvam_base_url}{TTS_ENDPOINT}",
                json={
                    "inputs": [text.strip()],
                    "target_language_code": lang,
                    "speaker": speaker,
                    "pace": 1.0,
                    "speech_sample_rate": 8000,
                    "enable_preprocessing": True,
                    "model": "bulbul:v3",
                },
                headers={"api-subscription-key": settings.sarvam_api_key},
                timeout=20.0,
            )

            if response.status_code != 200:
                logger.warning(
                    "tts_failed status=%d lang=%s response=%s",
                    response.status_code, lang, response.text[:200],
                )
                return None

            data = response.json()
            audios = data.get("audios", [])
            if audios and isinstance(audios, list) and len(audios) > 0:
                base64_audio = audios[0]
                logger.info("tts_success lang=%s chars=%d audio_len=%d", lang, len(text), len(base64_audio))
                return base64_audio
            else:
                logger.warning("tts_empty_audio_list lang=%s", lang)
                return None

    except httpx.TimeoutException:
        logger.warning("tts_timeout lang=%s", lang)
        return None
    except Exception as exc:
        logger.warning("tts_error lang=%s error=%s", lang, exc)
        return None
