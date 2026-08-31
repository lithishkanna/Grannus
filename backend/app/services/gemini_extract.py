"""
Gemini medical information extraction layer.

Gemini's ONLY job here is to reorganize what the patient said into the
StructuredMedicalSummary schema — per-symptom duration/severity/frequency/
location, negation-aware, with per-field confidence. It is explicitly
instructed not to diagnose, not to invent facts, and to mark things
unknown rather than guess. Priority/triage is entirely handled downstream
by app.priority — this module never decides urgency.
"""
from typing import Optional
import asyncio
import logging

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import StructuredMedicalSummary
from app.vocab import (
    is_known_symptom,
    normalize_body_location,
    normalize_symptom_name,
    parse_duration_text,
)

logger = logging.getLogger("rural_care.gemini_extract")

class GeminiExtractionError(RuntimeError):
    pass

_gemini_client: Optional["genai.Client"] = None

def _get_gemini_client() -> "genai.Client":
    """Return a cached GenAI client (one per process)."""
    global _gemini_client
    if _gemini_client is None:
        settings = get_settings()
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client

SYSTEM_INSTRUCTION = """\
You are a clinical information EXTRACTION assistant for a rural telehealth \
platform in India. You convert a patient's spoken description (already \
translated to English) into a structured summary for a human doctor to review.

STRICT RULES:
- You are NOT a diagnostic system. Never name a disease or medical condition \
  as the cause (no "pneumonia", "common cold", "heart disease", etc.). Only \
  record symptoms, facts, and context the patient actually stated. If a \
  colloquial term is ambiguous (e.g. a general word for "cold-like symptoms"), \
  record it as a symptom description, not a diagnosis.
- Never invent information. If something was not mentioned, leave the field \
  null/empty rather than guessing. Do not assume a temperature value, an \
  onset time, or a severity that wasn't stated.
- Extract EACH symptom as its own entry with its own duration, severity, \
  frequency, and body location. Do not merge multiple symptoms into one \
  summary-level duration/severity — a patient's fever and chest pain almost \
  never share the same timeline.
- Preserve frequency/intensity words the patient used (occasionally, \
  continuously, frequently, mild, moderate, severe, unbearable, slight) \
  instead of dropping them.
- Preserve temporal relationships between symptoms when stated (e.g. "the \
  chest pain started after the fever") in "onset_relation" — do not assume \
  simultaneous onset.
- Detect NEGATION. "I don't have chest pain" must be recorded with \
  negated=true, never as a present symptom. Never invert this.
- Detect UNCERTAINTY/HEDGING. "Maybe I have fever" should get a lower \
  confidence than "I have fever" — reflect this in the symptom's confidence \
  and in field_confidence.
- Scan the ENTIRE transcript for red flags, not just the first part. \
  Populate "red_flags" with any phrase indicating a possible emergency the \
  patient actually described (e.g. difficulty breathing, severe/unbearable \
  chest pain, heavy/uncontrolled bleeding, loss of consciousness, severe \
  injury, suicidal ideation). Do not infer red flags that were not stated \
  or implied, but also do not default to an empty list without actually \
  checking — chest pain mentioned anywhere in the transcript is a red flag \
  candidate.
- Fill "field_confidence" with a 0-1 confidence for each top-level field you \
  populated (e.g. "chief_complaint": 0.9, "existing_conditions": 0.4 if the \
  patient was vague about it).
- Output must strictly match the provided JSON schema. No extra commentary.
- Handle CODE-SWITCHING gracefully. Indian patients frequently mix Tamil/Hindi/Telugu \
  with English in the same sentence (e.g., 'enakku fever irukku and vomiting vara maathiri \
  irukku'). Extract medical information regardless of which language each word is in. \
  The transcript has already been translated to English, but translation artifacts \
  (literal translations, transliterations) may remain — interpret them charitably.
- Handle REGIONAL EXPRESSIONS. Indian patients may describe symptoms using colloquial \
  phrases (e.g., 'body is burning' for fever, 'gas problem' for bloating/acidity, \
  'sugar' for diabetes, 'BP' for hypertension). Map these to standard clinical terms.

EXAMPLES (follow this pattern exactly):

Example 1 — multi-symptom, temporal relationship, hedging:
Transcript: "I have had fever for 3 days. After that I started getting a mild
cough, maybe on and off. I don't have any chest pain."
Correct extraction highlights:
- symptom "fever": duration 3 days, no severity stated (severity=null, not "unclear")
- symptom "cough": onset_relation="started after the fever", severity="mild",
  frequency="intermittent", confidence lower (~0.6) because of "maybe"
- symptom "chest pain": negated=true, confidence 1.0 (the denial itself is clear)
- red_flags: [] (nothing concerning was actually described)

Example 2 — red flag scanning, ambiguous term:
Transcript: "Yesterday I had சளி and a mild headache. Today my chest pain
became severe and I'm finding it hard to breathe."
Correct extraction highlights:
- symptom name for "சளி": "cold-like symptoms" (never "common cold")
- symptom "chest pain": severity="severe"
- symptom "difficulty breathing": present, not negated
- red_flags: at least two entries — one for "severe chest pain", one for
  "difficulty breathing" — even though the transcript starts with mild,
  unrelated symptoms. Scan the WHOLE transcript, not just the first line.

Example 3 — vague/uncertain transcript:
Transcript: "I'm not feeling well, something is wrong with my stomach I think."
Correct extraction highlights:
- chief_complaint: "unwell, possible stomach-related symptom" (describes
  what was said, not a diagnosis)
- symptom "abdominal pain": confidence low (~0.4), severity=null
- field_confidence: low values across most fields (e.g. 0.3-0.5) rather than
  guessing precise details that weren't given
"""


def _build_prompt(transcript_english: str, patient_context: Optional[dict]) -> str:
    context_lines = []
    if patient_context:
        for key in ("age", "gender", "reported_duration", "known_conditions", "current_medications"):
            value = patient_context.get(key)
            if value:
                context_lines.append(f"- {key}: {value}")
    context_block = (
        "Additional patient-provided context (may be empty):\n" + "\n".join(context_lines)
        if context_lines
        else "Additional patient-provided context: none supplied."
    )

    return (
        f"Patient's transcribed and translated statement (English):\n"
        f'"""{transcript_english}"""\n\n'
        f"{context_block}\n\n"
        "Extract the structured clinical summary now."
    )


def _normalize(summary: StructuredMedicalSummary) -> StructuredMedicalSummary:
    """
    Defensive normalization pass. Gemini is instructed to use the controlled
    vocabulary and structured durations, but we don't fully trust free-form
    model output for anything that downstream code (priority engine,
    dashboards) keys off of — so we re-normalize here rather than assume.
    """
    for symptom in summary.symptoms:
        original_name = symptom.name
        symptom.name = normalize_symptom_name(symptom.name) or symptom.name
        if not is_known_symptom(original_name):
            # Track vocabulary gaps so the controlled vocabulary (app/vocab.py)
            # can be extended from real data instead of guessing what to add.
            logger.info("vocab_gap unrecognized_symptom=%r normalized_to=%r", original_name, symptom.name)

        symptom.body_location = normalize_body_location(symptom.body_location)
        if symptom.duration and symptom.duration.value is None and symptom.duration.raw_text:
            value, unit = parse_duration_text(symptom.duration.raw_text)
            if value is not None:
                symptom.duration.value = value
                symptom.duration.unit = unit

        # Post-hoc negation sanity check: verify that a negation word appears
        # DIRECTLY BEFORE the symptom name in the raw text, not just anywhere.
        raw_lower = (symptom.raw_text or "").lower()
        symptom_lower = symptom.name.lower()
        looks_negated = False
        if raw_lower and symptom_lower in raw_lower:
            # Find position of symptom name and check for negation word in the
            # 4-word window immediately before it.
            sym_pos = raw_lower.find(symptom_lower)
            prefix = raw_lower[:sym_pos].strip()
            prefix_words = prefix.split()
            last_few = " ".join(prefix_words[-4:]) if prefix_words else ""
            _CLOSE_NEGATIONS = ("don't", "do not", "doesn't", "does not",
                                "didn't", "did not", "not", "no", "never",
                                "isn't", "wasn't", "have no", "don't have")
            looks_negated = any(neg in last_few for neg in _CLOSE_NEGATIONS)
        if symptom.raw_text and looks_negated != symptom.negated:
            symptom.confidence = min(symptom.confidence, 0.5)
            note = (f"negation mismatch for '{symptom.name}': "
                    f"model said negated={symptom.negated} but raw text suggests {looks_negated}")
            summary.extraction_notes = (
                f"{summary.extraction_notes}; {note}" if summary.extraction_notes else note
            )
            logger.warning(
                "negation_check_flagged symptom=%r negated=%s raw_suggests=%s",
                symptom.name, symptom.negated, looks_negated,
            )

    return summary


async def extract_structured_summary(
    transcript_english: str,
    patient_context: Optional[dict] = None,
) -> StructuredMedicalSummary:
    """
    Calls Gemini with a forced JSON schema and returns a validated,
    normalized StructuredMedicalSummary. Raises if Gemini's output fails
    validation (fail loudly rather than silently passing bad data downstream).
    """
    settings = get_settings()
    client = _get_gemini_client()

    def _call_gemini():
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=_build_prompt(transcript_english, patient_context),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=StructuredMedicalSummary,
                temperature=0.1,  # low temperature: we want faithful extraction, not creativity
            ),
        )

    response = None
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(_call_gemini),
                timeout=settings.gemini_timeout_seconds
            )
            break
        except (ConnectionError, TimeoutError, asyncio.TimeoutError) as e:
            if attempt < max_attempts - 1:
                logger.warning(f"Network error calling Gemini: {e}. Retrying ({attempt + 1}/{max_attempts})...")
                await asyncio.sleep(2 ** attempt)
            else:
                raise GeminiExtractionError(f"Failed to call Gemini after {max_attempts} attempts due to network errors.")
        except genai_errors.APIError as e:
            # Retry on typical transient API errors like 429, 500, 503
            if getattr(e, 'code', None) in (429, 500, 503) or 'quota' in str(e).lower() or 'overloaded' in str(e).lower():
                if attempt < max_attempts - 1:
                    logger.warning(f"Transient API error calling Gemini: {e}. Retrying ({attempt + 1}/{max_attempts})...")
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise GeminiExtractionError(f"Failed to call Gemini after {max_attempts} attempts due to API errors.")
            else:
                raise GeminiExtractionError(f"Permanent API error from Gemini: {e}")
        except Exception as e:
            if attempt < max_attempts - 1:
                logger.warning(f"Unexpected error calling Gemini: {e}. Retrying ({attempt + 1}/{max_attempts})...")
                await asyncio.sleep(2 ** attempt)
            else:
                raise GeminiExtractionError(f"Failed to call Gemini due to unexpected error: {e}")

    parsed = response.parsed
    if parsed is None:
        # Fallback: validate the raw text ourselves if .parsed wasn't populated.
        try:
            parsed = StructuredMedicalSummary.model_validate_json(response.text)
        except ValidationError as e:
            brief_preview = (response.text[:200] + '...') if len(response.text) > 200 else response.text
            raise GeminiExtractionError(f"Gemini returned invalid JSON that could not be parsed: {brief_preview}") from e
    elif not isinstance(parsed, StructuredMedicalSummary):
        # google-genai can return a plain dict/BaseModel subclass depending on
        # version; re-validate through Pydantic either way so we never trust
        # unvalidated Gemini output downstream.
        try:
            parsed = StructuredMedicalSummary.model_validate(parsed)
        except ValidationError as e:
            raise GeminiExtractionError(f"Gemini returned structured object that failed validation.") from e

    return _normalize(parsed)
