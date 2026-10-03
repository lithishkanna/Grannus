"""
Transparent Clinical Scoring Engine for Grannus RuralCare AI.

Provides an explainable, deterministic clinical scoring protocol inspired by:
  - WHO IMCI (Integrated Management of Childhood Illness) Danger Signs
  - NEWS2 (National Early Warning Score) Physiological Risk Stratification
  - Indian National Telemedicine Triage Guidelines

Acts as a transparent clinical baseline and fallback alongside ML model predictions.
"""
from typing import Dict, List, Optional, Tuple
from app.schemas import (
    PriorityAssessment,
    PriorityLevel,
    SafetyScreening,
    StructuredMedicalSummary,
    Severity,
    Frequency,
)

# Critical danger signs inspired by WHO IMCI & Emergency Triage Assessment (ETAT)
WHO_DANGER_SIGNS = {
    "convulsion", "seizure", "fits",
    "loss of consciousness", "unconscious", "lethargic", "floppy",
    "cannot breathe", "difficulty breathing", "stridor", "cyanosis", "blue lips",
    "severe chest pain", "heart attack",
    "severe bleeding", "uncontrolled bleeding",
    "snakebite", "scorpion sting", "poisoning", "pesticide",
    "severe burns", "head injury",
}

# Organ system weights for transparent additive scoring
PHYSIOLOGICAL_SYSTEM_SCORES = {
    "cardiovascular": 4.0,   # Chest pain, palpitations with dizziness
    "respiratory": 4.0,      # Dyspnea, wheeze with distress
    "neurological": 4.0,     # Seizures, altered sensorium, focal weakness
    "toxicology": 4.0,       # Snakebite, poison, envenomation
    "gastrointestinal": 2.0, # Severe abdominal pain, persistent vomiting
    "infectious_high": 2.5,  # High continuous fever with chills
    "musculoskeletal": 0.5,  # Generalized aches
}


class TransparentTriageResult:
    def __init__(
        self,
        level: PriorityLevel,
        total_score: float,
        danger_signs: List[str],
        contributing_factors: List[str],
        protocol_applied: str,
        is_emergency: bool,
    ):
        self.level = level
        self.total_score = total_score
        self.danger_signs = danger_signs
        self.contributing_factors = contributing_factors
        self.protocol_applied = protocol_applied
        self.is_emergency = is_emergency

    def to_dict(self) -> Dict:
        return {
            "level": self.level.value,
            "total_score": round(self.total_score, 2),
            "danger_signs": self.danger_signs,
            "contributing_factors": self.contributing_factors,
            "protocol_applied": self.protocol_applied,
            "is_emergency": self.is_emergency,
        }


def assess_transparent_triage(
    summary: StructuredMedicalSummary,
    patient_context: Optional[dict] = None,
    safety_screening: Optional[SafetyScreening] = None,
) -> TransparentTriageResult:
    """
    Computes deterministic, point-based transparent triage using WHO IMCI / NEWS2 rural protocols.
    
    Tiers:
      - Tier 1 (HIGH, Emergency Referral): Any IMCI Danger Sign OR total_score >= 6.0
      - Tier 2 (MEDIUM, Priority Review within 12-24h): Score 3.0 to 5.9 OR vulnerability modifier
      - Tier 3 (LOW, Self-care & Home Remedy): Score < 3.0 AND no danger signs AND no gate exclusions
    """
    patient_context = patient_context or {}
    danger_signs_found: List[str] = []
    contributing_factors: List[str] = []
    score = 0.0

    # 1. Step 1: Check Deterministic Safety Screen
    if safety_screening and safety_screening.has_critical_flags:
        for f in safety_screening.red_flags:
            if f.severity == "critical":
                danger_signs_found.append(f.reason)
        return TransparentTriageResult(
            level=PriorityLevel.HIGH,
            total_score=10.0,
            danger_signs=danger_signs_found,
            contributing_factors=["Critical safety red flag detected"],
            protocol_applied="WHO_ETAT_CRITICAL_OVERRIDE",
            is_emergency=True,
        )

    # 2. Step 2: WHO Danger Signs Scan in Symptoms & Red Flags
    for symptom in summary.symptoms:
        if symptom.negated:
            continue
        s_name = (symptom.name or "").lower()
        for ds in WHO_DANGER_SIGNS:
            if ds in s_name:
                danger_signs_found.append(f"WHO Danger Sign: {s_name}")
                score += 4.0

    if danger_signs_found:
        return TransparentTriageResult(
            level=PriorityLevel.HIGH,
            total_score=max(score, 6.0),
            danger_signs=danger_signs_found,
            contributing_factors=danger_signs_found,
            protocol_applied="WHO_IMCI_DANGER_SIGNS",
            is_emergency=True,
        )

    # 3. Step 3: Additive Physiological & Symptom Severity Scoring
    for symptom in summary.symptoms:
        if symptom.negated:
            continue
        s_name = (symptom.name or "").lower()
        item_score = 0.5  # default baseline

        if any(k in s_name for k in ["chest", "heart"]):
            item_score = 3.0
        elif any(k in s_name for k in ["breath", "wheeze"]):
            item_score = 3.5
        elif any(k in s_name for k in ["headache", "abdominal"]):
            item_score = 1.5
        elif any(k in s_name for k in ["fever", "diarrhea", "vomiting"]):
            item_score = 1.0

        # Severity multiplier
        if symptom.severity == Severity.UNBEARABLE:
            item_score += 3.0
            contributing_factors.append(f"Unbearable {s_name} (+3.0)")
        elif symptom.severity == Severity.SEVERE:
            item_score += 2.0
            contributing_factors.append(f"Severe {s_name} (+2.0)")
        elif symptom.severity == Severity.MODERATE:
            item_score += 1.0

        if symptom.frequency in (Frequency.CONTINUOUS, Frequency.FREQUENT):
            item_score += 0.5

        score += item_score

    # 4. Step 4: Vulnerability & Demographic Modifiers (Age, Pregnancy, Comorbidity)
    age_raw = patient_context.get("age")
    if age_raw:
        try:
            import re
            digits = re.findall(r"\d+", str(age_raw))
            if digits:
                age_val = float(digits[0])
                if "month" in str(age_raw).lower() or age_val <= 1:
                    score += 2.5
                    contributing_factors.append("Infant presentation vulnerability (+2.5)")
                elif age_val < 5:
                    score += 1.0
                    contributing_factors.append("Child <5 vulnerability (+1.0)")
                elif age_val >= 60:
                    score += 1.0
                    contributing_factors.append("Elderly >=60 vulnerability (+1.0)")
        except Exception:
            pass

    # Pregnancy modifier
    is_preg = str(patient_context.get("is_pregnant", "")).lower() in ("yes", "true", "1")
    if is_preg:
        score += 2.0
        contributing_factors.append("Maternal pregnancy modifier (+2.0)")

    # Comorbidity modifier
    known_conds = patient_context.get("known_conditions", "")
    if known_conds and str(known_conds).lower() not in ("none", "nil", "no", "na", ""):
        score += 1.5
        contributing_factors.append(f"Comorbidity modifier ({known_conds}) (+1.5)")

    # 5. Final Thresholding
    if score >= 6.0:
        level = PriorityLevel.HIGH
        is_emergency = True
    elif score >= 3.0:
        level = PriorityLevel.MEDIUM
        is_emergency = False
    else:
        # Check safety screening missing critical info floor
        if safety_screening and safety_screening.missing_critical_info:
            level = PriorityLevel.MEDIUM
            contributing_factors.append("Missing critical info floor -> MEDIUM")
        else:
            level = PriorityLevel.LOW
        is_emergency = False

    return TransparentTriageResult(
        level=level,
        total_score=round(score, 2),
        danger_signs=danger_signs_found,
        contributing_factors=contributing_factors,
        protocol_applied="RURAL_TELEHEALTH_TRANSPARENT_PROTOCOL_V1",
        is_emergency=is_emergency,
    )
