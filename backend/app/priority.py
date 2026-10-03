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
from typing import Dict, List, Optional, Tuple

from app.feature_extraction import extract_features
from app.ml_model import get_model
from app.safety import screen_safety
from app.schemas import (
    PriorityAssessment,
    PriorityLevel,
    UrgencyTier,
    SafetyScreening,
    StructuredMedicalSummary,
    Symptom,
    Severity,
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
    "snakebite": 4.0,
    "scorpion sting": 3.0,
    "dog bite": 2.0,
    "burns": 2.5,
    "head injury": 4.0,
    "heart attack": 4.0,
    "cyanosis": 4.0,
    "poisoning": 4.0,
    "pesticide poisoning": 4.0,
}

_HIGH_RISK_SYMPTOMS = {
    "chest pain",
    "difficulty breathing",
    "shortness of breath",
    "breathlessness",
    "severe bleeding",
    "heavy bleeding",
    "loss of consciousness",
    "fainting",
    "seizure",
    "convulsion",
    "fits",
    "stroke",
    "poisoning",
    "snakebite", "scorpion sting", "dog bite", "burns", "head injury",
    "heart attack", "cyanosis", "pesticide poisoning",
    "can't breathe", "cannot breathe", "gasping", "choking",
}


def apply_floor(
    level: PriorityLevel,
    safety_screening: Optional[SafetyScreening],
) -> PriorityLevel:
    """
    Ensure the final priority level cannot be lower than deterministic safety flags:
      - Any 'critical' flag -> at least HIGH
      - Any 'high' flag     -> at least MEDIUM
    """
    if not safety_screening or not safety_screening.red_flags:
        return level

    has_critical = any(getattr(f, "severity", None) == "critical" for f in safety_screening.red_flags)
    has_high = any(getattr(f, "severity", None) == "high" for f in safety_screening.red_flags)

    if has_critical:
        return PriorityLevel.HIGH
    if has_high and level == PriorityLevel.LOW:
        return PriorityLevel.MEDIUM

    return level


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

    # 0.6: Do NOT discount high-risk symptoms by confidence. Uncertain chest pain
    # or breathing difficulty must retain full score so it escalates to at least MEDIUM/HIGH.
    is_high_risk = name in _HIGH_RISK_SYMPTOMS or _HIGH_RISK_SYMPTOM_WEIGHT.get(name, 0.0) >= 3.0
    if not is_high_risk:
        score *= max(symptom.confidence, 0.2)
    return score


def _score_summary(summary: StructuredMedicalSummary) -> float:
    """Fallback rule-based weighted score calculation."""
    score = sum(_score_symptom(s) for s in summary.symptoms)
    score += 1.5 * len(summary.red_flags)
    return round(score, 2)


# Patient-context escalation rules
def _age_escalation(patient_context: dict, summary: StructuredMedicalSummary) -> tuple[float, list[str]]:
    """Apply age-aware escalation rules. Returns (bonus_score, reasons)."""
    extra_score = 0.0
    reasons = []
    
    age_raw = patient_context.get("age")
    if age_raw is None:
        return extra_score, reasons
    
    try:
        age_str = str(age_raw).strip().lower()
        # Handle infant age in months
        if any(unit in age_str for unit in ["month", "week", "day", "mth"]):
            import re
            digits = re.findall(r"\d+", age_str)
            if digits:
                age_months = float(digits[0])
                # Convert to years for scoring
                age = age_months / 12.0
            else:
                return extra_score, reasons
        else:
            import re
            digits = re.findall(r"\d+", age_str)
            if digits:
                age = float(digits[0])
            else:
                return extra_score, reasons
    except (ValueError, TypeError):
        return extra_score, reasons
    
    # Infant rules (age < 1 year)
    if age < 1:
        # Any symptom in infants is elevated
        fever = any(s.name.lower() == "fever" for s in summary.symptoms if not s.negated)
        if fever:
            extra_score += 4.0  # Infant fever is always critical
            reasons.append(f"Age escalation: infant fever (age={age:.1f}y) - critical")
        else:
            extra_score += 2.0  # All infant presentations escalated
            reasons.append(f"Age escalation: infant (age={age:.1f}y) - elevated")
    
    # Children under 5
    elif age < 5:
        fever = any(s.name.lower() == "fever" for s in summary.symptoms if not s.negated)
        diarrhea = any(s.name.lower() == "diarrhea" for s in summary.symptoms if not s.negated)
        if fever:
            extra_score += 2.0
            reasons.append(f"Age escalation: child fever (age={age:.0f}y) - elevated")
        if diarrhea:
            extra_score += 1.5
            reasons.append(f"Age escalation: child diarrhea (age={age:.0f}y) - dehydration risk")
        extra_score += 0.5  # Baseline child escalation
    
    # Elderly (>= 60)
    elif age >= 60:
        extra_score += 1.0  # Baseline elderly escalation
        reasons.append(f"Age escalation: elderly (age={age:.0f}y)")
        # Elderly with fever
        fever = any(s.name.lower() == "fever" for s in summary.symptoms if not s.negated)
        if fever:
            extra_score += 1.0
            reasons.append(f"Age escalation: elderly fever (age={age:.0f}y) - elevated")
    
    return extra_score, reasons


def _pregnancy_escalation(patient_context: dict, summary: StructuredMedicalSummary) -> tuple[float, list[str]]:
    """Check for pregnancy and apply obstetric red flag escalation."""
    extra_score = 0.0
    reasons = []
    
    # Detect pregnancy from patient_context
    is_pregnant = str(patient_context.get("is_pregnant", "")).strip().lower() in ("yes", "true", "1")
    if not is_pregnant:
        is_pregnant = str(patient_context.get("pregnancy", "")).strip().lower() in ("yes", "true", "1")
    if not is_pregnant:
        context_str = " ".join(f"{v}".lower() for v in patient_context.values())
        conditions_str = " ".join(summary.existing_conditions).lower()
        history_str = (summary.relevant_history or "").lower()
        combined = f"{context_str} {conditions_str} {history_str}"
        if any(pw in combined for pw in ["pregnant", "pregnancy", "trimester", "gestation"]):
            is_pregnant = True
    
    if not is_pregnant:
        return extra_score, reasons
    
    extra_score += 1.0  # Baseline pregnancy escalation
    reasons.append("Pregnancy escalation: pregnant patient")
    
    # Obstetric red flags
    for symptom in summary.symptoms:
        if symptom.negated:
            continue
        name = symptom.name.lower()
        if "bleeding" in name:
            extra_score += 4.0
            reasons.append("Obstetric emergency: bleeding in pregnancy")
        if "abdominal pain" in name or "stomach pain" in name:
            extra_score += 2.0
            reasons.append("Obstetric concern: abdominal pain in pregnancy")
        if "headache" in name and symptom.severity in (Severity.SEVERE, Severity.UNBEARABLE):
            extra_score += 2.0
            reasons.append("Obstetric concern: severe headache in pregnancy (pre-eclampsia risk)")
    
    return extra_score, reasons


_ESCALATING_COMORBIDITIES = {
    "diabetes", "sugar", "diabetic", "type 1 diabetes", "type 2 diabetes",
    "hypertension", "bp", "high blood pressure", "high bp",
    "heart disease", "cardiac", "heart condition", "heart failure",
    "immunocompromised", "hiv", "aids", "cancer", "chemotherapy",
    "kidney disease", "renal", "dialysis",
    "liver disease", "cirrhosis",
    "asthma", "copd", "lung disease",
}

def _comorbidity_escalation(patient_context: dict, summary: StructuredMedicalSummary) -> tuple[float, list[str]]:
    """Apply comorbidity-based escalation."""
    extra_score = 0.0
    reasons = []
    
    # Collect all known conditions from patient_context and summary
    conditions = []
    known = patient_context.get("known_conditions", "")
    if known and str(known).strip().lower() not in ("none", "nil", "no", "na", "n/a", ""):
        conditions.extend([c.strip().lower() for c in str(known).split(",")])
    conditions.extend([c.strip().lower() for c in summary.existing_conditions])
    
    matched = set()
    for cond in conditions:
        if cond in ("none", "nil", "no", "na", "n/a", ""):
            continue
        for escalating in _ESCALATING_COMORBIDITIES:
            if escalating in cond or cond in escalating:
                matched.add(cond)
                break
    
    if matched:
        extra_score += 1.0 * min(len(matched), 3)  # Cap at 3.0
        reasons.append(f"Comorbidity escalation: {', '.join(list(matched)[:3])}")
    
    return extra_score, reasons


def determine_urgency_tier(
    level: PriorityLevel,
    emergency_override: bool = False,
    safety_screening: Optional[SafetyScreening] = None,
    score: float = 0.0,
) -> Tuple[UrgencyTier, int]:
    """
    Map PriorityLevel and clinical safety signals to the 4 product urgency tiers:
      - emergency: Immediate emergency, call 108/112 (critical flags / override)
      - doctor_today: Needs clinical review today / within 24 hours (HIGH or acute MEDIUM)
      - doctor_soon: Needs clinical consultation in 2-3 days (MEDIUM / PENDING_REVIEW)
      - self_care: Safe for home care with monitoring and 2-3 day follow-up (LOW)
    Returns: (urgency_tier, follow_up_days)
    """
    if emergency_override or (safety_screening and safety_screening.has_critical_flags):
        return UrgencyTier.EMERGENCY, 0

    if level == PriorityLevel.HIGH:
        if safety_screening and any(f.severity == "critical" for f in safety_screening.red_flags):
            return UrgencyTier.EMERGENCY, 0
        return UrgencyTier.DOCTOR_TODAY, 1

    if level == PriorityLevel.MEDIUM:
        if score >= 40.0:
            return UrgencyTier.DOCTOR_TODAY, 1
        return UrgencyTier.DOCTOR_SOON, 2

    if level == PriorityLevel.PENDING_REVIEW:
        return UrgencyTier.DOCTOR_SOON, 2

    return UrgencyTier.SELF_CARE, 3


def assess_priority(
    summary: StructuredMedicalSummary,
    patient_context: Optional[dict] = None,
    safety_screening: Optional[SafetyScreening] = None,
    features: Optional[dict] = None,
) -> PriorityAssessment:
    """
    Assess patient priority level using Safety Engine + ML Model with Rule-Based Fallback.
    """
    patient_context = patient_context or {}

   
    if safety_screening is None:
        safety_screening = screen_safety(summary)

    # 2. Calculate fallback rule score
    rule_score = _score_summary(summary)
    triggered_rules = [f.reason for f in safety_screening.red_flags]

    # Phase 1: Patient-context escalation rules
    age_bonus, age_reasons = _age_escalation(patient_context, summary)
    preg_bonus, preg_reasons = _pregnancy_escalation(patient_context, summary)
    comorbidity_bonus, comorbidity_reasons = _comorbidity_escalation(patient_context, summary)

    context_bonus = age_bonus + preg_bonus + comorbidity_bonus
    context_reasons = age_reasons + preg_reasons + comorbidity_reasons

    rule_score += context_bonus
    triggered_rules.extend(context_reasons)

    # 3. Check for Emergency / Safety Override
    if safety_screening.override_priority or safety_screening.has_critical_flags:
        logger.info("Safety override triggered priority=HIGH reasons=%s", triggered_rules)
        tier, fu_days = determine_urgency_tier(
            PriorityLevel.HIGH,
            emergency_override=True,
            safety_screening=safety_screening,
            score=rule_score,
        )
        return PriorityAssessment(
            level=PriorityLevel.HIGH,
            urgency_tier=tier,
            follow_up_days=fu_days,
            confidence=1.0,
            emergency_override=True,
            triggered_rules=triggered_rules,
            reasons=triggered_rules or ["Critical safety indicator detected"],
            score=rule_score,
            model_used="safety_override",
        )

    # 4. Use pre-computed features if provided, otherwise extract now
    if features is None:
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

            # Sanity gate: never let ML predict LOW when the rule-based score
            # is firmly in the HIGH range — the rule engine has better signal
            # for symptoms the ML model was not trained on.
            if level == PriorityLevel.LOW and rule_score >= HIGH_THRESHOLD:
                logger.warning(
                    "ML sanity gate: elevating ML LOW to MEDIUM because rule_score=%.2f >= HIGH_THRESHOLD=%.1f",
                    rule_score, HIGH_THRESHOLD,
                )
                level = PriorityLevel.MEDIUM
                confidence = max(confidence, 0.6)
                reasons = reasons + [f"Safety floor: rule-based score {rule_score:.1f} conflicts with ML LOW"]

            # 0.1 Apply deterministic safety floor (high flag -> at least MEDIUM, critical -> HIGH)
            floored_level = apply_floor(level, safety_screening)
            if floored_level != level:
                logger.warning("apply_floor elevated ML priority from %s to %s", level, floored_level)
                reasons = reasons + [f"Safety floor applied: elevated from {level.value} to {floored_level.value} due to deterministic safety flag"]
                level = floored_level
                confidence = max(confidence, 0.8)

            # 0.3 Insufficient input floor: empty extraction never yields LOW
            active_symptoms = [s for s in summary.symptoms if not s.negated]
            if len(active_symptoms) == 0 and not safety_screening.red_flags and level == PriorityLevel.LOW:
                logger.warning("Empty extraction floor elevated ML priority from LOW to MEDIUM")
                level = PriorityLevel.MEDIUM
                confidence = max(confidence, 0.6)
                reasons = reasons + ["Empty extraction floor: no active symptoms detected, routing to MEDIUM for clinician review"]

            # Phase 1: missing_critical_info floor to MEDIUM
            if safety_screening.missing_critical_info and level == PriorityLevel.LOW:
                level = PriorityLevel.MEDIUM
                reasons.append(f"Missing critical info floor: {'; '.join(safety_screening.missing_critical_info)}")

            logger.info("ML priority assessment level=%s conf=%.2f reasons=%s", level, confidence, reasons)
            tier, fu_days = determine_urgency_tier(
                level,
                emergency_override=False,
                safety_screening=safety_screening,
                score=rule_score,
            )
            return PriorityAssessment(
                level=level,
                urgency_tier=tier,
                follow_up_days=fu_days,
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

    # 0.1 Apply deterministic safety floor to rule engine output
    floored_level = apply_floor(level, safety_screening)
    if floored_level != level:
        logger.warning("apply_floor elevated fallback rule priority from %s to %s", level, floored_level)
        conf = max(conf, 0.8)
        level = floored_level

    # 0.3 Insufficient input floor: empty extraction never yields LOW
    active_symptoms = [s for s in summary.symptoms if not s.negated]
    if len(active_symptoms) == 0 and not safety_screening.red_flags and level == PriorityLevel.LOW:
        logger.warning("Empty extraction floor elevated fallback rule priority from LOW to MEDIUM")
        level = PriorityLevel.MEDIUM
        conf = max(conf, 0.6)

    fallback_reasons = [f"Rule-based score {rule_score:.2f}"]
    if floored_level != level:
        fallback_reasons.append(f"Safety floor applied: elevated to {level.value} due to deterministic safety flag")
    if len(active_symptoms) == 0 and not safety_screening.red_flags:
        fallback_reasons.append("Empty extraction floor: no active symptoms detected, routing to MEDIUM for clinician review")
    for s in summary.symptoms:
        if not s.negated and s.confidence >= 0.3:
            fallback_reasons.append(f"Reported symptom: {s.name}")

    # Phase 1: missing_critical_info floor to MEDIUM
    if safety_screening.missing_critical_info and level == PriorityLevel.LOW:
        level = PriorityLevel.MEDIUM
        fallback_reasons.append(f"Missing critical info floor: {'; '.join(safety_screening.missing_critical_info)}")

    logger.info("Rule-based fallback priority assessment level=%s score=%.2f", level, rule_score)
    tier, fu_days = determine_urgency_tier(
        level,
        emergency_override=False,
        safety_screening=safety_screening,
        score=rule_score,
    )
    return PriorityAssessment(
        level=level,
        urgency_tier=tier,
        follow_up_days=fu_days,
        confidence=conf,
        emergency_override=False,
        triggered_rules=triggered_rules,
        reasons=fallback_reasons[:5],
        score=rule_score,
        model_used="rule_based",
    )
