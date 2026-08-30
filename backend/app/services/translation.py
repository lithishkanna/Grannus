"""
Translation service for follow-up questions.

Translates English follow-up questions into the patient's selected language
using the Sarvam Translate API. Falls back to English if translation fails.

Common questions are cached in-memory to avoid repeated API calls for the
same text in the same language.
"""
import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger("rural_care.translation")

TRANSLATE_ENDPOINT = "/translate"

# In-memory cache: (text, target_language) -> translated_text
# This is a simple dict cache — sufficient for a prototype where the set
# of follow-up questions is small and predictable.
_translation_cache: dict[tuple[str, str], str] = {}


class TranslationError(RuntimeError):
    """Raised when translation fails."""


# Languages supported by Sarvam Translate API (BCP-47 codes)
SUPPORTED_LANGUAGES = {
    "hi-IN", "bn-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN",
    "pa-IN", "ta-IN", "te-IN", "gu-IN", "en-IN",
}


def _is_translatable(language_code: Optional[str]) -> bool:
    """Check if the language code is a non-English Indian language we can translate to."""
    if not language_code:
        return False
    # Don't translate if already English
    if language_code.lower().startswith("en"):
        return False
    return language_code in SUPPORTED_LANGUAGES


async def translate_text(
    text: str,
    target_language: str,
    source_language: str = "en-IN",
) -> str:
    """
    Translate text to the target language using Sarvam Translate API.

    Returns the original text if translation fails or the language is unsupported.

    Args:
        text: English text to translate.
        target_language: BCP-47 code (e.g. 'ta-IN').
        source_language: Source language code (default: English).

    Returns:
        Translated text, or original text on failure.
    """
    if not text or not text.strip():
        return text

    if not _is_translatable(target_language):
        return text

    # Check cache
    cache_key = (text.strip(), target_language)
    if cache_key in _translation_cache:
        logger.debug("translation_cache_hit lang=%s text_len=%d", target_language, len(text))
        return _translation_cache[cache_key]

    settings = get_settings()
    if not settings.sarvam_api_key:
        logger.warning("translation_skipped reason=no_api_key")
        return text

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.sarvam_base_url}{TRANSLATE_ENDPOINT}",
                json={
                    "input": text,
                    "source_language_code": source_language,
                    "target_language_code": target_language,
                    "mode": "formal",
                    "model": "mayura:v1",
                    "enable_preprocessing": True,
                },
                headers={"api-subscription-key": settings.sarvam_api_key},
                timeout=15.0,
            )

            if response.status_code != 200:
                logger.warning(
                    "translation_failed status=%d lang=%s response=%s",
                    response.status_code, target_language, response.text[:200],
                )
                return text

            result = response.json()
            translated = result.get("translated_text", "")
            if not translated or not translated.strip():
                logger.warning("translation_empty lang=%s", target_language)
                return text

            # Cache the result
            _translation_cache[cache_key] = translated
            logger.info(
                "translation_ok lang=%s chars_in=%d chars_out=%d",
                target_language, len(text), len(translated),
            )
            return translated

    except httpx.TimeoutException:
        logger.warning("translation_timeout lang=%s", target_language)
        return text
    except Exception as exc:
        logger.warning("translation_error lang=%s error=%s", target_language, exc)
        return text


async def translate_questions(
    questions: list[str],
    target_language: Optional[str],
) -> list[tuple[str, Optional[str]]]:
    """
    Translate a list of follow-up questions to the patient's language.

    Returns a list of (english_question, translated_question) tuples.
    translated_question is None if translation is not applicable or fails.
    """
    if not _is_translatable(target_language):
        return [(q, None) for q in questions]

    results = []
    for question in questions:
        translated = await translate_text(question, target_language)
        # Only set translated_question if it's actually different from English
        if translated != question:
            results.append((question, translated))
        else:
            results.append((question, None))

    return results
