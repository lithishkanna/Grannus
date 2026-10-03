import re
from typing import Optional
from app.schemas import StructuredMedicalSummary, Severity, Frequency, DurationUnit

SYMPTOM_FEATURES = [
    "symptom_headache",
    "symptom_fever",
    "symptom_body_pain",
    "symptom_chest_pain",
    "symptom_cold_like_symptoms",
    "symptom_cough",
    "symptom_difficulty_breathing",
    "symptom_vomiting",
    "symptom_nausea",
    "symptom_diarrhea",
    "symptom_abdominal_pain",
    "symptom_weakness",
    "symptom_fatigue",
    "symptom_dizziness",
    "symptom_loss_of_consciousness",
    "symptom_bleeding",
    "symptom_severe_bleeding",
    "symptom_hair_loss"
]

AGGREGATE_FEATURES = [
    "num_symptoms",
    "num_red_flags",
    "max_severity",
    "has_continuous_symptom",
    "has_frequent_symptom",
    "max_duration_days",
    "has_existing_conditions",
    "num_existing_conditions",
    "has_medications",
    "has_allergies",
    "severity_unknown",
    "num_low_confidence_symptoms",
    "num_safety_flags",
    "has_critical_safety_flag"
]

CONTEXT_FEATURES = [
    "age_group",
    "gender_male",
    "gender_female",
    "age_missing"
]

BIOMARKER_FEATURES = [
    "biomarker_cough_rate",
    "biomarker_wheeze_ratio",
    "biomarker_distress_score"
]

def get_feature_columns() -> list[str]:
    return SYMPTOM_FEATURES + AGGREGATE_FEATURES + CONTEXT_FEATURES + BIOMARKER_FEATURES

SEVERITY_MAP = {
    Severity.SLIGHT: 1,
    Severity.MILD: 2,
    Severity.MODERATE: 3,
    Severity.SEVERE: 4,
    Severity.UNBEARABLE: 5
}

def _symptom_to_feature_name(symptom_name: str) -> str:
    # "cold-like symptoms" -> "symptom_cold_like_symptoms"
    cleaned = re.sub(r'[^a-z0-9]', '_', symptom_name.lower())
    # remove duplicate underscores
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return f"symptom_{cleaned}"

def _duration_to_days(value: float, unit: DurationUnit) -> float:
    if unit == DurationUnit.MINUTES:
        return value / 1440.0
    if unit == DurationUnit.HOURS:
        return value / 24.0
    if unit == DurationUnit.DAYS:
        return value
    if unit == DurationUnit.WEEKS:
        return value * 7.0
    if unit == DurationUnit.MONTHS:
        return value * 30.0
    return 0.0

def _get_age_group(age: int) -> int:
    if age is None:
        return -1
    if age <= 1:
        return 0
    if age <= 4:
        return 1
    if age <= 12:
        return 2
    if age <= 19:
        return 3
    if age <= 59:
        return 4
    return 5

from app.schemas import AcousticBiomarkerResult, SafetyScreening

def extract_features(summary: StructuredMedicalSummary, patient_context: Optional[dict] = None, safety_screening: Optional[SafetyScreening] = None, biomarkers: Optional[AcousticBiomarkerResult] = None) -> dict:
    features = {col: 0 for col in get_feature_columns()}
    
    if patient_context is None:
        patient_context = {}

    # Patient Context
    age = patient_context.get("age")
    if age is not None:
        try:
            features["age_group"] = _get_age_group(int(age))
        except (ValueError, TypeError):
            features["age_group"] = -1
            features["age_missing"] = 1
    else:
        features["age_group"] = -1
        features["age_missing"] = 1
            
    gender = str(patient_context.get("gender", "")).lower()
    if gender in ["male", "m"]:
        features["gender_male"] = 1
    elif gender in ["female", "f"]:
        features["gender_female"] = 1

    # Symptoms
    valid_symptoms = []
    max_severity = 0
    has_continuous = 0
    has_frequent = 0
    max_duration = 0.0
    num_low_confidence = 0
    any_severity_specified = False
    
    for symptom in summary.symptoms:
        if symptom.negated:
            continue
        
        feature_name = _symptom_to_feature_name(symptom.name)
        
        if symptom.confidence < 0.3:
            num_low_confidence += 1
            if feature_name in features:
                features[feature_name] = 0.5
            continue
            
        valid_symptoms.append(symptom)
        if feature_name in features:
            features[feature_name] = 1
            
        if symptom.severity:
            any_severity_specified = True
            val = SEVERITY_MAP.get(symptom.severity, 0)
            max_severity = max(max_severity, val)
            
        if symptom.frequency:
            if symptom.frequency == Frequency.CONTINUOUS:
                has_continuous = 1
            elif symptom.frequency == Frequency.FREQUENT:
                has_frequent = 1
                
        if symptom.duration and symptom.duration.value and symptom.duration.unit:
            try:
                days = _duration_to_days(symptom.duration.value, symptom.duration.unit)
                max_duration = max(max_duration, days)
            except Exception:
                pass

    features["num_symptoms"] = len(valid_symptoms)
    features["num_red_flags"] = len(summary.red_flags)
    features["max_severity"] = max_severity
    features["has_continuous_symptom"] = has_continuous
    features["has_frequent_symptom"] = has_frequent
    features["max_duration_days"] = max_duration
    features["severity_unknown"] = 0 if any_severity_specified else 1
    features["num_low_confidence_symptoms"] = num_low_confidence
    
    features["num_existing_conditions"] = len(summary.existing_conditions)
    features["has_existing_conditions"] = 1 if summary.existing_conditions else 0
    features["has_medications"] = 1 if summary.medications else 0
    features["has_allergies"] = 1 if summary.allergies else 0
    
    if safety_screening is not None:
        features["num_safety_flags"] = len(safety_screening.red_flags)
        features["has_critical_safety_flag"] = 1 if any(f.severity == "critical" for f in safety_screening.red_flags) else 0
    
    if biomarkers is not None:
        features["biomarker_cough_rate"] = getattr(biomarkers, "cough_rate", biomarkers.cough_count / 1.0)
        features["biomarker_wheeze_ratio"] = biomarkers.wheeze_ratio
        features["biomarker_distress_score"] = biomarkers.respiratory_distress_score
    
    return features
