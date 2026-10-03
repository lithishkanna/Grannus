# Regulatory Positioning & Compliance Matrix

**Product:** Grannus (RuralCare AI)  
**Jurisdiction:** Republic of India  
**Applicable Frameworks:**
1. Central Drugs Standard Control Organisation (CDSCO) Medical Device Rules, 2017
2. Telemedicine Practice Guidelines, 2020 (Board of Governors, Medical Council of India / MoHFW)
3. Digital Personal Data Protection (DPDP) Act, 2023 (Ministry of Electronics and Information Technology)
4. Ayushman Bharat Digital Mission (ABDM) Standards (National Health Authority)

---

## 1. CDSCO Software as a Medical Device (SaMD) Assessment

### 1.1 Statutory Classification
Under the **Medical Device Rules, 2017** (amended 2020), software intended for diagnosis, prevention, monitoring, treatment, or alleviation of disease qualifies as a Medical Device if it acts autonomously or directly drives clinical actions.

**Grannus is legally positioned as Non-Device Clinical Decision Support (CDS) Software.**

| Assessment Criterion | Grannus Architecture | Regulatory Finding |
|---|---|---|
| **Autonomous Diagnosis** | Grannus explicitly emits `diagnosis: null` on all API outputs. It summarizes patient symptoms and flags urgency levels. | **Non-Diagnostic:** Does not diagnose; merely structures patient speech for clinician review. |
| **Direct Therapeutic Delivery** | Grannus does not operate, control, or trigger drug dispensers, infusion pumps, or physical devices. | **Non-Therapeutic:** Cannot prescribe or dispense autonomously. |
| **Independent Clinician Review** | Every summary requires mandatory review by a Registered Medical Practitioner (`clinician_review_required: true`). | **Decision Support:** RMP retains full medical responsibility and reviews original voice audio/transcripts. |
| **Self-Care / Low Priority** | Low-urgency home remedy advice is limited to basic non-pharmacological comfort measures with explicit red-flag warnings. | **Informational Support:** Does not substitute for formal primary care consultation. |

### 1.2 Statutory Labeling & Emergency Disclaimers
Grannus incorporates prominent disclaimers across all patient and clinician interfaces:
> **NOTICE:** *Grannus is an AI-assisted clinical decision support system, NOT a diagnostic medical device. It does NOT provide a final medical diagnosis. In any acute or life-threatening emergency, immediately call the National Ambulance Service 108 or Emergency 112.*

---

## 2. Telemedicine Practice Guidelines 2020 Compliance

Under the guidelines notified by the Ministry of Health and Family Welfare (MoHFW) on 25 March 2020:

### 2.1 Registered Medical Practitioner (RMP) Verification
- **Section 1.3:** Only doctors registered with the National Medical Commission (NMC) or a State Medical Council may provide telemedicine consultations and issue prescriptions.
- **Grannus Implementation:**
  - Mandatory doctor authentication verifying NMC or State Medical Council registration numbers (e.g., `TNMC-54321`, `KMC-45678`).
  - Cryptographically signed JWT tokens embedding verified RMP credentials.
  - Endpoints generating digital prescriptions (`/api/v1/doctor/voice-prescription`) and exporting clinical records (`/api/v1/export/fhir`) are strictly gated by `require_verified_doctor` and `require_role`.

### 2.2 Patient Identification & Consent
- **Section 3.2:** Explicit patient consent must be recorded before telemedicine services commence.
- **Grannus Implementation:** Multilingual DPDP-compliant consent dialog prior to audio recording (see Section 3 below).

### 2.3 Prescription Signing and Record Retention
- **Section 3.7:** Prescriptions generated via voice translation must be linked to the clinician's registration number and retained for at least 3 years.
- **Grannus Implementation:** Immutable audit logging (`audit_logger.py`) records the consulting doctor's ID, medical registration number, consultation UUID, and timestamp for all prescription and triage actions.

---

## 3. Digital Personal Data Protection (DPDP) Act 2023 Compliance Matrix

Grannus acts as a **Data Fiduciary** under the DPDP Act 2023.

| DPDP Section | Statutory Obligation | Grannus Technical Implementation | Verification Method |
|---|---|---|---|
| **Section 4 & 6** | Grounds for processing; Requirement of free, informed, specific, unconditional, and unambiguous consent. | Multilingual consent notices in English, Tamil, Hindi, and Telugu (`consent.py`). Mandatory affirmative checkbox before recording. | Unit & integration tests (`test_multilingual_dpdp_consent_notices`, `test_patient_consent_recording`). |
| **Section 5** | Notice with purpose specification and Data Protection Grievance Officer details. | Notice details exact clinical purpose, 72-hour audio retention, and Grievance Officer email (`grievance.officer@grannus.health`). | Endpoint `GET /api/v1/consent/notice` verified in test suite. |
| **Section 8(4)** | Implementation of technical and organizational measures to ensure personal data protection. | Field-level encryption (`encrypt_phi_field`), zero-PHI logging (`sanitize_log_message`), magic byte upload validation (`validate_audio_upload`). | Automated tests for encryption roundtrip and log sanitization. |
| **Section 8(6)** | Notification of personal data breaches to the Data Protection Board of India and affected Data Principals. | Formulated 6-hour response protocol detailed in `BREACH_RESPONSE_PLAN.md`. | Verified breach response procedure. |
| **Section 8(7)** | Erasure of personal data upon withdrawal of consent or expiry of specified purpose. | **Automated 72-Hour Data Retention Sweeper:** Raw audio files are scheduled for automatic deletion 72 hours post-intake (`data_retention.py`). | Automated deletion schedule verification test (`test_data_retention_and_statutory_erasure`). |
| **Section 9** | Processing of children's personal data. | Age-aware pediatric safeguards: Children under 5 and infants (age in months) cannot be triaged as LOW; parental consent required. | Phase 1 & Phase 3 unit tests (`test_feature_extraction_age_groups_and_infants`). |
| **Section 11** | Right to access information about personal data. | Patient intake lookup and consultation record export available to authorized users. | RBAC and consultation API. |
| **Section 12** | Statutory Right to Correction and Erasure (Right to be Forgotten). | Dedicated statutory endpoint `POST /api/v1/patient/request-erasure` purges raw voice files and anonymizes consultation metadata. | Integration test `test_statutory_erasure_endpoint`. |
| **Section 13** | Right of grievance redressal. | Contact info of the Data Protection Grievance Officer provided in all localized notices. | Displayed in frontend Consent Dialog and API responses. |

---

## 4. Ayushman Bharat Digital Mission (ABDM) Conformance

Grannus is engineered for seamless interoperability with India's national health stack:

1. **Milestone 1 (M1) — ABHA ID Integration:**
   - Patient intake supports Ayushman Bharat Health Account (ABHA) IDs (14 digits) and addresses.
   - De-identification engine protects ABHA IDs in logs and LLM dispatches while maintaining clinical linkage via cryptographic surrogates.

2. **Milestone 2 (M2) — FHIR R4 Clinical Document Generation:**
   - The `/api/v1/export/fhir` endpoint produces NRCES-compliant FHIR R4 `DocumentBundle` resources (`https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentBundle`).
   - Includes ABDM-required resources: `Composition` (OPConsultationRecord), `Patient`, `Encounter`, `Condition` (chief complaint), `Observation` (symptoms), `RiskAssessment` (triage level), and `DetectedIssue` (red flags).
   - Profile conformance verified programmatically via `validate_abdm_fhir_bundle()`.

3. **Milestone 3 (M3) — Health Information Exchange (HIP/HIU):**
   - Cryptographic short-lived signed URLs (`generate_signed_url`) ensure secure media transfer between health information providers and users without exposing public S3/Supabase storage buckets.

---

## 5. Security & Infrastructure Controls Summary

- **Authentication:** HMAC-SHA256 cryptographic JWT tokens with verified doctor credentials.
- **Input Sanitization:** Magic byte file inspection blocking Windows PEs, Linux ELFs, shell scripts, and HTML/PHP polyglots; strict regex-based path traversal protection.
- **Denial of Service Defense:** In-memory sliding window rate limiter (30 requests/min for intake, burst limit 10).
- **Zero-PHI Logging:** Direct Indian identifiers (Aadhaar, ABHA, phone, email) scrubbed automatically from all application logs.
- **Network Boundaries:** CORS restricted to approved client domains; secrets segregated in environment configurations.
