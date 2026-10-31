# End-to-End Evidence — WorkBuddy → CLI → RekaRasa API

**Date:** 2026-10-31
**Commit base:** `62bd6b1` (working tree modified)
**Purpose:** Replace the earlier simulation-only evidence
(`FreshGlow_Publication_Gate_Status.md`, which stated approval was
"hanya SIMULASI melalui percakapan") with a transcript produced by the shipped
system over real HTTP.

Everything below was executed against a local server (`python app.py`,
`provider=groq`, `database=sqlite`) through
`integrations/workbuddy/rekarasa_cli.py`. Raw transcripts are in
`evidence/e2e/`.

---

## 1. What was actually run

| # | Step | Command | Result |
|---|---|---|---|
| 1 | Register | `POST /api/register` | 200, user created |
| 2 | Login via CLI | `rekarasa_cli.py login` | Session persisted (`01_login.txt`) |
| 3 | Holiday context | `rekarasa_cli.py holidays` | "Tidak ada hari besar dalam 30 hari ke depan" (`02_holidays.txt`) |
| 4 | Projects | `rekarasa_cli.py projects` | 1 project listed (`03_projects.txt`) |
| 5 | **Planner** | `rekarasa_cli.py plan` | Real Groq call, 2 deliverables (`04_plan.txt`) |
| 6 | Confirm | `rekarasa_cli.py confirm` | 2 tasks created (`05_confirm.txt`) |
| 7 | **Gate probe** | `rekarasa_cli.py approve` before generation | **409 `review_required`** (`06_gate_blocked.txt`) |
| 8 | **Writer + Reviewer** | `rekarasa_cli.py generate` | Verdict `Needs Evidence` (`07_generate.txt`) |
| 9 | Remediation 1 | `rekarasa_cli.py revise` | Still `Needs Evidence`, fact support missing (`08_revise.txt`) |
| 10 | Remediation 2 | `rekarasa_cli.py revise` | Verdict `Pass`, `approved_pending_human` (`09_revise2.txt`) |
| 11 | **Human approval** | `rekarasa_cli.py approve` | `approved`, status `human_approved` (`10_approve.txt`) |
| 12 | Double approve | `rekarasa_cli.py approve` again | **409 `already_approved`** |
| 13 | Audit export | `rekarasa_cli.py audit --out ...` | 11 events (`audit-log.json`) |

---

## 2. The gate held — with evidence

**Before generation (no draft exists):**

```
{"error": "The latest version must be reviewed before a human decision.",
 "code": "review_required", "status": 409}
```

**After a passing review, approving twice:**

```
{"error": "This version is already approved. Create a new version to make changes.",
 "code": "already_approved", "status": 409}
```

The CLI exits non-zero on both, so an orchestrator cannot mistake a refusal for
a success.

## 3. The Reviewer actually rejected work

This is the part that a "ChatGPT wrapper" cannot show. First draft:

```
Verdict: Needs Evidence
[Pass] DEMO-CLAIM-001   no disease/medical claim
[Pass] DEMO-FACT-001    facts supported by source
[Pass] DEMO-HALAL-001   no halal claim
[Pass] DEMO-TONE-001    tone matches brief
[Needs Evidence] —      A Marketplace listing needs labelled copy blocks
                        (TITLE, DESCRIPTION). This draft labels 0 of the 1 required.
```

Remediation 1 fixed the labels and surfaced a new problem:

```
[Needs Evidence] DEMO-FACT-001 · klaim: Quick, on-the-go preparation for busy,
health-conscious adults. — This fact is not documented in the attached source.
```

Remediation 2 removed the unsupported claim and passed:

```
TITLE: Jahe Rasa Warm Ginger & Honey Drink Mix – 10 Sachets
DESCRIPTION:
- Natural blend of ginger and honey.
- 10 convenient sachets—mix one with hot water.
- Ready-to-mix: just add hot water for a warm beverage.
Verdict: Pass
```

Note the direction of travel: the model was *made worse-looking* and then
corrected by deterministic checks, not by asking it to try harder. The final
copy is shorter than the first draft because unsupported claims were removed.

## 4. Audit trail (real, from the run)

```
2026-10-31T10:11:53  human.approved        Demo · Jahe Rasa
2026-10-31T10:11:48  review.completed      Demo · Jahe Rasa
2026-10-31T10:11:48  writer.remediated     Demo · Jahe Rasa
2026-10-31T10:11:36  review.completed      Demo · Jahe Rasa
2026-10-31T10:11:36  writer.remediated     Demo · Jahe Rasa
2026-10-31T10:11:28  review.completed      Demo · Jahe Rasa
2026-10-31T10:11:28  writer.draft_created  Demo · Jahe Rasa
2026-10-31T10:11:16  plan.confirmed        Demo · Jahe Rasa
2026-10-31T10:11:10  planner.proposed      Demo · Jahe Rasa
2026-10-31T10:10:55  account.created       Demo · Jahe Rasa
```

Every version, every review, and the human decision are on one timeline. The
chain is reconstructable without trusting the agent's own narration.

## 5. Gap found during this run, and fixed

**Finding WB-5:** refused approvals were returned to the caller but never
recorded. A client retrying the gate in a loop left exactly the same audit trail
as a client that never tried — so an agent repeatedly attempting to approve its
own draft was invisible after the fact.

**Fix:** `POST /api/approve` and `/api/reject` now write an `approval.blocked`
event (with `reason`, and `verdict`/`task_status` where known) *before* raising,
then commit, so the record survives the request rollback.

Verified live after restarting the server:

```
2026-10-31T10:15:51  approval.blocked      Demo · Jahe Rasa
2026-10-31T10:11:53  human.approved        Demo · Jahe Rasa
```

Covered by `test_blocked_approval_is_recorded_in_the_audit_trail`,
`test_blocked_approval_records_the_verdict_that_caused_it`, and
`test_cli_bridge_drives_the_real_http_api`.

## 6. What this does NOT prove

- **No live image generation in this run.** The image path was exercised
  separately and is rate-limited by the free provider (see
  `DEMO_DAY_ARCHITECTURE.md`). Treat image quality as a known limitation, not a
  validated capability.
- **Approval authenticity is still procedural.** The server cannot tell a human
  clicking *Approve* from an agent calling `approve` with a valid session. The
  gate prevents approving *unreviewed* work; it does not prove a human made the
  decision. Tracked as WB-Future (agent-specific tokens) in the roadmap.
- **Single instance, single database.** All of this ran on SQLite on one machine.

## 7. How to reproduce

```bash
python app.py                      # terminal 1
python rekarasa_cli.py login --email <email> --password <password> --human
python rekarasa_cli.py holidays --human
python rekarasa_cli.py plan --project <id> --brief "..." --audience "..." --tone "..." --human
python rekarasa_cli.py confirm --plan <plan_id> --human
python rekarasa_cli.py approve --task <task_id> --human     # expect 409 review_required
python rekarasa_cli.py generate --task <task_id> --human
python rekarasa_cli.py revise --task <task_id> --human      # repeat until Pass (max 3)
python rekarasa_cli.py approve --task <task_id> --note "..." --human
python rekarasa_cli.py audit --out audit-log.json --human
```

Set `REKARASA_SESSION_FILE` to keep demo runs from overwriting a personal
session.
