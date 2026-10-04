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
    Enforces B6.2 invariant: strictly uses approved library entries or fixed
    demonstration fallback. Never allows free-form unvetted AI medical generation.

    Args:
        summary: The patient's clinical summary from extraction.
        patient_language: BCP-47 code for the patient's language.

    Returns:
        HomeRemedyGuidance populated with approved care steps, monitoring signs,
        and seek-doctor triggers.
    """
    from app.remedy_library import get_approved_home_remedy_guidance, get_default_home_remedy_guidance

    # 1. First consult our approved demonstration self-care library
    approved = get_approved_home_remedy_guidance(summary, patient_language)
    if approved:
        logger.info("Matched approved self-care library entry for symptoms")
        guidance = approved
    else:
        # 2. Strict B6.2 invariant: If no approved entry matches, return fixed approved message:
        # "Please consult a doctor", with explicit emergency criteria.
        logger.info("No approved home remedy match; returning standard clinician consultation guidance")
        guidance = get_default_home_remedy_guidance(patient_language)

    # 3. If translation to non-English is missing, translate only the approved text
    if not patient_language.lower().startswith("en") and not guidance.translated_care_steps:
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
            logger.warning("Translation of approved guidance failed: %s", e)

    logger.info(
        "home_remedies_served steps=%d monitoring=%d seek_triggers=%d lang=%s",
        len(guidance.care_steps),
        len(guidance.monitoring_signs),
        len(guidance.seek_doctor_if),
        patient_language,
    )
    return guidance

