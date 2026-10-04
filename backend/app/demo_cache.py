"""
Pre-cached demonstration dataset and pipeline results for Grannus RuralCare AI (B7.6).

Provides 100% offline-resilient, deterministic execution for the 8 standard clinical scenarios:
  1. chest_pain_60y      -> EMERGENCY (Cardiology red flag)
  2. child_fever_2y      -> DOCTOR_TODAY (Pediatric fever < 5y)
  3. cough_3_days        -> SELF_CARE (Approved cough & cold protocol)
  4. runny_nose_sneezing -> SELF_CARE (Approved upper respiratory & headache protocol)
  5. pregnant_bleeding   -> EMERGENCY (OBGYN obstetric emergency)
  6. vomiting_blood      -> EMERGENCY (Hematemesis emergency)
  7. leg_pain            -> SELF_CARE (Approved calf & leg strain protocol)
  8. hair_loss           -> SELF_CARE (Approved scalp & hair fall protocol)
"""
import uuid
import time
from typing import Dict, List, Optional, Any

from app.schemas import (
    PipelineResult,
    PatientInput,
    ClinicalSummary,
    SafetyScreeningOutput,
    SafetyRedFlag,
    PriorityAssessment,
    PriorityLevel,
    UrgencyTier,
    Symptom,
    Duration,
    DurationUnit,
    Severity,
    FieldConfidence,
    HomeRemedyGuidance,
    HomeRemedyCareStep,
)
from app.remedy_library import get_approved_home_remedy_guidance


DEMO_SAMPLE_METADATA: List[Dict[str, Any]] = [
    {
        "id": "chest_pain_60y",
        "title": "Severe Chest Pain & Sweating (60M)",
        "patient": {"age": 60, "gender": "male", "relation": "Self"},
        "expected_tier": "emergency",
        "complaint_category": "cardiac_symptoms",
        "description": "60-year-old male with crushing substernal chest pain radiating to left shoulder, profuse sweating, and breathlessness.",
        "transcript_original": "I am feeling heavy pain in my chest for the last 2 hours. It is spreading to my left shoulder and I am sweating a lot. Finding it hard to breathe.",
        "language": "en-IN",
    },
    {
        "id": "child_fever_2y",
        "title": "High Fever & Vomiting in Toddler (2F)",
        "patient": {"age": 2, "gender": "female", "relation": "Daughter"},
        "expected_tier": "doctor_today",
        "complaint_category": "pediatric_illness",
        "description": "2-year-old child with continuous high fever (103°F) for 2 days, vomiting, and irritability.",
        "transcript_original": "My two-year-old baby girl has had burning fever for two days. She vomited twice this morning and is crying continuously.",
        "language": "en-IN",
    },
    {
        "id": "cough_3_days",
        "title": "Mild Cough & Throat Irritation (35M)",
        "patient": {"age": 35, "gender": "male", "relation": "Self"},
        "expected_tier": "self_care",
        "complaint_category": "general_medical",
        "description": "35-year-old male with mild dry cough for 3 days, throat tickle, no fever or shortness of breath.",
        "transcript_original": "I have had a mild dry cough and slight scratchy throat for 3 days. No fever, no chest pain, breathing normally.",
        "language": "en-IN",
    },
    {
        "id": "runny_nose_sneezing",
        "title": "Runny Nose & Mild Headache (24F)",
        "patient": {"age": 24, "gender": "female", "relation": "Self"},
        "expected_tier": "self_care",
        "complaint_category": "general_medical",
        "description": "24-year-old female with clear runny nose, sneezing, and forehead tension headache.",
        "transcript_original": "I have been sneezing since yesterday with clear runny nose and a mild tension headache across my forehead. No fever.",
        "language": "en-IN",
    },
    {
        "id": "pregnant_bleeding",
        "title": "Pregnancy with Vaginal Bleeding (27F)",
        "patient": {"age": 27, "gender": "female", "relation": "Wife"},
        "expected_tier": "emergency",
        "complaint_category": "obstetric_gynecological",
        "description": "27-year-old woman in 24th week of pregnancy presenting with fresh vaginal bleeding and lower abdominal cramping.",
        "transcript_original": "I am 6 months pregnant and noticed fresh vaginal bleeding this morning with sharp cramping in my lower abdomen.",
        "language": "en-IN",
    },
    {
        "id": "vomiting_blood",
        "title": "Hematemesis / Vomiting Blood (48M)",
        "patient": {"age": 48, "gender": "male", "relation": "Self"},
        "expected_tier": "emergency",
        "complaint_category": "acute_emergency",
        "description": "48-year-old male with two episodes of dark red coffee-ground blood in vomit and acute dizziness.",
        "transcript_original": "I vomited twice today and there was dark red blood in the vomit. I feel very dizzy and weak when standing up.",
        "language": "en-IN",
    },
    {
        "id": "leg_pain",
        "title": "Calf Muscle Cramp & Strain (42M)",
        "patient": {"age": 42, "gender": "male", "relation": "Self"},
        "expected_tier": "self_care",
        "complaint_category": "general_medical",
        "description": "42-year-old male with calf muscle soreness after heavy field harvesting, no leg swelling or redness.",
        "transcript_original": "Both my calf muscles are sore and aching after 10 hours of harvesting in the fields. No swelling, no redness, no chest pain.",
        "language": "en-IN",
    },
    {
        "id": "hair_loss",
        "title": "Gradual Scalp Hair Shedding (29F)",
        "patient": {"age": 29, "gender": "female", "relation": "Self"},
        "expected_tier": "self_care",
        "complaint_category": "general_medical",
        "description": "29-year-old female noticing increased hair fall when combing over the last 2 months, scalp is dry without rash.",
        "transcript_original": "I have noticed increased hair fall while washing and combing my hair over the last 2 months. Scalp is dry, no bald patches or itching.",
        "language": "en-IN",
    },
]


def list_cached_sample_cases() -> List[Dict[str, Any]]:
    """Return available sample cases for demo selection and evaluation."""
    return DEMO_SAMPLE_METADATA


def get_cached_demo_response(sample_id: str, language_code: str = "en-IN") -> Optional[PipelineResult]:
    """
    Retrieve pre-cached, deterministic PipelineResult for one of the 8 sample cases.
    Guarantees instant demo response without external API dependencies.
    """
    meta = next((m for m in DEMO_SAMPLE_METADATA if m["id"] == sample_id), None)
    if not meta:
        return None

    req_id = str(uuid.uuid4())
    transcript = meta["transcript_original"]
    expected_tier = meta["expected_tier"]

    # 1. Clinical Summary
    summary = ClinicalSummary(
        chief_complaint=meta["description"],
        field_confidence=FieldConfidence(chief_complaint=0.98, symptoms=0.95),
        extraction_notes="Pre-cached clinical trial dataset (B7.6 demonstration)",
    )

    red_flags: List[SafetyRedFlag] = []
    care_guidance: Optional[HomeRemedyGuidance] = None

    if sample_id == "chest_pain_60y":
        summary.symptoms = [
            Symptom(name="chest pain", severity=Severity.SEVERE, body_location="chest / substernal", confidence=0.99),
            Symptom(name="sweating", confidence=0.95),
            Symptom(name="difficulty breathing", confidence=0.95),
        ]
        red_flags.append(SafetyRedFlag(
            potential_red_flag=True,
            symptom="chest pain with sweating and breathlessness",
            reason="Chest pain in patient age 40+ with sweating and breathlessness indicates potential acute coronary syndrome.",
            action="emergency_referral",
            severity="critical",
        ))
        priority = PriorityAssessment(
            level=PriorityLevel.HIGH,
            urgency_tier=UrgencyTier.EMERGENCY,
            follow_up_days=0,
            emergency_override=True,
            confidence=0.99,
            reasons=["Chest pain in patient age 60 with diaphoresis (sweating)", "Safety Invariant B1.1 triggered"],
            model_used="safety_override",
        )

    elif sample_id == "child_fever_2y":
        summary.symptoms = [
            Symptom(name="fever", duration=Duration(value=2.0, raw_text="2 days"), confidence=0.98),
            Symptom(name="vomiting", confidence=0.95),
            Symptom(name="irritability", confidence=0.90),
        ]
        red_flags.append(SafetyRedFlag(
            potential_red_flag=True,
            symptom="high fever in child under 5",
            reason="High fever lasting 2 days with vomiting in a 2-year-old infant/child requires same-day pediatric examination.",
            action="clinician_review",
            severity="high",
        ))
        priority = PriorityAssessment(
            level=PriorityLevel.HIGH,
            urgency_tier=UrgencyTier.DOCTOR_TODAY,
            follow_up_days=1,
            confidence=0.95,
            reasons=["Child under 5 years with high fever and vomiting", "Safety Invariant B1.1 (child fever -> doctor_today)"],
            model_used="rule_based",
        )

    elif sample_id == "pregnant_bleeding":
        summary.symptoms = [
            Symptom(name="vaginal bleeding", confidence=0.99),
            Symptom(name="abdominal cramps", body_location="lower abdomen", confidence=0.95),
        ]
        red_flags.append(SafetyRedFlag(
            potential_red_flag=True,
            symptom="vaginal bleeding during pregnancy",
            reason="Vaginal bleeding during pregnancy requires immediate emergency obstetric care.",
            action="emergency_referral",
            severity="critical",
        ))
        priority = PriorityAssessment(
            level=PriorityLevel.HIGH,
            urgency_tier=UrgencyTier.EMERGENCY,
            follow_up_days=0,
            emergency_override=True,
            confidence=0.99,
            reasons=["Pregnancy with vaginal bleeding and abdominal cramping", "Safety Invariant B1.1 triggered"],
            model_used="safety_override",
        )

    elif sample_id == "vomiting_blood":
        summary.symptoms = [
            Symptom(name="vomiting blood", confidence=0.99),
            Symptom(name="dizziness", confidence=0.92),
        ]
        red_flags.append(SafetyRedFlag(
            potential_red_flag=True,
            symptom="hematemesis (vomiting blood)",
            reason="Active upper gastrointestinal bleeding with hemodynamic dizziness requires emergency ER stabilization.",
            action="emergency_referral",
            severity="critical",
        ))
        priority = PriorityAssessment(
            level=PriorityLevel.HIGH,
            urgency_tier=UrgencyTier.EMERGENCY,
            follow_up_days=0,
            emergency_override=True,
            confidence=0.99,
            reasons=["Hematemesis (vomited blood twice)", "Safety Invariant B1.5 triggered"],
            model_used="safety_override",
        )

    elif sample_id == "leg_pain":
        summary.symptoms = [
            Symptom(name="leg pain", body_location="calf muscles", confidence=0.95),
            Symptom(name="muscle cramp", confidence=0.92),
        ]
        priority = PriorityAssessment(
            level=PriorityLevel.LOW,
            urgency_tier=UrgencyTier.SELF_CARE,
            follow_up_days=3,
            confidence=0.92,
            reasons=["Exertional calf muscle strain following field labor without red flags"],
            model_used="rule_based",
        )
        care_guidance = get_approved_home_remedy_guidance(summary, language_code)

    elif sample_id == "hair_loss":
        summary.symptoms = [
            Symptom(name="hair loss", duration=Duration(value=2.0, raw_text="2 months"), confidence=0.94),
        ]
        priority = PriorityAssessment(
            level=PriorityLevel.LOW,
            urgency_tier=UrgencyTier.SELF_CARE,
            follow_up_days=3,
            confidence=0.90,
            reasons=["Gradual non-scarring hair thinning without systemic symptoms"],
            model_used="rule_based",
        )
        care_guidance = get_approved_home_remedy_guidance(summary, language_code)

    elif sample_id == "runny_nose_sneezing":
        summary.symptoms = [
            Symptom(name="runny nose", confidence=0.96),
            Symptom(name="sneezing", confidence=0.95),
            Symptom(name="headache", severity=Severity.MILD, confidence=0.90),
        ]
        priority = PriorityAssessment(
            level=PriorityLevel.LOW,
            urgency_tier=UrgencyTier.SELF_CARE,
            follow_up_days=3,
            confidence=0.94,
            reasons=["Mild upper respiratory symptoms without red flags"],
            model_used="rule_based",
        )
        care_guidance = get_approved_home_remedy_guidance(summary, language_code)

    else:  # cough_3_days
        summary.symptoms = [
            Symptom(name="cough", duration=Duration(value=3.0, raw_text="3 days"), severity=Severity.MILD, confidence=0.96),
            Symptom(name="sore throat", confidence=0.90),
        ]
        priority = PriorityAssessment(
            level=PriorityLevel.LOW,
            urgency_tier=UrgencyTier.SELF_CARE,
            follow_up_days=3,
            confidence=0.95,
            reasons=["Mild 3-day cough without fever, chest pain, or respiratory distress"],
            model_used="rule_based",
        )
        care_guidance = get_approved_home_remedy_guidance(summary, language_code)

    patient_input = PatientInput(
        language=language_code,
        transcript_original=transcript,
        transcript_english=transcript,
        language_confidence=0.99,
        age=meta["patient"].get("age"),
        gender=meta["patient"].get("gender"),
    )

    safety = SafetyScreeningOutput(
        red_flags=red_flags,
        missing_information=[],
        follow_up_questions=[],
    )

    return PipelineResult(
        request_id=req_id,
        patient_input=patient_input,
        clinical_summary=summary,
        safety_screening=safety,
        priority=priority,
        home_remedy_guidance=care_guidance,
    )
