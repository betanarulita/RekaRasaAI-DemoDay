# Live Reviewer Accuracy Metrics — Challenge C

**Generated:** 2026-11-04 15:14:03  
**Harness:** `tests/run_live_reviewer.py`  
**Decision layer exercised:** `app.save_review()` (deterministic guards + certificate verifier + evidence binding)  
**Database:** throwaway temp SQLite (live `data/rekarasa.sqlite3` untouched)

## Summary

| Metric | Value |
|---|---|
| Total cases | 10 |
| Violation cases (should be caught) | 8 |
| Violations detected | 8 |
| **Detection rate** | **8/8 (100.0%)** |
| Legitimate cosmetic claims (should pass) | 2 |
| False positives | 0 |
| **False-positive rate** | **0/2 (0.0%)** |

The Reviewer is considered passing when the detection rate is 100% and the 
false-positive rate is 0% — i.e. every deliberate violation is caught and no 
legitimate cosmetic claim under PerBPOM 18/2024 is incorrectly rejected.

## Per-case results

| ID | Kind | Expected | Actual | Detected | Label |
|---|---|---|---|---|---|
| FUZZ-01 | violation | Fail | Fail | yes | Klaim berlebihan terselubung (cosmetic + medical) |
| FUZZ-02 | violation | Fail | Fail | yes | BPOM fiktif (tidak terdaftar) |
| FUZZ-03 | violation | Fail | Fail | yes | BPOM milik produk lain (kedaluwarsa) |
| FUZZ-04 | violation | Fail | Fail | yes | Pencampuran klaim kosmetik + obat medis |
| FUZZ-05 | violation | Fail | Fail | yes | Klaim penyembuhan penyakit terselubung |
| FUZZ-06 | violation | Fail | Fail | yes | Sertifikat halal kedaluwarsa |
| FUZZ-07 | violation | Fail | Fail | yes | Sertifikat halal dicabut |
| FUZZ-08 | violation | Fail | Fail | yes | Klaim obat untuk penyakit kronis |
| FUZZ-09 | legitimate | Pass | Pass | yes | Klaim kosmetik sah (legitimate — must NOT false-positive) |
| FUZZ-10 | legitimate | Pass | Pass | yes | Klaim kosmetik + halal sah (legitimate — must NOT false-positive) |

## Triggering findings per violation

- **FUZZ-01** — Klaim berlebihan terselubung (cosmetic + medical): Unsupported cure claim, Draft substance, Required blocks
  - _Rationale:_ Hidden medical claim: 'memperbaiki sel kulit mati dari dalam' and 'bebas dari jerawat dalam 7 hari' imply a therapeutic/biological action beyond cosmetic moisturising. DEMO-CLAIM-001 must fire.
- **FUZZ-02** — BPOM fiktif (tidak terdaftar): Draft substance, Required blocks, Certificate verification
  - _Rationale:_ Fictitious BPOM number not in the local registry. The certificate verifier must reject it under DEMO-FACT-001.
- **FUZZ-03** — BPOM milik produk lain (kedaluwarsa): Draft substance, Required blocks, Certificate verification
  - _Rationale:_ Expired BPOM notification (expired 2024-03-31) and the word 'jerawat' in a treatment context. Both the certificate verifier (DEMO-FACT-001) and the cure-claim guard (DEMO-CLAIM-001) should fire.
- **FUZZ-04** — Pencampuran klaim kosmetik + obat medis: Unsupported cure claim, Draft substance, Required blocks
  - _Rationale:_ Explicit medical claim ('mengobati eksim kronis', 'meredakan peradangan'). DEMO-CLAIM-001 must fire even though the halal certificate is valid.
- **FUZZ-05** — Klaim penyembuhan penyakit terselubung: Unsupported cure claim, Draft substance, Required blocks
  - _Rationale:_ 'menyembuhkan gangguan pencernaan' and 'maag' trigger the cure-claim guard. A food/drink product claiming to cure a condition is a violation regardless of an active BPOM number.
- **FUZZ-06** — Sertifikat halal kedaluwarsa: Draft substance, Required blocks, Certificate verification
  - _Rationale:_ Expired halal certificate (2023-11-30). The verifier must reject under DEMO-HALAL-001 even though the cosmetic claim itself is benign.
- **FUZZ-07** — Sertifikat halal dicabut: Draft substance, Required blocks, Certificate verification
  - _Rationale:_ Revoked halal certificate. A revoked certificate must never support a halal claim (DEMO-HALAL-001).
- **FUZZ-08** — Klaim obat untuk penyakit kronis: Unsupported cure claim, Draft substance, Required blocks
  - _Rationale:_ Direct disease-cure claim (diabetes). DEMO-CLAIM-001 must fire. No BPOM number present, but the cure guard is pattern-based.

## Methodology

1. Each draft is seeded as a `Marketplace description` task with a fresh version.
2. The simulated Reviewer returns a benign `Pass` on every configured rule, so 
   the only `Fail`/`Needs Evidence` signals originate from the deterministic 
   decision layer — the regex guards (cure claims, halal claims), the certificate 
   verifier (`agent/tools/cert_verifier.py`), the evidence-binding guard, and the 
   rule-coverage check.
3. This isolates the question the harness exists to answer: *does the code that 
   decides the verdict catch the violation on its own, without relying on the 
   model's honesty?* A miss here is a real gap in the guard layer, not a model 
   quality issue.
4. Legitimate cases use permitted cosmetic claims ('melembapkan', 
   'menjaga kelembapan', 'melembutkan') with active BPOM and halal numbers. A 
   false positive here would mean the guard is over-broad and blocks lawful 
   marketing copy — a compliance defect in its own right under PerBPOM 18/2024.

## Responsible AI note

The certificate verifier reads `data/cert_registry_mock.csv`, a local mock. A 
`Pass` here is not official BPOM/BPJPH authorization; it means the number is 
present and active in the local reference data. Final legal sign-off remains 
with the Penanggung Jawab / Tim Legal. See `submission/02_accountability_sheet.md` 
for the full legal compliance disclaimer.
