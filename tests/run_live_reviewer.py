#!/usr/bin/env python3
"""Live Reviewer fuzzing harness — Challenge C accuracy regression.

Runs 10 crafted drafts against the real decision layer (app.save_review) and
measures:
  * detection rate for deliberate violations (should-be-Fail cases)
  * false-positive rate on legitimate cosmetic claims under PerBPOM 18/2024
    (should-be-Pass cases — must stay at 0)

The "Reviewer" exercised here is the full deterministic stack in save_review():
the model-independent guards (cure claims, halal claims), the certificate
verifier, the evidence-binding guard, and the coverage check. This is the layer
that actually decides the verdict; the LLM Reviewer only proposes findings that
this layer then validates and overrides. Testing the decision layer directly is
what makes the harness hermetic and repeatable.

Output:
  * stdout  — per-case PASS/FAIL and a summary line
  * submission/03_live_reviewer_metrics.md — the written accuracy report

Run:
    python tests/run_live_reviewer.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

# Use a throwaway database so the live data/rekarasa.sqlite3 is never touched.
TEMP = tempfile.TemporaryDirectory(prefix="rekarasa-fuzz-")
os.environ["DATABASE_PATH"] = str(Path(TEMP.name) / "fuzz.sqlite3")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app  # noqa: E402
from agent.tools.cert_verifier import verify_certificate  # noqa: E402


# ---------------------------------------------------------------------------
# Fuzzing cases
# ---------------------------------------------------------------------------
# Each case is (id, label, draft, kind, expected_verdict, reason).
# kind = "violation" (Reviewer must catch) or "legitimate" (must NOT false-positive).
# expected_verdict is what save_review() should return for the draft.
CASES = [
    (
        "FUZZ-01",
        "Klaim berlebihan terselubung (cosmetic + medical)",
        "Serum Glow dengan ekstrak bunga. Menjaga kelembapan kulit sekaligus "
        "memperbaiki sel kulit mati dari dalam, sehingga kulit kembali sehat "
        "dan bebas dari jerawat dalam 7 hari. BPOM NA18240100001.",
        "violation",
        "Fail",
        "Hidden medical claim: 'memperbaiki sel kulit mati dari dalam' and "
        "'bebas dari jerawat dalam 7 hari' imply a therapeutic/biological action "
        "beyond cosmetic moisturising. DEMO-CLAIM-001 must fire.",
    ),
    (
        "FUZZ-02",
        "BPOM fiktif (tidak terdaftar)",
        "Serum Muka Premium dengan BPOM NA99999999999. Melembapkan dan "
        "meratakan warna kulit. Dipakai pagi dan malam.",
        "violation",
        "Fail",
        "Fictitious BPOM number not in the local registry. The certificate "
        "verifier must reject it under DEMO-FACT-001.",
    ),
    (
        "FUZZ-03",
        "BPOM milik produk lain (kedaluwarsa)",
        "Legacy Acne Toner, diformulasi khusus untuk jerawat. BPOM NA18200099999. "
        "Gunakan dua kali sehari.",
        "violation",
        "Fail",
        "Expired BPOM notification (expired 2024-03-31) and the word 'jerawat' "
        "in a treatment context. Both the certificate verifier (DEMO-FACT-001) "
        "and the cure-claim guard (DEMO-CLAIM-001) should fire.",
    ),
    (
        "FUZZ-04",
        "Pencampuran klaim kosmetik + obat medis",
        "Krim Malam Herbal. Melembapkan kulit dan mengobati eksim kronis serta "
        "meredakan peradangan. Bersertifikat halal ID0123456789.",
        "violation",
        "Fail",
        "Explicit medical claim ('mengobati eksim kronis', 'meredakan "
        "peradangan'). DEMO-CLAIM-001 must fire even though the halal "
        "certificate is valid.",
    ),
    (
        "FUZZ-05",
        "Klaim penyembuhan penyakit terselubung",
        "Minuman jahe madu alami. Hangat di perut, menenangkan maag, dan "
        "menyembuhkan gangguan pencernaan. BPOM NA18240100001.",
        "violation",
        "Fail",
        "'menyembuhkan gangguan pencernaan' and 'maag' trigger the cure-claim "
        "guard. A food/drink product claiming to cure a condition is a "
        "violation regardless of an active BPOM number.",
    ),
    (
        "FUZZ-06",
        "Sertifikat halal kedaluwarsa",
        "Cleansing Foam lembut untuk wajah. Bersertifikat halal ID9998887776. "
        "Bebas dari bahan keras dan aman untuk kulit sensitif.",
        "violation",
        "Fail",
        "Expired halal certificate (2023-11-30). The verifier must reject under "
        "DEMO-HALAL-001 even though the cosmetic claim itself is benign.",
    ),
    (
        "FUZZ-07",
        "Sertifikat halal dicabut",
        "Toner Konsentrat dengan ekstrak alami. Bersertifikat halal ID0000000001. "
        "Menyegarkan dan menyeimbangkan kulit.",
        "violation",
        "Fail",
        "Revoked halal certificate. A revoked certificate must never support a "
        "halal claim (DEMO-HALAL-001).",
    ),
    (
        "FUZZ-08",
        "Klaim obat untuk penyakit kronis",
        "Suplemen herbal alami. Mengobati diabetes tipe 2 dan menurunkan gula "
        "darah secara alami tanpa efek samping.",
        "violation",
        "Fail",
        "Direct disease-cure claim (diabetes). DEMO-CLAIM-001 must fire. No "
        "BPOM number present, but the cure guard is pattern-based.",
    ),
    (
        "FUZZ-09",
        "Klaim kosmetik sah (legitimate — must NOT false-positive)",
        "TITLE: FreshGlow Hydra Serum\n"
        "DESCRIPTION: FreshGlow Hydra Serum melembapkan kulit dan menjaga "
        "kelembapan sepanjang hari. Diformulasi dengan hyaluronic acid dan "
        "ekstrak bunga yang lembut. BPOM NA18240100001. Pakai pagi dan malam "
        "setelah bersihkan wajah. Cocok untuk kulit normal hingga kering.",
        "legitimate",
        "Pass",
        "Legitimate cosmetic moisturising claim with an active BPOM number. "
        "Under PerBPOM 18/2024, 'melembapkan' and 'menjaga kelembapan' are "
        "permitted cosmetic claims. Must NOT be flagged as a violation.",
    ),
    (
        "FUZZ-10",
        "Klaim kosmetik + halal sah (legitimate — must NOT false-positive)",
        "TITLE: FreshGlow Daily Moisturizer\n"
        "DESCRIPTION: FreshGlow Daily Moisturizer melembapkan dan melembutkan "
        "kulit wajah sepanjang hari. Diperkaya vitamin E dan aloe vera. "
        "Bersertifikat halal ID0123456789. BPOM NA18240100002. Pakai pagi dan "
        "malam untuk hasil optimal. Aman untuk pemakaian harian.",
        "legitimate",
        "Pass",
        "Both the BPOM number and the halal certificate are active. The cosmetic "
        "claims (melembapkan, melembutkan) are permitted. Must NOT be "
        "false-positived.",
    ),
]


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------
class FuzzHarness:
    def __init__(self):
        self.db_path = Path(TEMP.name) / "fuzz.sqlite3"
        app.DB_PATH = self.db_path
        if self.db_path.exists():
            self.db_path.unlink()
        app.init_db()
        self.owner = app.uid()
        db = app.connect()
        db.execute("INSERT INTO users VALUES(?,?,?,?)", (self.owner, "fuzz@example.test", "x", app.now()))
        db.commit()
        db.close()
        self.results = []

    def _seed_task(self, content):
        db = app.connect()
        project = app.uid()
        db.execute("INSERT INTO projects VALUES(?,?,?,?)", (project, self.owner, "Fuzz project", app.now()))
        conv, brief, plan, task, version = [app.uid() for _ in range(5)]
        db.execute("INSERT INTO conversations VALUES(?,?,?,?,?)", (conv, self.owner, project, "Brief", app.now()))
        db.execute("INSERT INTO briefs VALUES(?,?,?,?,?,?,?)", (brief, conv, "Make content", "Audience", "Warm", json.dumps(["Marketplace description"]), app.now()))
        db.execute("INSERT INTO plans VALUES(?,?,?,?,?)", (plan, brief, json.dumps({"tasks": []}), "confirmed", app.now()))
        db.execute("INSERT INTO tasks(id,plan_id,project_id,format,deadline,publish_at,status,remediation_count,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (task, plan, project, "Marketplace description", None, None, "needs_revision", 0, app.now()))
        db.execute("INSERT INTO content_versions VALUES(?,?,?,?,?,?,?,?)", (version, task, 1, content, "[]", "fail", 0, app.now()))
        db.commit()
        db.close()
        return task, version

    def _first_sentence(self, text):
        """Return the first sentence of the draft, verbatim, for the claim field.

        save_review's locate_span requires the claim to appear verbatim in the
        draft. Using the first sentence keeps the harness focused on guard
        behaviour rather than span-location edge cases.
        """
        end = text.find(".")
        return text[: end + 1] if end > 0 else text[:60]

    def run_one(self, case):
        case_id, label, draft, kind, expected, reason = case
        task_id, version_id = self._seed_task(draft)
        # Simulate the Reviewer returning a benign Pass on every configured rule,
        # so the only Fail signals come from the deterministic guards. The claim
        # field uses a verbatim substring of the draft so the evidence-binding
        # span locator does not downgrade it to Needs Evidence — we are testing
        # the guards, not the locator. Prohibition rules (CLAIM/HALAL/TONE) use
        # an empty claim, matching how a real Reviewer reports "nothing
        # prohibited found".
        source = self._add_source(draft)
        # save_review receives sources as dicts shaped like source_payload():
        # {"id", "name", "text"}. halal_is_documented() reads source["text"],
        # so the source must be passed here, not just its id — otherwise the
        # halal guard fires on every draft that mentions halal even when a
        # source documents it.
        sources_list = [{"id": source, "name": "Spec", "text": draft}]
        # Pick a short verbatim quote that appears in every draft we use.
        verbatim = self._first_sentence(draft)
        findings = [
            {"criterion": "Product facts", "result": "Pass", "claim": verbatim,
             "rule_id": "DEMO-FACT-001", "evidence_source_id": source,
             "explanation": "reviewer pass", "recommendation": ""},
            {"criterion": "Health claims", "result": "Pass", "claim": "",
             "rule_id": "DEMO-CLAIM-001", "evidence_source_id": None,
             "explanation": "no cure claim", "recommendation": ""},
            {"criterion": "Halal", "result": "Pass", "claim": "",
             "rule_id": "DEMO-HALAL-001", "evidence_source_id": None,
             "explanation": "no halal claim", "recommendation": ""},
            {"criterion": "Tone", "result": "Pass", "claim": "",
             "rule_id": "DEMO-TONE-001", "evidence_source_id": None,
             "explanation": "tone ok", "recommendation": ""},
        ]
        db = app.connect()
        try:
            task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            version = db.execute("SELECT * FROM content_versions WHERE id=?", (version_id,)).fetchone()
            review = app.save_review(db, self.owner, task, version, findings, {source}, sources_list)
            db.commit()
        finally:
            db.close()
        actual = review["verdict"]
        detected = (actual == "Fail") if kind == "violation" else (actual == "Pass")
        triggering = [
            f["criterion"] for f in review["findings"]
            if f["result"] in ("Fail", "Needs Evidence")
        ]
        self.results.append({
            "id": case_id,
            "label": label,
            "kind": kind,
            "expected": expected,
            "actual": actual,
            "detected": detected,
            "triggering_findings": triggering,
            "reason": reason,
        })
        return detected

    def _add_source(self, text):
        db = app.connect()
        source = app.uid()
        db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?)",
                   (source, self.project_for_task(), "Spec", "text/plain", text, app.now()))
        db.commit()
        db.close()
        return source

    def project_for_task(self):
        db = app.connect()
        row = db.execute("SELECT project_id FROM tasks ORDER BY rowid DESC LIMIT 1").fetchone()
        db.close()
        return row["project_id"]

    def summary(self):
        violations = [r for r in self.results if r["kind"] == "violation"]
        legitimates = [r for r in self.results if r["kind"] == "legitimate"]
        detected_v = sum(1 for r in violations if r["detected"])
        fp = sum(1 for r in legitimates if not r["detected"])
        return {
            "total": len(self.results),
            "violations": len(violations),
            "violations_detected": detected_v,
            "detection_rate": f"{detected_v}/{len(violations)} ({100 * detected_v / len(violations):.1f}%)" if violations else "n/a",
            "legitimates": len(legitimates),
            "false_positives": fp,
            "false_positive_rate": f"{fp}/{len(legitimates)} ({100 * fp / len(legitimates):.1f}%)" if legitimates else "n/a",
        }


def run_all():
    harness = FuzzHarness()
    print("=" * 72)
    print("Live Reviewer Fuzzing — 10 cases")
    print("=" * 72)
    for case in CASES:
        ok = harness.run_one(case)
        case_id, label, _, kind, expected, _ = case
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {case_id} ({kind:11s}) {label}")
    summary = harness.summary()
    print("-" * 72)
    print(f"Detection rate      : {summary['detection_rate']}")
    print(f"False-positive rate : {summary['false_positive_rate']}")
    print("=" * 72)
    return harness, summary


def write_report(harness, summary):
    report_dir = ROOT / "submission"
    report_dir.mkdir(exist_ok=True)
    lines = []
    lines.append("# Live Reviewer Accuracy Metrics — Challenge C")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append(f"**Harness:** `tests/run_live_reviewer.py`  ")
    lines.append(f"**Decision layer exercised:** `app.save_review()` (deterministic guards + certificate verifier + evidence binding)  ")
    lines.append(f"**Database:** throwaway temp SQLite (live `data/rekarasa.sqlite3` untouched)")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total cases | {summary['total']} |")
    lines.append(f"| Violation cases (should be caught) | {summary['violations']} |")
    lines.append(f"| Violations detected | {summary['violations_detected']} |")
    lines.append(f"| **Detection rate** | **{summary['detection_rate']}** |")
    lines.append(f"| Legitimate cosmetic claims (should pass) | {summary['legitimates']} |")
    lines.append(f"| False positives | {summary['false_positives']} |")
    lines.append(f"| **False-positive rate** | **{summary['false_positive_rate']}** |")
    lines.append("")
    lines.append("The Reviewer is considered passing when the detection rate is 100% and the ")
    lines.append("false-positive rate is 0% — i.e. every deliberate violation is caught and no ")
    lines.append("legitimate cosmetic claim under PerBPOM 18/2024 is incorrectly rejected.")
    lines.append("")
    lines.append("## Per-case results")
    lines.append("")
    lines.append("| ID | Kind | Expected | Actual | Detected | Label |")
    lines.append("|---|---|---|---|---|---|")
    for r in harness.results:
        flag = "yes" if r["detected"] else "NO"
        lines.append(f"| {r['id']} | {r['kind']} | {r['expected']} | {r['actual']} | {flag} | {r['label']} |")
    lines.append("")
    lines.append("## Triggering findings per violation")
    lines.append("")
    for r in harness.results:
        if r["kind"] != "violation":
            continue
        triggers = ", ".join(r["triggering_findings"]) or "(none — MISS)"
        lines.append(f"- **{r['id']}** — {r['label']}: {triggers}")
        lines.append(f"  - _Rationale:_ {r['reason']}")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("1. Each draft is seeded as a `Marketplace description` task with a fresh version.")
    lines.append("2. The simulated Reviewer returns a benign `Pass` on every configured rule, so ")
    lines.append("   the only `Fail`/`Needs Evidence` signals originate from the deterministic ")
    lines.append("   decision layer — the regex guards (cure claims, halal claims), the certificate ")
    lines.append("   verifier (`agent/tools/cert_verifier.py`), the evidence-binding guard, and the ")
    lines.append("   rule-coverage check.")
    lines.append("3. This isolates the question the harness exists to answer: *does the code that ")
    lines.append("   decides the verdict catch the violation on its own, without relying on the ")
    lines.append("   model's honesty?* A miss here is a real gap in the guard layer, not a model ")
    lines.append("   quality issue.")
    lines.append("4. Legitimate cases use permitted cosmetic claims ('melembapkan', ")
    lines.append("   'menjaga kelembapan', 'melembutkan') with active BPOM and halal numbers. A ")
    lines.append("   false positive here would mean the guard is over-broad and blocks lawful ")
    lines.append("   marketing copy — a compliance defect in its own right under PerBPOM 18/2024.")
    lines.append("")
    lines.append("## Responsible AI note")
    lines.append("")
    lines.append("The certificate verifier reads `data/cert_registry_mock.csv`, a local mock. A ")
    lines.append("`Pass` here is not official BPOM/BPJPH authorization; it means the number is ")
    lines.append("present and active in the local reference data. Final legal sign-off remains ")
    lines.append("with the Penanggung Jawab / Tim Legal. See `submission/02_accountability_sheet.md` ")
    lines.append("for the full legal compliance disclaimer.")
    lines.append("")
    (ROOT / "submission" / "03_live_reviewer_metrics.md").write_text(
        "\n".join(lines), encoding="utf-8")
    print(f"\nReport written to submission/03_live_reviewer_metrics.md")


# ---------------------------------------------------------------------------
# unittest wrapper so `python -m unittest` also picks it up
# ---------------------------------------------------------------------------
class TestLiveReviewerFuzz(unittest.TestCase):
    def test_all_violations_detected_and_no_false_positives(self):
        harness, summary = run_all()
        self.assertEqual(summary["violations_detected"], summary["violations"],
                         "Every deliberate violation must be detected.")
        self.assertEqual(summary["false_positives"], 0,
                         "No legitimate cosmetic claim may be false-positived.")


if __name__ == "__main__":
    harness, summary = run_all()
    write_report(harness, summary)
    # Exit non-zero if any case failed, so CI catches regressions.
    sys.exit(0 if summary["violations_detected"] == summary["violations"]
             and summary["false_positives"] == 0 else 1)
