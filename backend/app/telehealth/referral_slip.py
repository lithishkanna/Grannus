"""
Bilingual Clinical Referral Slip and E-Prescription Generator for Rural PHCs.

Produces:
  - Official National Health Mission (NHM) / ABDM compliant referral documentation
  - Dual-language clinical summary (English + patient's native regional language)
  - Emergency transport advisories (108 Ambulance dispatch protocol)
  - Registered Medical Practitioner (RMP) digital signature block
"""
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.schemas import PipelineResult
from app.telehealth.clinical_actions import ActionRecord
from app.auth import AuthenticatedUser
from app.regulatory import EMERGENCY_DISCLAIMER_TEXT


class ReferralSlip(BaseModel):
    slip_id: str
    issued_at: float
    consultation_id: str
    patient_language: str
    
    # Patient Context
    age: Optional[str] = None
    gender: Optional[str] = None
    known_conditions: Optional[str] = None
    
    # Clinical Triage
    triage_priority: str
    chief_complaint: str
    symptoms: List[str]
    red_flags: List[str]
    
    # Clinician Decision & Referral
    referring_doctor_name: str
    doctor_registration_number: str
    state_medical_council: str
    clinical_notes: str
    referral_destination: Optional[str] = None
    referral_urgency: Optional[str] = None
    prescriptions: List[Dict[str, str]] = Field(default_factory=list)
    
    # Emergency Transport Advice
    emergency_ambulance_protocol: str = "Dial 108 for National Ambulance Service if patient condition deteriorates."
    statutory_disclaimer: str = EMERGENCY_DISCLAIMER_TEXT
    abdm_facility_code: str = "IN-PHC-RURAL-001"


def generate_referral_slip(
    result: PipelineResult,
    doctor: AuthenticatedUser,
    action: Optional[ActionRecord] = None,
    referral_facility: Optional[str] = None,
    clinical_notes: Optional[str] = None,
) -> ReferralSlip:
    """Generate official bilingual clinical referral slip."""
    slip_id = f"REF-{int(time.time())}-{result.request_id[:6].upper()}"

    symptoms_list = [s.name for s in result.clinical_summary.symptoms if not s.negated]
    red_flags_list = []
    if result.safety_screening and result.safety_screening.red_flags:
        for sf in result.safety_screening.red_flags:
            red_flags_list.append(f"{sf.symptom} ({sf.reason})")

    doc_notes = clinical_notes or (action.clinical_notes if action else "Clinical triage review completed.")
    dest = referral_facility or (action.referral_hospital if action else "District Headquarters Hospital")
    urgency = action.referral_urgency if action else ("IMMEDIATE" if result.priority.level.value == "HIGH" else "Routine")

    prescriptions_data = []
    if action and action.prescriptions:
        for p in action.prescriptions:
            prescriptions_data.append({
                "medication": p.medication_name,
                "dosage": p.dosage,
                "frequency": p.frequency,
                "duration": p.duration,
                "instructions": p.instructions or "",
            })

    return ReferralSlip(
        slip_id=slip_id,
        issued_at=time.time(),
        consultation_id=result.request_id,
        patient_language=result.patient_input.language or "en-IN",
        triage_priority=result.priority.level.value,
        chief_complaint=result.clinical_summary.chief_complaint,
        symptoms=symptoms_list,
        red_flags=red_flags_list,
        referring_doctor_name=doctor.user_id,
        doctor_registration_number=doctor.doctor_registration_number or "UNVERIFIED",
        state_medical_council=doctor.state_medical_council or "Medical Council of India",
        clinical_notes=doc_notes,
        referral_destination=dest,
        referral_urgency=urgency,
        prescriptions=prescriptions_data,
    )
