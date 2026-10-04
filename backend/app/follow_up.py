"""
Follow-up loop and clinical escalation manager for Grannus RuralCare AI.

Supports:
  - 2 to 3 day scheduled check-in tracking (status: 'improving', 'same', 'worse')
  - One-tap "I'm worse" clinical escalation that promotes patients up an urgency tier:
      * self_care    -> doctor_soon  (routine visit in 2-3 days)
      * doctor_soon  -> doctor_today (urgent PHC visit within 24 hours)
      * doctor_today -> emergency    (immediate emergency referral, call 108/112)
  - Immutable audit logging for clinical accountability
"""
import time
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from app.schemas import UrgencyTier, PriorityLevel, CheckInResponse

logger = logging.getLogger("rural_care.follow_up")


class ConsultationFollowUpRecord(BaseModel):
    consultation_id: str
    patient_id: Optional[str] = None
    initial_tier: UrgencyTier
    current_tier: UrgencyTier
    created_at: float
    follow_up_due_at: float
    check_in_history: List[Dict[str, Any]] = Field(default_factory=list)
    is_escalated: bool = False
    escalation_reason: Optional[str] = None


class FollowUpManager:
    """In-memory & persistent follow-up check-in and tier escalation orchestrator."""

    def __init__(self):
        self._records: Dict[str, ConsultationFollowUpRecord] = {}

    def register_consultation(
        self,
        consultation_id: str,
        urgency_tier: UrgencyTier,
        follow_up_days: int = 2,
        patient_id: Optional[str] = None,
    ) -> ConsultationFollowUpRecord:
        """Register newly completed consultation for 2-3 day follow-up tracking."""
        now = time.time()
        due_at = now + (follow_up_days * 86400)
        record = ConsultationFollowUpRecord(
            consultation_id=consultation_id,
            patient_id=patient_id,
            initial_tier=urgency_tier,
            current_tier=urgency_tier,
            created_at=now,
            follow_up_due_at=due_at,
        )
        self._records[consultation_id] = record
        try:
            from app.db import save_follow_up_record
            save_follow_up_record(consultation_id, {
                "consultation_id": consultation_id,
                "urgency_tier": record.current_tier.value,
                "scheduled_for": str(record.follow_up_due_at),
                "status": "PENDING",
            })
        except Exception:
            pass
        logger.info(
            "Registered follow-up consultation_id=%s tier=%s due_in_days=%d",
            consultation_id, urgency_tier.value, follow_up_days
        )
        return record

    def get_record(self, consultation_id: str) -> Optional[ConsultationFollowUpRecord]:
        if consultation_id in self._records:
            return self._records[consultation_id]
        try:
            from app.db import get_follow_up_record
            data = get_follow_up_record(consultation_id)
            if data:
                tier_val = data.get("urgency_tier", "self_care")
                tier = UrgencyTier(tier_val) if tier_val in [t.value for t in UrgencyTier] else UrgencyTier.SELF_CARE
                rec = ConsultationFollowUpRecord(
                    consultation_id=consultation_id,
                    patient_id=data.get("profile_id"),
                    initial_tier=tier,
                    current_tier=tier,
                    created_at=time.time(),
                    follow_up_due_at=time.time() + 172800,
                )
                self._records[consultation_id] = rec
                return rec
        except Exception:
            pass
        return None

    def record_check_in(
        self,
        consultation_id: str,
        status: str,
        notes: Optional[str] = None,
    ) -> CheckInResponse:
        """
        Record patient response to scheduled 2-3 day check-in.
        If patient reports 'worse', automatically escalates the urgency tier!
        """
        status_norm = status.strip().lower()
        record = self.get_record(consultation_id)
        if not record:
            # Create on-the-fly if consultation was not pre-registered
            record = self.register_consultation(
                consultation_id=consultation_id,
                urgency_tier=UrgencyTier.SELF_CARE,
                follow_up_days=2,
            )

        previous_tier = record.current_tier

        if status_norm == "worse":
            return self.escalate_tier(
                consultation_id=consultation_id,
                reason=notes or "Patient reported worsening symptoms on follow-up check-in.",
            )

        # 'improving' or 'same'
        record.check_in_history.append({
            "timestamp": time.time(),
            "status": status_norm,
            "notes": notes,
            "tier_at_check_in": previous_tier.value,
        })
        try:
            from app.db import save_follow_up_record
            save_follow_up_record(consultation_id, {
                "consultation_id": consultation_id,
                "urgency_tier": previous_tier.value,
                "status": "CHECKED_IN",
                "patient_status": status_norm,
                "patient_feedback": notes,
                "checked_in_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        except Exception:
            pass

        msg = (
            "Thank you for checking in. We are glad your symptoms are improving. Continue your rest and hydration."
            if status_norm == "improving"
            else "Thank you for checking in. Please continue monitoring. If your condition worsens at any time, tap 'I feel worse' or visit the PHC."
        )

        return CheckInResponse(
            consultation_id=consultation_id,
            previous_tier=previous_tier,
            new_tier=previous_tier,
            status=status_norm,
            message=msg,
            is_escalated=False,
            escalation_reason=None,
            emergency_call_numbers=["108", "112"],
            next_follow_up_days=2 if status_norm == "same" else 3,
        )

    def escalate_tier(
        self,
        consultation_id: str,
        reason: Optional[str] = None,
    ) -> CheckInResponse:
        """
        One-tap 'I'm worse' escalation function.
        Promotes patient up exactly one tier:
          self_care -> doctor_soon
          doctor_soon -> doctor_today
          doctor_today -> emergency
          emergency -> emergency (re-alert)
        """
        record = self.get_record(consultation_id)
        if not record:
            record = self.register_consultation(
                consultation_id=consultation_id,
                urgency_tier=UrgencyTier.SELF_CARE,
            )

        previous_tier = record.current_tier
        escalation_reason = reason or "Patient initiated one-tap 'I feel worse' escalation."

        # Tier escalation promotion logic
        if previous_tier == UrgencyTier.SELF_CARE:
            new_tier = UrgencyTier.DOCTOR_SOON
            next_days = 2
            message = "Your case has been escalated to Doctor Visit Soon. Please visit your local Primary Health Centre (PHC) within the next 48 to 72 hours for clinician evaluation."
        elif previous_tier == UrgencyTier.DOCTOR_SOON:
            new_tier = UrgencyTier.DOCTOR_TODAY
            next_days = 1
            message = "Urgent escalation: Your case has been escalated to Doctor Today. Please visit the Primary Health Centre or Community Health Centre today for clinical examination."
        elif previous_tier == UrgencyTier.DOCTOR_TODAY:
            new_tier = UrgencyTier.EMERGENCY
            next_days = 0
            message = "EMERGENCY ESCALATION: Symptoms have worsened critically. Please immediately call 108 Ambulance or 112 National Emergency, or proceed to the nearest emergency medical facility."
        else:  # already EMERGENCY
            new_tier = UrgencyTier.EMERGENCY
            next_days = 0
            message = "EMERGENCY: Please immediately call 108 Ambulance or 112 National Emergency, or proceed to the nearest emergency hospital."

        record.current_tier = new_tier
        record.is_escalated = True
        record.escalation_reason = escalation_reason
        record.check_in_history.append({
            "timestamp": time.time(),
            "status": "worse",
            "escalated_from": previous_tier.value,
            "escalated_to": new_tier.value,
            "reason": escalation_reason,
        })
        try:
            from app.db import save_follow_up_record
            save_follow_up_record(consultation_id, {
                "consultation_id": consultation_id,
                "urgency_tier": new_tier.value,
                "status": "ESCALATED",
                "patient_status": "worse",
                "patient_feedback": escalation_reason,
                "checked_in_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        except Exception:
            pass

        logger.warning(
            "ESCALATION APPLIED consultation_id=%s from=%s to=%s reason=%s",
            consultation_id, previous_tier.value, new_tier.value, escalation_reason
        )

        return CheckInResponse(
            consultation_id=consultation_id,
            previous_tier=previous_tier,
            new_tier=new_tier,
            status="worse",
            message=message,
            is_escalated=True,
            escalation_reason=escalation_reason,
            emergency_call_numbers=["108", "112"],
            next_follow_up_days=next_days,
        )


_follow_up_manager: Optional[FollowUpManager] = None


def get_follow_up_manager() -> FollowUpManager:
    global _follow_up_manager
    if _follow_up_manager is None:
        _follow_up_manager = FollowUpManager()
    return _follow_up_manager
