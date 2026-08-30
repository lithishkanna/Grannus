"""
Missing-information detection + follow-up question engine.

Detects clinically relevant gaps in the structured summary and ranks them
so the caller only ever asks ONE question at a time (per the Day-1 review:
"Don't ask 10 questions at once"). The typical flow, e.g. for chest pain:

    Patient reports chest pain
            |
    Missing breathing information
            |
    Ask: "Are you having difficulty breathing?"
            |
    Patient answers -> merged back into patient_context
            |
    Re-run extraction/priority with updated context

This module only computes *what* to ask and in what order; the actual
loop of asking-and-waiting is driven by the caller (API layer), since it
needs a turn of user input in between.
"""
import logging
from typing import List, Optional

from app.schemas import MissingInformationItem, StructuredMedicalSummary

logger = logging.getLogger("rural_care.missing_info")


def _symptom_by_name(summary: StructuredMedicalSummary, name: str):
    for s in summary.symptoms:
        if not s.negated and (s.name or "").lower() == name:
            return s
    return None


def _has_any_symptom_with_name(summary: StructuredMedicalSummary, name: str) -> bool:
    """Check if a symptom exists (negated or not)."""
    return any((s.name or "").lower() == name for s in summary.symptoms)


def generate_missing_information(
    summary: StructuredMedicalSummary,
    patient_context: Optional[dict] = None,
) -> List[MissingInformationItem]:
    """
    Identify clinically relevant gaps in the structured summary.

    Returns items sorted by priority (lowest number = ask first).
    Each item includes an English question; translation is handled
    separately by the pipeline.
    """
    patient_context = patient_context or {}
    items: List[MissingInformationItem] = []

    # --- Patient demographics ---
    if not patient_context.get("age"):
        items.append(MissingInformationItem(
            field="age", description="Patient age", question="How old is the patient?", priority=1,
        ))

    # --- Chest pain: highest-value gap to fill ---
    chest_pain = _symptom_by_name(summary, "chest pain")
    if chest_pain is not None:
        breathing = _symptom_by_name(summary, "difficulty breathing")
        if breathing is None and not _has_any_symptom_with_name(summary, "difficulty breathing"):
            items.append(MissingInformationItem(
                field="chest_pain_breathing_difficulty",
                description="Whether breathing difficulty accompanies the chest pain",
                question="Are you having any difficulty breathing along with the chest pain?",
                priority=1,
            ))
        if chest_pain.duration is None:
            items.append(MissingInformationItem(
                field="chest_pain_duration",
                description="Duration of chest pain",
                question="How long has the chest pain been going on?",
                priority=2,
            ))
        if chest_pain.frequency is None:
            items.append(MissingInformationItem(
                field="chest_pain_frequency",
                description="Frequency of chest pain (constant vs. comes and goes)",
                question="Does the chest pain happen all the time, or does it come and go?",
                priority=2,
            ))
        if chest_pain.severity is None:
            items.append(MissingInformationItem(
                field="chest_pain_severity",
                description="Severity of chest pain",
                question="On a rough scale, would you say the chest pain is mild, moderate, or severe?",
                priority=2,
            ))

    # --- Fever-specific ---
    fever = _symptom_by_name(summary, "fever")
    if fever is not None and fever.duration is None:
        items.append(MissingInformationItem(
            field="fever_temperature",
            description="Exact temperature / fever duration",
            question="Do you know the exact temperature, or how many days the fever has lasted?",
            priority=3,
        ))

    # --- Bleeding-specific ---
    bleeding = _symptom_by_name(summary, "severe bleeding") or _symptom_by_name(summary, "bleeding")
    if bleeding is not None:
        if bleeding.body_location is None:
            items.append(MissingInformationItem(
                field="bleeding_location",
                description="Location of bleeding",
                question="Where exactly is the bleeding from?",
                priority=2,
            ))
        if bleeding.duration is None:
            items.append(MissingInformationItem(
                field="bleeding_duration",
                description="Duration of bleeding",
                question="How long has the bleeding been going on?",
                priority=2,
            ))

    # --- Difficulty breathing specifics ---
    breathing = _symptom_by_name(summary, "difficulty breathing")
    if breathing is not None:
        if breathing.severity is None:
            items.append(MissingInformationItem(
                field="breathing_severity",
                description="Severity of breathing difficulty",
                question="How bad is the breathing difficulty — mild, moderate, or severe?",
                priority=2,
            ))
        if breathing.duration is None:
            items.append(MissingInformationItem(
                field="breathing_duration",
                description="When breathing difficulty started",
                question="When did the breathing difficulty start?",
                priority=2,
            ))

    # --- Generic: duration missing for any symptom not covered above ---
    covered_symptoms = {"chest pain", "fever", "severe bleeding", "bleeding", "difficulty breathing"}
    for symptom in summary.symptoms:
        if symptom.negated or symptom.duration is not None:
            continue
        if symptom.name in covered_symptoms:
            continue  # already covered by the more specific checks above
        items.append(MissingInformationItem(
            field=f"{symptom.name.replace(' ', '_')}_onset",
            description=f"When '{symptom.name}' started",
            question=f"When did the {symptom.name} start?",
            priority=3,
        ))

    # --- Generic: severity missing for symptoms that have duration but no severity ---
    for symptom in summary.symptoms:
        if symptom.negated or symptom.severity is not None:
            continue
        if symptom.name in covered_symptoms:
            continue
        # Only ask about severity if the symptom seems clinically relevant
        # (has duration or is mentioned in red flags)
        if symptom.duration is not None:
            items.append(MissingInformationItem(
                field=f"{symptom.name.replace(' ', '_')}_severity",
                description=f"Severity of '{symptom.name}'",
                question=f"Would you say the {symptom.name} is mild, moderate, or severe?",
                priority=4,
            ))

    # --- Existing conditions / medications / allergies ---
    if not summary.existing_conditions and not patient_context.get("known_conditions"):
        items.append(MissingInformationItem(
            field="existing_conditions", description="Existing medical conditions",
            question="Do you have any ongoing health conditions, like diabetes or high blood pressure?", priority=4,
        ))
    if not summary.medications and not patient_context.get("current_medications"):
        items.append(MissingInformationItem(
            field="current_medications", description="Current medications",
            question="Are you currently taking any medicines?", priority=5,
        ))
    if not summary.allergies:
        items.append(MissingInformationItem(
            field="allergies", description="Known allergies",
            question="Do you have any known allergies?", priority=6,
        ))
    if not summary.relevant_history:
        items.append(MissingInformationItem(
            field="relevant_medical_history", description="Other relevant medical history",
            question="Is there anything else about your medical history the doctor should know?", priority=7,
        ))

    # de-duplicate by field, keep highest priority (lowest number) occurrence, then sort
    best: dict = {}
    for item in items:
        if item.field not in best or item.priority < best[item.field].priority:
            best[item.field] = item
    sorted_items = sorted(best.values(), key=lambda i: i.priority)

    logger.info(
        "missing_info_generated count=%d fields=%s",
        len(sorted_items), [i.field for i in sorted_items[:5]],
    )
    return sorted_items


def next_follow_up_question(missing_items: List[MissingInformationItem]) -> Optional[str]:
    """Ask the single most important missing thing first — never a batch of questions."""
    if not missing_items:
        return None
    return missing_items[0].question


def get_follow_up_questions(
    missing_items: List[MissingInformationItem],
    max_questions: int = 3,
) -> List[str]:
    """
    Return up to max_questions follow-up questions, ordered by priority.
    Used by the safety_screening section of the final output.
    """
    return [item.question for item in missing_items[:max_questions]]
