"""
Demographic & Language Fairness Audit Engine for Grannus RuralCare AI.

Evaluates triage equity and safety parity across:
  - Languages (Tamil, Hindi, Telugu, English, Tanglish, Hinglish)
  - Genders & Pregnancy (Male, Female, Pregnant)
  - Age groups (Infants <1y, Children 1-5y, Adults, Elderly >=60y)

Measures Disparate Impact, Under-triage Disparity, and Four-Fifths Rule compliance.
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.eval_stages import load_gold_cases, build_summary_from_case
from eval.metrics import compute_triage_metrics
from app.feature_extraction import extract_features
from app.priority import assess_priority
from app.safety import screen_safety


def run_fairness_audit() -> Dict[str, Any]:
    cases = load_gold_cases()

    # Run predictions on all cases
    all_data = []
    for c in cases:
        summary = build_summary_from_case(c)
        patient_context = c.get("patient_context", {})
        safety = screen_safety(
            summary=summary,
            transcript_english=c.get("transcript_english"),
            transcript_original=c.get("transcript_original"),
            language_code=c.get("language"),
        )
        features = extract_features(summary, patient_context, safety_screening=safety)
        priority_res = assess_priority(
            summary=summary,
            patient_context=patient_context,
            safety_screening=safety,
            features=features,
        )

        # Categorize age group
        age_str = patient_context.get("age", "")
        age_group = "adult"
        if "month" in age_str.lower() or age_str in ("0", "1"):
            age_group = "infant (<1y)"
        elif age_str in ("2", "3", "4"):
            age_group = "child (1-5y)"
        else:
            try:
                import re
                nums = re.findall(r"\d+", age_str)
                if nums and int(nums[0]) >= 60:
                    age_group = "elderly (>=60y)"
            except Exception:
                pass

        # Categorize gender / pregnancy
        is_preg = patient_context.get("is_pregnant", "no").lower() in ("yes", "true", "1")
        gender_group = "pregnant" if is_preg else patient_context.get("gender", "unknown")

        all_data.append({
            "case_id": c["id"],
            "language": c["language"],
            "gender_group": gender_group,
            "age_group": age_group,
            "true_priority": c["expected_priority"],
            "pred_priority": priority_res.level.value,
        })

    def audit_group(group_key: str) -> Dict[str, Any]:
        groups = {}
        for item in all_data:
            g = item[group_key]
            groups.setdefault(g, []).append(item)

        results = {}
        sensitivities = []
        under_triage_rates = []

        for g_name, items in groups.items():
            g_true = [it["true_priority"] for it in items]
            g_pred = [it["pred_priority"] for it in items]
            m = compute_triage_metrics(g_true, g_pred)
            
            sens = m["emergency_sensitivity"]
            utr = m["total_under_triage_rate"]
            cutr = m["critical_under_triage_rate"]

            sensitivities.append(sens)
            under_triage_rates.append(utr)

            results[g_name] = {
                "sample_size": len(items),
                "emergency_sensitivity": sens,
                "critical_under_triage_rate": cutr,
                "total_under_triage_rate": utr,
                "overall_accuracy": m["overall_accuracy"],
                "zero_critical_under_triage": (cutr == 0.0),
            }

        # Disparity ratio (min / max sensitivity across groups)
        min_sens = min(sensitivities) if sensitivities else 1.0
        max_sens = max(sensitivities) if sensitivities else 1.0
        disparity_ratio = (min_sens / max_sens) if max_sens > 0 else 1.0

        return {
            "subgroups": results,
            "min_sensitivity": round(min_sens, 4),
            "max_sensitivity": round(max_sens, 4),
            "disparity_ratio": round(disparity_ratio, 4),
            "four_fifths_rule_passed": disparity_ratio >= 0.80,
        }

    lang_audit = audit_group("language")
    gender_audit = audit_group("gender_group")
    age_audit = audit_group("age_group")

    overall_parity_passed = (
        lang_audit["four_fifths_rule_passed"] and
        gender_audit["four_fifths_rule_passed"] and
        age_audit["four_fifths_rule_passed"]
    )

    return {
        "total_evaluated": len(all_data),
        "overall_equity_passed": overall_parity_passed,
        "language_parity": lang_audit,
        "gender_maternal_parity": gender_audit,
        "age_demographic_parity": age_audit,
    }


if __name__ == "__main__":
    audit = run_fairness_audit()
    print("=" * 80)
    print("GRANNUS PHASE 2: DEMOGRAPHIC & LINGUISTIC FAIRNESS AUDIT")
    print("=" * 80)
    print(f"Total Evaluated Cases: {audit['total_evaluated']}")
    print(f"Overall Fairness Parity Passed: {audit['overall_equity_passed']}")
    
    print("\n1. Language Breakdown:")
    for lang, metrics in audit["language_parity"]["subgroups"].items():
        print(f"  {lang:<10}: Cases={metrics['sample_size']:<3} Sens={metrics['emergency_sensitivity']:.1%} "
              f"UnderTriage={metrics['total_under_triage_rate']:.1%} CritUnderTriage={metrics['critical_under_triage_rate']:.1%}")
    print(f"  Disparity Ratio: {audit['language_parity']['disparity_ratio']:.3f} (Four-Fifths Passed: {audit['language_parity']['four_fifths_rule_passed']})")

    print("\n2. Gender & Maternal Breakdown:")
    for g, metrics in audit["gender_maternal_parity"]["subgroups"].items():
        print(f"  {g:<10}: Cases={metrics['sample_size']:<3} Sens={metrics['emergency_sensitivity']:.1%} "
              f"UnderTriage={metrics['total_under_triage_rate']:.1%} CritUnderTriage={metrics['critical_under_triage_rate']:.1%}")
    print(f"  Disparity Ratio: {audit['gender_maternal_parity']['disparity_ratio']:.3f} (Four-Fifths Passed: {audit['gender_maternal_parity']['four_fifths_rule_passed']})")

    print("\n3. Age Demographic Breakdown:")
    for age, metrics in audit["age_demographic_parity"]["subgroups"].items():
        print(f"  {age:<16}: Cases={metrics['sample_size']:<3} Sens={metrics['emergency_sensitivity']:.1%} "
              f"UnderTriage={metrics['total_under_triage_rate']:.1%} CritUnderTriage={metrics['critical_under_triage_rate']:.1%}")
    print(f"  Disparity Ratio: {audit['age_demographic_parity']['disparity_ratio']:.3f} (Four-Fifths Passed: {audit['age_demographic_parity']['four_fifths_rule_passed']})")
    print("=" * 80)
