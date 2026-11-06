# Audit: RekaRasa Image Bridge

## Scope

Read-only inspection of `C:/Users/Beta/WorkBuddy AI/2026-11-04-16-39-26/rekarasa-image-bridge.zip`, compared with current RekaRasa code. The ZIP contains nine entries, including the agent definition, plugin manifest, scripts, references, avatar, and README. No scripts, provider calls, registration, tests, or package mutations were run. Existing marketplace installation was not verified.

## Findings

### High: edit fallback cannot execute

In `agnes_adapter.py`, `edit_image()` expects `_send()` to raise HTTPError for 404/405 so it can try the alternate request format. `_send()` catches HTTPError and calls `die()`, which exits through SystemExit instead. A missing edit endpoint terminates the script; the documented fallback is unreachable. Repair exception propagation before any edit canary.

### High: successful JSON is not proof of image generation or reference use

`_send()` returns any decoded JSON, including an empty object for an empty response. No image URL/base64 payload is validated, no output image is persisted or bound to a RekaRasa task, and successful HTTP does not demonstrate the reference was honored. Keep edit mode disabled until its model-specific contract and output behavior have been verified. Do not automatically switch edit requests to prompt-only generation.

### High: project integration is missing

Direct Agnes generation returns JSON to stdout. The agent instruction to save PNGs and list them through RekaRasa does not implement authenticated asset ingestion. A locally generated file does not automatically become a generated_images row, a composition, or a human-approved artifact. Add a deliberate backend provider integration using the existing task ownership, asset, version, audit, composition, and approval lifecycle.

### Medium: backend constraints are stale

The current backend supports catalog/photo uploads through POST /api/attachments, and reference editing through POST /api/generate-image with mode=edit, asset_id and mask via ComfyUI. A probe with an invalid task or against an older process cannot establish that valid edit parameters are unsupported. The current backend also supports the landscape ratio. Update the package against the actual source and running version; do not add a duplicate upload endpoint or require users to upload materials twice.

### Medium: Excel-to-Markdown can corrupt content structure

`to_markdown_table()` joins raw values without escaping vertical bars or normalizing multiline cells. A fact containing a pipe becomes an additional column; a multiline fact breaks rows. The XLSX reader assumes sheet1.xml rather than resolving the workbook's first selected sheet, and does not provide an explicit formula policy. It has no compressed/uncompressed size, cell-count, or row-count bounds. Keep the application's existing validated catalog import as the primary ingestion path and use a hardened Markdown converter only as an optional export/adapter.

### Medium: documentation overstates readiness and fallback availability

The README still contains TODO placeholders. References claim pricing, latency, rankings and native ImageGen credit ranges without primary-source links. The provider routing is prose rather than implemented fallback code. WorkBuddy-side ImageGen availability and credit must not be advertised as a free website API. The adapter reads process environment variables; it does not itself load .env despite the skill setup instructions implying that editing .env is sufficient.

## Official evidence

Agnes overview: https://agnes-ai.com/en/docs/overview documents image generation/editing, OpenAI-style API compatibility, the API base URL, and Bearer-key authentication. This overview alone does not validate the script's guessed edit body, model-specific multipart contract, current free quota, or production readiness.

## Recommended integration sequence

1. Preserve existing Project uploads, catalog grouping and exact image_filename matching.
2. Correct adapter error propagation and bounded response validation; explicitly configure a documented edit method instead of guessing or silently dropping references.
3. Verify official model-specific edit documentation and local account quota; store keys locally.
4. With explicit generation authorization, run a distinctive-reference canary and inspect the result. Treat that as one compatibility check, not a guarantee of product fidelity across arbitrary inputs.
5. Integrate the provider behind the current RekaRasa image interface, with provenance and persisted image/task binding.
6. Run the current composition and separate human approval flow; preserve original-photo composition when edit capability is unavailable, without presenting it as AI editing.

Decision: retain as a prototype; do not enable as the default image provider yet.
