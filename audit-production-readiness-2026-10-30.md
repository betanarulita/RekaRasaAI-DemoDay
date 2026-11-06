# Full Production Readiness Audit — RekaRasa.ai

**Tanggal audit:** 30 Oktober 2026  
**Auditor:** Senior Project Manager (superstar-engineer methodology)  
**Target:** `D:\RekaRasaAI-DemoDay` — RekaRasa.ai Creator Agent  
**Mode:** Read-only. Tidak ada kode yang dimodifikasi.  
**Metodologi:** Staff-level engineering analysis (Rule of Leverage, Boring Technology First, Assume Systemic Failure, Mechanical Sympathy)

---

## Deliverable 1: Executive Summary

RekaRasa.ai adalah aplikasi creator workspace yang dibangun untuk **AI CAN DO IT — Tencent Cloud Hackathon Indonesia 2026** (Challenge C). Arsitektur inti mengikuti pola **three-agent propose-decide-approve**: Planner → Writer → Reviewer, dengan code-side enforcement (`save_review()`) sebagai trust boundary, dan human approval gate sebagai keputusan akhir.

**Komitmen engineering yang terbukti:**

- 1 file Python (`app.py`, ~1567 baris) menggunakan **hanya stdlib** — tidak ada framework web, tidak ada ORM, tidak ada dotenv package. Satu-satunya dependency eksternal adalah `waitress` (production WSGI server).
- 66 test lulus (dari 66), mencakup account isolation, CSRF, cure-claim/halal guards, evidence requirements, bounded remediation, approval gate, provider failure mapping, migration idempotency, privacy disclosure accuracy, dan end-to-end orchestrated flow.
- Password hashing: PBKDF2-SHA256 dengan 310,000 iterasi dan 16-byte random salt — di atas standar OWASP 2023.
- CSP header ketat (`default-src 'self'; script-src 'self'; frame-ancestors 'none'`) di setiap response.
- Privacy disclosure yang **dapat diaudit** dan **diuji oleh test** (`test_privacy_disclosure_matches_what_the_model_receives`).

**Kondisi production readiness:**

Aplikasi ini **siap untuk demo day** dengan batasan yang sudah dideklarasikan secara jujur. Namun **belum siap untuk production multi-user/high-traffic** karena beberapa faktor struktural yang tidak bisa di-patch tanpa perubahan arsitektur (SQLite single-instance, no email verification, in-process rate limiting, no backup automation).

**Skor keseluruhan:** 6.8 / 10  
**Rekomendasi:** **GO untuk Demo Day, NO-GO untuk Production Scale-up** tanpa remediasi prioritas tinggi.

---

## Deliverable 2: Skor per-Area

| # | Area Audit | Skor | Status |
|---|---|---|---|
| 1 | Arsitektur | 7.5/10 | Solid untuk demo; monolit tunggal yang tepat untuk skala ini |
| 2 | Auth & Security | 7.0/10 | Fondasi kuat (PBKDF2, CSRF, CSP, session management); celah pada API key exposure |
| 3 | Data Privacy & Compliance | 6.5/10 | Disclosure jujur dan testable; belum ada UU PDP compliance, no account deletion |
| 4 | AI Agent Reliability | 8.0/10 | Schema validation, retry+backoff, deterministic guards, provider error mapping |
| 5 | DB & Infrastructure | 6.0/10 | Migration system baik; SQLite limit, no backup, disk hanya 1GB |
| 6 | Observability & Logging | 5.5/10 | Audit trail baik; tidak ada structured logging, metrics, atau alerting |
| 7 | Testing | 7.5/10 | 66 test berkualitas tinggi; tidak ada e2e/browser, no CI automation |
| 8 | Deployment & CI/CD | 5.5/10 | Dockerfile + render.yaml minimal; no CI pipeline, no health-gated deploy |
| 9 | Product Readiness | 7.0/10 | UX flow lengkap; no accessibility audit, no i18n, limited error UX |

---

## Deliverable 3: Critical Findings (P0 — Wajib sebelum demo/day production)

### C-1: Live API Key terekspos di file `.env` lokal

**Lokasi:** `D:\RekaRasaAI-DemoDay\.env` baris 8  
**Detail:** File `.env` berisi `GROQ_API_KEY=gsk_uPHv4ymzW2s9I...` — sebuah live Groq API key. File `.env` **tidak di-track di git** (sudah benar di `.gitignore`) dan **tidak pernah masuk git history** (terverifikasi). Namun key ini ada di disk lokal dan bisa dibaca oleh siapa saja yang memiliki akses filesystem.

**Risiko:** Jika repo di-push ke remote publik di masa depan dan `.env` tidak sengaja di-stage, key akan bocor. Jika mesin ini di-share, key bisa diekstrak.

**Rekomendasi:** Rotasi key ini sebelum demo day. Pastikan key production hanya diset melalui Render dashboard secret, bukan file `.env`.

### C-2: SQLite sebagai database production tanpa backup strategy

**Lokasi:** `render.yaml` baris 32-35, `Dockerfile` baris 2  
**Detail:** Deployment Render menggunakan SQLite di disk 1GB (`/var/data/rekarasa.sqlite3`). Tidak ada:
- Automated backup
- Point-in-time recovery
- Database export/snapshot scheduling
- Disk usage monitoring (1GB bisa habis dengan generated images)

**Risiko:** Disk penuh → semua write gagal. Database corruption → kehilangan total data pengguna. Tidak ada recovery path selain manual restore.

**Rekomendasi:** Tambahkan cron job atau Render disk snapshot. Untuk production jangka panjang, migrasi ke managed PostgreSQL (sudah dicatat di README sebagai known limit).

### C-3: Tidak ada email verification atau SMTP

**Lokasi:** `app.py` baris 1106-1130, README baris 162  
**Detail:** Registrasi tidak memverifikasi email. Siapa saja bisa mendaftar dengan email palsu. Password reset token dicetak ke console server (bukan dikirim via email), yang tidak bisa diandalkan di production Render (console mungkin tidak selalu terlihat).

**Risiko:** Account abuse, tidak ada recovery path yang reliable untuk pengguna nyata, token reset bisa terlihat di log Render dashboard.

**Rekomendasi:** Untuk demo day, ini acceptable (dideklarasikan jujur). Untuk production, tambahkan SMTP integration (SendGrid/Resend) untuk email verification dan password reset.

---

## Deliverable 4: High Findings (P1 — Sebelum production scale-up)

### H-1: Rate limiting in-process, tidak shared antar instance

**Lokasi:** `app.py` baris 259-276, 279-299  
**Detail:** `RATE_HITS` dan `LOGIN_HITS` adalah `defaultdict(deque)` di memory proses. Dokumentasi code sendiri menyatakan: *"correct for one instance, deliberately not shared"*. Jika deploy ke lebih dari 1 instance, rate limit tidak efektif.

**Risiko:** Brute force atau abuse dapat melewati throttle pada multi-instance deployment.

**Rekomendasi:** Pindahkan ke Redis atau database-backed counter jika scaling diperlukan.

### H-2: No CORS headers — API tidak bisa diakses dari domain berbeda

**Lokasi:** `app.py` baris 218-222  
**Detail:** `json_response()` tidak menyetel header `Access-Control-Allow-Origin`. Aplikasi melayani frontend dari same-origin (`static/`), jadi ini by-design. Namun jika frontend dipisah ke CDN terpisah, API akan blocking cross-origin requests.

**Risiko:** Arsitektur terkunci ke single-origin. Bukan masalah untuk demo, tapi membatasi evolution path.

**Rekomendasi:** Tidak perlu diubah untuk demo day. Pertimbangkan jika frontend dipisah.

### H-3: Tidak ada structured logging dengan correlation ID

**Lokasi:** `app.py` baris 28, 434, 1153, 1530-1536  
**Detail:** Logging menggunakan `logging.getLogger("rekarasa")` dengan format `%(asctime)s %(levelname)s %(name)s %(message)s`. Tidak ada:
- Correlation/request ID per request
- Structured JSON logging
- Request method/path/user context in log entries
- Log aggregation setup (tidak ada Sentry, Datadog, dll)

**Risiko:** Saat debugging issue di production, tidak ada cara untuk menghubungkan sebuah request dengan log entries terkait. Stack trace tertangkap (`log.exception`) tapi tanpa context.

**Rekomendasi:** Tambahkan request ID middleware (UUID per request), structured JSON log format, dan integrasi error tracking (Sentry free tier cukup untuk demo).

### H-4: Generated images disimpan di disk filesystem, bukan object storage

**Lokasi:** `app.py` baris 65, 1219-1225  
**Detail:** `IMAGE_STORAGE_PATH` default ke `data/generated-images/`. Di Render, ini di disk yang sama dengan database (1GB total). Setiap PNG bisa sampai 15MB. ~66 gambar = disk penuh.

**Risiko:** Disk full → database write gagal → aplikasi crash. Tidak ada cleanup policy untuk gambar lama.

**Rekomendasi:** Untuk production, gunakan S3/Cloud Storage untuk images. Tambahkan cleanup atau retention policy.

### H-5: No CI/CD pipeline

**Lokasi:** Tidak ada `.github/workflows/`, tidak ada CI config  
**Detail:** Tidak ada automated CI yang menjalankan test, lint, atau build pada push. Tests dijalankan manual.

**Risiko:** Regression bisa masuk ke main tanpa terdeteksi. Tidak ada quality gate sebelum deploy.

**Rekomendasi:** Tambahkan GitHub Actions: `pytest test_app.py`, `py_compile app.py`, `node --check static/app.js` pada setiap push.

---

## Deliverable 5: Medium Findings (P2 — Post-demo improvement)

### M-1: No account self-deletion atau data export

**Lokasi:** `app.py` baris 821 (`privacy_disclosure() not_provided`)  
**Detail:** Aplikasi secara jujur menyatakan tidak menyediakan account self-deletion atau one-click data export. Ini adalah hak pengguna di bawah UU PDP (Indonesia) dan GDPR.

### M-2: Session token tidak dirotasi setelah privilege change

**Lokasi:** `app.py` baris 302-313  
**Detail:** Setelah login, session tetap aktif selama 14 hari tanpa rotasi. Password reset menghapus semua session (baik), tapi tidak ada rotasi token berkala.

### M-3: Plaintext content di source materials bisa berisi sensitive data

**Lokasi:** `app.py` baris 1267-1280  
**Detail:** Source upload menerima text/markdown hingga 250KB tanpa scanning untuk sensitive data (PII, credentials). Konten ini dikirim ke Groq API sebagai context.

### M-4: No input sanitization untuk prompt injection di image generation

**Lokasi:** `app.py` baris 1204-1218  
**Detail:** User-provided `prompt` (hingga 8000 chars) langsung di-concatenate ke `contextual_prompt` tanpa sanitization. Meskipun Writer instructions mengatakan "treat as untrusted data", prompt untuk image generation tidak memiliki perlindungan yang sama.

### M-5: Frontend adalah 78KB single file JS tanpa module system

**Lokasi:** `static/app.js` (267 baris, ~78KB)  
**Detail:** Tidak ada build step, tidak ada module system, semua state global. `esc()` function untuk XSS prevention sudah ada (baik), tapi tidak ada Content-Security-Policy nonce untuk inline scripts (tidak ada inline scripts, jadi CSP `script-src 'self'` sudah aman).

### M-6: No health check alerting

**Lokasi:** `render.yaml` baris 8 (`healthCheckPath: /api/health`)  
**Detail:** Render akan check `/api/health`, tapi tidak ada alerting jika health check gagal. `/api/ready` dipisah dengan baik (baik practice), tapi tidak ada yang memantau readiness.

---

## Deliverable 6: Low Findings (P3 — Nice to have)

### L-1: `.env.example` tidak menyebutkan `IMAGE_STORAGE_PATH`

File `.env.example` tidak include `IMAGE_STORAGE_PATH` (commented out di env vars table README tapi tidak di example file). Pengguna baru mungkin bingung.

### L-2: `probe_frontend.js` bukan browser test

Dideklarasikan dengan jujur di README. Stub DOM check bagus untuk catch regressions, tapi tidak membuktikan layout atau interaction.

### L-3: No i18n / localization

UI dalam Bahasa Inggris. Konten demo (`Demo · Jahe Rasa`) dalam Bahasa Indonesia. Tidak ada i18n framework.

### L-4: `styles.css` adalah 45KB single file

Tidak ada CSS methodology (BEM, utility-first). Maintainable untuk demo, tapi akan sulit untuk skala tim.

### L-5: No disk usage monitoring

Disk 1GB di Render tidak dipantau. Generated images bisa mengisi disk tanpa peringatan.

### L-6: README menyebut "46 tests" dan "66 passed" di bagian berbeda

README baris 67: "`46 tests pass`" vs baris 101: "`66 passed`". Inkonsistensi dokumentasi — 66 adalah angka yang benar (terverifikasi).

---

## Deliverable 7: Risk Heatmap

```
                Impact
          Low      Medium    High
       ┌──────────┬──────────┬──────────┐
  H    │          │  M-2     │  C-1     │   ← Probability: High
  i    │          │  M-3     │  C-2     │
  g    │          │          │  H-1     │
  h    ├──────────┼──────────┼──────────┤
       │  L-3     │  M-4     │  H-3     │   ← Probability: Medium
       │  L-4     │  M-5     │  H-4     │
       │  L-5     │          │          │
       ├──────────┼──────────┼──────────┤
  L    │  L-1     │  M-1     │  C-3     │   ← Probability: Low (demo only)
  o    │  L-2     │  M-6     │          │
  w    │  L-6     │          │          │
       └──────────┴──────────┴──────────┘
```

**Zona merah (mitigasi wajib):** C-1 (API key), C-2 (no backup), H-1 (rate limit)  
**Zona kuning (mitigasi sebelum scale):** H-3 (logging), H-4 (image storage), H-5 (CI/CD)  
**Zona hijau (acceptable untuk demo):** Semua L-level, sebagian M-level

---

## Deliverable 8: Prioritized Action Plan

### Sprint 0 — Sebelum Demo Day (Wajib, ~2-4 jam)

| # | Action | Area | Estimasi |
|---|---|---|---|
| 1 | Rotasi Groq API key; pastikan hanya di Render dashboard secret | C-1 | 30 menit |
| 2 | Perbaiki README: ganti "46 tests" → "66 tests" | L-6 | 5 menit |
| 3 | Verifikasi `/api/health` dan `/api/ready` setelah deploy | C-2 | 30 menit |
| 4 | Test full workflow di deployment Render (register → plan → generate → review → approve) | — | 1 jam |
| 5 | Setup Render disk snapshot (manual atau scheduled) | C-2 | 30 menit |

### Sprint 1 — Post-Demo, Pre-Production (P1, ~1-2 sprint)

| # | Action | Area | Estimasi |
|---|---|---|---|
| 6 | Tambahkan GitHub Actions CI (test + lint + compile check) | H-5 | 2 jam |
| 7 | Tambahkan request ID + structured JSON logging | H-3 | 4 jam |
| 8 | Integrasikan Sentry untuk error tracking | H-3 | 1 jam |
| 9 | Migrasi image storage ke S3/Cloud Storage | H-4 | 4 jam |
| 10 | Tambahkan SMTP untuk email verification + password reset | C-3 | 6 jam |

### Sprint 2 — Production Hardening (P2, ~2-3 sprint)

| # | Action | Area | Estimasi |
|---|---|---|---|
| 11 | Migrasi SQLite → PostgreSQL (jika multi-instance diperlukan) | C-2, H-1 | 1-2 hari |
| 12 | Implement Redis-backed rate limiting | H-1 | 4 jam |
| 13 | Tambahkan account self-deletion dan data export | M-1 | 4 jam |
| 14 | Sanitasi prompt injection di image generation | M-4 | 2 jam |
| 15 | Tambahkan disk usage monitoring + alerting | L-5, M-6 | 2 jam |

---

## Deliverable 9: Architecture Diagram Assessment

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER (Single Origin)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ index.html│  │ app.js   │  │ styles.css│  │  Logo.png│        │
│  │ (515 B)   │  │ (78 KB)  │  │ (45 KB)   │  │          │        │
│  └─────┬─────┘  └────┬─────┘  └──────────┘  └──────────┘        │
│        │              │                                           │
│        └──────┬───────┘                                           │
│               │ fetch() + CSRF header + SameSite cookie           │
└───────────────┼───────────────────────────────────────────────────┘
                │
                │ HTTPS (Same-Origin)
                │
┌───────────────┼───────────────────────────────────────────────────┐
│         WSGI APPLICATION (app.py — 1567 lines, stdlib only)       │
│               │                                                   │
│  ┌────────────▼────────────┐                                      │
│  │   application() router   │                                      │
│  │  17 API routes + static  │                                      │
│  └────────────┬────────────┘                                      │
│               │                                                   │
│  ┌────────────▼────────────────────────────────────────────────┐  │
│  │                  TRUST BOUNDARY                              │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐  │  │
│  │  │ Planner  │  │ Writer   │  │ Reviewer                  │  │  │
│  │  │ (Groq)   │  │ (Groq)   │  │ (Groq)                    │  │  │
│  │  │ JSON     │  │ JSON     │  │ JSON                      │  │  │
│  │  │ Schema   │  │ Schema   │  │ Schema                    │  │  │
│  │  │ strict   │  │ strict   │  │ strict                    │  │  │
│  │  └────┬─────┘  └────┬─────┘  └────────────┬─────────────┘  │  │
│  │       │             │                      │                 │  │
│  │       └─────────────┴──────────────────────┘                 │  │
│  │                      │                                       │  │
│  │       ┌──────────────▼──────────────────┐                    │  │
│  │       │    save_review() — CODE         │                    │  │
│  │       │    7 deterministic checks:      │                    │  │
│  │       │    1. rule_id in registry       │                    │  │
│  │       │    2. source_id in project      │                    │  │
│  │       │    3. factual pass → cite src   │                    │  │
│  │       │    4. uncovered rule = Needs E  │                    │  │
│  │       │    5. regex guard: cure/halal   │                    │  │
│  │       │    6. draft substance floor     │                    │  │
│  │       │    7. format block requirement  │                    │  │
│  │       └────────────────────────────────┘                    │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │ Auth &       │  │ Rate Limit   │  │ Image Provider       │    │
│  │ Session      │  │ (in-process) │  │ (OpenAI / ComfyUI)   │    │
│  │ PBKDF2-SHA256│  │ 8/min/route  │  │                      │    │
│  │ CSRF token   │  │ 8 login/5min │  │ PNG → disk           │    │
│  │ HttpOnly     │  │              │  │                      │    │
│  │ SameSite     │  │              │  │                      │    │
│  └──────────────┘  └──────────────┘  └──────────────────────┘    │
│               │                                                   │
│  ┌────────────▼──────────────────────────────────────────────┐   │
│  │              SQLite (WAL mode, FK=ON)                      │   │
│  │  6 migrations, versioned schema_migrations                 │   │
│  │  13 tables + password_resets + generated_images            │   │
│  │  Indexes: audit, sessions, reviews, runs, images, etc.     │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Production: waitress (4 threads, 65s channel timeout)            │
└───────────────────────────────────────────────────────────────────┘
                │                           │
                ▼                           ▼
    ┌───────────────────┐     ┌───────────────────────┐
    │ Groq API          │     │ OpenAI Images API     │
    │ gpt-oss-20b       │     │ gpt-image-2.5-sunburst│
    │ Strict JSON       │     │ PNG generation        │
    │ Schema            │     │                       │
    └───────────────────┘     └───────────────────────┘
```

**Penilaian arsitektur:**

| Prinsip | Penilaian |
|---|---|
| **Boring Technology** | Excellent: stdlib + SQLite + waitress. Tidak ada hype-driven dependency. |
| **Blast Radius** | Good: trust boundary antara model dan code. Jika Groq down, draft preserved, review retryable. |
| **State Management** | Good: state di SQLite, business logic stateless di functions. Session di DB hash. |
| **Observability** | Weak: audit_events table bagus untuk product audit, tapi logging untuk debugging minim. |
| **Mechanical Sympathy** | Good: WAL mode, indexes pada query paths yang benar, body size limits. |
| **Assume Systemic Failure** | Strong: retry+backoff, provider error mapping, draft preservation on failure, review_error recovery. |

---

## Deliverable 10: Go / No-Go Recommendation

### Verdict: **CONDITIONAL GO untuk Demo Day**

| Kondisi | Status |
|---|---|
| Aplikasi berfungsi end-to-end | **Lolos** — 66 test pass, verified live provider path |
| Security fundamentals | **Lolos** — PBKDF2, CSRF, CSP, session management, rate limiting |
| AI agent reliability | **Lolos** — schema validation, deterministic guards, bounded remediation |
| Privacy disclosure | **Lolos** — honest, testable, tidak mengklaim compliance yang tidak ada |
| Deployment readiness | **Conditional** — Dockerfile + render.yaml ada, tapi belum ada verified public deployment |
| Backup & recovery | **Gagal** — no automated backup, 1GB disk limit |
| Production monitoring | **Gagal** — no alerting, no error tracking, no structured logs |

### Syarat GO untuk Demo Day:

1. **Rotasi Groq API key** sebelum deploy (C-1)
2. **Setup Render disk snapshot** setelah first deploy (C-2)
3. **Verify full workflow** di deployment (register → plan → generate → review → approve)
4. **Fix README inconsistency** (L-6: "46 tests" → "66 tests")

### Syarat NO-GO untuk Production Scale-up:

Berikut faktor yang **harus** diselesaikan sebelum aplikasi melayani pengguna nyata dalam skala non-demo:

1. SQLite → PostgreSQL migration (atau setidaknya automated backup)
2. SMTP/email integration untuk password reset dan email verification
3. CI/CD pipeline dengan automated testing
4. Structured logging + error tracking (Sentry)
5. Image storage ke object storage (S3/Cloud Storage)
6. Account self-deletion dan data export (UU PDP compliance)

### Red Team Critique (single biggest risk)

**Race condition pada `/api/revise`:** Route ini memulai dengan `BEGIN IMMEDIATE`, membaca task state, lalu memanggil `llm_json()` (Writer) yang bisa memakan 55+ detik. Setelah Writer selesai, code melakukan `BEGIN IMMEDIATE` lagi dan re-read task state untuk memvalidasi remediation_count — **ini sudah benar dan defensive**. Namun selama 55 detik itu, SQLite WAL lock bisa memblok write lain ke task yang sama, dan jika dua request revise datang bersamaan untuk task berbeda, keduanya akan menunggu Writer call masing-masing tanpa koordinasi cross-task. Untuk demo single-user, ini tidak akan terjadi. Untuk multi-user concurrent, ini bisa menyebabkan timeout dan用户体验 buruk. Solusi: queue-based background processing (Redis + Celery, atau Render background worker).

---

## Lampiran A: Test Coverage Analysis

**66 test functions** dalam `test_app.py` (81KB), dikategorikan:

| Kategori | Jumlah | Coverage |
|---|---|---|
| Auth & Session | 8 | password hashing, dotenv, login throttle, password reset |
| Planner | 6 | schema validation, preference coverage, custom format, failure retry |
| Writer & Reviewer | 10 | cure-claim guard, halal guard, substance floor, block requirement, revision ratio |
| Workflow lifecycle | 12 | generate → review → approve, remediation limit, edit-after-approval, review-error retry |
| Provider failure | 5 | auth error, schema rejection, rate limit retry, unavailable, malformed |
| Image generation | 3 | ComfyUI workflow, PNG persistence, prompt context |
| Privacy & disclosure | 4 | disclosure accuracy, credential exclusion, provider matching |
| Migration | 3 | idempotency, legacy task preservation, schema versioning |
| End-to-end | 2 | orchestrated brief→review→approval, FreshGlow reject→revise→re-review |
| Calendar & dates | 3 | date separation, calendar view, audit persistence |
| Rate limiting & health | 4 | readiness, health independence, throttle, rate limit retry |
| Schema contracts | 2 | closed schemas, required fields |

**Gap yang teridentifikasi:**
- No browser/E2E testing (hanya stub-DOM probe)
- No load/performance testing
- No security penetration testing
- ComfyUI live path untested (hanya fake-service)
- No test untuk concurrent request handling

---

## Lampiran B: Dependency Audit

| Dependency | Version | Purpose | Risk |
|---|---|---|---|
| Python stdlib | 3.13 | Core (http, json, sqlite3, hashlib, hmac, secrets, uuid, wsgiref) | None — battle-tested |
| waitress | >=3.0,<4.0 | Production WSGI server | Low — established, well-maintained |
| Groq API | External | LLM inference (gpt-oss-20b) | Medium — provider availability, rate limits |
| OpenAI API | External | Image generation | Medium — provider availability, cost |
| ComfyUI | Optional/local | SD 1.5 image generation | High — untested live, local-only |

**Total external dependencies: 1 (waitress).** Ini adalah hasil yang sangat baik untuk blast radius management.

---

## Lampiran C: File Inventory

| File | Size | Lines | Purpose |
|---|---|---|---|
| `app.py` | 108 KB | 1,567 | Application server (all logic) |
| `test_app.py` | 82 KB | ~1,200 | 66 test functions |
| `static/app.js` | 78 KB | 267 | Frontend SPA |
| `static/styles.css` | 45 KB | 17 (minified) | Styles |
| `static/index.html` | 515 B | 15 | HTML shell |
| `Dockerfile` | 531 B | 11 | Container image |
| `render.yaml` | 375 B | 36 | Render blueprint |
| `requirements.txt` | 19 B | 1 | Single dependency |
| `README.md` | 13 KB | 167 | Documentation |
| `migrations/` | — | 6 files | SQL migrations 001-006 |
| `.env.example` | 501 B | 17 | Environment template |
| `.gitignore` | 375 B | 23 | Ignore rules |

---

*Audit selesai. Tidak ada kode yang dimodifikasi. Semua temuan bersifat read-only observation.*
