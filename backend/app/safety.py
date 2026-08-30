import logging
from typing import List, Tuple

from app.schemas import (
    StructuredMedicalSummary,
    SafetyScreening,
    SafetyRedFlag,
    Severity,
)

logger = logging.getLogger('rural_care.safety')

# Format: (keywords_to_match, requires_severe_flag, severity_output, action_output, reason_output)
RED_FLAG_RULES: List[Tuple[List[str], bool, str, str, str]] = [
    (["severe chest pain", "unbearable chest pain"], False, "critical", "emergency_referral", "Severe chest pain reported"),
    (["chest pain"], True, "critical", "emergency_referral", "Severe chest pain reported"),
    (["chest pain"], False, "high", "clinician_review", "Chest pain reported"),

    (["difficulty breathing", "shortness of breath"], False, "critical", "emergency_referral", "Breathing difficulty reported"),
    
    (["loss of consciousness", "fainting", "unconscious"], False, "critical", "emergency_referral", "Loss of consciousness reported"),
    
    (["severe bleeding", "heavy bleeding", "uncontrolled bleeding"], False, "critical", "emergency_referral", "Severe bleeding reported"),
    (["bleeding"], True, "critical", "emergency_referral", "Severe bleeding reported"),
    
    (["seizure", "convulsion", "fits"], False, "critical", "emergency_referral", "Seizure or convulsions reported"),
    
    (["severe allergic reaction", "anaphylaxis"], False, "critical", "emergency_referral", "Severe allergic reaction reported"),
    (["allergic reaction"], True, "critical", "emergency_referral", "Severe allergic reaction reported"),
    
    (["high fever"], False, "high", "clinician_review", "High fever reported"),
    (["fever"], True, "high", "clinician_review", "High fever reported"),
    
    (["suicidal ideation", "self-harm"], False, "critical", "emergency_referral", "Suicidal ideation or self-harm reported"),
    
    (["stroke", "slurred speech", "one-sided weakness", "sudden confusion"], False, "critical", "emergency_referral", "Potential stroke symptoms reported"),
    
    (["poisoning", "ingestion of harmful substance"], False, "critical", "emergency_referral", "Poisoning reported"),
    
    (["severe abdominal pain"], False, "high", "clinician_review", "Severe abdominal pain reported"),
    (["abdominal pain"], True, "high", "clinician_review", "Severe abdominal pain reported"),
    
    (["severe headache", "thunderclap", "worst headache"], False, "high", "clinician_review", "Severe headache reported"),
    (["headache"], True, "high", "clinician_review", "Severe headache reported"),
    
    (["vomiting blood", "blood in stool"], False, "high", "clinician_review", "Vomiting blood or blood in stool reported"),
    
    (["severe dehydration"], False, "high", "clinician_review", "Severe dehydration reported"),
    (["dehydration"], True, "high", "clinician_review", "Severe dehydration reported"),
]

def screen_safety(summary: StructuredMedicalSummary) -> SafetyScreening:
    """
    Evaluates the structured medical summary for predefined red flags.
    This process is deterministic and does not rely on LLM judgements.
    """
    logger.info("Starting safety screening")
    
    red_flags: List[SafetyRedFlag] = []
    missing_critical_info: List[str] = []
    
    has_chest_pain = False
    has_breathing_info = False

    def check_text_against_rules(text: str, is_severe: bool, source_symptom: str) -> None:
        """Helper to match text against defined red flag rules and generate safety flags."""
        text = text.lower()
        matched_reasons = set() # Avoid duplicate flags for the same reason
        
        for keywords, requires_severe, out_severity, out_action, out_reason in RED_FLAG_RULES:
            if out_reason in matched_reasons:
                continue
                
            if requires_severe and not is_severe:
                continue
                
            if any(kw in text for kw in keywords):
                red_flags.append(SafetyRedFlag(
                    potential_red_flag=True,
                    symptom=source_symptom,
                    reason=out_reason,
                    action=out_action,
                    severity=out_severity
                ))
                matched_reasons.add(out_reason)

    # 1. Process symptoms
    for symptom in summary.symptoms:
        # SKIP negated symptoms
        if symptom.negated:
            continue
            
        is_severe = symptom.severity in (Severity.SEVERE, Severity.UNBEARABLE)
        
        text_to_check = symptom.name.lower()
        if symptom.raw_text:
            text_to_check += f" {symptom.raw_text.lower()}"
            
        check_text_against_rules(text_to_check, is_severe, symptom.name)
        
        if "chest pain" in text_to_check:
            has_chest_pain = True
        if any(kw in text_to_check for kw in ["breath", "breathing", "respiration"]):
            has_breathing_info = True

    # 2. Process Gemini-extracted red flags
    for flag in summary.red_flags:
        text_to_check = flag.phrase.lower()
        # Assume these might not have an explicit severity tag, but we check text
        # If it explicitly says "severe", we count it as severe
        is_severe = "severe" in text_to_check or "unbearable" in text_to_check
        source_name = flag.related_symptom if flag.related_symptom else flag.phrase
        
        check_text_against_rules(text_to_check, is_severe, source_name)
        
        if "chest pain" in text_to_check:
            has_chest_pain = True
        if any(kw in text_to_check for kw in ["breath", "breathing", "respiration"]):
            has_breathing_info = True

    # Deduplicate red flags
    unique_flags = []
    seen = set()
    for f in red_flags:
        key = (f.symptom, f.reason, f.severity)
        if key not in seen:
            seen.add(key)
            unique_flags.append(f)
            
    # Remove high flags if a critical flag exists for the SAME reason/symptom family
    # E.g., if we have "Severe chest pain reported" (critical) and "Chest pain reported" (high), keep critical.
    final_flags = []
    for f in unique_flags:
        if f.severity == "high":
            # Check if there's a critical version for this symptom
            has_critical = any(
                other.severity == "critical" 
                and other.symptom == f.symptom 
                and ("chest pain" in f.reason.lower() and "chest pain" in other.reason.lower() or
                     "fever" in f.reason.lower() and "fever" in other.reason.lower())
                for other in unique_flags
            )
            if has_critical:
                continue
        final_flags.append(f)

    # 3. Missing critical info
    if has_chest_pain and not has_breathing_info:
        missing_critical_info.append("Breathing status is unknown for patient with chest pain.")

    # 4. Override behavior
    has_critical_flags = any(f.severity == "critical" for f in final_flags)
    override_priority = has_critical_flags

    return SafetyScreening(
        red_flags=final_flags,
        has_critical_flags=has_critical_flags,
        override_priority=override_priority,
        missing_critical_info=missing_critical_info
    )
