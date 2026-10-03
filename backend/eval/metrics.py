"""
Clinical Metrics Engine for Grannus RuralCare AI.

Defines and computes clinical triage metrics:
  - Emergency Sensitivity (Target >= 99%)
  - Critical Under-Triage Rate (HIGH -> LOW, Target 0.0%)
  - Total Under-Triage & Over-Triage Rates
  - STT Word Error Rate (WER) & Character Error Rate (CER)
  - Extraction Precision, Recall, Negation Accuracy
  - Demographic & Language Disparity Ratios
"""
from typing import Dict, List, Any, Tuple
import numpy as np


def compute_levenshtein_distance(seq1: List[str], seq2: List[str]) -> int:
    """Compute standard Levenshtein edit distance between two token lists."""
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # Deletion
                    dp[i][j - 1],      # Insertion
                    dp[i - 1][j - 1],  # Substitution
                )
    return dp[m][n]


def compute_wer(reference: str, hypothesis: str) -> float:
    """Compute Word Error Rate (WER = S + D + I / N)."""
    ref_words = reference.lower().strip().split()
    hyp_words = hypothesis.lower().strip().split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    dist = compute_levenshtein_distance(ref_words, hyp_words)
    return float(dist / len(ref_words))


def compute_cer(reference: str, hypothesis: str) -> float:
    """Compute Character Error Rate (CER)."""
    ref_chars = list(reference.lower().strip())
    hyp_chars = list(hypothesis.lower().strip())
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    dist = compute_levenshtein_distance(ref_chars, hyp_chars)
    return float(dist / len(ref_chars))


def compute_triage_metrics(ground_truth: List[str], predictions: List[str]) -> Dict[str, Any]:
    """
    Compute clinical triage performance metrics across HIGH, MEDIUM, LOW.
    
    Levels are ordered by risk: HIGH > MEDIUM > LOW.
    """
    assert len(ground_truth) == len(predictions), "Mismatched lengths"
    n = len(ground_truth)
    if n == 0:
        return {}

    levels = ["HIGH", "MEDIUM", "LOW"]
    level_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    # Confusion matrix: rows = ground_truth, cols = predicted
    matrix = {true_lvl: {pred_lvl: 0 for pred_lvl in levels} for true_lvl in levels}
    for t, p in zip(ground_truth, predictions):
        t_clean = t.upper()
        p_clean = p.upper()
        if t_clean in matrix and p_clean in matrix[t_clean]:
            matrix[t_clean][p_clean] += 1

    # Emergency (HIGH) metrics
    tp_high = matrix["HIGH"]["HIGH"]
    fn_high_med = matrix["HIGH"]["MEDIUM"]
    fn_high_low = matrix["HIGH"]["LOW"]
    total_high = tp_high + fn_high_med + fn_high_low

    emergency_sensitivity = (tp_high / total_high) if total_high > 0 else 1.0

    non_high_total = sum(matrix[l][p] for l in ["MEDIUM", "LOW"] for p in levels)
    tn_high = sum(matrix[l][p] for l in ["MEDIUM", "LOW"] for p in ["MEDIUM", "LOW"])
    emergency_specificity = (tn_high / non_high_total) if non_high_total > 0 else 1.0

    # Under-triage calculations
    critical_under_triage = fn_high_low          # HIGH classified as LOW (dangerous!)
    major_under_triage = fn_high_med             # HIGH classified as MEDIUM
    minor_under_triage = matrix["MEDIUM"]["LOW"] # MEDIUM classified as LOW

    total_under_triaged = critical_under_triage + major_under_triage + minor_under_triage
    under_triage_rate = total_under_triaged / n
    critical_under_triage_rate = critical_under_triage / total_high if total_high > 0 else 0.0

    # Over-triage calculations
    over_triaged = (
        matrix["LOW"]["MEDIUM"] +
        matrix["LOW"]["HIGH"] +
        matrix["MEDIUM"]["HIGH"]
    )
    over_triage_rate = over_triaged / n

    # Per-class Precision, Recall, F1
    per_class = {}
    for lvl in levels:
        tp = matrix[lvl][lvl]
        total_pred = sum(matrix[l][lvl] for l in levels)
        total_actual = sum(matrix[lvl][l] for l in levels)

        prec = (tp / total_pred) if total_pred > 0 else 0.0
        rec = (tp / total_actual) if total_actual > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        per_class[lvl] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support": total_actual,
        }

    overall_accuracy = sum(matrix[l][l] for l in levels) / n

    return {
        "total_cases": n,
        "overall_accuracy": round(overall_accuracy, 4),
        "emergency_sensitivity": round(emergency_sensitivity, 4),
        "emergency_specificity": round(emergency_specificity, 4),
        "critical_under_triage_count": critical_under_triage,
        "critical_under_triage_rate": round(critical_under_triage_rate, 4),
        "major_under_triage_count": major_under_triage,
        "minor_under_triage_count": minor_under_triage,
        "total_under_triage_rate": round(under_triage_rate, 4),
        "over_triage_rate": round(over_triage_rate, 4),
        "confusion_matrix": matrix,
        "per_class": per_class,
    }


def compute_extraction_metrics(
    expected_symptoms_list: List[List[Dict[str, Any]]],
    predicted_symptoms_list: List[List[Dict[str, Any]]],
    expected_red_flags_list: List[List[str]],
    predicted_red_flags_list: List[List[str]],
) -> Dict[str, Any]:
    """Compute precision, recall, negation accuracy, and red-flag recall for extraction stage."""
    total_expected_symptoms = 0
    total_matched_symptoms = 0
    total_predicted_symptoms = 0
    correct_negations = 0

    for exp_syms, pred_syms in zip(expected_symptoms_list, predicted_symptoms_list):
        total_expected_symptoms += len(exp_syms)
        total_predicted_symptoms += len(pred_syms)

        pred_map = {s.get("name", "").lower(): s.get("negated", False) for s in pred_syms}

        for exp in exp_syms:
            exp_name = exp.get("name", "").lower()
            if exp_name in pred_map:
                total_matched_symptoms += 1
                if pred_map[exp_name] == exp.get("negated", False):
                    correct_negations += 1

    symptom_recall = (total_matched_symptoms / total_expected_symptoms) if total_expected_symptoms > 0 else 1.0
    symptom_precision = (total_matched_symptoms / total_predicted_symptoms) if total_predicted_symptoms > 0 else 1.0
    symptom_f1 = (2 * symptom_precision * symptom_recall / (symptom_precision + symptom_recall)) if (symptom_precision + symptom_recall) > 0 else 0.0
    negation_accuracy = (correct_negations / total_matched_symptoms) if total_matched_symptoms > 0 else 1.0

    # Red-flag recall
    total_rf_expected = 0
    total_rf_recalled = 0
    for exp_rfs, pred_rfs in zip(expected_red_flags_list, predicted_red_flags_list):
        total_rf_expected += len(exp_rfs)
        pred_text = " ".join(p.lower() for p in pred_rfs)
        for rf in exp_rfs:
            if any(term.lower() in pred_text for term in rf.split()):
                total_rf_recalled += 1

    red_flag_recall = (total_rf_recalled / total_rf_expected) if total_rf_expected > 0 else 1.0

    return {
        "symptom_recall": round(symptom_recall, 4),
        "symptom_precision": round(symptom_precision, 4),
        "symptom_f1": round(symptom_f1, 4),
        "negation_accuracy": round(negation_accuracy, 4),
        "red_flag_recall": round(red_flag_recall, 4),
        "total_expected_symptoms": total_expected_symptoms,
        "total_matched_symptoms": total_matched_symptoms,
    }
