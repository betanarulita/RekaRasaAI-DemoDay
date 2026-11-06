import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

TEMP = tempfile.TemporaryDirectory(prefix="rekarasa-evidence-")
os.environ["DATABASE_PATH"] = str(Path(TEMP.name) / "test.sqlite3")
import app


DRAFT = (
    "Jahe Rasa is a warm ginger and honey drink mix, blended in small batches. "
    "Mix one sachet with hot water, stir well, and serve warm. Pack size: ten sachets. "
    "Keep the tin closed and dry after opening, and finish within two months."
)
CURE_DRAFT = (
    "Jahe Rasa is a warm ginger and honey drink mix, blended in small batches. "
    "Minum setiap hari untuk menyembuhkan maag kronis. Pack size: ten sachets. "
    "Keep the tin closed and dry after opening, and finish within two months."
)


class Base(unittest.TestCase):
    """Seeds one project, task and draft so save_review can be exercised for real."""

    def setUp(self):
        app.DB_PATH = Path(TEMP.name) / (self.id().replace(".", "_") + ".sqlite3")
        if app.DB_PATH.exists():
            app.DB_PATH.unlink()
        app.init_db()
        self.owner = app.uid()
        db = app.connect()
        db.execute("INSERT INTO users VALUES(?,?,?,?)", (self.owner, "owner@example.test", "x", app.now()))
        db.commit()
        db.close()
        self.project_id, self.task_id, self.version_id = self.seed(DRAFT)

    def seed(self, content):
        db = app.connect()
        project = app.uid()
        db.execute("INSERT INTO projects VALUES(?,?,?,?)", (project, self.owner, "Evidence project", app.now()))
        conv, brief, plan, task, version = [app.uid() for _ in range(5)]
        db.execute("INSERT INTO conversations VALUES(?,?,?,?,?)", (conv, self.owner, project, "Brief", app.now()))
        db.execute("INSERT INTO briefs VALUES(?,?,?,?,?,?,?)", (brief, conv, "Make content", "Audience", "Warm", json.dumps(["Social video script"]), app.now()))
        db.execute("INSERT INTO plans VALUES(?,?,?,?,?)", (plan, brief, json.dumps({"tasks": []}), "confirmed", app.now()))
        db.execute("INSERT INTO tasks(id,plan_id,project_id,format,deadline,publish_at,status,remediation_count,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (task, plan, project, "Social video script", None, None, "needs_revision", 0, app.now()))
        db.execute("INSERT INTO content_versions VALUES(?,?,?,?,?,?,?,?)", (version, task, 1, content, "[]", "fail", 0, app.now()))
        db.commit()
        db.close()
        return project, task, version

    def new_version(self, content):
        db = app.connect()
        version = app.uid()
        db.execute("INSERT INTO content_versions VALUES(?,?,?,?,?,?,?,?)", (version, self.task_id, 2, content, "[]", "fail", 0, app.now()))
        db.commit()
        db.close()
        self.version_id = version
        return version

    def add_source(self, text):
        db = app.connect()
        source = app.uid()
        db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?)",
                   (source, self.project_id, "Spec sheet", "text/plain", text, app.now()))
        db.commit()
        db.close()
        return source

    def review(self, findings, allowed=(), sources=None):
        db = app.connect()
        try:
            task = db.execute("SELECT * FROM tasks WHERE id=?", (self.task_id,)).fetchone()
            version = db.execute("SELECT * FROM content_versions WHERE id=?", (self.version_id,)).fetchone()
            review = app.save_review(db, self.owner, task, version, findings, set(allowed), sources or [])
            db.commit()
            return review
        finally:
            db.close()

    def rows(self):
        db = app.connect()
        try:
            return [dict(r) for r in db.execute(
                "SELECT criterion,result,claim,rule_id,document_id,span_start,span_end,"
                "evidence_source_id,evidence_item_id,instrument_id FROM findings").fetchall()]
        finally:
            db.close()

    def content(self):
        db = app.connect()
        try:
            return db.execute("SELECT content FROM content_versions WHERE id=?", (self.version_id,)).fetchone()["content"]
        finally:
            db.close()


class SpanLocation(unittest.TestCase):
    def test_unique_match_returns_offsets(self):
        self.assertEqual(app.locate_span("abc def", "def"), (4, 7))

    def test_missing_claim_is_not_located(self):
        self.assertIsNone(app.locate_span("abc def", "ghi"))

    def test_ambiguous_claim_is_not_located(self):
        self.assertIsNone(app.locate_span("halal dan halal", "halal"))

    def test_empty_claim_is_not_located(self):
        self.assertIsNone(app.locate_span("abc", ""))


class GuardRejects(unittest.TestCase):
    def test_pass_without_document_id_is_refused(self):
        with self.assertRaises(app.EvidenceBindingError):
            app.assert_evidence_bound({"result": "Pass", "criterion": "x", "span_start": 0, "span_end": 3}, {}, set())

    def test_pass_without_span_is_refused(self):
        with self.assertRaises(app.EvidenceBindingError):
            app.assert_evidence_bound({"result": "Pass", "criterion": "x", "document_id": "v1"}, {}, set())

    def test_empty_span_is_refused(self):
        with self.assertRaises(app.EvidenceBindingError):
            app.assert_evidence_bound({"result": "Fail", "criterion": "x", "document_id": "v1",
                                       "span_start": 5, "span_end": 5}, {}, set())

    def test_evidence_rule_without_a_source_is_refused(self):
        known = {"R": {"requires_evidence": 1, "verdict_basis": None, "instrument_id": None}}
        with self.assertRaises(app.EvidenceBindingError):
            app.assert_evidence_bound({"result": "Pass", "criterion": "x", "document_id": "v1",
                                       "span_start": 0, "span_end": 3, "rule_id": "R",
                                       "claim": "some claim"}, known, set())

    def test_policy_verdict_without_instrument_is_refused(self):
        known = {"R": {"requires_evidence": 0, "verdict_basis": "POLICY", "instrument_id": None}}
        with self.assertRaises(app.EvidenceBindingError):
            app.assert_evidence_bound({"result": "Fail", "criterion": "x", "document_id": "v1",
                                       "span_start": 0, "span_end": 3, "rule_id": "R"}, known, {"R"})

    def test_policy_verdict_with_an_unresolvable_instrument_is_refused(self):
        known = {"R": {"requires_evidence": 0, "verdict_basis": "POLICY", "instrument_id": None}}
        with self.assertRaises(app.EvidenceBindingError):
            app.assert_evidence_bound({"result": "Fail", "criterion": "x", "document_id": "v1",
                                       "span_start": 0, "span_end": 3, "rule_id": "R",
                                       "instrument_id": "UU 8/1999"}, known, {"R"})

    def test_policy_verdict_with_a_resolvable_instrument_is_accepted(self):
        known = {"R": {"requires_evidence": 0, "verdict_basis": "POLICY", "instrument_id": "UU 8/1999"}}
        app.assert_evidence_bound({"result": "Fail", "criterion": "x", "document_id": "v1",
                                   "span_start": 0, "span_end": 3, "rule_id": "R",
                                   "instrument_id": "UU 8/1999"}, known, {"R", "UU 8/1999"})

    def test_fail_on_an_evidence_rule_needs_no_source(self):
        known = {"R": {"requires_evidence": 1, "verdict_basis": None, "instrument_id": None}}
        app.assert_evidence_bound({"result": "Fail", "criterion": "x", "document_id": "v1",
                                   "span_start": 0, "span_end": 3, "rule_id": "R",
                                   "claim": "Teruji klinis"}, known, set())

    def test_vacuous_pass_on_an_evidence_rule_needs_no_source(self):
        known = {"R": {"requires_evidence": 1, "verdict_basis": None, "instrument_id": None}}
        app.assert_evidence_bound({"result": "Pass", "criterion": "x", "document_id": "v1",
                                   "span_start": 0, "span_end": 3, "rule_id": "R", "claim": ""}, known, set())

    def test_deferred_verdict_needs_no_reference(self):
        app.assert_evidence_bound({"result": "Needs Evidence", "criterion": "x"}, {}, set())


class StoredRows(Base):
    def test_guard_failure_is_stored_with_its_span(self):
        self.new_version(CURE_DRAFT)
        self.review([])
        rows = [r for r in self.rows() if r["rule_id"] == "DEMO-CLAIM-001" and r["result"] == "Fail"]
        self.assertEqual(len(rows), 1, "the cure guard should fire on the cure draft")
        row = rows[0]
        self.assertEqual(row["document_id"], self.version_id)
        self.assertEqual(self.content()[row["span_start"]:row["span_end"]], row["claim"])

    def test_locatable_pass_keeps_its_span(self):
        source = self.add_source("Pack size: ten sachets.")
        self.review([{"criterion": "Product fact", "result": "Pass", "claim": "ten sachets",
                      "rule_id": "DEMO-FACT-001", "evidence_source_id": source,
                      "explanation": "The spec sheet states it.", "recommendation": "None"}],
                    allowed=[source])
        stored = [r for r in self.rows() if r["criterion"] == "Product fact"]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["result"], "Pass")
        self.assertEqual(self.content()[stored[0]["span_start"]:stored[0]["span_end"]], "ten sachets")

    def test_every_stored_pass_or_fail_carries_a_reference(self):
        source = self.add_source("Pack size: ten sachets.")
        self.new_version(CURE_DRAFT)
        self.review([{"criterion": "Product fact", "result": "Pass", "claim": "ten sachets",
                      "rule_id": "DEMO-FACT-001", "evidence_source_id": source,
                      "explanation": "x", "recommendation": "y"}], allowed=[source])
        decided = [r for r in self.rows() if r["result"] in ("Pass", "Fail")]
        self.assertGreaterEqual(len(decided), 2, "expected at least one Pass and the guard Fail")
        for row in decided:
            self.assertEqual(row["document_id"], self.version_id, row)
            self.assertIsInstance(row["span_start"], int, row)
            self.assertIsInstance(row["span_end"], int, row)
            self.assertGreater(row["span_end"], row["span_start"], row)

    def test_unlocatable_pass_is_downgraded_not_stored(self):
        review = self.review([{"criterion": "Product fact", "result": "Pass",
                               "claim": "Made from ginger", "rule_id": "DEMO-FACT-001",
                               "evidence_source_id": None, "explanation": "Looks fine",
                               "recommendation": "None"}])
        stored = [r for r in self.rows() if r["criterion"] == "Product fact"]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["result"], "Needs Evidence")
        self.assertIsNone(stored[0]["span_start"])
        finding = [f for f in review["findings"] if f["criterion"] == "Product fact"][0]
        self.assertIn("could not be located", finding["explanation"])

    def test_prohibition_pass_with_no_claim_cites_the_whole_document(self):
        self.review([{"criterion": "Halal check", "result": "Pass", "claim": "",
                      "rule_id": "DEMO-HALAL-001", "evidence_source_id": None,
                      "explanation": "No halal claim present.", "recommendation": "None"}])
        stored = [r for r in self.rows() if r["criterion"] == "Halal check"]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["result"], "Pass")
        self.assertEqual((stored[0]["span_start"], stored[0]["span_end"]), (0, len(self.content())))

    def test_claim_is_stored_in_full(self):
        claim = "Jahe Rasa is a warm ginger and honey drink mix, blended in small batches."
        source = self.add_source(claim)
        self.review([{"criterion": "Product fact", "result": "Pass", "claim": claim,
                      "rule_id": "DEMO-FACT-001", "evidence_source_id": source,
                      "explanation": "x", "recommendation": "y"}], allowed=[source])
        stored = [r for r in self.rows() if r["criterion"] == "Product fact"][0]
        self.assertEqual(stored["claim"], claim)


class PolicyInstrument(Base):
    def seed_policy_rule(self, instrument=None):
        db = app.connect()
        db.execute("INSERT INTO rule_registry(id,version,text,kind,requires_evidence,verdict_basis,instrument_id) "
                   "VALUES(?,?,?,?,?,?,?)",
                   ("TEST-POLICY-001", "1.0", "No absolute guarantee of any kind.", "demo", 0, "POLICY", instrument))
        db.commit()
        db.close()

    def policy_finding(self, **kw):
        finding = {"criterion": "Absolute guarantee", "result": "Fail", "claim": "ten sachets",
                   "rule_id": "TEST-POLICY-001", "explanation": "x", "recommendation": "y"}
        finding.update(kw)
        return finding

    def test_policy_fail_without_instrument_is_not_stored(self):
        # A rule that names no instrument, and a finding that names none either.
        self.seed_policy_rule(instrument=None)
        before = len(self.rows())
        with self.assertRaises(app.EvidenceBindingError):
            self.review([self.policy_finding()])
        self.assertEqual(len(self.rows()), before, "nothing may be written when the guard refuses")

    def test_policy_fail_with_unregistered_instrument_is_not_stored(self):
        self.seed_policy_rule(instrument=None)
        before = len(self.rows())
        with self.assertRaises(app.EvidenceBindingError):
            self.review([self.policy_finding(instrument_id="UU 8/1999")])
        self.assertEqual(len(self.rows()), before)

    def test_policy_fail_with_registered_instrument_is_stored(self):
        self.seed_policy_rule(instrument="UU 8/1999")
        self.review([self.policy_finding(instrument_id="UU 8/1999")])
        stored = [r for r in self.rows() if r["criterion"] == "Absolute guarantee"][0]
        self.assertEqual(stored["result"], "Fail")
        self.assertEqual(stored["instrument_id"], "UU 8/1999")


class RegulatoryContextTests(Base):
    def test_checked_references_are_scoped_and_not_certificate_validation(self):
        context = app.reference_context()
        references = app.policy_references("DEMO-FACT-001", context)
        cosmetics = next(item for item in references if item["id"] == "BPOM-18-2024")
        self.assertEqual(cosmetics["category"], "cosmetics_only")
        self.assertTrue(cosmetics["provisions"])
        self.assertEqual(context["certificate_validation"], "not_performed")
        self.assertEqual(app.policy_references("DEMO-TONE-001", context), [])
        self.assertEqual(app.policy_references("invented-rule", context), [])

    def test_reference_snapshot_survives_reconnect_and_map_change(self):
        from unittest.mock import patch
        db = app.connect()
        task = dict(db.execute("SELECT * FROM tasks WHERE id=?", (self.task_id,)).fetchone())
        task["tone"] = "Warm"
        version = db.execute("SELECT * FROM content_versions WHERE id=?", (self.version_id,)).fetchone()
        try:
            with patch.object(app, "llm_json", return_value=({"findings":[]}, {})) as model:
                result = app.review_draft(db, self.owner, task, version, [], "Fake review failed")
            sent = model.call_args.args[2]["regulatory_context"]
            db.commit()
        finally:
            db.close()
        db = app.connect()
        try:
            event = db.execute("SELECT details FROM audit_events WHERE task_id=? AND event='review.reference_context'", (self.task_id,)).fetchone()
            snapshot = json.loads(event["details"])
            self.assertEqual(snapshot["review_id"], result["id"])
            self.assertEqual(snapshot["sha256"], sent["sha256"])
            with patch.object(app, "reference_context", return_value={"map_version":"future", "references":[]}):
                task_row = db.execute("SELECT * FROM tasks WHERE id=?", (self.task_id,)).fetchone()
                serialized = app.serialize_task(db, task_row)
            review = serialized["versions"][-1]["review"]
            self.assertEqual(review["reference_map_version"], sent["map_version"])
            self.assertEqual(review["reference_context_kind"], "review_snapshot")
            self.assertTrue(any(item["policy_references"] for item in review["findings"]))
            self.assertFalse(serialized["versions"][-1]["human_approved"])
        finally:
            db.close()


class CertificateVerification(Base):
    """The deterministic cert verifier must reject drafts that cite an invalid
    BPOM/Halal number even when the Reviewer model returned a Pass."""

    def setUp(self):
        super().setUp()
        demo = patch.dict(os.environ, {"CERTIFICATE_REGISTRY_MODE": "mock_demo"})
        demo.start()
        self.addCleanup(demo.stop)

    def test_expired_bpom_number_produces_fail_verdict(self):
        content = (
            "FreshGlow Hydra Serum, melembapkan kulit sepanjang hari. "
            "BPOM NA18200099999. Pakai pagi dan malam."
        )
        self.new_version(content)
        findings = [{"criterion": "Product facts", "result": "Pass",
                     "claim": "FreshGlow Hydra Serum", "rule_id": "DEMO-FACT-001",
                     "evidence_source_id": None, "explanation": "ok", "recommendation": ""}]
        review = self.review(findings)
        self.assertEqual(review["verdict"], "Fail")
        cert_findings = [f for f in review["findings"] if f.get("criterion") == "Certificate verification"]
        self.assertEqual(len(cert_findings), 1)
        self.assertIn("kedaluwarsa", cert_findings[0]["explanation"])
        self.assertEqual(cert_findings[0]["rule_id"], "DEMO-FACT-001")

    def test_unregistered_bpom_number_produces_fail_verdict(self):
        content = "Serum muka dengan BPOM NA99999999999, formula premium."
        self.new_version(content)
        findings = [{"criterion": "Product facts", "result": "Pass",
                     "claim": "Serum muka", "rule_id": "DEMO-FACT-001",
                     "evidence_source_id": None, "explanation": "ok", "recommendation": ""}]
        review = self.review(findings)
        self.assertEqual(review["verdict"], "Fail")
        cert = [f for f in review["findings"] if f.get("criterion") == "Certificate verification"][0]
        self.assertIn("tidak terdaftar", cert["explanation"])

    def test_active_bpom_number_does_not_block_pass(self):
        content = (
            "FreshGlow Hydra Serum, melembapkan kulit sepanjang hari. "
            "BPOM NA18240100001. Pakai pagi dan malam."
        )
        self.new_version(content)
        source = self.add_source("FreshGlow Hydra Serum BPOM NA18240100001 aktif.")
        findings = [{"criterion": "Product facts", "result": "Pass",
                     "claim": "FreshGlow Hydra Serum", "rule_id": "DEMO-FACT-001",
                     "evidence_source_id": source, "explanation": "ok", "recommendation": ""}]
        review = self.review(findings, allowed={source})
        cert_findings = [f for f in review["findings"] if f.get("criterion") == "Certificate verification"]
        self.assertEqual(cert_findings, [], "active certificate must not add a finding")

    def test_expired_halal_number_produces_fail_verdict(self):
        content = "Cleansing Foam bersertifikat halal ID9998887776, aman setiap hari."
        self.new_version(content)
        findings = [{"criterion": "Halal certification", "result": "Pass",
                     "claim": "", "rule_id": "DEMO-HALAL-001",
                     "evidence_source_id": None, "explanation": "no halal claim", "recommendation": ""}]
        review = self.review(findings)
        self.assertEqual(review["verdict"], "Fail")
        cert = [f for f in review["findings"] if f.get("criterion") == "Certificate verification"][0]
        self.assertEqual(cert["rule_id"], "DEMO-HALAL-001")
        self.assertIn("kedaluwarsa", cert["explanation"])

    def test_certificate_finding_carries_document_and_span(self):
        content = "Serum dengan BPOM NA18200099999, formula premium."
        self.new_version(content)
        findings = [{"criterion": "Product facts", "result": "Pass",
                     "claim": "Serum", "rule_id": "DEMO-FACT-001",
                     "evidence_source_id": None, "explanation": "ok", "recommendation": ""}]
        self.review(findings)
        rows = [r for r in self.rows() if r["criterion"] == "Certificate verification"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsNotNone(row["document_id"])
        self.assertIsNotNone(row["span_start"])
        self.assertIsNotNone(row["span_end"])
        # The span must point exactly at the cited number in the stored draft.
        stored = self.content()
        self.assertEqual(stored[row["span_start"]:row["span_end"]], "NA18200099999")


class RealCertificateUncertainty(Base):
    def test_real_certificate_is_not_authenticated_by_a_mock_match(self):
        self.new_version(DRAFT + " BPOM NA18240100001.")
        with patch.dict(os.environ, {"CERTIFICATE_REGISTRY_MODE": "manual"}), patch.object(app, "verify_certificate") as mock_lookup:
            review = self.review([])
        mock_lookup.assert_not_called()
        finding = next(f for f in review["findings"] if f["criterion"] == "Certificate verification")
        self.assertEqual(finding["result"], "Needs Evidence")
        self.assertIn("not been checked", finding["explanation"])
        self.assertNotEqual(review["verdict"], "Pass")


if __name__ == "__main__":
    unittest.main(verbosity=2)
