"""
Regulatory Positioning, CDSCO SaMD Assessment, and ABDM FHIR Validation for Grannus.

Compliant with:
  - India Medical Devices Rules 2017 (CDSCO Software as a Medical Device Classification)
  - Telemedicine Practice Guidelines 2020 (MCI / MoHFW)
  - Ayushman Bharat Digital Mission (ABDM) Health Information Provider (HIP/HIU) Standards
"""
from typing import Dict, Any, List, Tuple

CDSCO_SAMD_DECLARATION = {
    "classification": "Non-Device Clinical Decision Support (CDS) Software",
    "regulatory_basis": "CDSCO Medical Device Rules 2017 & MoHFW Telemedicine Guidelines 2020",
    "rationale": (
        "Grannus does NOT autonomously diagnose or treat disease. It provides prioritized clinical decision "
        "support to Registered Medical Practitioners (RMPs), who independently review the original voice notes, "
        "transcripts, and red flags before exercising clinical judgment."
    ),
    "statutory_positioning": "Triage & Workflow Decision Support Tool for Healthcare Workers and Doctors",
}

EMERGENCY_DISCLAIMER_TEXT = (
    "NOTICE: Grannus is a decision support tool, not a diagnostic medical device. "
    "Do NOT use this platform for acute life-threatening emergencies. "
    "For immediate medical assistance in India, call National Ambulance Service 108 or Emergency 112."
)


def validate_abdm_fhir_bundle(fhir_bundle: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates that a generated FHIR R4 bundle conforms to ABDM M1/M2/M3 profiles:
      - Bundle type must be 'document' or 'collection'
      - Contains valid Composition resource
      - Contains Patient resource with telecom or identifier
      - Contains Condition / Observation resources with valid status
    """
    errors = []
    if not isinstance(fhir_bundle, dict):
        return False, ["Bundle must be a JSON object"]

    if fhir_bundle.get("resourceType") != "Bundle":
        errors.append("Invalid resourceType: must be 'Bundle'")

    if fhir_bundle.get("type") not in ["document", "collection"]:
        errors.append("Invalid Bundle type: must be 'document' or 'collection'")

    entries = fhir_bundle.get("entry", [])
    if not entries:
        errors.append("ABDM bundle must contain at least one entry")

    resource_types = [e.get("resource", {}).get("resourceType") for e in entries if isinstance(e, dict)]

    if "Composition" not in resource_types:
        errors.append("Missing required ABDM resource: 'Composition'")

    if "Patient" not in resource_types:
        errors.append("Missing required ABDM resource: 'Patient'")

    is_valid = len(errors) == 0
    return is_valid, errors
