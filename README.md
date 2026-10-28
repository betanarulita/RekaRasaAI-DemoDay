# RekaRasa.ai — Demo Day

An independent creator workspace for briefs, product sources, AI plans and drafts, evidence-based review, human approval, and a persistent audit trail. This project was built in `RekaRasaAI-DemoDay`; it does not import or depend on the separate local RekaRasa project.

## Implementation log

- Foundation: isolated Python WSGI application, SQLite schema migrations, account sessions, per-user ownership checks, and demo rule registry.
- Core workflow: separate Planner, Writer, and Reviewer contracts; confirmed plans; source-checked drafts; bounded remediation; immutable versions; review findings; human approval; and audit events.
- Product UI: connected Home, New Chat, Planner list/calendar, Projects, Riwayat, Settings, and workbench flows. Browser smoke testing found and fixed an invalid CSS line-break issue; mobile width now fits the viewport.
- Verification: see the latest unit-test and provider smoke-test results below.
- Deployment: Docker and Render configuration are prepared. No Render account/repository authorization is available in this environment, so there is no public deployment URL yet.

## Latest provider migration

- Default development provider is Groq at `https://api.groq.com/openai/v1`, using model `openai/gpt-oss-20b`.
- `.env` loads at startup without overwriting process environment variables; the existing local `.env` is ignored by Git and was left untouched.
- Groq strict JSON Schema is sent for all three roles; the app validates output locally and enforces constraints Groq does not receive.
- Image providers now include OpenAI Images (default) and local ComfyUI. ComfyUI uses the standard `/prompt`, `/history/{prompt_id}`, and `/view` routes with a core-node SD 1.5 workflow. Local ComfyUI was not reachable during this session, so only fake-service coverage is verified.
- Current verification: `python -m py_compile app.py test_app.py` passed and `python -m unittest -q test_app` passed (35 tests). Tests use fake model/image services and do not verify live Groq or ComfyUI connectivity.

## What works

- Account registration and sign-in, salted PBKDF2 password hashes, expiring HTTP-only sessions, SameSite cookies, and CSRF checks on mutations.
- Per-account projects, Markdown/plain-text source material, Planner conversations, tasks, versions, reviews, findings, approvals, token usage, and audit events stored in SQLite.
- Server-side Groq Chat Completions calls using `openai/gpt-oss-20b` and strict JSON Schema contracts for Planner, Writer, and Reviewer. The server validates every response against the local contract before use. Content Studio keeps OpenAI Images as its default and can instead send a generated SD 1.5 workflow to local ComfyUI; resulting PNGs and task metadata persist in the configured image folder/database.
- A plan must be confirmed before tasks can generate drafts. Initial generation reviews every version; revisions are user-triggered and each creates a new immutable version.
- Demo review rules are versioned in the database. Unknown rule/source references cannot justify approval; claim findings that pass without source evidence are downgraded to `Needs Evidence`; a deterministic demo guard rejects disease-cure claims.
- A maximum of three remediation attempts per task. The first Writer revision after rejection counts as attempt 1. At attempt 3, unresolved findings move to human escalation.
- Human approval requires a passing review of the latest version. Editing creates a fresh pending version and clears the previous approval. Manual copy is enabled only after approval.
- Planner list and calendar views; production deadlines and planned publication times are separate fields. No publishing integration is configured and the app never reports a publication.
- Plain text and Markdown file upload, capped at 250 KB. PDF extraction is not implemented.
- A natural-language brief can reach Planner without output preferences. Planner may propose up to six deliverables (including posters/static ads, hero-image direction, social content, short-form video, marketplace listings, bundles, and custom formats), each with a short selection reason. Preferences remain optional guidance; existing TikTok and marketplace tasks remain supported. Users can edit title, format, platform, angle, and goal before confirmation.
- Approved text can be copied or downloaded as a TXT file. Content Studio can generate and persist a separate PNG visual per task through OpenAI Images or configured local ComfyUI. External publishing, scheduling, and video generation are not implemented.

## Local development

Requirements: Python 3.13+ and a modern browser. The application uses a small standard-library `.env` loader, so no dotenv package is required. `waitress` is used by the production Docker image.

1. Copy `.env.example` to `.env` only if you do not already have a local `.env`; the app reads it at startup and never replaces variables already set in the process environment.
2. Set `GROQ_API_KEY` for live text generation. For OpenAI image generation, set `OPENAI_API_KEY`. For local ComfyUI, set `IMAGE_PROVIDER=comfyui`, `COMFYUI_URL` (default `http://127.0.0.1:8188`), and `COMFYUI_CHECKPOINT` to the exact installed checkpoint filename. The local ComfyUI server must be reachable from the backend process.
3. Start with `python app.py` from this directory.
4. Open `http://127.0.0.1:8000`, create an account, and start in the seeded **Demo · Jahe Rasa** project.

The app creates `data/rekarasa.sqlite3`, stores image files in `data/generated-images`, and applies numbered SQL migrations from `migrations/` plus the versioned demo rule registry at startup. Migration versions are recorded in `schema_migrations`. To reset a local demo, stop the server and remove that local `data` directory; this deletes the local demo data. Do not use that reset on a deployment without first exporting the database.

## Tests and checks

Run `python -m unittest -v test_app` and `python -m py_compile app.py test_app.py`. The tests cover account isolation, CSRF, source and rule references, the cure-claim rule, missing evidence, bounded remediation, human approval, edit-after-approval, provider-unavailable behavior, schemas, persisted versions/audit events, preservation of existing task rows during migration, and two-output generation/review/approval.

The dependency-free client is `static/app.js` and does not require a Node build. Automated image tests mock the provider and make no paid API calls. Browser smoke checked Planner-to-workbench navigation, the brief-filled prompt, missing-key error/loading recovery, and the generated-image preview state. The real provider smoke failed as recorded above.

## Environment variables

| Name | Purpose | Default |
|---|---|---|
| `APP_ENV` | Set to `production` to add the Secure cookie attribute | `development` |
| `HOST` | Bind address | `127.0.0.1` |
| `PORT` | HTTP port | `8000` |
| `DATABASE_PATH` | SQLite path; use persistent mounted storage when hosted | `./data/rekarasa.sqlite3` |
| `LLM_PROVIDER` | Provider selector (currently Groq) | `groq` |
| `GROQ_API_KEY` | Server-only Groq API credential | unset; agent calls fail clearly |
| `MODEL` | Groq text model ID | `openai/gpt-oss-20b` |
| `IMAGE_PROVIDER` | Image provider (`openai` or `comfyui`) | `openai` |
| `OPENAI_API_KEY` | Server-only OpenAI Images credential | unset; image action reports setup instructions |
| `IMAGE_MODEL` | OpenAI image generation model | `gpt-image-2.5-sunburst` |
| `COMFYUI_URL` | Local ComfyUI server base URL | `http://127.0.0.1:8188` |
| `COMFYUI_CHECKPOINT` | Installed SD 1.5 checkpoint filename used by ComfyUI | unset; required when provider is `comfyui` |
| `COMFYUI_TIMEOUT` | Maximum time to wait for ComfyUI generation (seconds, capped at 900) | `300` |
| `IMAGE_STORAGE_PATH` | Generated PNG storage folder; use durable storage when hosted | `./data/generated-images` beside SQLite database |
| Groq API base URL | OpenAI-compatible Chat Completions endpoint | `https://api.groq.com/openai/v1` |

Groq documents `openai/gpt-oss-20b` as supporting strict JSON Schema outputs. All fields in the strict schemas are required and nested objects disallow extra fields. Local-only array bounds are removed from the outbound provider schema and still checked by application validation. Provider errors, invalid JSON, and schema-invalid responses fail the agent run rather than being accepted as successful output. See [Groq Structured Outputs](https://console.groq.com/docs/structured-outputs) and [OpenAI compatibility](https://console.groq.com/docs/openai).

Each account is private within the database. The seeded demo project is created on registration for each account; no shared privileged login is embedded in the app.

## Deployment preparation

`Dockerfile` and `render.yaml` describe a Render web service in Singapore with a persistent 1 GB disk mounted at `/var/data`. SQLite is appropriate here only for this single-service demo deployment; do not scale the service to multiple instances. The blueprint expects a Render account, a valid Groq key, and a paid persistent disk.

1. Push this new directory as its own repository; it has no dependency on the old project.
2. In Render, create a Blueprint from that repository and inspect the proposed service and disk before applying it.
3. Add a valid `GROQ_API_KEY` as a secret in the Render dashboard. Keep it out of Git and client assets.
4. Deploy, then verify `/api/health`, sign-in, source persistence after restart, and one full plan → confirm → generate → review workflow.
5. Back up `/var/data/rekarasa.sqlite3` before destructive maintenance. To recover, restore the database to the persistent disk and redeploy the same image.

No hosting account is bundled with this project. Live inference should be verified using the server-side Groq key before demo day. A deploy is not complete until Render returns a public URL and the deployed workflow has been verified.

## Review boundaries

The `DEMO-*` rules are sample product policies, not legal requirements, legal advice, a halal certification assessment, or a complete advertising-compliance engine. A Reviewer model result is only one part of the process: code validates schema, ownership, rule IDs and source IDs, evidence requirements, approval transitions, and attempt limits. Uncertain findings should remain `Needs Evidence` or go to a human.

## Known limits

- PDF text extraction, email verification, password reset, external identity providers, multi-seat collaboration, background queues, scheduled publishing, and platform publishing are not implemented.
- SQLite and the embedded server target one low-volume demo instance. Use managed Postgres and a production-grade job/server architecture before multi-instance or high-traffic use.
- Model calls can fail from invalid credentials, provider limits, timeouts, malformed data, or unavailable network; the UI reports the failure and preserves a retry path where possible.
- Estimated cost is not shown because no model pricing table is bundled. Input and output token totals are recorded when returned by Groq.
