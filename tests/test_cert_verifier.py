"""Unit tests for agent/tools/cert_verifier.py.

Covers the verifier contract and the cases declared in tests/cases.json,
including the expired-certificate rejection path.
"""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.tools.cert_verifier import (  # noqa: E402
    verify_certificate,
    certificates_in_draft,
    _load_registry,
)


class TestVerifyCertificate(unittest.TestCase):
    def test_active_bpom_is_valid(self):
        r = verify_certificate("NA18240100001", "bpom")
        self.assertTrue(r["found"])
        self.assertTrue(r["valid"])
        self.assertEqual(r["status"], "aktif")
        self.assertEqual(r["rule_reference"], "DEMO-FACT-001")
        self.assertIn("terdaftar dan aktif", r["audit_message"])

    def test_expired_bpom_is_invalid(self):
        r = verify_certificate("NA18200099999", "bpom")
        self.assertTrue(r["found"])
        self.assertFalse(r["valid"])
        self.assertEqual(r["status"], "kedaluwarsa")
        self.assertIn("kedaluwarsa", r["audit_message"])

    def test_revoked_bpom_is_invalid(self):
        r = verify_certificate("NA18200088888", "bpom")
        self.assertTrue(r["found"])
        self.assertFalse(r["valid"])
        self.assertEqual(r["status"], "cabut")
        self.assertIn("dicabut", r["audit_message"])

    def test_unregistered_bpom_number(self):
        r = verify_certificate("NA99999999999", "bpom")
        self.assertFalse(r["found"])
        self.assertFalse(r["valid"])
        self.assertEqual(r["status"], "unregistered")

    def test_expired_halal_certificate(self):
        r = verify_certificate("ID9998887776", "halal")
        self.assertTrue(r["found"])
        self.assertFalse(r["valid"])
        self.assertEqual(r["status"], "kedaluwarsa")
        self.assertEqual(r["rule_reference"], "DEMO-HALAL-001")

    def test_active_halal_certificate(self):
        r = verify_certificate("ID0123456789", "halal")
        self.assertTrue(r["valid"])
        self.assertEqual(r["status"], "aktif")

    def test_revoked_halal_certificate(self):
        r = verify_certificate("ID0000000001", "halal")
        self.assertFalse(r["valid"])
        self.assertEqual(r["status"], "cabut")

    def test_unknown_jenis_is_unregistered(self):
        r = verify_certificate("XYZ123", "bpjs")
        self.assertFalse(r["valid"])
        self.assertEqual(r["status"], "unregistered")
        self.assertIn("tidak dikenali", r["audit_message"])

    def test_empty_number_is_unregistered(self):
        r = verify_certificate("", "bpom")
        self.assertFalse(r["valid"])
        self.assertEqual(r["status"], "unregistered")

    def test_case_insensitive_jenis(self):
        r = verify_certificate("NA18240100001", "BPOM")
        self.assertTrue(r["valid"])

    def test_future_expiry_is_still_active(self):
        # The active row NA18240100001 expires 2027-08-31; freeze today before it.
        import agent.tools.cert_verifier as cv
        original = cv._today
        cv._today = lambda: date(2026, 1, 1)
        try:
            r = verify_certificate("NA18240100001", "bpom")
            self.assertTrue(r["valid"])
        finally:
            cv._today = original

    def test_past_expiry_lapses_even_if_status_aktif(self):
        # If a registry row says aktif but the date is in the past, it is invalid.
        import agent.tools.cert_verifier as cv
        original = cv._today
        cv._today = lambda: date(2030, 1, 1)
        try:
            r = verify_certificate("NA18240100001", "bpom")
            self.assertFalse(r["valid"])
            self.assertEqual(r["status"], "kedaluwarsa")
        finally:
            cv._today = original

    def test_valid_result_states_local_not_official(self):
        r = verify_certificate("NA18240100001", "bpom")
        self.assertIn("bukan otorisasi resmi BPOM/BPJPH", r["audit_message"])


class TestCertificatesInDraft(unittest.TestCase):
    def test_finds_bpom_and_halal_numbers(self):
        draft = "BPOM NA18240100001 dan halal ID0123456789."
        found = certificates_in_draft(draft)
        self.assertIn(("NA18240100001", "bpom"), found)
        self.assertIn(("ID0123456789", "halal"), found)

    def test_no_numbers_returns_empty(self):
        self.assertEqual(certificates_in_draft("Tidak ada nomor di sini."), [])

    def test_short_strings_not_matched(self):
        # NA + 7 digits is below the 8-digit floor and must not match.
        self.assertEqual(certificates_in_draft("BPOM NA1234567"), [])


class TestCasesJsonContract(unittest.TestCase):
    """Every case in tests/cases.json must hold against the live verifier."""

    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((ROOT / "tests" / "cases.json").read_text(encoding="utf-8"))["cases"]

    def test_each_case_matches_verifier(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                r = verify_certificate(case["cited_number"], case["jenis"])
                self.assertEqual(r["status"], case["expected_status"], case["id"])
                self.assertEqual(r["valid"], case["expected_valid"], case["id"])
                self.assertEqual(r["rule_reference"], case["expected_rule_reference"], case["id"])

    def test_expired_case_present(self):
        expired = [c for c in self.cases if c["expected_status"] == "kedaluwarsa"]
        self.assertGreaterEqual(len(expired), 2, "cases.json must cover expired BPOM and expired halal")


class TestRegistryIntegrity(unittest.TestCase):
    def test_registry_loads_with_required_columns(self):
        rows = _load_registry()
        self.assertGreater(len(rows), 0)
        # Every row has the expected keys.
        for row in rows.values():
            self.assertIn("status", row)
            self.assertIn("tanggal_expired", row)
            self.assertIn("nama_produk", row)


if __name__ == "__main__":
    unittest.main()
