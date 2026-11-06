# RekaRasa.ai — Demo Day Architecture Brief

**Tanggal:** 30 Oktober 2026
**Target:** AI CAN DO IT — Tencent Cloud Hackathon Indonesia 2026, Challenge C
**Status:** Demo-ready, all free-tier stack

---

## System Architecture (No Overlap)

```
┌─────────────────────────────────────────────────────────────────┐
│  HUMAN USER                                                      │
│  "Buat konten untuk FreshGlow skincare — marketplace + video"   │
└──────────────┬──────────────────────────────────────────────────┘
               │ natural language
               ▼
┌─────────────────────────────────────────────────────────────────┐
│  WorkBuddy AI (Orchestrator Layer)                               │
│  Skill: rekarasa-creator                                         │
│                                                                  │
│  Role: TRANSLATE intent → API calls. Nothing more.              │
│  - Does NOT write content                                        │
│  - Does NOT review content                                       │
│  - Does NOT approve content                                      │
│  - Asks explicit permission before confirm and before approve   │
│                                                                  │
│  Communication: HTTP (cookie + CSRF), same as browser            │
└──────────────┬──────────────────────────────────────────────────┘
               │ HTTP: POST /api/plan, /api/generate, /api/approve
               ▼
┌─────────────────────────────────────────────────────────────────┐
│  RekaRasa.ai API Server (app.py — Python stdlib + waitress)     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  AUTH: PBKDF2-SHA256, CSRF, HttpOnly SameSite cookie     │   │
│  │  RATE LIMIT: 8/min/route (in-process, acceptable beta)   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  PLANNER AGENT (Groq: gpt-oss-20b, free tier)            │   │
│  │  - Receives: brief, sources, audience, tone              │   │
│  │  - Holiday awareness: Indonesian national + religious    │   │
│  │    holidays auto-injected (within 30 days)               │   │
│  │  - Returns: 1-6 tasks with title, format, platform,      │   │
│  │    angle, goal, selection_reason                         │   │
│  │  - Grounded facts only (no invention)                    │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │  WRITER AGENT (Groq: gpt-oss-20b, free tier)             │   │
│  │  - Receives: task, sources, prior review feedback        │   │
│  │  - Returns: content draft per format                     │   │
│  │  - Retry with exponential backoff (max 4 attempts)       │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │  REVIEWER AGENT (Groq: gpt-oss-20b, free tier)           │   │
│  │  - Receives: draft, rules, sources                       │   │
│  │  - Returns: findings per rule + verdict                   │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │  TRUST BOUNDARY: save_review() — CODE, not LLM           │   │
│  │  7 deterministic guards:                                  │   │
│  │    1. DEMO-CLAIM-001: no cure/health claims              │   │
│  │    2. DEMO-HALAL-001: no halal claims without source     │   │
│  │    3. Rule coverage check                                 │   │
│  │    4. Substance check (draft must be real content)        │   │
│  │    5. Block check (no blocked patterns)                   │   │
│  │    6. Invalid reference check                             │   │
│  │    7. Evidence requirement check                          │   │
│  │  Verdict: Pass / Fail / Needs Evidence                    │   │
│  │  Status: approved_pending_human / needs_revision /        │   │
│  │          escalated                                        │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │  HUMAN GATE: POST /api/approve                            │   │
│  │  - Rejects if verdict != "Pass"                           │   │
│  │  - Rejects if status != "approved_pending_human"          │   │
│  │  - Sets human_approved=1 in DB                            │   │
│  │  - Records in audit_events table                          │   │
│  │  - WorkBuddy can call this ONLY after explicit human OK   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  IMAGE GENERATION (separate from content pipeline)        │   │
│  │  Provider: Pollinations.ai (Flux model)                   │   │
│  │  - FREE, no API key, no registration required             │   │
│  │  - Quality: photorealistic (vs SD 1.5 which was unusable) │   │
│  │  - LIMIT: ~1 image / 45s per IP + occasional HTTP 503     │   │
│  │    -> pre-generate demo images, app retries once          │   │
│  │  - Anonymous output carries a small watermark             │   │
│  │  - Prompt: sanitized (8 injection patterns filtered)      │   │
│  │  - NOT reviewed by Reviewer (visual asset, not content)   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  SQLite (WAL mode, 7 migrations, FK=ON)                         │
│  Audit trail: agent_runs, agent_messages, audit_events          │
│  Privacy: account deletion, data export, prompt sanitization    │
└──────────────────────────────────────────────────────────────────┘
```

## Responsibility Matrix (No Overlap)

| Capability | Planner | Writer | Reviewer | save_review() | WorkBuddy | Human |
|---|---|---|---|---|---|---|
| Write content | | ✅ | | | | |
| Review content | | | ✅ | | | |
| Enforce rules (code) | | | | ✅ | | |
| Approve publication | | | | | | ✅ |
| Orchestrate flow | | | | | ✅ | |
| Generate images | | | | | | (via API) |
| Holiday awareness | ✅ (context) | | | | | |

## Free-Tier Stack (Zero Cost)

| Component | Service | Cost | Why |
|---|---|---|---|
| LLM (Planner/Writer/Reviewer) | Groq API (gpt-oss-20b) | Free tier | Fast inference, structured output, generous free quota |
| Image generation | Pollinations.ai (Flux) | Free, no key | Good quality; ~1 img/45s limit — pre-generate for demo |
| Hosting | Render (starter) | Free/$7 mo | Docker, health checks, persistent disk |
| Database | SQLite (WAL mode) | Free | File-based, no server needed, adequate for demo |
| Email | Local Mailbox (staging) or SMTP (production) | Free | Password reset, email verification |
| Error tracking | Sentry (optional) | Free tier | 5K events/month free |
| CI/CD | GitHub Actions | Free | 2000 min/month free for public repos |
| Backup | scripts/backup_db.py | Free | SQLite online backup API |

**Total monthly cost for Demo Day: $0** (all free tiers)

### Image Provider Decision (verified 2026-10-31)

| Option | Quality | Reliability | Setup | Verdict |
|---|---|---|---|---|
| ComfyUI + SD 1.5 (old default) | ❌ Unusable at 1024px — 512px-native model, produces mush | High (local) | Already installed | **Rejected — root cause of "gambar acak-acakan"** |
| Pollinations + Flux (new default) | ✅ Coherent, photorealistic | ⚠️ ~1 img/45s, occasional 503 | None | **Chosen — best free/no-setup trade-off** |
| ComfyUI + SDXL (1024-native) | ✅ Good | High (local) | ~6.5GB download | Best if you have time before demo |
| ComfyUI + FLUX.1-schnell fp8 | ✅✅ Best | Medium (slow on 6GB VRAM) | ~7GB download | Optional upgrade |

**Root cause of the original bad images:** the checkpoint was `v1-5-pruned-emaonly.safetensors` — Stable Diffusion 1.5, a 2022 model that is 512×512-native. Asking it for 1024px product photography puts it far outside its training distribution, so it hallucinates. Swapping the model (not the prompt) is the actual fix.

**Demo Day recommendation:** pre-generate 3–4 images the night before and keep them in `evidence/`. Live generation is then a bonus, not a dependency.

## What Changed for Demo Day

### 1. Image Generation Fixed
- **Before:** ComfyUI + SD 1.5 checkpoint → poor, random, unusable images
- **After:** Pollinations.ai + Flux model → photorealistic, professional quality
- **Cost:** Free (no API key, no registration, no local GPU needed)
- **Code:** `call_pollinations_provider()` added as default provider

### 2. Indonesian Holiday Awareness Added
- **Feature:** Planner auto-receives upcoming Indonesian holidays (national + religious)
- **Dataset:** Static list covering 2025-2027 (Idul Fitri, Independence Day, Natal, etc.)
- **Injection:** `holiday_context_for_planner()` appended to Planner system prompt
- **Window:** 30 days from current date
- **API:** `GET /api/holidays` (public endpoint)
- **CLI:** `rekarasa_cli.py holidays` subcommand

### 3. Architecture Clarified
- WorkBuddy = orchestrator (not agent keempat)
- Three agents (Planner/Writer/Reviewer) run inside server, enforced by code
- Trust boundary (`save_review()`) is deterministic, not LLM-based
- Human gate rejects unreviewed or unpassed drafts
- Image generation is separate from content pipeline (not reviewed)

## Test Coverage

- 88 tests pass (66 original + 7 Fase 1 + 10 Fase 2 + 5 Demo Day)
- `py_compile` OK for app.py, test_app.py, backup_db.py, rekarasa_cli.py
- `node --check` OK for app.js, probe_frontend.js

## Demo Flow

```
WorkBuddy: "Halo! Saya bisa bantu buat konten produk. Apa produknya?"

User: "FreshGlow skincare, mau untuk marketplace dan video pendek"

WorkBuddy:
  1. holidays → "Hari besar terdekat: Hari Raya Natal (25 Des, 56 hari lagi)"
  2. rules → menampilkan 4 aturan demo
  3. plan → Planner menghasilkan 2 tasks (marketplace + video pendek)
     - Planner tahu tentang Natal → bisa suggest angle festive
  4. "Plan ini sudah dibuat. Lanjutkan?" → TUNGGU JAWAB USER

User: "Ya, lanjut"

WorkBuddy:
  5. generate → Writer draft + Reviewer verdict
  6. Laporkan hasil apa adanya (Pass/Fail/Needs Evidence)

  (jika Pass)
  7. "Draft lolos review. Setujui publikasi?" → TUNGGU JAWAB USER

User: "Setuju"

WorkBuddy:
  8. approve → human_approved=1
  9. audit → menampilkan jejak lengkap

  (jika user mau gambar)
  10. generate-image → Pollinations/Flux → gambar berkualitas tinggi
```
