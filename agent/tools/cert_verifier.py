"""Deterministic mock verifier for BPOM registration and BPJPH halal certificates.

This module supports synthetic Challenge C demonstrations only. It does not
close the external-validation gap or authenticate real certificates.
It reads a local registry CSV (`data/cert_registry_mock.csv`) and resolves a
registration/certificate number to a status, expiry date, and an audit message.

Design contract
---------------
* `verify_certificate` returns a dict with a stable shape:
    {
      "found": bool,
      "valid": bool,               # found AND status==aktif AND not expired
      "status": "aktif"|"kedaluwarsa"|"cabut"|"unregistered",
      "tanggal_expired": str|None,
      "nama_produk": str|None,
      "jenis": str|None,
      "audit_message": str,        # human-readable, citeable in a finding
      "rule_reference": str|None,  # the DEMO-* rule id this verdict supports
    }
* It never raises on a missing/unknown number: an unregistered number is a
  legitimate finding ("not found"), not an exception. It raises only on a
  malformed registry (missing column) so the operator notices the data fault.
* `jenis_sertifikat` is normalized case-insensitively to {"bpom","halal"};
  anything else returns an "unregistered" result so the Reviewer cannot pass
  on a type the verifier does not cover.

Why a separate module and not inline in save_review()
-----------------------------------------------------
The Reviewer integration calls `verify_certificate`; the fuzzing harness
(tests/run_live_reviewer.py) calls the same function without a server. Keeping
the lookup pure and stdlib-only means the harness can exercise real rejection
logic without booting the WSGI app.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "cert_registry_mock.csv"

# Map a certificate type to the demo rule a Pass/Fail on it supports. These are
# the project policy rules, not legal instruments: a rejected number produces a
# DEMO-FACT-001 finding (an unsupported factual claim), and a halal number that
# does not resolve also feeds DEMO-HALAL-001 because the certification claim
# has no backing document.
RULE_BY_JENIS = {
    "bpom": "DEMO-FACT-001",
    "halal": "DEMO-HALAL-001",
}

# "aktif" is the only status that can support a claim. kedaluwarsa and cabut
# are both failures for different reasons: expiry is a lapse, revocation is a
# regulatory action. The audit message distinguishes them.
VALID_STATUS = "aktif"


def _today() -> date:
    """Indirection so tests can monkey-patch the 'current' date."""
    return date.today()


def _load_registry(path: Path | None = None) -> dict[tuple[str, str], dict]:
    """Load the CSV into a dict keyed by (nomor_izin, jenis).

    Raises ValueError if a required column is missing — a silent registry fault
    would let every number pass, which is the defect this module exists to
    prevent.
    """
    path = path or REGISTRY_PATH
    required = {"nomor_izin", "jenis", "nama_produk", "status", "tanggal_expired"}
    rows: dict[tuple[str, str], dict] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"cert_registry_mock.csv missing column(s): {sorted(missing)}")
        for row in reader:
            nomor = (row["nomor_izin"] or "").strip()
            jenis = (row["jenis"] or "").strip().lower()
            if not nomor or not jenis:
                continue
            rows[(nomor, jenis)] = {
                "nama_produk": row["nama_produk"].strip(),
                "status": row["status"].strip().lower(),
                "tanggal_expired": row["tanggal_expired"].strip(),
            }
    return rows


def _parse_expiry(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _result(found: bool, valid: bool, status: str, row: dict | None,
            jenis: str | None, audit_message: str, rule_reference: str | None) -> dict:
    return {
        "found": found,
        "valid": valid,
        "status": status,
        "tanggal_expired": row["tanggal_expired"] if row else None,
        "nama_produk": row["nama_produk"] if row else None,
        "jenis": jenis,
        "audit_message": audit_message,
        "rule_reference": rule_reference,
    }


def verify_certificate(nomor_izin: str, jenis_sertifikat: str, path: Path | None = None) -> dict:
    """Resolve a registration/certificate number to a validity verdict.

    Parameters
    ----------
    nomor_izin:
        The BPOM notification number or BPJPH halal certificate id as it
        appears in the draft (e.g. "NA18240100001").
    jenis_sertifikat:
        "bpom" or "halal". Case-insensitive.
    path:
        Override the registry path (used by tests).

    Returns
    -------
    dict with keys: found, valid, status, tanggal_expired, nama_produk,
    jenis, audit_message, rule_reference.
    """
    jenis = (jenis_sertifikat or "").strip().lower()
    nomor = (nomor_izin or "").strip()
    rule_reference = RULE_BY_JENIS.get(jenis)

    # An unknown jenis is treated as unregistered rather than raising: the
    # Reviewer must not pass on a certificate type the verifier does not cover.
    if jenis not in RULE_BY_JENIS:
        return _result(
            found=False, valid=False, status="unregistered", row=None, jenis=jenis,
            audit_message=(
                f"Jenis sertifikat '{jenis_sertifikat}' tidak dikenali oleh verifier. "
                "Hanya 'bpom' dan 'halal' yang dapat diverifikasi."
            ),
            rule_reference=rule_reference,
        )

    if not nomor:
        return _result(
            found=False, valid=False, status="unregistered", row=None, jenis=jenis,
            audit_message="Nomor izin kosong; tidak dapat diverifikasi.",
            rule_reference=rule_reference,
        )

    registry = _load_registry(path)
    row = registry.get((nomor, jenis))
    if row is None:
        return _result(
            found=False, valid=False, status="unregistered", row=None, jenis=jenis,
            audit_message=(
                f"Nomor {nomor} ({jenis}) tidak terdaftar di pangkalan data referensi lokal. "
                "Klaim nomor izin tidak dapat didukung tanpa pendaftaran yang aktif."
            ),
            rule_reference=rule_reference,
        )

    status = row["status"]
    expiry = _parse_expiry(row["tanggal_expired"])
    today = _today()

    if status == "cabut":
        return _result(
            found=True, valid=False, status="cabut", row=row, jenis=jenis,
            audit_message=(
                f"Nomor {nomor} ({jenis}, produk: {row['nama_produk']}) telah dicabut. "
                "Klaim berdasarkan nomor yang dicabut melanggar kepatuhan dan harus dihapus."
            ),
            rule_reference=rule_reference,
        )

    if status == "kedaluwarsa" or (expiry is not None and expiry < today):
        return _result(
            found=True, valid=False, status="kedaluwarsa", row=row, jenis=jenis,
            audit_message=(
                f"Nomor {nomor} ({jenis}, produk: {row['nama_produk']}) kedaluwarsa pada "
                f"{row['tanggal_expired']}. Klaim berdasarkan nomor kedaluwarsa tidak dapat didukung."
            ),
            rule_reference=rule_reference,
        )

    if status == VALID_STATUS and (expiry is None or expiry >= today):
        return _result(
            found=True, valid=True, status=VALID_STATUS, row=row, jenis=jenis,
            audit_message=(
                f"Nomor {nomor} ({jenis}, produk: {row['nama_produk']}) terdaftar dan aktif "
                f"(kedaluwarsa {row['tanggal_expired']}). Verifikasi pada pangkalan data referensi lokal, "
                "bukan otorisasi resmi BPOM/BPJPH."
            ),
            rule_reference=rule_reference,
        )

    # Defensive: an unknown status string in the registry itself.
    return _result(
        found=True, valid=False, status=status, row=row, jenis=jenis,
        audit_message=(
            f"Nomor {nomor} ({jenis}) memiliki status '{status}' yang tidak dikenali. "
            "Tidak dapat mendukung klaim."
        ),
        rule_reference=rule_reference,
    )


# --- Draft-level convenience used by save_review() ---------------------------

# Patterns a draft uses to cite a registration number. BPOM notification
# numbers for cosmetics follow "NA" + 11 digits; BPJPH halal ids are typically
# "ID" + 10 digits. We match liberally and let the verifier reject unknowns.
BPOM_NUMBER_RE = r"\bNA\d{8,12}\b"
HALAL_NUMBER_RE = r"\bID\d{8,12}\b"


def certificates_in_draft(content: str) -> list[tuple[str, str]]:
    """Return [(nomor_izin, jenis), ...] for every registration number found.

    Used by save_review() to run the verifier on whatever the Writer cited,
    independent of the model's opinion. The Reviewer may pass a halal claim
    and still fail here if the cited certificate number is expired.
    """
    import re
    out: list[tuple[str, str]] = []
    for match in re.finditer(BPOM_NUMBER_RE, content or ""):
        out.append((match.group(0), "bpom"))
    for match in re.finditer(HALAL_NUMBER_RE, content or ""):
        out.append((match.group(0), "halal"))
    return out
