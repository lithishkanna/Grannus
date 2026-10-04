import datetime
import uuid
from typing import Dict, Any, Optional

from app.schemas import PatientInput, ClinicalSummary, SafetyScreeningOutput, PriorityAssessment


def generate_fhir_bundle(
    request_id: str,
    patient_input: PatientInput,
    clinical_summary: ClinicalSummary,
    safety_screening: SafetyScreeningOutput,
    priority: PriorityAssessment,
    patient_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generates a FHIR R4 JSON bundle from the AI extraction pipeline output.
    """
    patient_uuid = str(uuid.uuid4())
    encounter_uuid = str(uuid.uuid4())
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

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

    # 0. Composition Resource (Required by ABDM profile for Clinical Artifacts)
    comp_uuid = str(uuid.uuid4())
    comp_resource = {
        "resourceType": "Composition",
        "id": comp_uuid,
        "status": "final",
        "type": {
            "coding": [
                {
                    "system": "https://projectndhm.in/fhir/ndhm/CodeSystem/ndhm-record-type",
                    "code": "OPConsultationRecord",
                    "display": "OP Consultation Record"
                }
            ],
            "text": "RuralCare AI Clinical Triage Summary"
        },
        "subject": {
            "reference": f"urn:uuid:{patient_uuid}"
        },
        "date": timestamp,
        "title": "Clinical Triage and Safety Screening",
    }
    bundle["entry"].append({
        "fullUrl": f"urn:uuid:{comp_uuid}",
        "resource": comp_resource
    })

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
    
    # Demographics: gender, age, language
    gender_val = getattr(patient_input, "gender", None) or (patient_context and patient_context.get("gender"))
    if gender_val:
        g = str(gender_val).lower().strip()
        if g in ("m", "male"):
            patient_resource["gender"] = "male"
        elif g in ("f", "female"):
            patient_resource["gender"] = "female"
        else:
            patient_resource["gender"] = "other"

    age_val = getattr(patient_input, "age", None) or (patient_context and patient_context.get("age"))
    if age_val:
        patient_resource["extension"] = [
            {
                "url": "http://hl7.org/fhir/StructureDefinition/patient-age",
                "valueString": str(age_val)
            }
        ]

    lang_val = getattr(patient_input, "language", None) or (patient_context and patient_context.get("language"))
    if lang_val:
        patient_resource["communication"] = [
            {
                "language": {
                    "coding": [
                        {
                            "system": "urn:ietf:bcp:47",
                            "code": str(lang_val)
                        }
                    ],
                    "text": str(lang_val)
                },
                "preferred": True
            }
        ]

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

    # 3. Condition Resource (Chief Complaint - Problem List Item, not confirmed diagnosis)
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
                            "code": "problem-list-item",
                            "display": "Problem List Item"
                        }
                    ]
                }
            ],
            "code": {
                "text": f"Triage complaint category: {clinical_summary.chief_complaint}"
            },
            "subject": {
                "reference": f"urn:uuid:{patient_uuid}"
            },
            "note": [
                {
                    "text": "AI-extracted triage complaint category. Not a confirmed diagnosis."
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

    # 7. MedicationStatement Resources (Patient-reported medications)
    for med in getattr(clinical_summary, "medications", []):
        if med and med.strip() and med.lower() not in ("none", "nil", "no", "na", "n/a"):
            med_uuid = str(uuid.uuid4())
            med_resource = {
                "resourceType": "MedicationStatement",
                "id": med_uuid,
                "status": "active",
                "subject": {
                    "reference": f"urn:uuid:{patient_uuid}"
                },
                "medicationCodeableConcept": {
                    "text": med.strip()
                },
                "note": [
                    {
                        "text": "Patient-reported medication during triage intake."
                    }
                ]
            }
            bundle["entry"].append({
                "fullUrl": f"urn:uuid:{med_uuid}",
                "resource": med_resource
            })

    # 8. AllergyIntolerance Resources (Patient-reported allergies)
    for allergy in getattr(clinical_summary, "allergies", []):
        if allergy and allergy.strip() and allergy.lower() not in ("none", "nil", "no", "na", "n/a"):
            alg_uuid = str(uuid.uuid4())
            alg_resource = {
                "resourceType": "AllergyIntolerance",
                "id": alg_uuid,
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                            "code": "active"
                        }
                    ]
                },
                "patient": {
                    "reference": f"urn:uuid:{patient_uuid}"
                },
                "code": {
                    "text": allergy.strip()
                },
                "note": [
                    {
                        "text": "Patient-reported allergy during triage intake."
                    }
                ]
            }
            bundle["entry"].append({
                "fullUrl": f"urn:uuid:{alg_uuid}",
                "resource": alg_resource
            })

    return bundle
