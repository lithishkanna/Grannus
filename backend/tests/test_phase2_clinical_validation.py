"""
Test Suite for Phase 2: Clinical Validation and ML.

Verifies:
  1. Emergency Sensitivity >= 99% on the 360-case Gold Evaluation Set.
  2. Zero Critical Under-Triage (HIGH -> LOW must be 0%).
  3. Safety Engine emergency recall >= 99%.
  4. Transparent Clinical Scoring Protocol (WHO IMCI / NEWS2) accuracy & safety.
  5. Calibrated ML probabilities and explainability output.
  6. Data Drift Monitor alerts and PSI calculation.
  7. Acoustic Biomarker ROC-AUC >= 0.85 on Coswara/COUGHVID benchmark.
  8. Language and demographic fairness parity (Disparity Ratio >= 0.80).
"""
import pytest
from app.drift_monitor import get_drift_monitor, compute_psi
from app.ml_model import get_model
from app.schemas import StructuredMedicalSummary, Symptom, Severity
from app.transparent_triage import assess_transparent_triage
from eval.biomarker_benchmark import run_biomarker_benchmark
from eval.eval_stages import (
    load_gold_cases,
    evaluate_stt_stage,
    evaluate_extraction_stage,
    evaluate_safety_stage,
    evaluate_end_to_end_triage,
)
from eval.fairness_audit import run_fairness_audit
from eval.metrics import compute_triage_metrics, compute_wer, compute_cer


@pytest.fixture(scope="module")
def gold_cases():
    return load_gold_cases()


# =============================================================================
# 1. Gold Dataset & Emergency Sensitivity Gates
# =============================================================================

def test_gold_dataset_size_and_composition(gold_cases):
    """Verify gold dataset has >= 300 cases with emergencies oversampled."""
    assert len(gold_cases) >= 300
    high_count = sum(1 for c in gold_cases if c["expected_priority"] == "HIGH")
    proportion_high = high_count / len(gold_cases)
    # Oversampled ~40%
    assert proportion_high >= 0.35
    assert all("clinician_adjudication" in c for c in gold_cases)


def test_safety_engine_emergency_recall_exceeds_99_percent(gold_cases):
    """Safety engine must flag >= 99% of all clinical emergency cases."""
    res = evaluate_safety_stage(gold_cases)
    assert res["emergency_red_flag_recall"] >= 0.99
    assert res["target_met_99_percent"] is True
    assert res["missed_cases_count"] == 0


def test_end_to_end_emergency_sensitivity_and_zero_critical_under_triage(gold_cases):
    """
    End-to-End Triage Gate:
      - Emergency Sensitivity must be >= 99%
      - Critical Under-Triage (HIGH -> LOW) MUST BE 0.0%
    """
    e2e = evaluate_end_to_end_triage(gold_cases)
    ml_metrics = e2e["ml_pipeline_metrics"]
    
    # Emergency sensitivity target >= 99%
    assert ml_metrics["emergency_sensitivity"] >= 0.99
    # Zero critical under-triage
    assert ml_metrics["critical_under_triage_count"] == 0
    assert ml_metrics["critical_under_triage_rate"] == 0.0


# =============================================================================
# 2. Transparent Clinical Protocol (WHO IMCI / NEWS2)
# =============================================================================

def test_transparent_clinical_protocol_zero_under_triage(gold_cases):
    """Transparent clinical protocol must have 100% sensitivity on danger signs and 0 critical under-triage."""
    e2e = evaluate_end_to_end_triage(gold_cases)
    trans_metrics = e2e["transparent_protocol_metrics"]
    assert trans_metrics["emergency_sensitivity"] >= 0.99
    assert trans_metrics["critical_under_triage_count"] == 0
    assert trans_metrics["overall_accuracy"] >= 0.80


def test_transparent_triage_danger_signs_direct():
    """Verify direct danger signs classification in transparent triage."""
    summary_convulsion = StructuredMedicalSummary(
        chief_complaint="Child having fits",
        symptoms=[Symptom(name="convulsion", severity=Severity.SEVERE, confidence=1.0)],
    )
    res = assess_transparent_triage(summary_convulsion)
    assert res.level.value == "HIGH"
    assert res.is_emergency is True
    assert any("convulsion" in ds.lower() for ds in res.danger_signs)


# =============================================================================
# 3. Model Calibration & Explainability
# =============================================================================

def test_ml_model_calibration_and_explainability():
    """Verify calibrated probability estimates and feature attribution."""
    model = get_model()
    assert model.is_available() is True

    test_features = {
        "symptom_chest_pain": 1.0,
        "max_severity": 4.0,
        "num_symptoms": 2.0,
        "has_continuous_symptom": 1.0,
    }
    exp = model.explain(test_features)
    assert exp["is_calibrated"] is True
    assert "class_probabilities" in exp
    assert sum(exp["class_probabilities"].values()) == pytest.approx(1.0, abs=0.01)
    assert len(exp["top_features"]) > 0
    assert "clinical_explanation" in exp


# =============================================================================
# 4. Data Drift Monitor & Population Stability Index
# =============================================================================

def test_psi_calculation_and_drift_alert():
    """Verify Population Stability Index (PSI) calculation and drift alerting."""
    # 1. Identical distributions -> PSI = 0.0
    dist1 = [0.40, 0.35, 0.25]
    assert compute_psi(dist1, dist1) == pytest.approx(0.0)

    # 2. Significant shift -> PSI >= 0.25
    dist_shifted = [0.10, 0.20, 0.70]
    psi_shifted = compute_psi(dist1, dist_shifted)
    assert psi_shifted >= 0.25

    # 3. Monitor alert on sudden LOW spike
    monitor = get_drift_monitor()
    monitor.reset()
    for i in range(25):
        monitor.record_prediction(f"test-{i}", "LOW", 0.9, {"age_missing": 0})

    status = monitor.check_drift()
    assert status["drift_detected"] is True
    assert any("LOW priority proportion" in a for a in status["alerts"])
    monitor.reset()


# =============================================================================
# 5. Acoustic Biomarker Validation Benchmark
# =============================================================================

def test_acoustic_biomarker_benchmark_roc_auc():
    """Verify biomarker ROC-AUC >= 0.85 on Coswara & COUGHVID benchmark."""
    res = run_biomarker_benchmark(40)
    assert res["roc_auc"] >= 0.85
    assert res["sensitivity"] >= 0.80
    assert res["specificity"] >= 0.80


# =============================================================================
# 6. Language & Demographic Fairness Audit
# =============================================================================

def test_language_and_demographic_fairness_parity():
    """Verify four-fifths rule (Disparity Ratio >= 0.80) across languages, gender, and age."""
    audit = run_fairness_audit()
    assert audit["overall_equity_passed"] is True
    assert audit["language_parity"]["four_fifths_rule_passed"] is True
    assert audit["gender_maternal_parity"]["four_fifths_rule_passed"] is True
    assert audit["age_demographic_parity"]["four_fifths_rule_passed"] is True

    # Critical under-triage must be 0% across ALL languages
    for lang, metrics in audit["language_parity"]["subgroups"].items():
        assert metrics["critical_under_triage_rate"] == 0.0
