# Statutory Personal Data Breach Response Plan

**Product:** Grannus (RuralCare AI)  
**Entity:** Data Fiduciary  
**Governing Laws:**
- Digital Personal Data Protection (DPDP) Act, 2023 (Section 8(6))
- Information Technology (The Indian Computer Emergency Response Team and Manner of Performing Functions and Duties) Rules, 2013 & CERT-In Directions 2022

---

## 1. Purpose & Scope

This document establishes the mandatory protocol for identifying, containing, investigating, and reporting any breach or suspected unauthorized compromise of personal data or protected health information (PHI) processed by Grannus.

This plan applies to:
- Raw acoustic voice recordings of patients
- Synthesized audio and voice prescriptions
- ASHA worker and patient intake transcripts
- Registered Medical Practitioner (RMP) credentials and clinical summaries
- System databases, backups, and external LLM/STT API communication channels

---

## 2. Breach Severity Classification

| Severity Level | Definition | Impact | Statutory Action |
|---|---|---|---|
| **Severity 1 (Critical)** | Active, confirmed exfiltration of unencrypted PHI, patient voice recordings, or medical registration database. | High risk of harm, identity fraud, or reputational damage to patients. | Mandatory notification to DPBI and CERT-In within 6 hours. Emergency executive convening. |
| **Severity 2 (High)** | Unauthorized access or compromise of an internal service, credential exposure, or misconfiguration without confirmed bulk exfiltration. | Potential exposure of limited patient triage records. | Investigation within 12 hours. Containment & DPBI notification upon confirmation. |
| **Severity 3 (Medium)** | Intermittent security exception, rate limiter bypass, or isolated account compromise. | Localized; no systemic data breach. | Remediation within 24 hours. Internal incident logging. |
| **Severity 4 (Low)** | Scanned probe, blocked malicious file upload, or attempted path traversal safely prevented by input validation. | Zero data exposed. Defensive controls operated as designed. | Logged in security audit trail (`audit_logger.py`). No external notification required. |

---

## 3. Incident Response Team (IRT)

| Role | Designation | Responsibilities |
|---|---|---|
| **Incident Commander** | Lead Security Engineer | Directs technical containment, forensic preservation, and eradication. |
| **Data Protection Officer (DPO)** | Grievance & Compliance Officer | Evaluates DPDP Act liabilities, coordinates DPBI notification, and manages patient communications. |
| **Medical Lead** | Chief Medical Officer / Consulting RMP | Assesses clinical safety impact on patient triage or pending prescriptions. |
| **Infrastructure Lead** | DevSecOps / Cloud Architect | Isolates compromised containers, rotates cryptographic keys, reviews zero-PHI audit logs. |

---

## 4. Five-Stage Incident Lifecycle

```
[1. Detection & Triage] ➔ [2. Containment] ➔ [3. Investigation] ➔ [4. Statutory Notification] ➔ [5. Remediation]
      (< 1 Hour)             (< 2 Hours)         (< 4 Hours)              (< 6 Hours)              (Post-Mortem)
```

### Stage 1: Detection & Triage (< 1 hour)
- Security alerts triggered via anomalous API patterns, rate-limiter breaches, or external bug reports.
- IRT convenes immediately to verify authenticity and assign Severity (Sev-1 through Sev-4).

### Stage 2: Immediate Containment (< 2 hours)
1. **Network & Token Invalidation:**
   - Invalidate active JWT sessions by rotating `GEMINI_API_KEY` / cryptographic signing secret.
   - Revoke compromised API keys and temporary signed media URLs.
2. **Infrastructure Quarantine:**
   - Isolate affected backend containers or database replicas from the public gateway.
   - Halt automatic background tasks if storage integrity is questioned.
3. **Data Retention Sweep:**
   - Trigger immediate retention purge (`DataRetentionManager.execute_retention_sweep()`) to ensure no expired raw audio (>72 hours) remains vulnerable.

### Stage 3: Forensic Investigation (< 4 hours)
- Inspect immutable audit logs recorded by `audit_logger.py`.
- Identify the exact scope: number of patient consultation UUIDs affected, categories of data compromised (e.g., transcripts, symptoms vs. direct identifiers).
- Verify whether field-level encryption (`encrypt_phi_field`) prevented plaintext extraction of database rows.

### Stage 4: Statutory Reporting & Notification (< 6 hours)

#### 4.1 Notice to the Data Protection Board of India (DPBI)
Pursuant to Section 8(6) of the DPDP Act 2023, the DPO shall notify the Board with:
- Nature and extent of the personal data breach
- Estimated number of affected Data Principals (patients / doctors)
- Potential consequences and safety risks
- Immediate containment and mitigation measures implemented
- Contact details of the Data Protection Grievance Officer

#### 4.2 Notice to CERT-In (Within 6 Hours)
Pursuant to CERT-In Direction No. 20(3)/2022-CERT-In, report the cyber incident via `incident@cert-in.org.in` covering:
- Time of incident detection
- System and architecture affected
- Vulnerability or attack vector utilized

#### 4.3 Notice to Affected Data Principals (Patients)
Direct notification provided in clear, plain language (in patient's preferred native language: English, Hindi, Tamil, Telugu) containing:
- What happened and what data was involved
- Reassurance regarding medical record status and clinical validity of previous advice
- Recommended protective measures (if any)
- Direct helpline and Grievance Officer contact (`grievance.officer@grannus.health`)

### Stage 5: Remediation & Post-Incident Review
- Deploy permanent patch and code refactor.
- Run complete test suite (`pytest tests/`) ensuring zero regression.
- Produce formal Root Cause Analysis (RCA) report retained for 5 years.
- Conduct team debrief and update threat models.
