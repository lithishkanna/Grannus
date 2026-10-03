# Graceful Degradation Matrix & Operational Runbook

**Product:** Grannus (RuralCare AI)  
**System Class:** Clinical Decision Support (CDS)  
**Safety Mandate:** A system degradation must NEVER result in an under-triage of an emergency case to `LOW`. Failures must always fail-safe to `MEDIUM` or `HIGH` with human clinician review required.

---

## 1. Graceful Degradation Matrix

| Subsystem | Failure Mode | Detection Signal | Automated Fallback Behavior | Resulting Triage State |
|---|---|---|---|---|
| **Sarvam STT** | Down, Timeout (>15s), or HTTP 5xx | `SarvamSTTError` or circuit breaker open | 1. Retry with exponential backoff (2 attempts).<br>2. Prompt clinician to type reported symptoms manually.<br>3. Retain raw audio for asynchronous transcription. | Fail-to-review floor applied: Priority clamped to at least `MEDIUM`. Never `LOW`. |
| **Gemini 2.5 LLM** | API Error, Rate Limit (429), or Malformed JSON | `GeminiExtractionError` | 1. Fallback from Primary model to Secondary model (`gemini-2.5-flash` → fallback chain).<br>2. If both fail, execute `TransparentClinicalProtocol` and deterministic keyword matcher (`safety.py`). | Priority floored to at least `MEDIUM`. Red-flag regex scanner operates independently on raw transcripts. |
| **ML Priority Classifier** | Model file corrupted, drift detected (PSI > 0.25), or feature schema mismatch | Model assertion error or `MLPredictionError` | Model automatically disables itself (`is_available = False`). Priority dynamically falls back to the deterministic rule engine (`PriorityAssessment` rule-based scoring). | Rule-engine triage with full transparent rationale. No outage visible to clinician. |
| **Acoustic Biomarkers** | Audio too short (<0.5s), silent frames, or feature extraction error | `num_frames <= 0` or acoustic exception | Feature extraction safely returns default neutral values (cough count: 0, wheeze probability: 0.0). | Biomarker flags disabled. Core triage proceeds based on patient speech and symptoms. |
| **Supabase Database** | Network partition, connection pool exhaustion, or maintenance | PostgreSQL connection timeout | Dashboard falls back to read-only cached consultation data; new intake results cached locally in client `sessionStorage` and queued for synchronization. | Zero clinical data lost. Synchronized upon reconnection. |
| **External Internet Gateway** | Rural PHC offline / disconnected | DNS failure or network offline | PWA offline intake caches patient audio locally; informs health worker that triage is pending sync. | Intake securely stored on local device until cellular/broadband connection is restored. |

---

## 2. Fail-Safe Triage Guarantees

In all failure conditions, Grannus strictly adheres to the following non-negotiable safety invariant:

$$\text{Final Priority} = \max(\text{Model Prediction}, \text{Deterministic Floor}, \text{Fail-Safe Review Floor})$$

Where:
- Any deterministic critical flag (chest pain, severe dyspnea, stroke signs, cyanosis, infant lethargy) $\rightarrow \textbf{HIGH}$.
- Any high flag or unresolvable extraction failure $\rightarrow \textbf{MEDIUM}$ with $\textbf{clinician\_review\_required} = \text{true}$.
- Under no circumstances does a timeout, API 500, or empty extraction yield $\textbf{LOW}$.

---

## 3. Deployment & Rollback Strategy

### 3.1 Blue/Green Deployments via AWS ECS Fargate
1. New container images are built and pushed to AWS ECR with Git commit SHA tags.
2. The staging task definition is deployed to Green target group.
3. Automated synthetic health and readiness checks query `/health` and `/ready`.
4. The CI/CD gold test suite runs against Green.
5. If all tests pass, ALB traffic is shifted 100% from Blue to Green.
6. The Blue task definition remains active for 15 minutes before deregistration to permit instant rollback if anomalies arise.

### 3.2 Instant Rollback Procedure
If error rates spike or latency exceeds 3.0s post-deploy:
```bash
# Rollback ALB target group to Blue revision immediately
aws ecs update-service \
  --cluster grannus-ruralcare-prod-cluster \
  --service grannus-backend-service \
  --task-definition grannus-backend:PREVIOUS_REVISION \
  --force-new-deployment
```

---

## 4. Disaster Recovery & Backup Objectives

| Metric | Target Objective | Implementation |
|---|---|---|
| **Recovery Point Objective (RPO)** | **< 1 Hour** | Supabase continuous WAL archiving and daily automated database snapshots. |
| **Recovery Time Objective (RTO)** | **< 2 Hours** | Infrastructure defined entirely as code in Terraform; container tasks redeployable to any secondary AWS region. |
| **Data Retention Compliance** | **72-Hour Purge** | S3 lifecycle policies and automated backend sweeps ensure raw voice files are purged permanently within 72 hours. |
