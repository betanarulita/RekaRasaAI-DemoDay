# Creator Agent validation — 2 November 2026

## Result

Baseline: **123 passed** (`test_app` 100 + `test_evidence_binding` 23).
Final full suite: **146 passed**, 182.212 seconds, exit 0. The 23 added tests
cover visual workflow/layout/snapshots and the synthetic evaluation corpus/scorer.
No existing test was removed or weakened. [Full output](./creator-agent-tests-2026-11-02.txt).

```text
python -X utf8 scripts/run_tests.py
Ran 146 tests in 182.212s
OK
```

The first baseline attempt was interrupted after discovering that the existing
test setup read local SMTP configuration and attempted email delivery. A rerun
with process-only SMTP/Sentry isolation passed 123 tests. The new runner additionally
shadows model credentials and rejects external socket connections. Local HTTP is
allowed for the actual CLI-to-WSGI integration test. No .env or credential was changed.

Intermediate layout checks caught an overlong-token regression after increasing
the image text size. The renderer now fits a word only within a bounded readable
font range and otherwise rejects the copy. Escaping assertions were retained.
The final full suite above includes that correction, all four canvas ratios, and
the snapshot-integrity changes.

## What the final tests prove

- A brief with no format can request all six supported channels; task/channel
  preferences are preserved and unsupported Planner facts are removed.
- Omitted requested channels fail before conversation/task creation; retry does
  not leave a second partial plan.
- Existing FreshGlow reject → revise → re-review → pending human approval →
  explicit approval and audit persistence still pass.
- The deterministic cure guard also catches acne/jerawat claims when a fake
  Reviewer incorrectly returns Pass.
- HEADLINE/BODY/CTA are extracted from the saved version; CAPTION/VISUAL are not
  painted onto the image. Markup is escaped and overlong/overflowing copy is refused.
- Writer VISUAL reaches the configured image-provider call; defaults and canvas
  are derived from task/channel context. The tests use a fake image provider.
- Image generation failure leaves no image/composition/approval rows or files.
- Compose retry is idempotent; a newly generated image does not inherit approval.
- Visual approval requires latest-copy approval and explicit image inspection;
  wrong-account and missing-CSRF requests are refused.
- Editing copy invalidates export of the old composition. A task at its revision
  limit cannot bypass it through visual approval.
- Image SHA-256, SVG snapshot and render SHA-256 persist after reconnect. A later
  renderer cannot change an approved snapshot; a modified snapshot is refused.
- Account data export includes the exact SVG snapshot as base64.
- Existing legacy task/image rows remain readable; migration reapplication is safe.
- The corpus is reproducible (240 unique IDs), spans match exact text, and all
  variants of a family stay in one split. Missing predictions do not look like a
  perfect result; an unrelated source does not count as a grounded pass.

## Browser and CLI checks

Used temporary SQLite databases, temporary image storage, fake text/image providers,
and disabled SMTP. The real application UI, WSGI routes and persistence were used.
No GPU, live Groq, paid image call or real WorkBuddy account was used.

| Check | Observed result |
|---|---|
| Brief without format, Instagram + Marketplace | Two independent image tasks; initial rejected copy shown with findings |
| Writer revision and re-review | Safe facts-only revision, Pass, still pending human approval |
| Image direction | Defaults to the Writer VISUAL block; Instagram default portrait |
| Visual before copy approval | Waiting for copy approval; no final export controls |
| Explicit copy and visual approval | Separate states and decisions; final visual export enabled |
| Final browser rasterization | HTTP 200 SVG → image/png, 1024×1280, 78,565 bytes; PNG signature 137 80 78 71 13 10 26 10 |
| Edit approved copy | v2, pending human copy approval; old composition stale; old export HTTP 409; export buttons absent |
| Planner List | Fixed missing `listView`; approved/unscheduled tasks open again |
| Mobile navigation | Menu opens, navigation closes it, task is keyboard accessible, menu hit target is unobstructed |
| Eight viewport widths | 320, 360, 390, 768, 1024, 1280, 1440, 1920: document scroll width never exceeded viewport width |
| New visual-region text/control contrast | Ten sampled visible elements: 7.44:1–14.61:1, above 4.5:1; not a whole-app accessibility audit |
| Real CLI subprocess | Login → projects → images → compose-visual → same-ID retry → logout; status stayed pending_copy_approval |

The CLI smoke used a temporary session file and dummy test credentials. A first
capture hit Windows stdout encoding mismatch; invoking Python with `-X utf8`
resolved the capture without changing CLI/server production rules.

[Mobile UI capture](./visual-workflow-mobile.png) and
[composed fixture PNG](./freshglow-composed-fixture.png) are **test fixtures**.
The plain base image is generated by a fake service, not by live AI inference. They
prove copy placement/export and controls, not product photography quality.
The integration browser did not expose an OS download event reliably; PNG validity
was verified from the actual browser canvas Blob bytes, not an assumed saved file.

JavaScript syntax and the calendar/list/diff probe passed using the existing
VS Code Node runtime v24.22.1 with `ELECTRON_RUN_AS_NODE=1`; no Node/package install.
Python compile checks passed. `git diff --check` reported no whitespace errors.
The Dockerfile was updated to include the new module/reference data; a Docker image
was not built, and GitHub Actions was not run remotely in this session.

## Hallmark / antislop delivery checks

Scope for the delivered UI change is the brief channel disclosure, image studio,
approval states, Planner List fix and mobile navigation behavior. The brand,
palette, typography, navigation destinations and existing content workflow remain.

- PASS — New controls have real actions; browser checks exercised composition,
  approvals, rasterization and editing, and the CLI retry stayed unapproved.
- PASS — New visual region handles empty/loading/error/saved/stale/approved states;
  provider errors have fake-service coverage, and copy overflow produces an error.
- PASS — Native inspection checkbox, keyboard activation, focus styling and 44px
  action targets are present; measured new-region contrast and viewport checks above.
- PASS — No new product facts, counters, testimonials, logos or publication claims
  were invented. Dataset and screenshot materials are explicitly marked synthetic.

**Whole-app Hallmark lint is not passed.** The final static scan exits 1:
346 FAIL, 272 REFLEX, 40 WARN. [Full findings](./hallmark-legacy-check-2026-11-02.txt).
Many findings concern the existing hard-coded CSS values, label styles, old contrast
and global stamp conventions. This is not a clean whole-app design score. A broad
CSS rewrite was outside this focused change. The Hallmark render tier could not run
because puppeteer-core is absent; direct browser/CDP checks above are recorded
separately, not presented as a Hallmark render pass.

Browser console also showed pre-existing CSP violations from inline styles on the
login form. No CSP relaxation was introduced. Full accessibility, full responsive
coverage across all old screens and a clean whole-app console are not claimed.

## Limits before calling this demo production-ready

1. Live text/image quality and provider availability were not reverified. Check one
   FreshGlow run on the actual configured services before demo day.
2. No OCR/vision verification of the base image, product-photo reference upload,
   generated-video rendering, or external publishing integration.
3. The 240 labels are author-proposed synthetic cases, not adjudicated legal ground
   truth. No live-model benchmark or accuracy percentage is reported.
4. Official Indonesian references are a reference map, not a complete regulation
   registry or automatic legal assessment. Semantic claim entailment, authenticity
   of product evidence/certificates and data-protection obligations need review.
5. Explicit approvals authenticate the current account/session; the server cannot
   distinguish a person from automation that holds the same session credentials.
6. Raw base-image previews remain accessible to the owner for inspection. The
   final-export gate is not DRM and does not technically control off-app publishing.

See the [demo guide](../docs/CREATOR_AGENT_DEMO_2026-11-02.md),
[dataset datacard](../evaluation/DATACARD.md), and
[official reference map](../governance/references.json).
