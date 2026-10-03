# Clinical Field Pilot Deployment Guide & Standard Operating Procedures (SOP)

**Product:** Grannus (RuralCare AI)  
**Target Settings:** Sub-Centres (Ayushman Arogya Mandir) & Primary Health Centres (PHC)  
**Primary Users:** Accredited Social Health Activists (ASHAs), Auxiliary Nurse Midwives (ANMs), and PHC Medical Officers (RMPs)

---

## 1. Operating Model & Roles

```
[ Village Patient ]
        │
        ▼ (Spoken in Tamil, Hindi, Telugu, or regional dialect)
[ ASHA Worker / ANM ]  ──────► [ Grannus Mobile PWA ]
                                       │
                       (Asynchronous Job Intake / Offline Sync)
                                       ▼
                       [ AI Clinical Triage & Safety Engine ]
                                       │
                                       ▼ (Prioritized Queue)
[ PHC Medical Officer ] ◄───── [ Doctor Telehealth Dashboard ]
        │
        ├──► 1. Confirm Triage & Issue Voice / Digital E-Prescription
        ├──► 2. Priority Override (Clinical Judgment)
        └──► 3. Generate Official Bilingual Referral Slip ──► [ 108 Emergency / District Hospital ]
```

---

## 2. ASHA & Community Health Worker SOP

### 2.1 Patient Intake & Multilingual Consent
1. Greet the patient and select their native language (Tamil, Hindi, Telugu, or English).
2. Present the **DPDP Act 2023 Statutory Consent Screen**:
   - Explain in the patient's language: *"Your voice is recorded only to assist the doctor and is automatically scheduled for deletion within 72 hours."*
   - Check the affirmative consent box upon voluntary patient agreement.
   - If the patient exhibits acute life-threatening distress (unconscious, severe chest agony, choking), **immediately dial 108 or 112** without waiting for the app.

### 2.2 Recording Best Practices
- Keep the smartphone microphone 10–15 cm from the patient's mouth.
- Encourage the patient to describe:
  1. What is bothering them most (chief complaint).
  2. How many days/hours it has lasted.
  3. Associated sensations (e.g. fever with chills, pain radiating to arm).
- Minimum recording duration: **5 seconds**; Maximum: **60 seconds**.

### 2.3 Handling Low-Connectivity / Offline Villages
- If no 4G/cellular signal is available:
  - The app enters **Offline Intake Mode** and saves the voice note locally to the encrypted offline queue (`offline-queue.ts`).
  - Do NOT re-record. Once the device reconnects to network coverage at the sub-centre or village Wi-Fi, the app automatically syncs queued consultations with exponential backoff.

---

## 3. PHC Medical Officer (Doctor) SOP

### 3.1 Authentication & Credential Verification
- Every medical practitioner must log in through the **Clinician Access Portal** with:
  - Full Name / User ID
  - Valid National Medical Commission (NMC) or State Medical Council registration number (e.g. `TNMC-54321`, `KMC-45678`).
- Gated in compliance with the **Telemedicine Practice Guidelines 2020**.

### 3.2 Reviewing AI Triage Summaries
- Cases appear on the Doctor Dashboard color-coded by urgency:
  - 🔴 **HIGH Priority:** Immediate review required. Check Red Flags detected (e.g., suspected myocardial infarction, snakebite, respiratory distress, obstetric hemorrhage).
  - 🟡 **MEDIUM Priority:** High-risk context (infant under 1 year, pregnancy, uncontrolled diabetes) or moderate symptoms.
  - 🟢 **LOW Priority:** Mild, self-limiting symptoms with verified negative red-flag screenings.
- Doctors must listen to the original voice recording or read the verbatim transcript before finalizing clinical decisions.

### 3.3 Telehealth Decision Loop & Actions
From the patient detail drawer, doctors can execute:
1. **Confirm Triage:** Validates AI priority and assigns patient to PHC outpatient queue.
2. **Override Priority:** Elevates or lowers urgency based on physical examination or clinical discretion.
3. **Voice Prescription:** Speaks advice in English; Grannus transcribes, translates, and synthesizes regional audio for the patient.
4. **Referral to District Hospital:** Generates an official bilingual referral slip (`generate_referral_slip`) detailing clinical findings, oxygen/medication administered, and emergency transit advisories.

---

## 4. Emergency Escalation Protocols (Call 108 / 112)

Whenever a case triggers `HIGH` priority with deterministic red flags:
1. **Immediate Stabilization:** Administer first-aid per standard PHC standing orders (e.g. oral hydration, sublingual aspirin for cardiac chest pain, oxygen mask for dyspnea).
2. **Ambulance Dispatch:** Dial **108 (National Ambulance Service)** or local emergency fleet.
3. **Referral Hand-off:** Print or digitally share the bilingual **Clinical Referral Slip (Slip ID: `REF-...`)** with the ambulance EMT and receiving district hospital casualty.
