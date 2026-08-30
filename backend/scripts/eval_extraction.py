"""
Extraction accuracy eval harness.

Runs `eval/labeled_cases.json` through `gemini_extract.extract_structured_summary`
and scores the output against hand-labeled expectations, so prompt/vocab
changes can be measured instead of eyeballed. This is the "labeled eval set"
referenced in DAY2_CHANGES.md — re-run this every time gemini_extract.py's
prompt or app/vocab.py changes.

Usage:
    cd backend
    python scripts/eval_extraction.py                  # real Gemini calls
    python scripts/eval_extraction.py --mock            # offline harness self-test,
                                                         # no API key required

Scoring per case:
  - symptom_recall     : fraction of expected symptoms whose (normalized)
                          name was found anywhere in the predicted symptoms.
  - negation_accuracy   : of the matched symptoms, fraction where
                          predicted.negated == expected.negated.
  - red_flag_recall     : fraction of expected red-flag keywords found in
                          *some* predicted red_flag phrase (substring match).
  - case_score          : simple average of the three above (0-1).

The aggregate report at the end is what you track over time.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `import app.*`

from dotenv import load_dotenv

load_dotenv()

from app.schemas import Duration, RedFlag, StructuredMedicalSummary, Symptom  # noqa: E402
from app.vocab import normalize_symptom_name  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent.parent / "eval" / "labeled_cases.json"


def _mock_extract(transcript_english: str, patient_context=None) -> StructuredMedicalSummary:
    """
    Tiny keyword-based stand-in for Gemini, used only so this harness can be
    exercised without an API key (e.g. in CI, or to sanity-check the scoring
    logic itself). NOT a substitute for running against the real model —
    swap --mock off to actually measure Gemini's accuracy.
    """
    text = transcript_english.lower()
    symptoms: List[Symptom] = []
    red_flags: List[RedFlag] = []

    def add(name, negated=False):
        symptoms.append(Symptom(name=normalize_symptom_name(name), negated=negated, raw_text=name))

    neg = lambda kw: any(f"{n} {kw}" in text or f"{n}, {kw}" in text for n in ("don't have", "no", "not"))

    if "fever" in text:
        add("fever", negated="don't have fever" in text or "no fever" in text)
    if "cough" in text:
        add("cough")
    if "chest pain" in text:
        add("chest pain", negated="don't have any chest pain" in text or "don't have chest pain" in text)
    if "breath" in text:
        add("difficulty breathing", negated="don't have any breathing" in text or "don't have breathing" in text)
    if "cold-like symptoms" in text or "cold" in text:
        add("cold-like symptoms")
    if "headache" in text:
        add("headache")
    if "hair loss" in text:
        add("hair loss")
    if "stomach" in text:
        add("abdominal pain")
    if "bleeding" in text:
        add("severe bleeding" if "heavy" in text else "bleeding")
    if "dizzy" in text:
        add("dizziness")
    if "body pain" in text:
        add("body pain")

    if "chest pain" in text and not any(s.name == "chest pain" and s.negated for s in symptoms):
        red_flags.append(RedFlag(phrase="chest pain"))
    if "breath" in text and not any(s.name == "difficulty breathing" and s.negated for s in symptoms):
        red_flags.append(RedFlag(phrase="difficulty breathing"))
    if "bleeding" in text:
        red_flags.append(RedFlag(phrase="heavy bleeding"))

    return StructuredMedicalSummary(
        chief_complaint="mock extraction",
        symptoms=symptoms,
        red_flags=red_flags,
    )


def _score_case(case: dict, predicted: StructuredMedicalSummary) -> dict:
    expected_symptoms = case["expected_symptoms"]
    predicted_by_name = {s.name: s for s in predicted.symptoms}

    matched = 0
    negation_correct = 0
    for exp in expected_symptoms:
        exp_name = normalize_symptom_name(exp["name"])
        pred = predicted_by_name.get(exp_name)
        if pred is not None:
            matched += 1
            if pred.negated == exp["negated"]:
                negation_correct += 1

    symptom_recall = matched / len(expected_symptoms) if expected_symptoms else 1.0
    negation_accuracy = negation_correct / matched if matched else (1.0 if not expected_symptoms else 0.0)

    expected_kw = case.get("expected_red_flag_keywords", [])
    predicted_phrases = " ".join(f.phrase.lower() for f in predicted.red_flags)
    kw_hits = sum(1 for kw in expected_kw if kw.lower() in predicted_phrases)
    red_flag_recall = kw_hits / len(expected_kw) if expected_kw else 1.0

    case_score = (symptom_recall + negation_accuracy + red_flag_recall) / 3
    return {
        "id": case["id"],
        "symptom_recall": round(symptom_recall, 2),
        "negation_accuracy": round(negation_accuracy, 2),
        "red_flag_recall": round(red_flag_recall, 2),
        "case_score": round(case_score, 2),
        "predicted_symptoms": [(s.name, s.negated) for s in predicted.symptoms],
        "predicted_red_flags": [f.phrase for f in predicted.red_flags],
    }


async def run(mock: bool) -> None:
    cases = json.loads(CASES_PATH.read_text())

    if mock:
        extract = _mock_extract
    else:
        from app.services.gemini_extract import extract_structured_summary as extract  # noqa: E402

    results = []
    for case in cases:
        predicted = extract(case["transcript_english"], {})
        result = _score_case(case, predicted)
        results.append(result)
        print(f"[{result['case_score']:.2f}] {result['id']}  "
              f"symptom_recall={result['symptom_recall']} "
              f"negation_accuracy={result['negation_accuracy']} "
              f"red_flag_recall={result['red_flag_recall']}")
        print(f"    predicted symptoms  : {result['predicted_symptoms']}")
        print(f"    predicted red_flags : {result['predicted_red_flags']}")

    n = len(results)
    avg = lambda key: round(sum(r[key] for r in results) / n, 3) if n else 0.0
    print("\n=== AGGREGATE ===")
    print(f"cases                 : {n}")
    print(f"avg symptom_recall    : {avg('symptom_recall')}")
    print(f"avg negation_accuracy : {avg('negation_accuracy')}")
    print(f"avg red_flag_recall   : {avg('red_flag_recall')}")
    print(f"avg case_score        : {avg('case_score')}")


def main():
    parser = argparse.ArgumentParser(description="Score gemini_extract.py against eval/labeled_cases.json")
    parser.add_argument("--mock", action="store_true", help="Use a keyword-based mock instead of calling Gemini (no API key needed; for testing the harness itself).")
    args = parser.parse_args()
    asyncio.run(run(mock=args.mock))


if __name__ == "__main__":
    main()
