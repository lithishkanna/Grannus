"""
Gemini-powered home remedy and self-care guidance generator.

Invoked ONLY for LOW priority cases. Generates safe, general self-care
information based on the patient's reported symptoms.

STRICT SAFETY CONSTRAINTS (enforced in system prompt):
- No disease names or diagnosis
- No medication names, dosages, or prescriptions
- No "cure" or "treatment" language
- Must include monitoring signs for worsening
- Must include clear "seek doctor immediately if..." triggers
- Information is general health guidance only

This module is NOT a diagnostic or prescriptive system.
"""
import asyncio
import logging
from typing import Optional

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import ClinicalSummary, HomeRemedyGuidance, HomeRemedyCareStep
from app.services.translation import translate_text

logger = logging.getLogger("rural_care.home_remedies")


class HomeRemedyError(RuntimeError):
    """Raised when home remedy generation fails."""


# ---------------------------------------------------------------------------
# Gemini client (module-level cache)
# ---------------------------------------------------------------------------

_gemini_client: Optional["genai.Client"] = None


def _get_gemini_client() -> "genai.Client":
    """Return a cached GenAI client (one per process)."""
    global _gemini_client
    if _gemini_client is None:
        settings = get_settings()
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_HOME_REMEDY_SYSTEM_INSTRUCTION = """\
You are a health information assistant for a rural telehealth platform in India.
A patient has been assessed as LOW priority by a clinical triage system.
Your job is to provide GENERAL, SAFE self-care information to help the patient
manage their mild symptoms at home until they can see a doctor if needed.

ABSOLUTE CONSTRAINTS — violating any of these is not acceptable:
1. NEVER name a disease, condition, or diagnosis (no "common cold", "flu", "viral fever").
2. NEVER name a specific medication, drug, or supplement, or recommend a dosage.
3. NEVER use "cure", "treat", or "remedy for [disease]" language.
4. ALWAYS include clear conditions for when to seek immediate medical attention.
5. ALWAYS include monitoring signs — what changes would indicate the patient is getting worse.
6. Keep advice general and suitable for a rural setting with limited resources.
7. The output is for a human patient, so use clear, simple, reassuring language.
8. This is general health guidance ONLY — not a substitute for medical consultation.

Output structure (JSON matching the schema):
- care_steps: 3-5 general self-care actions (rest, hydration, etc.)
- monitoring_signs: 3-4 warning signs to watch for
- seek_doctor_if: 3-4 specific triggers for immediate medical attention

Example (for mild fever + headache):
care_steps:
  - "Rest and avoid strenuous physical activity"
  - "Drink plenty of clean water and fluids throughout the day"
  - "Stay in a cool, well-ventilated room"
  - "Use a clean, damp cloth on the forehead to help with discomfort"

monitoring_signs:
  - "Symptoms getting significantly worse over the next 24 hours"
  - "Difficulty breathing or chest discomfort"
  - "Unable to keep fluids down due to vomiting"

seek_doctor_if:
  - "High fever that does not reduce after 2 days"
  - "Severe headache, stiff neck, or confusion develops"
  - "Any symptoms of chest pain or difficulty breathing appear"
  - "You feel significantly worse or are concerned about your condition"
"""


def _build_home_remedy_prompt(summary: ClinicalSummary) -> str:
    """Build the user-facing prompt from the clinical summary."""
    active_symptoms = [
        s.name + (f" ({s.severity.value} severity)" if s.severity else "")
        for s in summary.symptoms
        if not s.negated
    ]
    chief = summary.chief_complaint or "general discomfort"
    symptom_list = ", ".join(active_symptoms) if active_symptoms else "no specific symptoms reported"

    return (
        f"Patient's chief complaint: {chief}\n"
        f"Reported symptoms: {symptom_list}\n\n"
        "Provide safe, general self-care guidance for this patient. "
        "Remember: no diagnosis, no medication names, general guidance only."
    )


# ---------------------------------------------------------------------------
# Structured schema for Gemini output
# ---------------------------------------------------------------------------

class _HomeRemedyRaw(HomeRemedyGuidance):
    """
    Intermediate Pydantic model used as the Gemini response schema.
    Excludes translated fields (those are added by us after translation).
    """
    pass


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

async def generate_home_remedies(
    summary: ClinicalSummary,
    patient_language: str = "en-IN",
) -> Optional[HomeRemedyGuidance]:
    """
    Generate safe self-care guidance for a LOW priority patient.

    Args:
        summary: The patient's clinical summary from Gemini extraction.
        patient_language: BCP-47 code for the patient's language (for translation).

    Returns:
        HomeRemedyGuidance populated with care steps, monitoring signs, and
        seek-doctor triggers (with translations if patient_language != English).
        Returns None if generation fails (pipeline continues without guidance).
    """
    settings = get_settings()
    client = _get_gemini_client()
    prompt = _build_home_remedy_prompt(summary)

    def _call_gemini():
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_HOME_REMEDY_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=_HomeRemedyRaw,
                temperature=0.2,  # slightly more flexible than extraction, still conservative
            ),
        )

    response = None
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(_call_gemini),
                timeout=settings.gemini_timeout_seconds,
            )
            break
        except (ConnectionError, TimeoutError, asyncio.TimeoutError) as e:
            if attempt < max_attempts - 1:
                logger.warning("Network error calling Gemini for home remedies: %s. Retry %d/%d", e, attempt + 1, max_attempts)
                await asyncio.sleep(2 ** attempt)
            else:
                logger.error("Home remedy generation failed after %d attempts: %s", max_attempts, e)
                return None
        except genai_errors.APIError as e:
            if getattr(e, "code", None) in (429, 500, 503) or "quota" in str(e).lower():
                if attempt < max_attempts - 1:
                    logger.warning("Transient Gemini API error for home remedies: %s. Retry %d/%d", e, attempt + 1, max_attempts)
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error("Home remedy generation failed: %s", e)
                    return None
            else:
                logger.error("Permanent Gemini API error for home remedies: %s", e)
                return None
        except Exception as e:
            if attempt < max_attempts - 1:
                logger.warning("Unexpected error in home remedy generation: %s. Retry %d/%d", e, attempt + 1, max_attempts)
                await asyncio.sleep(2 ** attempt)
            else:
                logger.error("Home remedy generation failed unexpectedly: %s", e)
                return None

    if response is None:
        return None

    # Parse and validate Gemini response
    guidance: Optional[HomeRemedyGuidance] = None
    try:
        parsed = response.parsed
        if parsed is None:
            guidance = HomeRemedyGuidance.model_validate_json(response.text)
        elif isinstance(parsed, HomeRemedyGuidance):
            guidance = parsed
        else:
            guidance = HomeRemedyGuidance.model_validate(parsed)
    except (ValidationError, Exception) as e:
        logger.warning("Home remedy response validation failed: %s. Returning None.", e)
        return None

    # Ensure mandatory disclaimer is always present
    if not guidance.disclaimer:
        guidance.disclaimer = (
            "This is general health information only, not a medical diagnosis or treatment plan. "
            "If symptoms worsen or you are concerned, please seek medical attention immediately."
        )

    guidance.language = patient_language

    # Translate care steps and seek-doctor triggers to patient language if needed
    if not patient_language.lower().startswith("en"):
        care_texts = [step.step for step in guidance.care_steps]
        seek_texts = guidance.seek_doctor_if

        async def _translate(text: str) -> str:
            return await translate_text(text, patient_language)

        all_texts = care_texts + seek_texts
        try:
            translated_all = await asyncio.gather(*[_translate(t) for t in all_texts], return_exceptions=True)
            n_care = len(care_texts)
            translated_care = [
                r if not isinstance(r, Exception) else care_texts[i]
                for i, r in enumerate(translated_all[:n_care])
            ]
            translated_seek = [
                r if not isinstance(r, Exception) else seek_texts[i]
                for i, r in enumerate(translated_all[n_care:])
            ]
            guidance.translated_care_steps = translated_care
            guidance.translated_seek_doctor_if = translated_seek
        except Exception as e:
            logger.warning("Translation of home remedy guidance failed: %s", e)
            # Non-critical — guidance is still returned in English

    logger.info(
        "home_remedies_generated steps=%d monitoring=%d seek_triggers=%d lang=%s",
        len(guidance.care_steps),
        len(guidance.monitoring_signs),
        len(guidance.seek_doctor_if),
        patient_language,
    )
    return guidance
