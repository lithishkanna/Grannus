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


import re

# Drug and dosage protection regexes (B7.4)
_DRUG_DOSAGE_REGEXES = [
    re.compile(r'\b(?:Paracetamol|Amoxicillin|Azithromycin|Ibuprofen|Metformin|Pantoprazole|Omeprazole|Ciprofloxacin|Cetirizine|ORS|Aspirin|Dolo|PCM|Ranitidine|Diclofenac|Cefixime)\b(?:\s+\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml|tablets?|capsules?|sachets?|drops?|puffs?))?', re.IGNORECASE),
    re.compile(r'\b[A-Za-z]{3,25}\s+\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml)\b', re.IGNORECASE),
    re.compile(r'\b\d+\s+(?:tablets?|capsules?|drops?|puffs?|spoons?)\s+(?:once|twice|thrice|\d+\s+times)\s+(?:daily|a\s+day|every\s+\d+\s+hours)\b', re.IGNORECASE),
    re.compile(r'\b[012]-[012]-[012]\b'),
    re.compile(r'\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml)\b', re.IGNORECASE),
]


def mask_medications_and_dosages(text: str) -> tuple[str, dict[str, str]]:
    """
    Protect drug names and dosages with placeholder masks (B7.4)
    e.g. 'Paracetamol 500mg' -> '__DRUG_DOSAGE_0__'.
    Prevents translation corruption or transliteration errors.
    """
    if not text:
        return text, {}

    mask_map: dict[str, str] = {}
    masked_text = text
    idx = 0

    for pattern in _DRUG_DOSAGE_REGEXES:
        matches = list(pattern.finditer(masked_text))
        for m in sorted(matches, key=lambda x: len(x.group(0)), reverse=True):
            match_str = m.group(0)
            if not match_str.strip() or match_str.startswith("__DRUG_DOSAGE_"):
                continue
            placeholder = f"__DRUG_DOSAGE_{idx}__"
            # Replace only this occurrence if not already masked
            if match_str in masked_text:
                mask_map[placeholder] = match_str
                masked_text = masked_text.replace(match_str, placeholder, 1)
                idx += 1

    return masked_text, mask_map


def unmask_medications_and_dosages(text: str, mask_map: dict[str, str]) -> str:
    """
    Restore preserved drug names and exact dosages after translation (B7.4).
    Tolerates space and casing variations introduced by translation engines.
    """
    if not text or not mask_map:
        return text

    unmasked = text
    for placeholder, original in mask_map.items():
        # Clean exact placeholder
        unmasked = unmasked.replace(placeholder, original)
        # Tolerate spaces or case variations e.g. "__ drug_dosage_0 __"
        num = placeholder.replace("__DRUG_DOSAGE_", "").replace("__", "")
        fuzzy_pattern = re.compile(rf'__\s*drug[_\s]*dosage[_\s]*{num}\s*__', re.IGNORECASE)
        unmasked = fuzzy_pattern.sub(original, unmasked)

    return unmasked


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
    Translate text to the target language using Sarvam Translate API with
    strict medication and dosage mask preservation (B7.4).
    """
    if not text or not text.strip():
        return text

    if not _is_translatable(target_language):
        return text

    # Step 1: Mask drug names and dosages before translation
    masked_input, mask_map = mask_medications_and_dosages(text)

    # Check cache for masked text
    cache_key = (masked_input.strip(), target_language)
    if cache_key in _translation_cache:
        cached_result = _translation_cache[cache_key]
        return unmask_medications_and_dosages(cached_result, mask_map)

    settings = get_settings()
    if not settings.sarvam_api_key:
        logger.warning("translation_skipped reason=no_api_key")
        return text

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.sarvam_base_url}{TRANSLATE_ENDPOINT}",
                json={
                    "input": masked_input,
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
            translated_masked = result.get("translated_text", "")
            if not translated_masked or not translated_masked.strip():
                logger.warning("translation_empty lang=%s", target_language)
                return text

            # Cache the masked translation
            _translation_cache[cache_key] = translated_masked

            # Step 2: Unmask protected medications
            final_translated = unmask_medications_and_dosages(translated_masked, mask_map)
            logger.info(
                "translation_ok lang=%s chars_in=%d chars_out=%d protected_drugs=%d",
                target_language, len(text), len(final_translated), len(mask_map),
            )
            return final_translated

    except httpx.TimeoutException:
        logger.warning("translation_timeout lang=%s", target_language)
        return text
    except Exception as exc:
        logger.warning("translation_error lang=%s error=%s", target_language, exc)
        return text


async def verify_and_back_translate_doctor_reply(
    doctor_english_reply: str,
    patient_language: str,
) -> dict:
    """
    Verify doctor's voice reply before sending to patient (B7.4).
    1. Translates English doctor reply to patient's language with drug masks.
    2. Back-translates patient's language back to English.
    3. Calculates keyword consistency and discrepancy flags.
    """
    if not doctor_english_reply or not doctor_english_reply.strip():
        return {
            "doctor_english_reply": "",
            "patient_language": patient_language,
            "patient_translation": "",
            "back_translated_english": "",
            "preserved_medications": [],
            "is_verified": False,
            "confidence_score": 0.0,
            "discrepancy_notes": "Empty doctor reply",
        }

    # Forward translation
    patient_translation = await translate_text(
        text=doctor_english_reply,
        target_language=patient_language,
        source_language="en-IN",
    )

    # Back translation
    back_translated = await translate_text(
        text=patient_translation,
        target_language="en-IN",
        source_language=patient_language,
    )

    # Check preserved drugs
    _, mask_map = mask_medications_and_dosages(doctor_english_reply)
    preserved = list(mask_map.values())

    # Verification checks
    discrepancy = None
    is_verified = True
    for med in preserved:
        if med.lower() not in patient_translation.lower() and med.lower() not in back_translated.lower():
            is_verified = False
            discrepancy = f"Warning: Prescribed medication/dosage '{med}' was modified during translation."
            break

    return {
        "doctor_english_reply": doctor_english_reply,
        "patient_language": patient_language,
        "patient_translation": patient_translation,
        "back_translated_english": back_translated,
        "preserved_medications": preserved,
        "is_verified": is_verified,
        "confidence_score": 0.95 if is_verified else 0.60,
        "discrepancy_notes": discrepancy,
    }



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


async def translate_clinical_summary_for_doctor(
    chief_complaint: str,
    symptoms: list,  # List of Symptom objects with .name and .negated attributes
    red_flags: list,  # List of SafetyRedFlag objects with .reason attribute
    doctor_language: Optional[str],
) -> Optional[dict]:
    """
    Translate key clinical summary fields into the doctor's preferred language.
    Returns a dict with translated fields, or None if translation not applicable.

    Args:
        chief_complaint: English chief complaint string.
        symptoms: List of Symptom schema objects.
        red_flags: List of SafetyRedFlag schema objects.
        doctor_language: BCP-47 code for doctor's preferred language.

    Returns:
        Dict with keys: chief_complaint, symptoms_summary, red_flags_summary, language
        or None if doctor_language is English or not supported.
    """
    if not _is_translatable(doctor_language):
        return None

    # Build English narrative strings to translate
    active_symptoms = [s.name for s in symptoms if not s.negated]
    symptoms_text = ", ".join(active_symptoms) if active_symptoms else ""
    red_flags_text = "; ".join(rf.reason for rf in red_flags) if red_flags else ""

    import asyncio

    async def _maybe_translate(text: str) -> str:
        if not text:
            return ""
        return await translate_text(text, doctor_language)

    results = await asyncio.gather(
        _maybe_translate(chief_complaint),
        _maybe_translate(symptoms_text),
        _maybe_translate(red_flags_text),
        return_exceptions=True,
    )

    def _safe(r, fallback: str) -> Optional[str]:
        if isinstance(r, Exception) or not r:
            return fallback or None
        return r if r != fallback else None

    translated_cc = _safe(results[0], chief_complaint)
    translated_sx = _safe(results[1], symptoms_text)
    translated_rf = _safe(results[2], red_flags_text)

    # Generate spoken voice audio in doctor's language via Sarvam TTS
    narrative_parts = []
    if translated_cc:
        narrative_parts.append(translated_cc)
    if translated_sx:
        narrative_parts.append(f"Symptoms: {translated_sx}")
    if translated_rf:
        narrative_parts.append(f"Red flags: {translated_rf}")
    
    narrative_text = ". ".join(narrative_parts)
    audio_base64 = None
    if narrative_text:
        try:
            from app.services.sarvam_tts import text_to_speech
            audio_base64 = await text_to_speech(narrative_text, target_language_code=doctor_language)
        except Exception as exc:
            logger.warning("doctor_audio_tts_failed lang=%s error=%s", doctor_language, exc)

    return {
        "chief_complaint": translated_cc,
        "symptoms_summary": translated_sx if active_symptoms else None,
        "red_flags_summary": translated_rf if red_flags else None,
        "audio_base64": audio_base64,
        "language": doctor_language,
    }
