"""
Priority / triage engine.

Combines:
  1. Safety engine (screen_safety) — deterministic red-flag overrides.
  2. Feature extraction (extract_features) — maps clinical summary to ML features.
  3. ML Priority Model (PriorityMLModel) — RandomForest classification into HIGH / MEDIUM / LOW.
  4. Rule-based fallback — if ML model is unavailable.

Explainable priority assessment output with level, confidence, emergency override flag,
triggered rules, and contributing reasons.
"""
import logging
from typing import Dict, List, Optional

from app.feature_extraction import extract_features
from app.ml_model import get_model
from app.safety import screen_safety
from app.schemas import (
    PriorityAssessment,
    PriorityLevel,
    SafetyScreening,
    StructuredMedicalSummary,
    Symptom,
)

logger = logging.getLogger("rural_care.priority")

HIGH_THRESHOLD = 6.0
MEDIUM_THRESHOLD = 3.0

_SEVERITY_WEIGHT = {
    "unbearable": 4.0,
    "severe": 3.0,
    "moderate": 1.5,
    "mild": 0.5,
    "slight": 0.25,
}

_HIGH_RISK_SYMPTOM_WEIGHT = {
    "chest pain": 3.0,
    "difficulty breathing": 4.0,
    "severe bleeding": 4.0,
    "loss of consciousness": 4.0,
    "fever": 0.5,
}


def _score_symptom(symptom: Symptom) -> float:
    if symptom.negated:
        return 0.0
    name = (symptom.name or "").lower()
    score = _HIGH_RISK_SYMPTOM_WEIGHT.get(name, 0.3)
    if symptom.severity:
        score += _SEVERITY_WEIGHT.get(
            symptom.severity.value if hasattr(symptom.severity, "value") else str(symptom.severity).lower(),
            0.0,
        )
    if symptom.frequency and getattr(symptom.frequency, "value", str(symptom.frequency)).lower() in ("continuous", "frequent"):
        score += 0.5
    score *= max(symptom.confidence, 0.2)
    return score


def _score_summary(summary: StructuredMedicalSummary) -> float:
    """Fallback rule-based weighted score calculation."""
    score = sum(_score_symptom(s) for s in summary.symptoms)
    score += 1.5 * len(summary.red_flags)
    return round(score, 2)


def assess_priority(
    summary: StructuredMedicalSummary,
    patient_context: Optional[dict] = None,
    safety_screening: Optional[SafetyScreening] = None,
) -> PriorityAssessment:
    """
    Assess patient priority level using Safety Engine + ML Model with Rule-Based Fallback.
    """
    patient_context = patient_context or {}

    # 1. Run safety screening if not provided
    if safety_screening is None:
        safety_screening = screen_safety(summary)

    # 2. Calculate fallback rule score
    rule_score = _score_summary(summary)
    triggered_rules = [f.reason for f in safety_screening.red_flags]

    # 3. Check for Emergency / Safety Override
    if safety_screening.override_priority or safety_screening.has_critical_flags:
        logger.info("Safety override triggered priority=HIGH reasons=%s", triggered_rules)
        return PriorityAssessment(
            level=PriorityLevel.HIGH,
            confidence=1.0,
            emergency_override=True,
            triggered_rules=triggered_rules,
            reasons=triggered_rules or ["Critical safety indicator detected"],
            score=rule_score,
            model_used="safety_override",
        )

    # 4. Extract features for ML model
    features = extract_features(summary, patient_context)
    ml_model = get_model()

    # 5. ML Inference
    if ml_model.is_available():
        try:
            level_str, confidence, reasons = ml_model.predict(features)

            # Map level string to PriorityLevel enum
            level = PriorityLevel.MEDIUM
            if level_str == "HIGH":
                level = PriorityLevel.HIGH
            elif level_str == "LOW":
                level = PriorityLevel.LOW

            logger.info("ML priority assessment level=%s conf=%.2f reasons=%s", level, confidence, reasons)
            return PriorityAssessment(
                level=level,
                confidence=confidence,
                emergency_override=False,
                triggered_rules=triggered_rules,
                reasons=reasons,
                score=rule_score,
                model_used="ml_random_forest",
            )
        except Exception as exc:
            logger.warning("ML prediction failed, falling back to rule engine: %s", exc)

    # 6. Fallback Rule Engine
    if rule_score >= HIGH_THRESHOLD:
        level = PriorityLevel.HIGH
        conf = min(1.0, 0.7 + (rule_score - HIGH_THRESHOLD) * 0.05)
    elif rule_score >= MEDIUM_THRESHOLD:
        level = PriorityLevel.MEDIUM
        conf = 0.8
    else:
        level = PriorityLevel.LOW
        conf = 0.85

    fallback_reasons = [f"Rule-based score {rule_score:.2f}"]
    for s in summary.symptoms:
        if not s.negated and s.confidence >= 0.3:
            fallback_reasons.append(f"Reported symptom: {s.name}")

    logger.info("Rule-based fallback priority assessment level=%s score=%.2f", level, rule_score)
    return PriorityAssessment(
        level=level,
        confidence=conf,
        emergency_override=False,
        triggered_rules=triggered_rules,
        reasons=fallback_reasons[:5],
        score=rule_score,
        model_used="rule_based",
    )
