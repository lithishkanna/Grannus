"""
Clinician Telehealth Decision Loop and Patient Action Management for Grannus.

Supports:
  - Doctor confirmation or clinical override of AI triage priority
  - Inpatient admission, home care discharge, or secondary referral tracking
  - Audited medical decision logging under Telemedicine Practice Guidelines 2020
"""
import time
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser
from app.security.audit_logger import get_audit_logger


class DoctorActionType(str, Enum):
    CONFIRM_TRIAGE = "CONFIRM_TRIAGE"
    OVERRIDE_PRIORITY = "OVERRIDE_PRIORITY"
    PRESCRIBE_MEDICATION = "PRESCRIBE_MEDICATION"
    REFER_TO_DISTRICT_HOSPITAL = "REFER_TO_DISTRICT_HOSPITAL"
    ADMIT_TO_PHC = "ADMIT_TO_PHC"
    DISCHARGE_HOME_CARE = "DISCHARGE_HOME_CARE"


class PrescriptionItem(BaseModel):
    medication_name: str
    dosage: str
    frequency: str
    duration: str
    instructions: Optional[str] = None


class DoctorActionRequest(BaseModel):
    consultation_id: str
    action_type: DoctorActionType
    clinical_notes: str = Field(..., min_length=3, description="Doctor's clinical rationale")
    new_priority: Optional[str] = Field(None, description="Updated priority level if OVERRIDE_PRIORITY")
    referral_hospital: Optional[str] = Field(None, description="Name of destination facility if referred")
    referral_urgency: Optional[str] = Field(None, description="e.g. Immediate, Within 24h, Routine")
    prescriptions: Optional[List[PrescriptionItem]] = Field(default_factory=list)


class ActionRecord(BaseModel):
    action_id: str
    consultation_id: str
    doctor_id: str
    doctor_registration_number: Optional[str]
    state_medical_council: Optional[str]
    action_type: DoctorActionType
    clinical_notes: str
    new_priority: Optional[str]
    referral_hospital: Optional[str]
    referral_urgency: Optional[str]
    prescriptions: List[PrescriptionItem]
    timestamp: float = Field(default_factory=time.time)


class ClinicalActionManager:
    def __init__(self):
        # consultation_id -> list of ActionRecord
        self._history: Dict[str, List[ActionRecord]] = {}

    def record_action(
        self,
        req: DoctorActionRequest,
        doctor: AuthenticatedUser,
    ) -> ActionRecord:
        action_id = f"ACT-{int(time.time())}-{req.consultation_id[:8]}"
        record = ActionRecord(
            action_id=action_id,
            consultation_id=req.consultation_id,
            doctor_id=doctor.user_id,
            doctor_registration_number=doctor.doctor_registration_number,
            state_medical_council=doctor.state_medical_council,
            action_type=req.action_type,
            clinical_notes=req.clinical_notes,
            new_priority=req.new_priority,
            referral_hospital=req.referral_hospital,
            referral_urgency=req.referral_urgency,
            prescriptions=req.prescriptions or [],
            timestamp=time.time(),
        )

        if req.consultation_id not in self._history:
            self._history[req.consultation_id] = []
        self._history[req.consultation_id].append(record)

        get_audit_logger().log(
            action=f"CLINICAL_ACTION_{req.action_type.value}",
            user_id=doctor.user_id,
            role=doctor.role.value,
            doctor_registration_number=doctor.doctor_registration_number,
            consultation_id=req.consultation_id,
            details={
                "action_id": action_id,
                "notes": req.clinical_notes,
                "referral": req.referral_hospital,
            },
        )
        return record

    def get_consultation_actions(self, consultation_id: str) -> List[ActionRecord]:
        return self._history.get(consultation_id, [])


_action_manager = ClinicalActionManager()


def get_clinical_action_manager() -> ClinicalActionManager:
    return _action_manager
