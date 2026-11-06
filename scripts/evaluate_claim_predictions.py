"""Score supplied Reviewer predictions without calling any model or assigning labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


LABELS = ("Pass", "Fail", "Needs Evidence")


def score(cases: list[dict], predictions: list[dict]) -> dict:
    by_id = {row["id"]: row for row in cases}
    predicted = {row["id"]: row for row in predictions}
    if len(predicted) != len(predictions) or set(predicted) - set(by_id):
        raise ValueError("Duplicate or unknown prediction identifiers.")
    if any(row.get("result") not in LABELS for row in predictions):
        raise ValueError("Every prediction must have Pass, Fail, or Needs Evidence as its result.")
    matrix = {actual: {label: 0 for label in (*LABELS, "Missing")} for actual in LABELS}
    bound_passes = 0
    for identifier, case in by_id.items():
        result = predicted.get(identifier, {})
        matrix[case["expected"]["result"]][result.get("result", "Missing")] += 1
        if result.get("result") == "Pass" and case["expected"]["result"] == "Pass":
            bound_passes += int(result.get("rule_id") == case["expected"]["rule_id"] and result.get("evidence_source_id") == case["expected"]["evidence_source_id"] and result.get("claim") == case["claim"])
    recalls = {label: matrix[label][label] / sum(matrix[label].values()) if sum(matrix[label].values()) else None for label in LABELS}
    precision = {label: matrix[label][label] / sum(matrix[actual][label] for actual in LABELS) if sum(matrix[actual][label] for actual in LABELS) else None for label in LABELS}
    blocked = sum(sum(matrix[label].values()) for label in ("Fail", "Needs Evidence"))
    unsafe_passes = sum(matrix[label]["Pass"] for label in ("Fail", "Needs Evidence"))
    observed_blocked = sum(sum(matrix[label][prediction] for prediction in LABELS) for label in ("Fail", "Needs Evidence"))
    family_results = {}
    for case in cases:
        family = family_results.setdefault(case["family_id"], {"cases": 0, "received": 0, "correct": 0, "unsafe_passes": 0})
        prediction = predicted.get(case["id"])
        family["cases"] += 1
        family["received"] += int(prediction is not None)
        family["correct"] += int(bool(prediction) and prediction["result"] == case["expected"]["result"])
        family["unsafe_passes"] += int(bool(prediction) and prediction["result"] == "Pass" and case["expected"]["result"] != "Pass")
    return {
        "dataset_cases": len(cases), "predictions_received": len(predicted),
        "coverage": len(predicted) / len(cases) if cases else 0,
        "confusion_matrix": matrix, "precision_by_class": precision, "recall_by_class": recalls,
        "balanced_accuracy": sum(value for value in recalls.values() if value is not None) / sum(value is not None for value in recalls.values()) if cases else None,
        "blocked_cases": blocked, "blocked_cases_with_prediction": observed_blocked,
        "unsafe_pass_count": unsafe_passes, "unsafe_pass_rate": unsafe_passes / observed_blocked if observed_blocked else None,
        "correct_passes_with_rule_claim_and_source": bound_passes,
        "family_results": family_results,
        "label_status": "author-proposed synthetic labels; not a legal or real-world accuracy benchmark",
        "warning": "Near-duplicate placements share a family. Report grouped results; rows are not independent observations. Missing predictions are counted in recall, not discarded.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=Path(__file__).resolve().parents[1] / "evaluation" / "claims-v1.jsonl")
    parser.add_argument("--predictions", type=Path, required=True, help="JSONL with id, result, rule_id, claim, evidence_source_id from an actual reviewer run")
    parser.add_argument("--split", choices=("development", "calibration", "held_out"))
    args = parser.parse_args()
    load = lambda path: [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    cases, predictions = load(args.cases), load(args.predictions)
    if set(row["id"] for row in predictions) - {row["id"] for row in cases}:
        raise ValueError("Unknown prediction identifiers.")
    if args.split:
        cases = [case for case in cases if case["split"] == args.split]
        selected = {case["id"] for case in cases}
        predictions = [row for row in predictions if row["id"] in selected]
    print(json.dumps(score(cases, predictions), indent=2))
