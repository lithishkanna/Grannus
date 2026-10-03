# Model Card: Grannus Triage Priority Classifier

## Model Overview
- **Model Name**: Grannus Priority Random Forest Classifier (`priority_model.joblib`)
- **Version**: 1.2.0 (Phase 2 Clinical Validation Release)
- **Model Type**: Random Forest Classifier (`sklearn.ensemble.RandomForestClassifier`)
- **Input Dimensions**: 39 clinical, aggregate, context, and acoustic biomarker features
- **Output Classes**: `HIGH` (Emergency / Immediate Referral), `MEDIUM` (Priority Review), `LOW` (Self-Care & Routine Monitoring)
- **Probability Calibration**: Temperature-scaled / Platt-style posterior probabilities

---

## Intended Use & Clinical Scope
- **Intended Use**: Clinical decision-support system to assist rural community healthcare workers (ASHA/ANM) and telemedicine clinicians in prioritizing patient audio consultations in rural India.
- **Intended Users**: Registered medical practitioners, telemedicine triage officers, clinical triage nurses.
- **Out-of-Scope / Prohibited Use**:
  - Autonomous diagnosis of medical conditions.
  - Sole basis for refusing or terminating medical care.
  - Triage of acute major trauma or multi-casualty disasters without clinician oversight.

---

## Training Data & Methodology
> [!IMPORTANT]
> **Data Origin Disclosure**: The current weights in `priority_model.joblib` were trained on **synthetic and clinical protocol-derived cases** designed to mirror the demographic and epidemiological patterns of rural India. Real, patient-identifiable clinical data has not yet been introduced prior to Phase 3 DPDP/ethical clearance.

- **Baseline Protocols**: Incorporates decision thresholds from:
  - **WHO IMCI (Integrated Management of Childhood Illness)**
  - **NEWS2 (National Early Warning Score)**
  - **Indian Ministry of Health & Family Welfare Telemedicine Practice Guidelines**
- **Feature Set**:
  - 18 normalized symptom binary flags
  - 14 aggregate clinical features (max severity, duration, continuous/frequent indicators, safety flags)
  - 4 demographic context features (infant age=0, age groups, gender, age missing)
  - 3 acoustic biomarker features (cough rate, wheeze tonality, respiratory distress score)

---

## Safety Safeguards & Architecture
The ML model operates strictly **within a multi-layered safety envelope**:
1. **Deterministic Safety Engine (`safety.py`)**: Critical danger signs (chest pain, acute dyspnea, stroke, snakebite, scorpion sting, poisoning, severe bleeding, eclampsia) trigger an immediate deterministic emergency override to `HIGH`, bypassing the ML model entirely.
2. **Deterministic Safety Floor (`apply_floor`)**: The final level can never be lower than deterministic flags (critical $\rightarrow$ at least `HIGH`, high $\rightarrow$ at least `MEDIUM`).
3. **ML Sanity Gate**: If rule-based clinical score $\ge 6.0$ (High threshold), ML prediction of `LOW` is automatically elevated to `MEDIUM`.
4. **Insufficient Input Floor**: Empty symptoms, low STT language confidence, or service failures strictly floor triage to `MEDIUM` and mandate human review.
5. **Transparent Baseline Protocol (`app.transparent_triage`)**: Deterministic point-based triage runs alongside ML, providing 100% explainability.

---

## Calibration & Explainability
- **Calibration**: Posterior class probabilities $P(\text{class}|X)$ are smoothed using temperature scaling to prevent overconfident classification.
- **Explainability**: Every inference exposes top feature contributions and plain-language clinical rationales for clinician dashboards (`ml_model.explain()`).
- **Drift Monitoring**: Population Stability Index (PSI) tracks incoming feature distribution and priority shifts (`app.drift_monitor`).
