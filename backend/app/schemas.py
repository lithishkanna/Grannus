"""
Data contracts for the RuralCare AI pipeline:
Voice -> Audio Preprocessing -> Sarvam STT -> Gemini extraction ->
normalization -> safety engine -> feature extraction -> priority engine.

Design principles:
- Gemini only EXTRACTS. It never decides diagnosis or priority.
- Every field is either traceable to something the patient said, or null.
- Uncertainty is per-field, not one global boolean.
- Symptoms carry their own duration/severity/frequency/location, not one
  summary-level "duration"/"severity"/"body_location".
- Safety screening is deterministic (rule-based), separate from LLM.
- Final output format matches the doctor dashboard API contract.
"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared enums / value objects
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    UNBEARABLE = "unbearable"
    SLIGHT = "slight"


class Frequency(str, Enum):
    CONTINUOUS = "continuous"
    INTERMITTENT = "intermittent"
    OCCASIONAL = "occasional"
    FREQUENT = "frequent"


class DurationUnit(str, Enum):
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


class InfoSource(str, Enum):
    PATIENT_REPORTED = "patient_reported"
    AI_INFERRED = "ai_inferred"


class Duration(BaseModel):
    """Structured duration. Prefer this over free-text 'duration' strings."""
    value: Optional[float] = Field(default=None, description="Numeric magnitude, e.g. 3.")
    unit: Optional[DurationUnit] = Field(default=None, description="Unit for 'value'.")
    raw_text: Optional[str] = Field(
        default=None, description="Patient's original phrasing, e.g. 'a couple of days', kept verbatim when it can't be cleanly parsed into value/unit."
    )


class Symptom(BaseModel):
    """
    One symptom, fully self-contained. Nothing about timing, severity,
    location or frequency is shared across symptoms — each symptom carries
    its own, because a patient's fever and chest pain rarely share a
    duration or a story.
    """
    name: str = Field(
        description=(
            "Normalized symptom name from the controlled vocabulary where possible "
            "(e.g. 'headache', 'cold-like symptoms'). Never a diagnosis (no 'common cold', "
            "'pneumonia', etc.) — only what the patient described."
        )
    )
    raw_text: Optional[str] = Field(
        default=None, description="The patient's own words for this symptom, kept verbatim."
    )
    body_location: Optional[str] = Field(default=None, description="Body part/area for THIS symptom only.")
    duration: Optional[Duration] = Field(default=None, description="How long THIS symptom has lasted. Null if not stated — never assumed.")
    onset_relation: Optional[str] = Field(
        default=None,
        description="Temporal relationship to other symptoms if the patient stated one, e.g. 'started after the fever'. Null if not stated.",
    )
    severity: Optional[Severity] = Field(
        default=None, description="Patient-described severity for THIS symptom. Null (not 'unclear') if not stated."
    )
    frequency: Optional[Frequency] = Field(
        default=None, description="How often THIS symptom occurs, if stated (e.g. intermittent chest pain)."
    )
    negated: bool = Field(
        default=False,
        description="True if the patient explicitly denied this symptom (e.g. 'I don't have chest pain'). Negated symptoms must never be treated as present.",
    )
    source: InfoSource = Field(default=InfoSource.PATIENT_REPORTED)
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="0-1 confidence that this symptom was actually reported as described. Lower for hedged language ('maybe', 'I think').",
    )


class RedFlag(BaseModel):
    """
    An emergency-indicator phrase pulled from the patient's own words.
    This is Gemini's extraction only — whether it actually triggers an
    emergency override is decided by the separate safety engine (safety.py),
    never by Gemini itself.
    """
    phrase: str = Field(description="The concerning phrase/symptom as the patient described it, e.g. 'severe chest pain'.")
    related_symptom: Optional[str] = Field(default=None, description="Which symptom name (if any) this red flag is tied to.")
    source: InfoSource = Field(default=InfoSource.PATIENT_REPORTED)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class FieldConfidence(BaseModel):
    chief_complaint: float = Field(default=1.0, ge=0.0, le=1.0, description="0-1 confidence for chief_complaint.")
    symptoms: float = Field(default=1.0, ge=0.0, le=1.0, description="0-1 confidence for symptoms.")
    existing_conditions: float = Field(default=1.0, ge=0.0, le=1.0, description="0-1 confidence for existing_conditions.")
    medications: float = Field(default=1.0, ge=0.0, le=1.0, description="0-1 confidence for medications.")
    allergies: float = Field(default=1.0, ge=0.0, le=1.0, description="0-1 confidence for allergies.")


class StructuredMedicalSummary(BaseModel):
    """
    Structured, English-language clinical summary extracted from the
    patient's own words. This is NOT a diagnosis. No field here may say
    "patient has X disease" — only "symptom detected" / "potential concern".
    """

    chief_complaint: str = Field(
        description="The main problem in a short clinical phrase, e.g. 'fever with body pain'. Describes symptoms only, never a diagnosis."
    )
    symptoms: List[Symptom] = Field(default_factory=list, description="Every symptom mentioned, each with its own duration/severity/frequency/location.")
    existing_conditions: List[str] = Field(default_factory=list, description="Pre-existing conditions the patient mentioned (e.g. diabetes).")
    medications: List[str] = Field(default_factory=list, description="Medications the patient says they are currently taking.")
    allergies: List[str] = Field(default_factory=list, description="Allergies the patient mentioned.")
    relevant_history: Optional[str] = Field(default=None, description="Other relevant history mentioned by the patient.")
    red_flags: List[RedFlag] = Field(
        default_factory=list,
        description=(
            "Emergency-indicator phrases found in the patient's own words. This must NOT default "
            "to an empty list just because nothing obviously alarming was said early in the transcript — "
            "scan the entire transcript. Empty list is only correct if truly nothing qualifies."
        ),
    )
    field_confidence: FieldConfidence = Field(
        default_factory=FieldConfidence,
        description="Per-field confidence (0-1) for main clinical sections.",
    )
    extraction_notes: Optional[str] = Field(
        default=None, description="Short note about ambiguity, negation, code-switching, etc. that a doctor should know about."
    )


class TranscriptionResult(BaseModel):
    transcript_original: str = Field(description="Transcript in the patient's spoken language, preserved verbatim.")
    transcript_english: str = Field(description="English translation of the same speech.")
    language_code: Optional[str] = Field(default=None, description="BCP-47 code detected/used, e.g. 'ta-IN'.")
    language_probability: Optional[float] = Field(default=None, description="Confidence in detected language, if auto-detected.")


class PriorityLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    PENDING_REVIEW = "PENDING_REVIEW"


class PriorityAssessment(BaseModel):
    """
    Output of the safety engine + ML model + rule fallback (priority.py).
    Gemini never sets this — it is computed downstream from the structured
    summary, which is what makes the priority explainable.
    """
    level: PriorityLevel
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="0-1 prediction confidence. From ML model probability if available, else rule-based heuristic.",
    )
    emergency_override: bool = Field(default=False, description="True if an emergency override rule fired, bypassing normal scoring.")
    triggered_rules: List[str] = Field(default_factory=list, description="Human-readable names of every rule that fired (explainability).")
    reasons: List[str] = Field(default_factory=list, description="Human-readable reasons contributing to this priority level.")
    score: float = Field(default=0.0, description="Underlying numeric score before thresholding, for audit/debugging.")
    model_used: str = Field(default="rule_based", description="Which model/engine produced this: 'ml_random_forest', 'rule_based', 'safety_override'.")


class MissingInformationItem(BaseModel):
    field: str = Field(description="Machine-readable identifier, e.g. 'chest_pain_breathing_difficulty'.")
    description: str = Field(description="What information is missing, for display on a clinician dashboard.")
    question: str = Field(description="A single, patient-facing follow-up question (English).")
    translated_question: Optional[str] = Field(
        default=None, description="The question translated into the patient's language, if applicable."
    )
    priority: int = Field(description="Lower number = more clinically important / ask first.")


# ---------------------------------------------------------------------------
# Safety screening models (separate deterministic layer)
# ---------------------------------------------------------------------------

class SafetyRedFlag(BaseModel):
    """A single red-flag finding from the deterministic safety engine."""
    potential_red_flag: bool = Field(default=True)
    symptom: str = Field(description="The symptom or phrase that triggered this flag.")
    reason: str = Field(description="Why this is flagged, e.g. 'Chest pain reported'.")
    action: str = Field(default="clinician_review", description="Recommended action: 'clinician_review', 'emergency_referral'.")
    severity: str = Field(default="high", description="Severity of this flag: 'critical', 'high', 'moderate'.")


class SafetyScreening(BaseModel):
    """Output of the deterministic safety engine (safety.py)."""
    red_flags: List[SafetyRedFlag] = Field(default_factory=list)
    has_critical_flags: bool = Field(default=False, description="True if any critical/emergency flags were found.")
    override_priority: bool = Field(
        default=False,
        description="True if safety flags should override/elevate the ML priority prediction.",
    )
    missing_critical_info: List[str] = Field(
        default_factory=list,
        description="Critical safety-relevant information that is missing (e.g., breathing status when chest pain present).",
    )


# ---------------------------------------------------------------------------
# Audio preprocessing result
# ---------------------------------------------------------------------------

class AudioPreprocessingResult(BaseModel):
    """Metadata from the audio preprocessing stage."""
    original_duration_seconds: float = Field(description="Duration of the raw audio input.")
    processed_duration_seconds: float = Field(description="Duration after silence trimming.")
    original_sample_rate: int
    noise_reduced: bool = Field(default=False)
    volume_normalized: bool = Field(default=False)
    silence_trimmed: bool = Field(default=False)
    format_converted: bool = Field(default=False)
    quality_warning: Optional[str] = Field(default=None, description="Warning if audio quality is poor.")


# ---------------------------------------------------------------------------
# Final pipeline output — matches doctor dashboard API contract
# ---------------------------------------------------------------------------

class PatientInput(BaseModel):
    """Grouped patient input data for the final API response."""
    language: Optional[str] = Field(default=None, description="BCP-47 language code, e.g. 'ta-IN'.")
    transcript_original: str = Field(description="Transcript in the patient's spoken language.")
    transcript_english: str = Field(description="English translation.")
    language_confidence: Optional[float] = Field(default=None)
    language_verification_required: bool = Field(default=False)


class ClinicalSummary(BaseModel):
    """Grouped clinical extraction for the final API response."""
    chief_complaint: str = Field(default="")
    symptoms: List[Symptom] = Field(default_factory=list)
    existing_conditions: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    relevant_history: Optional[str] = Field(default=None)
    field_confidence: FieldConfidence = Field(default_factory=FieldConfidence)
    extraction_notes: Optional[str] = Field(default=None)


class SafetyScreeningOutput(BaseModel):
    """Safety section of the final API response."""
    red_flags: List[SafetyRedFlag] = Field(default_factory=list)
    missing_information: List[MissingInformationItem] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """
    Final output: everything downstream layers (dashboard, triage queue) consume.
    Matches the doctor dashboard API contract.
    """

    request_id: str

    patient_input: PatientInput

    clinical_summary: ClinicalSummary

    safety_screening: SafetyScreeningOutput

    priority: PriorityAssessment

    clinician_review_required: bool = Field(
        default=True,
        description="True if a clinician should review this case before any action is taken.",
    )

    diagnosis: None = Field(
        default=None,
        description="Always null. This system does NOT diagnose. Explicit null to signal this to consumers.",
    )

    disclaimer: str = (
        "AI-generated structured summary for clinician review. This system detects and organizes "
        "reported symptoms and potential concerns — it does not diagnose. Priority level is a "
        "triage aid, not a medical judgement, and does not replace clinician review."
    )

    # ---- Internal/debug fields (not part of the doctor-facing contract) ----
    audio_preprocessing: Optional[AudioPreprocessingResult] = Field(
        default=None, description="Audio preprocessing metadata (debug/audit)."
    )
    pipeline_stages: Optional[Dict[str, Any]] = Field(
        default=None, description="Per-stage timing and status for debugging."
    )
