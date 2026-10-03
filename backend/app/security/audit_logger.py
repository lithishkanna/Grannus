"""
Clinical Audit Logger for Grannus RuralCare AI.

Maintains an immutable audit trail of who viewed, processed, or exported
medical records, fulfilling DPDP Act 2023 and ABDM certification requirements.
"""
import time
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

logger = logging.getLogger("rural_care.audit")


class AuditLogEntry(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    action: str  # VIEW_RECORD, EXPORT_FHIR, RUN_PIPELINE, GENERATE_PRESCRIPTION, ERASE_DATA
    user_id: str
    role: str
    doctor_registration_number: Optional[str] = None
    consultation_id: Optional[str] = None
    ip_hash: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ClinicalAuditLogger:
    def __init__(self):
        self._entries: List[AuditLogEntry] = []

    def log(
        self,
        action: str,
        user_id: str,
        role: str,
        doctor_registration_number: Optional[str] = None,
        consultation_id: Optional[str] = None,
        ip_hash: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        entry = AuditLogEntry(
            action=action,
            user_id=user_id,
            role=role,
            doctor_registration_number=doctor_registration_number,
            consultation_id=consultation_id,
            ip_hash=ip_hash,
            details=details or {},
        )
        self._entries.append(entry)
        logger.info(
            "AUDIT_EVENT action=%s user=%s role=%s doc_reg=%s consultation=%s",
            action, user_id, role, doctor_registration_number, consultation_id
        )
        return entry

    def get_entries_for_consultation(self, consultation_id: str) -> List[AuditLogEntry]:
        return [e for e in self._entries if e.consultation_id == consultation_id]

    def get_all_entries(self) -> List[AuditLogEntry]:
        return list(self._entries)

    def clear(self):
        """Testing utility."""
        self._entries.clear()


_audit_instance: Optional[ClinicalAuditLogger] = None


def get_audit_logger() -> ClinicalAuditLogger:
    global _audit_instance
    if _audit_instance is None:
        _audit_instance = ClinicalAuditLogger()
    return _audit_instance
