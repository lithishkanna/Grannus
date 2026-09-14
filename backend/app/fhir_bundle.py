import datetime
import uuid
from typing import Dict, Any

from app.schemas import PatientInput, ClinicalSummary, SafetyScreeningOutput, PriorityAssessment


def generate_fhir_bundle(
    request_id: str,
    patient_input: PatientInput,
    clinical_summary: ClinicalSummary,
    safety_screening: SafetyScreeningOutput,
    priority: PriorityAssessment,
) -> Dict[str, Any]:
    """
    Generates a FHIR R4 JSON bundle from the AI extraction pipeline output.
    """
    patient_uuid = str(uuid.uuid4())
    encounter_uuid = str(uuid.uuid4())
    
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"

    bundle: Dict[str, Any] = {
        "resourceType": "Bundle",
        "id": request_id,
        "type": "collection",
        "timestamp": timestamp,
        "meta": {
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentBundle"]
        },
        "entry": []
    }

    # 1. Patient Resource
    patient_resource = {
        "resourceType": "Patient",
        "id": patient_uuid,
        "identifier": [
            {
                "system": "https://healthid.abdm.gov.in",
                "value": "PENDING"
            }
        ]
    }
    bundle["entry"].append({
        "fullUrl": f"urn:uuid:{patient_uuid}",
        "resource": patient_resource
    })

    # 2. Encounter Resource
    encounter_resource = {
        "resourceType": "Encounter",
        "id": encounter_uuid,
        "status": "triaged",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory"
        },
        "subject": {
            "reference": f"urn:uuid:{patient_uuid}"
        }
    }
    bundle["entry"].append({
        "fullUrl": f"urn:uuid:{encounter_uuid}",
        "resource": encounter_resource
    })

    # 3. Condition Resource (Chief Complaint)
    if clinical_summary.chief_complaint:
        condition_uuid = str(uuid.uuid4())
        condition_resource = {
            "resourceType": "Condition",
            "id": condition_uuid,
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active"
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                            "code": "encounter-diagnosis"
                        }
                    ]
                }
            ],
            "code": {
                "text": clinical_summary.chief_complaint
            },
            "subject": {
                "reference": f"urn:uuid:{patient_uuid}"
            },
            "note": [
                {
                    "text": "AI-extracted triage data. Not a diagnosis."
                }
            ]
        }
        bundle["entry"].append({
            "fullUrl": f"urn:uuid:{condition_uuid}",
            "resource": condition_resource
        })

    # 4. Observation Resources (Symptoms)
    for symptom in clinical_summary.symptoms:
        if not symptom.negated:
            obs_uuid = str(uuid.uuid4())
            obs_resource = {
                "resourceType": "Observation",
                "id": obs_uuid,
                "status": "preliminary",
                "category": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                "code": "exam",
                                "display": "Exam"
                            }
                        ]
                    }
                ],
                "code": {
                    "text": symptom.name
                },
                "subject": {
                    "reference": f"urn:uuid:{patient_uuid}"
                },
                "encounter": {
                    "reference": f"urn:uuid:{encounter_uuid}"
                },
                "valueString": symptom.raw_text or symptom.name
            }
            bundle["entry"].append({
                "fullUrl": f"urn:uuid:{obs_uuid}",
                "resource": obs_resource
            })

    # 5. RiskAssessment Resource (Priority)
    risk_uuid = str(uuid.uuid4())
    priority_level_val = priority.level.value if hasattr(priority.level, 'value') else str(priority.level)
    risk_resource = {
        "resourceType": "RiskAssessment",
        "id": risk_uuid,
        "status": "final",
        "subject": {
            "reference": f"urn:uuid:{patient_uuid}"
        },
        "encounter": {
            "reference": f"urn:uuid:{encounter_uuid}"
        },
        "prediction": [
            {
                "qualitativeRisk": {
                    "text": priority_level_val
                }
            }
        ]
    }
    bundle["entry"].append({
        "fullUrl": f"urn:uuid:{risk_uuid}",
        "resource": risk_resource
    })

    # 6. DetectedIssue Resources (Red Flags)
    for flag in safety_screening.red_flags:
        issue_uuid = str(uuid.uuid4())
        issue_resource = {
            "resourceType": "DetectedIssue",
            "id": issue_uuid,
            "status": "preliminary",
            "patient": {
                "reference": f"urn:uuid:{patient_uuid}"
            },
            "code": {
                "text": flag.symptom
            },
            "detail": flag.reason,
            "mitigation": [
                {
                    "action": {
                        "text": flag.action
                    }
                }
            ]
        }
        bundle["entry"].append({
            "fullUrl": f"urn:uuid:{issue_uuid}",
            "resource": issue_resource
        })

    return bundle
