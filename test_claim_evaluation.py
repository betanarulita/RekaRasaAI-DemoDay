import json
from collections import Counter
from pathlib import Path
import unittest

from scripts.build_claim_evaluation import build_cases
from scripts.evaluate_claim_predictions import score


class ClaimEvaluationTests(unittest.TestCase):
    def test_corpus_is_reproducible_and_spans_and_splits_are_consistent(self):
        cases = build_cases()
        stored = [json.loads(line) for line in (Path(__file__).parent / "evaluation" / "claims-v1.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(cases, stored)
        self.assertEqual(len(cases), 240)
        self.assertEqual(len({case["id"] for case in cases}), 240)
        self.assertEqual(Counter(case["split"] for case in cases), {"development": 160, "calibration": 40, "held_out": 40})
        split_by_family = {}
        for case in cases:
            self.assertEqual(case["draft"][case["span_start"]:case["span_end"]], case["claim"])
            self.assertTrue(case["synthetic"])
            self.assertTrue(case["requires_human_adjudication"])
            self.assertIn("not_independently_adjudicated", case["label_status"])
            split_by_family.setdefault(case["family_id"], set()).add(case["split"])
        self.assertTrue(all(len(splits) == 1 for splits in split_by_family.values()))

    def test_missing_predictions_do_not_create_a_perfect_score(self):
        cases = build_cases()
        report = score(cases, [])
        self.assertEqual(report["coverage"], 0)
        self.assertEqual(report["balanced_accuracy"], 0)
        self.assertIsNone(report["unsafe_pass_rate"])
        self.assertEqual(sum(row["Missing"] for row in report["confusion_matrix"].values()), 240)

    def test_wrong_source_does_not_count_as_a_grounded_pass(self):
        case = next(case for case in build_cases() if case["expected"]["result"] == "Pass")
        prediction = {"id": case["id"], "result": "Pass", "rule_id": case["expected"]["rule_id"], "claim": case["claim"], "evidence_source_id": "unrelated"}
        report = score([case], [prediction])
        self.assertEqual(report["balanced_accuracy"], 1)
        self.assertEqual(report["correct_passes_with_rule_claim_and_source"], 0)

    def test_unsafe_pass_and_unknown_ids_are_reported(self):
        case = next(case for case in build_cases() if case["expected"]["result"] == "Fail")
        report = score([case], [{"id": case["id"], "result": "Pass"}])
        self.assertEqual(report["unsafe_pass_rate"], 1)
        with self.assertRaises(ValueError):
            score([case], [{"id": "invented", "result": "Pass"}])


if __name__ == "__main__":
    unittest.main()
