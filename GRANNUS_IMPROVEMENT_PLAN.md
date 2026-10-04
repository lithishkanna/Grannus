# Grannus (RuralCare AI): Improvement Plan

Backend and frontend, in build order. Each item has an ID so it can be handed to an agent on its own.

**Priority key:** `P0` = do first, before any real user logs in. `P1` = needed for the demo. `P2` = polish.

---

## 0. Product definition

Grannus is a **voice bridge with urgency routing** for a specific hospital.

1. A patient speaks symptoms in their own language.
2. The system translates and structures the complaint, assigns an **urgency tier**, and routes it to the right department and an available doctor.
3. The doctor replies by voice in English. The patient hears it in their language.
4. Mild cases get fixed, approved self-care information. Serious cases go to a doctor. Emergencies get the "call 108 / go to the nearest ER" screen immediately.

### Positioning rules (apply everywhere)

- [ ] The product **routes by complaint category and translates. It does not diagnose.**
- [ ] Use the words "urgency" and "self-care information". Do not use "diagnosis", "validated", or "clinician-approved" unless a real clinician has signed off.
- [ ] Show a **"Demo: synthetic data, not medical advice"** banner on every screen until a hospital pilot is approved.
- [ ] The doctor can always re-route a case or override the urgency tier (with a logged reason).

### Urgency tiers

| Tier | Meaning | Patient sees |
|---|---|---|
| `emergency` | Red flags | Full-screen "Call 108 now", nearest emergency facility, and the hospital ER is alerted |
| `doctor_today` | Needs review within 24 h | Queued with a wait estimate |
| `doctor_soon` | Needs review in 2 to 3 days | Asynchronous doctor reply |
| `self_care` | Mild, self-limiting | Approved remedy, "See a doctor if...", automatic check-in |

---

## 1. Backend

### B1. Urgency and safety logic `P0`

- [ ] **B1.1** Fix `determine_urgency_tier` in `priority.py`. Currently chest pain (60 y, sweating), vomiting blood, and a 2-year-old with high fever all return `doctor_soon`.
  - Any `high` safety flag maps to at least `doctor_today`.
  - Chest pain with age 40+ or sweating or breathlessness maps to `emergency`.
  - Fever in an infant or child under 5 maps to at least `doctor_today`.
  - Pregnancy with bleeding maps to `emergency`.
- [ ] **B1.2** Add pytest cases asserting those scenarios can never land in `doctor_soon` or `self_care`.
- [ ] **B1.3** Add **raw-text-only** emergency tests (Gemini returns nothing) in English, Hindi, Tamil, Telugu, Hinglish, Tanglish.
- [ ] **B1.4** Keep regression tests for negation: "chest pain and nausea", "severe chest pain, no fever", "pregnant with heavy bleeding", Hindi "पसीना", and true negations ("I do not have chest pain") that must stay unflagged.
- [ ] **B1.5** Unrated "bleeding" and "vomited and there was blood" must escalate, not return LOW.
- [ ] **B1.6** Biomarker flags are advisory only (no emergency override) and labelled "experimental".
- [ ] **B1.7** Invariant: no component (LLM, ML, API failure) can lower the tier below a deterministic flag. Failure or insufficient input routes to a human, never `self_care`.

**Acceptance:** the test suite includes every scenario above and passes in CI.

### B2. Authentication and sessions `P0`

- [ ] **B2.1** Replace `/api/v1/auth/login`, which currently issues an admin token to anyone with no credentials.
- [ ] **B2.2** Patients log in with **phone OTP** through a provider (Supabase Auth phone, Twilio Verify, or MSG91). Check current India SMS/DLT requirements with the provider.
  - 6 digits, 5-minute expiry, single use, stored hashed.
  - Maximum 5 attempts, resend cooldown, rate limits per number and per IP.
  - OTPs never appear in logs.
  - No hardcoded bypass code. Use the provider's test numbers in development.
- [ ] **B2.3** Doctors, nurses, and admins log in with **email and password**, with accounts created by a hospital admin.
- [ ] **B2.4** Remove the hardcoded fallback signing secret in `auth.py`. The app must refuse to start without `JWT_SECRET_KEY`.
- [ ] **B2.5** Short-lived access tokens, refresh tokens, logout, and revocation.
- [ ] **B2.6** Enforce roles (`patient`, `doctor`, `nurse`, `admin`) on every route.
- [ ] **B2.7** Add authorization to endpoints that are currently open: `/consultations/{id}/escalate`, `/thread` (GET and patient-reply), `/check-in`, `/pipeline/job-status/{job_id}`, and confirm `/media/stream`.
- [ ] **B2.8** A patient can only access their own account's profiles and consultations (test this).

**Acceptance:** every endpoint returns 401 without a token and 403 for the wrong role. No path issues a token without a verified OTP or password.

### B3. Persistence and multi-tenancy `P0`

- [ ] **B3.1** Move all in-memory state to a database: jobs, voice threads, follow-up records, doctor actions, **audit log**, retention schedule, erasure list. Today a restart wipes them.
- [ ] **B3.2** Add migrations and a schema with `hospital_id` on every table, so adding a second hospital later needs no redesign.
- [ ] **B3.3** Core tables: `hospitals`, `departments`, `users`, `doctors`, `accounts` (phone), `patient_profiles`, `consultations`, `pipeline_results`, `messages`, `assignments`, `audit_log`, `consents`.
- [ ] **B3.4** The backend is the **only** database writer. Enable row-level security on every table, deny by default.
- [ ] **B3.5** The audit log is append-only.
- [ ] **B3.6** Audio goes to object storage with short-lived signed URLs and an automatic deletion schedule.

**Acceptance:** restart the server and no consultation, thread, check-in, or audit entry is lost. An anonymous request using only the public database key returns nothing.

### B4. Patient accounts, profiles, consent `P0/P1`

- [ ] **B4.1** One verified phone number holds many patient profiles (name, age, gender, relation, language, allergies, medications).
- [ ] **B4.2** Every consultation belongs to a **profile**, never directly to a phone.
- [ ] **B4.3** Optional 4-digit PIN per profile so family members sharing a phone cannot read each other's reports.
- [ ] **B4.4** "This isn't my number" action and an account-recovery path for recycled numbers.
- [ ] **B4.5** Versioned, timestamped **consent** in the patient's language before the first recording.
- [ ] **B4.6** Data export and erasure endpoints that operate on the database.
- [ ] **B4.7** Doctors see only the profile attached to their case, never the whole account.

### B5. Doctors and routing `P1`

- [ ] **B5.1** Doctor profile: name, registration number, specialty, languages, weekly schedule, capacity, status.
- [ ] **B5.2** Registration numbers are verified by a hospital admin, not matched by a regex.
- [ ] **B5.3** Routing order:
  1. `emergency`: ER screen and ER alert, no queue.
  2. Otherwise map complaint category to department.
  3. Pick an on-duty doctor who speaks the patient's language, with the lowest load.
  4. Fall back to another doctor in the department, then General Medicine, then the duty doctor.
- [ ] **B5.4** Claim locking so two doctors cannot answer one case.
- [ ] **B5.5** Unclaimed-case timer per tier, with automatic escalation.
- [ ] **B5.6** Reassignment, and tier override with a mandatory reason.
- [ ] **B5.7** Log every routing decision with its reason.
- [ ] **B5.8** Routing is described as "by complaint category", never "the system identified the condition".

### B6. Self-care and follow-up `P1`

- [ ] **B6.1** Add approved entries to `remedy_library.py` for **leg pain** and **hair loss** (they currently have none).
- [ ] **B6.2** Remove the free-written Gemini fallback. If no approved entry matches, return a fixed message: "Please consult a doctor", with when to go urgently. Gemini only translates approved text.
- [ ] **B6.3** Remove "clinician-vetted" and "WHO IMCI compliant" wording from `remedy_library.py` until a clinician has actually reviewed it.
- [ ] **B6.4** Every remedy carries a "See a doctor if..." list.
- [ ] **B6.5** Add a scheduler that actually sends the 2 to 3 day check-in (SMS, or an in-app prompt on next open). Today only a due date is stored.
- [ ] **B6.6** "Improving" never lowers a tier without a doctor.
- [ ] **B6.7** "I feel worse" moves the case up one tier and re-routes it.

### B7. AI pipeline reliability `P1`

- [ ] **B7.1** Delimit or escape the transcript in the Gemini prompt (treat it as untrusted input).
- [ ] **B7.2** Remove diagnosis-style mappings from extraction ("sugar" to diabetes, "BP" to hypertension). Record what was said and let the doctor confirm.
- [ ] **B7.3** Gemini fallback model, timeouts, retries, and a circuit breaker. Verify model names in config against current provider docs (`saaras:v2` vs `v3`, `gemini-3.6-flash`).
- [ ] **B7.4** **Back-translate every doctor reply** to English so the doctor can verify it before sending. Never translate drug names or doses.
- [ ] **B7.5** Run independent stages concurrently (`asyncio.gather`).
- [ ] **B7.6** **Demo mode:** cached pipeline responses for your sample recordings, so an API outage cannot break a demo.

### B8. Security hardening `P1`

- [ ] **B8.1** CORS set per environment, plus security headers.
- [ ] **B8.2** Rate limits on every public endpoint.
- [ ] **B8.3** No transcripts or PHI in logs.
- [ ] **B8.4** Upload validation (type, size, magic bytes), dependency and secret scanning in CI.
- [ ] **B8.5** Delete `test-supabase.js`, `check-*.js`, `schema.json`. **Rotate the Supabase key**, which is in public git history (commit `4d6a1e2`).
- [ ] **B8.6** Generic error messages with a `request_id` (confirm no exception text is returned).

### B9. Honesty and documentation `P0`

- [ ] **B9.1** Change the `CLINICAL_VALIDATION_REPORT.md` header from "VALIDATED, PASSED ALL CLINICAL EXIT CRITERIA" to **"Synthetic benchmark only"**.
- [ ] **B9.2** State that STT metrics are simulated (hypothesis equals reference) and extraction is scored on oracle input.
- [ ] **B9.3** State that the ML model is trained on synthetic data.
- [ ] **B9.4** FHIR: change the Condition category from `encounter-diagnosis`, and add Patient demographics, medications, and allergies.
- [ ] **B9.5** Make the README and regulatory documents match what the code actually does.

### B10. Operations and quality `P2`

- [ ] **B10.1** Keep CI green: full pytest suite, ruff, mypy, `tsc`, eslint.
- [ ] **B10.2** Structured logs with `request_id`, health checks, error tracking.
- [ ] **B10.3** Database backups and a tested restore.
- [ ] **B10.4** Degradation rule: if any service fails, route to a human.

---

## 2. Frontend

### F1. Architecture `P0`

- [ ] **F1.1** Remove direct Supabase access from `store-result.ts`, `use-consultations.ts`, and `results/page.tsx`. Everything goes through the authenticated API.
- [ ] **F1.2** Remove the hardcoded Supabase URL and key from `supabase.ts`.
- [ ] **F1.3** One API client that attaches the token, refreshes it, and handles 401s.
- [ ] **F1.4** Replace simulated progress timers (`simulateStages`) with real job-status polling.
- [ ] **F1.5** Role-based routes and route guards.

### F2. Patient app `P1`

- [ ] **F2.1** Phone number entry, OTP screen, resend timer, clear error states.
- [ ] **F2.2** "Who is this for?" profile picker, add-person flow, optional PIN.
- [ ] **F2.3** Consent screen before the first recording.
- [ ] **F2.4** Large record button, language names in their own script (தமிழ், हिन्दी, తెలుగు), live waveform, clear "listening" state.
- [ ] **F2.5** Result screen per tier, using **icons and text as well as color**:
  - `emergency`: full-screen, one big "Call 108" button, nearest emergency facility.
  - `self_care`: approved remedy, "See a doctor if...", check-in.
  - doctor tiers: expected wait, and the doctor's name and department once assigned.
- [ ] **F2.6** "I feel worse" button, always visible after a result.
- [ ] **F2.7** History timeline per profile: date, tier, doctor reply.
- [ ] **F2.8** Voice thread: play doctor replies with speed and repeat controls, record a reply.
- [ ] **F2.9** "Visit hospital" card with address, hours, and a map link.

### F3. Doctor dashboard `P1`

- [ ] **F3.1** Split view: queue on the left, selected case on the right.
- [ ] **F3.2** Queue sorted by tier, with wait timers, claim state, and urgent badges.
- [ ] **F3.3** Case view: both transcripts, extracted symptoms, flags, patient context, audio player.
- [ ] **F3.4** Voice reply recorder that shows the **back-translation** before sending.
- [ ] **F3.5** Re-route, override with reason, and request-more-info actions.
- [ ] **F3.6** Availability toggle.

### F4. Nurse and admin views `P1/P2`

- [ ] **F4.1** All-queues view and a routing log.
- [ ] **F4.2** Doctor roster management and registration verification.
- [ ] **F4.3** Simple analytics: cases by tier and department, unclaimed cases.

### F5. Design, accessibility, language `P1/P2`

- [ ] **F5.1** Consistent design system, large tap targets, light and dark themes, mobile-first for patients.
- [ ] **F5.2** Never rely on color alone for urgency.
- [ ] **F5.3** Screen-reader labels, and keyboard use on the doctor dashboard.
- [ ] **F5.4** UI strings translated into English, Hindi, Tamil, Telugu, with audio prompts for low-literacy users.
- [ ] **F5.5** Offline recording queue (`offline-queue.ts` exists; test it).
- [ ] **F5.6** Demo banner and a "Reset demo data" button.

---

## 3. Demo data (doctor side only)

- [ ] Seed **8 fictional doctors**, each labelled "Demo doctor", with obviously fake registration numbers: General Medicine, Cardiology, Paediatrics, Dermatology, OB-GYN, Orthopaedics, ENT, Duty Doctor.
- [ ] Each has specialty, languages, schedule, and capacity.
- [ ] **No seeded patients.** Patients sign up through real OTP.
- [ ] Record 6 to 8 sample voices yourselves:
  1. Chest pain and sweating (emergency)
  2. Child with high fever (doctor today)
  3. Fever for 3 days (doctor soon)
  4. Hair loss (self-care)
  5. Leg ache after walking (self-care)
  6. Pregnancy with bleeding (emergency, OB-GYN)
  7. Mumbled audio (fail-to-review path)

---

## 4. Out of scope for now

- WhatsApp intake, IVR, and ASHA mode.
- Real clinical validation with clinicians and real recordings.

Without real validation, do not present the product as validated and do not use it for real care decisions. Treat everything as a prototype.

---

## 5. Build order

| Block | Work | Items |
|---|---|---|
| A | Safety and honesty | B1, B9, B2.4, B8.5 |
| B | Database and real auth | B3, B2, F1 |
| C | Patients and consent | B4, F2.1 to F2.3 |
| D | Doctors and routing | B5, B6, F3 |
| E | Pipeline and security | B7, B8 |
| F | Patient UI and design | F2 (rest), F4, F5 |
| G | Rehearsal | Run the full demo end to end twice, using team members as patients |

**Do Block A before anyone outside your team logs in.**

---

## 6. Definition of "demo ready"

- [ ] An anonymous user can read nothing and cannot obtain any token.
- [ ] Chest pain, vomiting blood, infant fever, and pregnancy bleeding never produce `doctor_soon` or `self_care`.
- [ ] A patient logs in with a real OTP, picks a profile, records, and sees a tier-appropriate result.
- [ ] The same phone number shows each person's own reports by profile.
- [ ] The right department and doctor receive the case, and the doctor's voice reply reaches the patient.
- [ ] Leg pain and hair loss return approved self-care text with a "See a doctor if..." list.
- [ ] A server restart loses no data, including the audit log.
- [ ] CI is green, no secrets are in the repo, and every screen carries the demo banner.
- [ ] No document or screen claims diagnosis, validation, or clinician approval.

---

## 7. Agent prompt template

Use one prompt per block:

> Implement items `<IDs>` from `GRANNUS_IMPROVEMENT_PLAN.md` in this repository. Write the failing tests first. Do not change unrelated files. Do not add claims of diagnosis, validation, or clinician approval. When done, run the full backend test suite and `tsc`, and list which acceptance checks pass.

*This plan is an engineering roadmap, not legal or medical advice. Have counsel review CDSCO, DPDP Act, and Telemedicine Practice Guidelines questions, and have a licensed clinician review the triage rules and remedy library before any real use.*
