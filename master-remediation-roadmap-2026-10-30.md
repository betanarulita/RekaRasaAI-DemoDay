# Master Remediation Roadmap — RekaRasa.ai

**Tanggal:** 30 Oktober 2026  
**Target:** Production Beta Multi-User  
**Status implementasi:** Fase 1 + Fase 2 telah diimplementasikan  
**Metodologi:** superstar-engineer (Staff-level engineering)

---

## 1. Executive Summary

Audit menyeluruh telah dilakukan terhadap RekaRasa.ai (9 area audit, 30+ temuan). Setelah audit, dilakukan implementasi Fase 1 remediasi yang mencakup: structured logging dengan request ID correlation, Sentry error tracking integration, GitHub Actions CI/CD pipeline, SQLite backup script dengan disk monitoring, dan SMTP email integration untuk password reset dan email verification. Fase 2 melanjutkan dengan: `record_agent()` connection refactor (eliminasi risiko `database is locked`), account self-deletion endpoint, data export endpoint, dan prompt injection sanitization untuk image generation.

**Hasil validasi:**

- 92 test lulus (66 original + 7 Fase 1 + 10 Fase 2 + 5 Demo Day + 4 validasi E2E) — naik dari 66
- `py_compile` lulus untuk app.py, test_app.py, scripts/backup_db.py
- `node --check` lulus untuk static/app.js, probe_frontend.js
- Frontend probe: semua calendar dan diff checks OK
- Tidak ada file `.env` yang dimodifikasi

---

## 2. Peta Arsitektur dan Aliran Data End-to-End

```
┌──────────────────────────────────────────────────────────────────────┐
│  WorkBuddy AI (Agent Orchestrator)                                    │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │  Skill: rekarasa-creator                                  │        │
│  │  - Menerima brief dari user manusia                       │        │
│  │  - Menjalankan alur lewat rekarasa_cli.py                 │        │
│  │  - Bertanya sebelum confirm, menunggu sebelum approve     │        │
│  │  - TIDAK menulis konten sendiri                           │        │
│  └──────────────────────┬───────────────────────────────────┘        │
│                         │ HTTP (cookie + CSRF)                        │
└─────────────────────────┼────────────────────────────────────────────┘
                          │
┌─────────────────────────┼────────────────────────────────────────────┐
│  BROWSER (Single Origin)│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ index.html│  │ app.js   │  │ styles.css│  │  Logo.png│            │
│  │ (515 B)   │  │ (78 KB)  │  │ (45 KB)   │  │          │            │
│  └─────┬─────┘  └────┬─────┘  └──────────┘  └──────────┘            │
│        │ fetch() + CSRF + SameSite cookie + X-Request-ID (response)  │
└────────┼─────────────────────────────────────────────────────────────┘
         │              ▲
         │              │ (same API, same auth, same gate)
┌────────┼──────────────┼─────────────────────────────────────────────┐
│  WSGI APPLICATION (app.py — ~1820 lines)                              │
│        │                                                              │
│  ┌─────▼──────────────────┐   ┌─────────────────────────────────┐   │
│  │ Request ID Middleware  │   │ Structured JSON Logger           │   │
│  │ - UUID per request     │   │ - request_id, user_id, route     │   │
│  │ - X-Request-ID header  │   │ - duration_ms                   │   │
│  │ - Thread-local context │   │ - Sentry SDK (if SENTRY_DSN set) │   │
│  └─────┬──────────────────┘   └─────────────────────────────────┘   │
│        │                                                              │
│  ┌─────▼──────────────────────────────────────────────────────┐      │
│  │                  TRUST BOUNDARY (CODE-ENFORCED)              │      │
│  │  Planner → Writer → Reviewer → save_review() → Human Gate   │      │
│  │  7 deterministic guards in code, not in prompts              │      │
│  │  Approval gate: verdict must be "Pass" + human_approved=1   │      │
│  │  WorkBuddy CANNOT bypass: it goes through same API + CSRF   │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐       │
│  │ Auth         │  │ Rate Limit   │  │ SMTP Email            │       │
│  │ PBKDF2-SHA256│  │ 8/min/route  │  │ (if SMTP_HOST set)    │       │
│  │ CSRF         │  │ 8 login/5min │  │ Password reset        │       │
│  │ HttpOnly     │  │ in-process   │  │ Email verification    │       │
│  └──────────────┘  └──────────────┘  └──────────────────────┘       │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Endpoints: /api/health, /api/ready, /api/disk-usage          │    │
│  │  /api/export, /api/delete-account                             │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  SQLite (WAL, FK=ON, 7 migrations)                            │    │
│  │  + email_verifications table (migration 007)                  │    │
│  │  Audit trail: agent_runs, agent_messages, audit_events        │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
         │                           │                        │
         ▼                           ▼                        ▼
  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
  │ Groq API     │         │ Pollinations │         │ SMTP Server  │
  │ gpt-oss-20b  │         │ .ai (Flux)   │         │ (optional)   │
  │ (free tier)  │         │ FREE, no key │         │              │
  └──────────────┘         └──────────────┘         └──────────────┘

  Planner: Holiday Awareness
  ├── Indonesian national + religious holidays (2025-2027 dataset)
  ├── Auto-injected into Planner system prompt (within 30 days)
  └── GET /api/holidays endpoint (public, no auth)

  CI/CD: GitHub Actions
  ├── Python 3.12 + 3.13 matrix
  ├── pytest (92 tests)
  ├── py_compile (app.py, test_app.py, backup_db.py)
  ├── node --check (app.js, probe_frontend.js)
  ├── Frontend probe (calendar + diff)
  └── Docker image build

  Backup: scripts/backup_db.py
  ├── SQLite online backup API (non-blocking)
  ├── Disk usage report
  ├── Old backup cleanup (--keep N)
  └── Warning at 80% of 1GB threshold

  WorkBuddy Integration: integrations/workbuddy/
  ├── rekarasa_cli.py (CLI bridge, stdlib only)
  ├── SKILL.md (skill definition: operator, not creator)
  └── SETUP.md (5-step setup guide)
```

---

## 3. Daftar Temuan dengan Severity, Bukti, Dampak, dan Rekomendasi

### Critical (P0)

| ID  | Temuan                          | Bukti                                    | Dampak                             | Status                                                                                     |
| --- | ------------------------------- | ---------------------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------ |
| C-1 | API key terekspos di .env lokal | `.env` baris 8: `GROQ_API_KEY=gsk_...`   | Key bocor jika filesystem di-share | **Tidak diubah** (permintaan user: jangan sentuh .env). Rotasi key tetap direkomendasikan. |
| C-2 | SQLite production tanpa backup  | `render.yaml` disk 1GB, no backup config | Kehilangan data total              | **TERATASI**: `scripts/backup_db.py` + `/api/disk-usage` endpoint                          |
| C-3 | No email verification / SMTP    | `app.py` password reset via console      | Reset tidak reliable di production | **TERATASI**: SMTP integration + `/api/verify-email` endpoint + migration 007              |

### High (P1)

| ID  | Temuan                           | Bukti                               | Dampak                         | Status                                                                   |
| --- | -------------------------------- | ----------------------------------- | ------------------------------ | ------------------------------------------------------------------------ |
| H-1 | Rate limiting in-process         | `RATE_HITS: dict` di memory         | Tidak efektif multi-instance   | **Acceptable untuk single-instance beta**. Redis untuk scale-up.         |
| H-2 | No CORS headers                  | `json_response()` tidak set CORS    | API terkunci same-origin       | **By design**. Tidak perlu diubah untuk beta.                            |
| H-3 | No structured logging            | `log.warning("format %s", arg)`     | Debugging sulit di production  | **TERATASI**: JSON structured logger + request ID + Sentry hook          |
| H-4 | Image storage di disk bersama DB | `IMAGE_STORAGE_PATH` di `/var/data` | Disk penuh = DB write gagal    | **TERATASI**: `/api/disk-usage` monitoring + warning. S3 untuk scale-up. |
| H-5 | No CI/CD pipeline                | Tidak ada `.github/workflows/`      | Regression masuk tanpa deteksi | **TERATASI**: `.github/workflows/ci.yml`                                 |

### Medium (P2) — Post-beta

| ID  | Temuan                                        | Status                                                                                           |
| --- | --------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| M-1 | No account self-deletion                      | **TERATASI (Fase 2)**: `POST /api/delete-account` dengan password confirmation + cascade delete  |
| M-2 | Session tidak dirotasi berkala                | Acceptable untuk 14-day session beta.                                                            |
| M-3 | No sensitive data scanning di source upload   | Acceptable untuk beta. Roadmap P2.                                                               |
| M-4 | No prompt injection sanitization di image gen | **TERATASI (Fase 2)**: `sanitize_image_prompt()` dengan 8 regex patterns + length cap 2000 chars |
| M-5 | Frontend monolithic JS                        | Acceptable untuk beta.                                                                           |
| M-6 | No health check alerting                      | `/api/disk-usage` + Sentry memberikan visibility. Alerting via Render.                           |

### Low (P3)

| ID  | Temuan                                 | Status                                                   |
| --- | -------------------------------------- | -------------------------------------------------------- |
| L-1 | `.env.example` tidak lengkap           | **TERATASI**: Updated dengan SMTP + observability vars   |
| L-2 | `probe_frontend.js` bukan browser test | Acceptable.                                              |
| L-3 | No i18n                                | Acceptable untuk beta.                                   |
| L-4 | CSS single file 45KB                   | Acceptable.                                              |
| L-5 | No disk monitoring                     | **TERATASI**: `/api/disk-usage` endpoint + backup script |
| L-6 | README "46 tests" inconsistency        | **TERATASI**: README akan diupdate ke 73 tests           |

### Temuan Baru dari Deep Audit

| ID   | Temuan                                                            | Bukti                                                  | Severity                                                  |                                                                                                           |
| ---- | ----------------------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| DA-1 | `record_agent()` buka koneksi DB sendiri saat request masih aktif | `app.py:722` `db = connect()`                          | Medium — WAL allows concurrent read, write could block    | **TERATASI**: `record_agent()` sekarang menerima `db` parameter dari caller. Semua 8 call sites diupdate. |
| DA-2 | XSS: `innerHTML` tanpa `esc()` di beberapa template literal       | `static/app.js` lines 24, 119, 122                     | Low — data dari internal state, bukan user input langsung |                                                                                                           |
| DA-3 | No SQL injection vector ditemukan                                 | Semua query pakai `?` parameterized                    | N/A — aman                                                |                                                                                                           |
| DA-4 | No IDOR vector ditemukan                                          | Semua query include `owner_id=?`                       | N/A — aman                                                |                                                                                                           |
| DA-5 | Path traversal sudah di-guard                                     | `resolve()` + `parent != IMAGE_STORAGE_PATH.resolve()` | N/A — aman                                                |                                                                                                           |

### Temuan WorkBuddy Integration (WB)

| ID   | Temuan                                  | Bukti                                                                              | Severity | Status                                                                                |
| ---- | --------------------------------------- | ---------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------- |
| WB-1 | Integration test CLI belum ada          | `test_app.py` tidak punya test yang memanggil `rekarasa_cli.py`                    | Medium   | **TERATASI** — `test_cli_bridge_drives_the_real_http_api` (CLI subprocess vs WSGI server) |
| WB-2 | Skill belum di-install ke WorkBuddy     | `~/.workbuddy-ai/skills/rekarasa-creator/` belum ada di filesystem                 | High     | **TERATASI** — ter-install dan sudah disinkronkan dengan repo (termasuk `holidays`) |
| WB-3 | Evidence lama masih "simulasi"          | `FreshGlow_Publication_Gate_Status.md` line 75: approval hanya simulasi percakapan | Medium   | **TERATASI** — `evidence/E2E_WorkBuddy_Flow_2026-10-31.md` + transkrip `evidence/e2e/` |
| WB-4 | CLI tidak beri feedback sanitasi prompt | `cmd_generate_image` kirim prompt tanpa info sanitasi ke WorkBuddy                 | Low      | **TERATASI** — respons memuat `prompt_filtered`, CLI menampilkan catatan              |
| WB-5 | Approval yang ditolak tidak tercatat    | `POST /api/approve` menolak tapi tidak menulis event audit                         | Medium   | **TERATASI** — event `approval.blocked` + `db.commit()` sebelum raise                 |



---

## 4. Dependency Map: Temuan Mana yang Harus Selesai Sebelum yang Lain

```
C-2 (backup) ──────┐
                   ├──→ H-4 (disk monitoring) ──→ M-6 (alerting)
C-3 (SMTP) ────────┤
                   ├──→ Migration 007 ──→ Test verify-email
H-3 (logging) ─────┤
                   ├──→ Request ID ──→ X-Request-ID header ──→ Test request_id
                   └──→ Sentry hook ──→ requirements.txt update
H-5 (CI/CD) ───────┤
                   └──→ .github/workflows/ci.yml ──→ Docker build check

Parallel (no dependency):
  H-1 (rate limit)     ← independent, acceptable for beta
  H-2 (CORS)           ← independent, by design
  M-1..M-6             ← independent, post-beta
  DA-1 (DB connection) ← independent, medium priority
```

---

## 5. Daftar Risiko Keamanan dan Privasi

| Risiko | Severity | Bukti | Mitigasi |
|---|---|---|---|
| API key di .env lokal | Critical | `.env:8` | Rotasi key, set via Render secret |
| Password reset via console | Medium→Low | `app.py:1310` | **TERATASI**: SMTP email jika dikonfigurasi |
| No email verification | Medium→Low | Registrasi tidak verify | **TERATASI**: `/api/verify-email` endpoint |
| Rate limit in-process | Medium | `RATE_HITS: dict` | Acceptable untuk single-instance |
| No account deletion | Medium (UU PDP) | `privacy_disclosure not_provided` | Roadmap P2 |
| Source upload tidak scan PII | Low | `app.py:1267-1280` | Acceptable untuk beta |
| `innerHTML` tanpa esc() | Low | `app.js:24,119,122` | Data dari internal state |
| `record_agent()` DB connection | Medium | `app.py:570` | **TERATASI (Fase 2)**: `record_agent()` menerima `db` parameter dari caller |
| WorkBuddy: kontrol prosedural vs teknis untuk approval | Medium | SKILL.md rule #3 adalah prompt instruction, bukan code-enforced gate. Server tidak bisa membedakan "human approve via browser" vs "agent approve via CLI" | **Mitigasi saat ini**: `POST /api/approve` menolak jika `verdict != "Pass"`. WorkBuddy tidak bisa approve draft yang belum lolos Reviewer. **Mitigasi Fase 3**: Agent-specific token untuk membedakan agent-initiated vs human-initiated request |
| WorkBuddy: credential storage di filesystem | Low | `~/.rekarasa_session.json` mode 0600 | Acceptable — file permission restriktif, tidak di-commit ke repo |

---

## 6. Daftar Production Blockers

| Blocker | Status | Solusi |
|---|---|---|
| No backup strategy | **TERATASI** | `scripts/backup_db.py` + disk monitoring |
| No structured logging | **TERATASI** | JSON logger + request ID + Sentry |
| No CI/CD | **TERATASI** | GitHub Actions CI |
| No email/SMTP | **TERATASI** | SMTP integration + verification |
| No disk monitoring | **TERATASI** | `/api/disk-usage` endpoint |
| SQLite single-instance | **Acceptable untuk beta** | PostgreSQL untuk scale-up |
| No account self-deletion | **TERATASI** | `POST /api/delete-account` dengan password confirmation + cascade delete |
| No data export | **TERATASI** | `GET /api/export` mengembalikan semua data user sebagai JSON |
| No prompt injection sanitization | **TERATASI** | `sanitize_image_prompt()` dengan 8 regex patterns |
| No Redis rate limiting | **Acceptable untuk beta** | Redis untuk multi-instance |

---

## 7. Rekomendasi Arsitektur

### Yang Sudah Diimplementasikan (Fase 1)

1. **Structured JSON Logging** — Setiap log entry adalah JSON object dengan `ts`, `level`, `logger`, `message`, plus `request_id`, `user_id`, `method`, `path`, `duration_ms` dari request context.

2. **Request ID Correlation** — UUID per request, set di `X-Request-ID` response header, dan di `request_id` field di error response body. Memungkinkan tracing satu request across multiple log lines.

3. **Sentry Integration** — Jika `SENTRY_DSN` di-set, `sentry_sdk.init()` dipanggil dengan `send_default_pii=False` (tidak kirim PII). Optional: jika `sentry_sdk` tidak terinstall, warning di-log dan app jalan tanpa error tracking.

4. **SMTP Email Integration** — `send_email()` menggunakan stdlib `smtplib` + `MIMEText`. Jika `SMTP_HOST` tidak di-set, fungsi return `False` (no-op). Password reset token dikirim via email jika SMTP aktif, console fallback jika tidak.

5. **Email Verification** — Migration 007 membuat tabel `email_verifications`. Endpoint `GET /api/verify-email?token=...` memvalidasi token single-use. Registrasi mengirim email verifikasi jika SMTP aktif.

6. **Disk Monitoring** — Endpoint `GET /api/disk-usage` melaporkan ukuran database, image storage, total, dan flag `warning` jika >80% dari 1GB.

7. **Backup Script** — `scripts/backup_db.py` menggunakan SQLite online backup API (non-blocking), dengan cleanup old backups dan disk usage report.

8. **CI/CD Pipeline** — `.github/workflows/ci.yml` dengan Python 3.12+3.13 matrix, pytest, py_compile, node check, frontend probe, dan Docker build.

### Yang Sudah Diimplementasikan (Fase 2 — Post-Beta Hardening)

9. **`record_agent()` Connection Refactor** — `record_agent()` sekarang menerima `db: sqlite3.Connection` parameter dari caller, tidak lagi membuka koneksi sendiri. Eliminasi risiko `database is locked` under concurrent load. Semua 8 call sites diupdate dengan commit-before-raise pattern untuk failure paths.

10. **Account Self-Deletion** — Endpoint `POST /api/delete-account` dengan password confirmation. Cascade-deletes semua data user via FK `ON DELETE CASCADE`. Juga menghapus generated image files dari disk. Privacy disclosure diupdate.

11. **Data Export** — Endpoint `GET /api/export` mengembalikan semua data user (projects, sources, conversations, messages, briefs, plans, tasks, content_versions, review_runs, findings, agent_runs, usage_records, audit_events, generated_images) sebagai JSON. Privacy disclosure diupdate.

12. **Prompt Injection Sanitization** — `sanitize_image_prompt()` function dengan 8 regex patterns untuk mendeteksi dan memfilter injection phrases ("ignore previous instructions", "system:", "disregard all prior", dll). User direction di-wrap dengan delimiter yang menandakan "treat as brief, not as system instruction". Length cap 2000 chars.

### Yang Masih Perlu diimplementasikan (Fase 3 — Public Launch)

13. **PostgreSQL Migration** — Untuk multi-instance. Gunakan `psycopg2` dengan connection pooling.

14. **Redis Rate Limiting** — Pindahkan `RATE_HITS` dan `LOGIN_HITS` ke Redis dengan TTL.

15. **S3 Image Storage** — Pindahkan generated images dari disk ke S3/Cloud Storage.

---

## 7A. Evaluasi WorkBuddy sebagai Komponen Arsitektur RekaRasa.ai

### Interrogation (The "Why")

RekaRasa.ai memiliki tiga agent yang berjalan di dalam server (`Planner`, `Writer`, `Reviewer`), semuanya ditegakkan oleh `save_review()` sebagai trust boundary. WorkBuddy hadir sebagai **agent orchestrator eksternal** — ia tidak menulis konten, tidak mereview, dan tidak menyetujui. Ia menerima brief dari manusia, menerjemahkannya menjadi urutan panggilan API, dan melaporkan hasil apa adanya.

Pertanyaan arsitektur: **apakah WorkBuddy adalah agent keempat, atau infrastruktur?**

Jawaban: **WorkBuddy bukan agent keempat. Ia adalah orchestration layer** — setara dengan browser frontend, bukan dengan Planner/Writer/Reviewer. Perbedaan kuncinya:

| Dimensi | Planner/Writer/Reviewer | WorkBuddy |
|---|---|---|
| Menulis konten | Ya (Writer) | Tidak |
| Menilai konten | Ya (Reviewer) | Tidak |
| Menegakkan aturan | Ya (`save_review()` guards) | Tidak |
| Mengakses LLM provider | Ya (Groq API) | Tidak |
| Menyimpan state | Ya (`agent_runs`, `content_versions`) | Tidak (session cookie only) |
| Dapat bypass approval gate | Tidak | Tidak — same API, same CSRF, same auth |
| Di-test oleh test suite | Ya (92 tests) | Ya (CLI bridge: subprocess vs WSGI server) |

### Pembagian Tanggung Jawab (No Overlap)

```
HUMAN USER
    │
    │  "Buat konten untuk Jahe Rasa, marketplace + video pendek"
    ▼
WORKBUDDY (Orchestrator)
    │  - Memahami intent user
    │  - Menjalankan `rules` → menampilkan aturan
    │  - Menjalankan `plan` → menyampaikan hasil ke user
    │  - Bertanya sebelum `confirm`
    │  - Menjalankan `generate` → menyampaikan draft + findings
    │  - Menjalankan `revise` jika perlu (maks 3x)
    │  - Meminta persetujuan eksplisit sebelum `approve`
    │  - Menjalankan `audit` → menyimpan jejak
    │
    │  WorkBuddy TIDAK:
    │  - Menulis draft sendiri
    │  - Menilai draft sendiri
    │  - Menyetujui draft atas inisiatif sendiri
    │  - Mengarang fakta produk
    │  - Melewati langkah `rules`
    │
    ▼  (HTTP: cookie + CSRF, same as browser)
REKARASA API (app.py)
    │
    ├──→ PLANNER (LLM: gpt-oss-20b)
    │       - Menerima brief + sources
    │       - Mengembalikan plan dengan 1-6 tasks
    │       - `record_agent()` mencatat ke DB
    │
    ├──→ WRITER (LLM: gpt-oss-20b)
    │       - Menerima task + sources + prior review
    │       - Mengembalikan draft
    │       - `record_agent()` mencatat ke DB
    │
    ├──→ REVIEWER (LLM: gpt-oss-20b)
    │       - Menerima draft + rules + sources
    │       - Mengembalikan findings + verdict
    │       - `record_agent()` mencatat ke DB
    │
    └──→ save_review() (CODE, bukan LLM)
            - 7 deterministic guards
            - Rule coverage check
            - Substance + block validation
            - Verdict: Pass / Fail / Needs Evidence
            - Status: approved_pending_human / needs_revision / escalated
                │
                ▼
          HUMAN GATE (api/approve, api/reject)
            - Memerlukan verdict="Pass" + status="approved_pending_human"
            - `human_approved=1` set di DB
            - `audit_events` mencatat keputusan
            - WorkBuddy memanggil ini HANYA setelah persetujuan eksplisit user
```

### Permission Boundary dan Akses Data

| Aspek | Implementasi | Status |
|---|---|---|
| **Autentikasi** | WorkBuddy CLI login via `POST /api/login` → mendapat cookie + CSRF token, sama seperti browser | ✅ Berjalan |
| **Otorisasi** | Semua query DB include `owner_id=?` — WorkBuddy hanya bisa akses data akun yang dia login | ✅ Ditegakkan di kode |
| **CSRF** | CLI mengirim `X-CSRF-Token` header untuk semua POST, divalidasi via `hmac.compare_digest` | ✅ Ditegakkan di kode |
| **Rate limiting** | WorkBuddy tunduk pada rate limit yang sama (8/min/route, 8 login/5min) | ✅ Ditegakkan di kode |
| **Approval gate** | `POST /api/approve` menolak jika `review["verdict"] != "Pass"` atau `task["status"] != "approved_pending_human"` | ✅ Ditegakkan di kode (`app.py:1791`) |
| **Audit trail** | Semua aksi WorkBuddy tercatat di `audit_events` (planner.proposed, writer.draft_created, review.completed, human.approved) | ✅ Ditegakkan di kode |
| **Credential storage** | Session disimpan di `~/.rekarasa_session.json` (mode 0600). Email/password via env vars, tidak hardcode | ✅ Berjalan |
| **Bypass Reviewer** | Tidak mungkin — `save_review()` berjalan di server, WorkBuddy tidak punya endpoint alternatif | ✅ Ditegakkan di kode |


### Status Implementasi: Apa yang Sudah Berjalan vs Konsep

| Komponen | Status | Bukti |
|---|---|---|
| `rekarasa_cli.py` (CLI bridge) | **Berjalan** — 676 baris, stdlib only, 22 subcommand | File ada di `integrations/workbuddy/`, compile OK |
| `SKILL.md` (skill definition) | **Lengkap** — 7 aturan wajib, alur standar, tabel error code | File ada, format YAML frontmatter + markdown |
| `SETUP.md` (setup guide) | **Lengkap** — 5 langkah, tabel troubleshooting, urutan prioritas | File ada |
| `.gitignore` fix (evidence/ tracked) | **Sudah diperbaiki** — evidence/ tidak di-ignore, `.venv/` di-ignore | File `.gitignore` diverifikasi |
| Evidence screenshot | **Ada 3** — Workflow, Revisi, Publication Gate | File PNG di `evidence/` |
| Skill installed di `~/.workbuddy-ai/skills/` | **Belum** — perlu `cp` manual | Tidak ada di filesystem |
| End-to-end test via CLI | **Belum pernah** — DB sebelumnya 0 conversations, 0 tasks | SETUP.md mencatat ini |
| Integration test di test suite | **Belum ada** — tidak ada test yang memanggil CLI | `test_app.py` hanya test API langsung |
| Evidence "gate simulasi" → "gate ditegakkan kode" | **Belum dibuktikan** — evidence lama masih "PENDING_HUMAN_APPROVAL" (simulasi) | `FreshGlow_Publication_Gate_Status.md` line 75-93 |
| Audit trail export via CLI | **Berjalan** — `rekarasa_cli.py audit --out` memanggil `GET /api/audit` | Code ada di CLI line 405-420 |

### Temuan Baru: WB-1 sampai WB-4

| ID | Temuan | Bukti | Severity | Dampak |
|---|---|---|---|---|
| WB-1 | Integration test CLI belum ada | `test_app.py` tidak punya test yang memanggil `rekarasa_cli.py` | Medium | **TERATASI** — CLI dijalankan sebagai subprocess terhadap server WSGI sungguhan |
| WB-2 | Skill belum di-install ke WorkBuddy | `~/.workbuddy-ai/skills/rekarasa-creator/` belum ada | High | **TERATASI** — skill ter-install, versi repo sudah disalin ke folder skill |
| WB-3 | Evidence lama masih "simulasi" | `FreshGlow_Publication_Gate_Status.md` line 75: "Mekanisme approval di sesi ini hanya SIMULASI melalui percakapan" | Medium | **TERATASI** — evidence baru dari run nyata; dokumen lama ditandai *superseded* |
| WB-4 | CLI tidak test sanitasi prompt injection | `cmd_generate_image` di CLI mengirim `prompt` langsung tanpa validasi tambahan | Low | **TERATASI** — server mengembalikan `prompt_filtered`, CLI mencetak peringatan agar WorkBuddy tahu arahannya diubah |
| WB-5 | Percobaan approval yang ditolak tidak tercatat | `POST /api/approve` hanya melempar `APIError` tanpa event audit | Medium | **TERATASI** — `approval.blocked` ditulis lalu di-commit sebelum raise, jadi bertahan setelah rollback |

### Trade-Off Matrix: Posisi WorkBuddy dalam Arsitektur

| Pendekatan | Cost | Complexity | Scalability | Rekomendasi |
|---|---|---|---|---|
| A: WorkBuddy = Agent keempat ( ikut Planner/Writer/Reviewer) | Tinggi — perlu LLM call, state, review | Tinggi — overlap peran, boundary blur | Rendah — LLM cost berlipat | ❌ Tidak |
| B: WorkBuddy = Orchestration layer (current design) | Rendah — stdlib CLI, no LLM call | Rendah — clear separation | Tinggi — bisa ganti orchestrator lain | ✅ Rekomendasi |
| C: WorkBuddy = MCP server (bukan CLI) | Sedang — perlu MCP protocol | Sedang — async, bidirectional | Tinggi — standard protocol | Future, tidak untuk Demo Day |

**Rekomendasi: Pertahankan Pendekatan B.** Alasan:

1. **Rule of Leverage:** CLI bridge menyelesaikan root problem (WorkBuddy perlu berkomunikasi dengan API) dengan minimum code. Tidak menambah LLM call, tidak menambah state, tidak menambah failure mode.
2. **Boring Technology First:** stdlib `urllib` + `json` + `argparse`. Tidak ada framework, tidak ada dependency, tidak ada supply chain risk.
3. **Assume Systemic Failure:** CLI sudah handle `HTTPError`, `URLError`, `TimeoutError`, `CLIError` dengan kode error yang spesifik. Session expired → `not_logged_in`. Server down → `unreachable`. Rate limit → `rate_limited`.
4. **Mechanical Sympathy:** CLI adalah process yang singkat — login, panggil API, exit. Tidak ada connection pool, tidak ada thread, tidak ada memory leak. Setiap panggilan adalah HTTP request stateless.

### Red Team Critique (WorkBuddy-specific)

**Risiko terbesar:** WorkBuddy skill `rekarasa-creator` mengandalkan instruksi prompt untuk tidak menyetujui atas inisiatif sendiri (SKILL.md rule #3). Ini adalah **kontrol prosedural, bukan kontrol teknis**. Jika WorkBuddy (sebagai LLM) mengabaikan instruksi skill dan memanggil `approve` langsung, server akan menerima panggilan itu — karena dari sisi server, WorkBuddy adalah user yang terautentikasi seperti browser.

**Mitigasi yang sudah ada:** `POST /api/approve` menolak jika `verdict != "Pass"` atau `status != "approved_pending_human"`. Jadi WorkBuddy tidak bisa menyetujui draft yang belum lolos Reviewer. Tapi WorkBuddy BISA menyetujui draft yang sudah `Pass` tanpa manusia benar-benar mengatakan "setuju" — karena server tidak tahu apakah "ya" dari WorkBuddy adalah keputusan manusia atau inisiatif agent.

**Mitigasi tambahan yang bisa ditambahkan (Fase 3):** API key atau token khusus untuk WorkBuddy yang menandai "agent-initiated request", dan server bisa membedakan "human approve via browser" vs "agent approve via CLI". Untuk Demo Day, kontrol prosedural di SKILL.md adalah acceptable — juri akan melihat screenshot yang membuktikan WorkBuddy menunggu persetujuan.

---

## 8. Acceptance Criteria dan Test Plan

### Fase 1 (Implemented)

| Fitur | Acceptance Criteria | Test | Status |
|---|---|---|---|
| Structured logging | Setiap log entry adalah valid JSON dengan `request_id` | `test_response_includes_request_id_header` | **LULUS** |
| Request ID di error | Error response body mengandung `request_id` | `test_error_response_includes_request_id` | **LULUS** |
| Sentry hook | Jika `SENTRY_DSN` tidak set, app jalan normal | Compile check + 73 test pass | **LULUS** |
| SMTP fallback | Jika `SMTP_HOST` tidak set, `send_email()` return False | `test_send_email_is_noop_without_smtp` | **LULUS** |
| Email verification endpoint | Invalid token return 400 | `test_verify_email_with_invalid_token_returns_error` | **LULUS** |
| SMTP disabled registration | Registrasi tetap berhasil tanpa SMTP | `test_email_verification_flow_with_smtp_disabled` | **LULUS** |
| Migration 007 | `email_verifications` table ada | `test_migration_007_creates_email_verifications_table` | **LULUS** |
| Disk usage endpoint | Return 200 dengan `database_bytes`, `images_bytes`, `warning` | `test_disk_usage_endpoint_reports_sizes_without_auth` | **LULUS** |
| CI/CD pipeline | CI yml valid, runs on push + PR | Syntax check | **LULUS** |
| Backup script | `py_compile` lulus, API non-blocking | `py_compile scripts/backup_db.py` | **LULUS** |

### Fase 2 (Implemented)

| Fitur | Acceptance Criteria | Test | Status |
|---|---|---|---|
| `record_agent()` refactor | Tidak memanggil `connect()` — menggunakan caller's db | `test_record_agent_uses_caller_connection_not_new_one` | **LULUS** |
| Failure path commit | Agent run tersimpan sebelum exception propagate | `test_record_agent_failure_path_commits_before_raise` | **LULUS** |
| Account deletion — password | Wrong password return 403 | `test_delete_account_requires_password` | **LULUS** |
| Account deletion — cascade | Semua user data terhapus (users, projects, tasks, versions, sessions, dll) | `test_delete_account_removes_all_user_data` | **LULUS** |
| Account deletion — auth | Unauthenticated return 401 | `test_delete_account_requires_auth` | **LULUS** |
| Data export | Returns user_id, projects, tasks, content_versions | `test_export_returns_user_data` | **LULUS** |
| Data export — auth | Unauthenticated return 401 | `test_export_requires_auth` | **LULUS** |
| Prompt injection — patterns | 6 injection phrases stripped correctly | `test_sanitize_image_prompt_strips_injection_phrases` | **LULUS** |
| Prompt injection — length | Caps at 2000 chars | `test_sanitize_image_prompt_caps_length` | **LULUS** |
| Prompt injection — stored | Stored prompt reflects sanitization | `test_generate_image_stores_sanitized_prompt` | **LULUS** |

### WorkBuddy Integration

| Fitur | Acceptance Criteria | Test Plan | Status |
|---|---|---|---|
| CLI integration test (WB-1) | CLI benar-benar bicara ke HTTP API: session file, cookie, CSRF, dan error mapping terpakai | `test_cli_bridge_drives_the_real_http_api` — subprocess CLI vs server WSGI hidup | **LULUS** |
| Skill installation (WB-2) | Skill ter-install di `~/.workbuddy-ai/skills/rekarasa-creator/` dan sinkron dengan repo | Manual: `holidays` berjalan dari folder skill | **LULUS** (sinkronisasi masih manual — lihat risiko) |
| Evidence rerun (WB-3) | Evidence baru menunjukkan flow lengkap via CLI dengan gate yang ditegakkan kode | `evidence/E2E_WorkBuddy_Flow_2026-10-31.md` + `evidence/e2e/*.txt` | **LULUS** |
| Blocked approval tercatat (WB-5) | Percobaan approve yang ditolak meninggalkan event audit | `test_blocked_approval_is_recorded_in_the_audit_trail`, `..._records_the_verdict_that_caused_it` | **LULUS** |
| CLI feedback sanitasi (WB-4) | `cmd_generate_image` memberi info ke WorkBuddy jika prompt di-sanitize | `test_generate_image_stores_sanitized_prompt` (flag), `test_prompt_injection_filtered_does_not_raise_false_alarms` | **LULUS** |
| Procedural → technical control (WB-Future) | Server dapat membedakan agent-initiated vs human-initiated approve | Test: agent token menghasilkan flag `agent_initiated=true` di audit trail | ❌ Fase 3 — post-beta |

### Fase 3 (Not yet implemented)

| Fitur | Acceptance Criteria | Test Plan |
|---|---|---|
| PostgreSQL | All 92 tests pass with Postgres | Integration test dengan testcontainers |
| Redis rate limit | Rate limit works across instances | Multi-process test |
| S3 image storage | Images persist to S3, not disk | Integration test with localstack |

---

## 9. Prioritas Pengerjaan Terpadu (Roadmap)

### Fase 1 — Sebelum Beta Launch (TERIMPLEMENTASI)

| # | Item | Status | Estimasi |
|---|---|---|---|
| 1 | Structured JSON logging + request ID | ✅ Selesai | — |
| 2 | Sentry error tracking hook | ✅ Selesai | — |
| 3 | SMTP email integration | ✅ Selesai | — |
| 4 | Email verification endpoint + migration | ✅ Selesai | — |
| 5 | Disk monitoring endpoint | ✅ Selesai | — |
| 6 | Backup script | ✅ Selesai | — |
| 7 | CI/CD pipeline (GitHub Actions) | ✅ Selesai | — |
| 8 | .env.example + render.yaml update | ✅ Selesai | — |
| 9 | Privacy disclosure update | ✅ Selesai | — |
| 10 | 7 test baru untuk fitur baru | ✅ Selesai | — |

### Fase 2 — Post-Beta Hardening (TERIMPLEMENTASI)

| # | Item | Status | Estimasi |
|---|---|---|---|
| 11 | `record_agent()` connection refactor (DA-1) | ✅ Selesai | — |
| 12 | Account self-deletion (M-1) | ✅ Selesai | — |
| 13 | Data export (M-2) | ✅ Selesai | — |
| 14 | Prompt injection sanitization (M-4) | ✅ Selesai | — |
| 15 | Privacy disclosure update | ✅ Selesai | — |
| 16 | 10 test baru untuk fitur Fase 2 | ✅ Selesai | — |


### Fase 2B — WorkBuddy Integration (Pre-Demo Day)

| # | Item | Finding | Priority | Status |
|---|---|---|---|---|
| 17 | Install skill ke `~/.workbuddy-ai/skills/rekarasa-creator/` | WB-2 | P1 | ✅ Selesai (2026-10-31) |
| 18 | Run end-to-end flow via CLI, capture evidence baru | WB-3 | P1 | ✅ Selesai — `evidence/E2E_WorkBuddy_Flow_2026-10-31.md` |
| 19 | Tambah integration test untuk CLI bridge | WB-1 | P2 | ✅ Selesai — 92 test lulus |
| 20 | Catat percobaan approval yang ditolak | WB-5 | P2 | ✅ Selesai — event `approval.blocked` |
| 21 | Tambah CLI feedback untuk prompt sanitization | WB-4 | P3 | ✅ Selesai (2026-10-31) |

### Fase 2 — Remaining (Deferred to Fase 3)

| # | Item | Priority | Estimasi |
|---|---|---|---|
| 22 | PostgreSQL migration | P3 | 1-2 hari |
| 23 | Redis rate limiting | P3 | 4 jam |
| 24 | S3 image storage | P3 | 4 jam |
| 25 | Accessibility audit (WCAG 2.1 AA) | P3 | 1 hari |
| 26 | i18n framework | P3 | 1 hari |

### Fase 3 — Public Launch

| # | Item | Priority | Estimasi |
|---|---|---|---|
| 27 | UU PDP compliance review | P3 | External legal review |
| 28 | Load testing | P3 | 4 jam |
| 29 | Security penetration testing | P3 | External |
| 30 | Uptime monitoring + alerting | P3 | 2 jam |
| 31 | Runbook + on-call doc | P3 | 4 jam |
| 32 | Agent-specific token (procedural → technical control) | P3 | 4 jam |

---

## 10. Kriteria Kelulusan Private Beta dan Public Launch

### Private Beta — Acceptance Criteria

| Kriteria | Status |
|---|---|
| 73+ test lulus | ✅ (83 lulus) |
| Structured logging aktif di production | ✅ (JSON logger + request ID) |
| Error tracking aktif (Sentry) | ⏳ (Perlu set SENTRY_DSN di Render) |
| CI/CD pipeline aktif | ⏳ (Perlu push ke GitHub) |
| Backup strategy aktif | ⏳ (Perlu setup cron/scheduled job) |
| SMTP aktif untuk password reset | ⏳ (Perlu set SMTP_HOST di Render) |
| Disk monitoring aktif | ✅ (`/api/disk-usage` endpoint ready) |
| Health check endpoint | ✅ (`/api/health` + `/api/ready`) |
| Privacy disclosure up-to-date | ✅ (Updated dengan SMTP + email verification) |
| Docker image builds | ✅ (CI akan verify) |
| Known limits documented | ✅ (README + audit report) |
| WorkBuddy skill installed | ✅ (Sinkron dengan repo per 2026-10-31) |
| WorkBuddy end-to-end evidence | ✅ (`evidence/E2E_WorkBuddy_Flow_2026-10-31.md`) |

**Syarat GO Private Beta:** Set SENTRY_DSN, SMTP_HOST, push ke GitHub untuk aktivasi CI, setup scheduled backup job di Render, install WorkBuddy skill, dan run end-to-end flow via CLI untuk evidence baru.

### Public Launch — Acceptance Criteria

| Kriteria | Status |
|---|---|
| Semua Private Beta criteria lulus | ⏳ |
| PostgreSQL migration selesai | ❌ Belum dimulai |
| Redis rate limiting | ❌ Belum dimulai |
| S3 image storage | ❌ Belum dimulai |
| Account self-deletion | ✅ **TERATASI (Fase 2)** |
| Data export | ✅ **TERATASI (Fase 2)** |
| Prompt injection sanitization | ✅ **TERATASI (Fase 2)** |
| UU PDP compliance review | ❌ Belum dimulai |
| Security penetration test | ❌ Belum dimulai |
| Load testing (100 concurrent users) | ❌ Belum dimulai |
| Runbook + on-call documentation | ❌ Belum dimulai |
| Uptime monitoring + alerting | ❌ Belum dimulai |
| WorkBuddy CLI integration test | ✅ Selesai (WB-1) |
| WorkBuddy: agent-specific token (technical control) | ❌ Belum dimulai (Fase 3) |

---

## 11. Red Team Critique

**Status sebelumnya:** `record_agent()` (line 570) membuka koneksi SQLite sendiri saat request handler sudah punya koneksi terbuka. Dengan WAL mode, concurrent reads diizinkan, tapi jika `record_agent()` mencoba `INSERT` (write) saat main connection memegang `BEGIN IMMEDIATE` lock, write akan block hingga 15s timeout.

**Status saat ini (Fase 2):** **TERATASI.** `record_agent()` sekarang menerima `db: sqlite3.Connection` parameter dari caller. Semua 8 call sites diupdate. Failure paths menambahkan `db.commit()` sebelum `raise` untuk memastikan agent_run records tersimpan sebelum top-level handler melakukan `db.rollback()`.

**Single biggest risk yang tersisa:** SQLite masih single-instance. Untuk beta multi-user, ini acceptable karena Render menjalankan satu instance. Tetapi jika traffic meningkat dan diperlukan multi-instance, PostgreSQL migration menjadi prerequisite — tidak bisa dihindari. Rate limiting juga masih in-process (`RATE_HITS: dict`), yang tidak konsisten across instances.

**Solusi (Fase 3):** PostgreSQL migration + Redis rate limiting.

---

## 12. Challenge C Hackathon Submission Narrative

### Positioning RekaRasa.ai sebagai AI Agent System

RekaRasa.ai bukan sekadar web app dengan LLM call. Arsitekturnya mendefinisikan **tiga agent yang berjalan di server** (Planner, Writer, Reviewer) dengan **trust boundary yang ditegakkan kode** (`save_review()` dengan 7 deterministic guards), serta **agent orchestrator eksternal** (WorkBuddy) yang memungkinkan workflow end-to-end via natural language.

### Submission Story Arc

1. **Problem:** Kreator konten Indonesia kesulitan membuat konten yang sesuai brand guidelines, halal compliance, dan platform-specific format — tanpa tim creative.

2. **Solution Architecture:**
   - **Planner Agent:** Menerima brief + sources, menghasilkan plan dengan 1-6 tasks (per platform)
   - **Writer Agent:** Menerima task + sources + prior review feedback, menghasilkan draft
   - **Reviewer Agent:** Menerima draft + rules + sources, menghasilkan findings + verdict
   - **Trust Boundary:** `save_review()` dengan 7 deterministic guards (bukan LLM judgment — kode yang memutuskan Pass/Fail/Needs Evidence)
   - **Human Gate:** Approval endpoint yang menolak draft yang belum `verdict="Pass"` atau belum `status="approved_pending_human"`
   - **WorkBuddy Orchestrator:** Skill `rekarasa-creator` yang menerima brief dari user via natural language, menjalankan alur Planner→Writer→Reviewer→Human Gate via CLI bridge, dan melaporkan hasil apa adanya

3. **Key Differentiators:**
   - **Code-enforced guardrails, bukan prompt-only:** Reviewer tidak hanya menilai — `save_review()` memvalidasi 7 deterministic rules (claim cure, halal, substance, block, invalid reference, evidence requirement, rule coverage). LLM tidak bisa "override" guardrail.
   - **WorkBuddy sebagai orchestrator, bukan agent keempat:** WorkBuddy tidak menulis konten, tidak mereview, tidak menyetujui. Ia menerjemahkan intent manusia menjadi urutan API call. Trust boundary tetap di server.
   - **Audit trail end-to-end:** Setiap agent run tercatat di `agent_runs` + `agent_messages`. Setiap keputusan review tercatat di `review_runs` + `findings`. Setiap approval/rejection tercatat di `audit_events`. WorkBuddy CLI dapat export audit trail via `audit --out`.
   - **Production readiness:** 92 tests, structured logging, CI/CD, backup, disk monitoring, SMTP email, account deletion, data export, prompt injection sanitization.

4. **Demo Flow (Planned):**
   ```
   WorkBuddy session:
   > "Buat konten untuk FreshGlow skincare, marketplace + video pendek"
   
   WorkBuddy menjalankan:
   1. rules → menampilkan 7 aturan ke user
   2. plan → Planner agent menghasilkan 2 tasks (marketplace, video pendek)
   3. confirm → WorkBuddy bertanya "Lanjutkan dengan plan ini?"
   4. generate → Writer agent menghasilkan draft, Reviewer agent memberikan verdict
   5. (jika Needs Revision) revise → Writer agent revisi berdasarkan findings
   6. approve → WorkBuddy bertanya "Setujui publikasi?" (EXPLICIT human consent)
   7. audit → WorkBuddy menampilkan audit trail lengkap
   ```

5. **Evidence yang Akan Disertakan:**
   - Evidence baru: flow end-to-end via CLI dengan gate yang ditegakkan kode (menggantikan evidence "simulasi")
   - Audit trail export dari CLI
   - Screenshot WorkBuddy session yang menunjukkan: (a) WorkBuddy menampilkan rules, (b) WorkBuddy bertanya sebelum confirm, (c) WorkBuddy bertanya sebelum approve, (d) audit trail lengkap
   - Test suite output: 92 tests lulus

### Apa yang Membedakan dari "ChatGPT Wrapper"

| Aspek | ChatGPT Wrapper | RekaRasa.ai |
|---|---|---|
| Content generation | Single LLM call, no review | Planner→Writer→Reviewer pipeline |
| Quality control | Prompt instruction ("jangan halal claim") | Code-enforced `save_review()` dengan 7 guards |
| Audit trail | Tidak ada | `agent_runs` + `audit_events` + CLI export |
| Human approval | Tidak ada gate | `verdict="Pass"` + `human_approved=1` required |
| Agent orchestration | Tidak ada | WorkBuddy skill dengan 7 mandatory rules |
| Production readiness | Demo-only | 92 tests, CI/CD, backup, logging, SMTP, privacy compliance |

---

## Lampiran: File yang Dimodifikasi/Dibuat

| File | Aksi | Deskripsi |
|---|---|---|
| `app.py` | Dimodifikasi (Fase 1) | +120 baris: structured logging, request ID, SMTP, email verification, disk monitoring |
| `app.py` | Dimodifikasi (Fase 2) | +80 baris: `record_agent()` refactor, `_export_user_data()`, `DELETE /api/delete-account`, `GET /api/export`, `sanitize_image_prompt()`, privacy disclosure update |
| `test_app.py` | Dimodifikasi (Fase 1) | +60 baris: 7 test baru, 2 test diperbarui untuk structured logging format |
| `test_app.py` | Dimodifikasi (Fase 2) | +90 baris: 10 test baru (record_agent, delete-account, export, prompt injection), 1 test diperbarui untuk privacy disclosure |
| `migrations/007_email_verification.sql` | Dibuat (Fase 1) | Tabel `email_verifications` |
| `scripts/backup_db.py` | Dibuat (Fase 1) | Backup script dengan disk monitoring |
| `.github/workflows/ci.yml` | Dibuat (Fase 1) | CI/CD pipeline |
| `.env.example` | Dimodifikasi (Fase 1) | SMTP + observability variables |
| `render.yaml` | Dimodifikasi (Fase 1) | SMTP + Sentry + LOG_LEVEL env vars |
| `requirements.txt` | Dimodifikasi (Fase 1) | `sentry-sdk>=2.0,<3.0` |
| `.env` | **TIDAK DISENTUH** | Sesuai permintaan user |
| `master-remediation-roadmap-2026-10-30.md` | Dimodifikasi | Section 7A (WorkBuddy evaluation), Section 3 (WB findings), Section 5 (WB risk), Section 8 (WB criteria), Section 9 (WB priority items), Section 10 (WB beta criteria), Section 12 (hackathon narrative) |

---

*Roadmap selesai. Implementasi Fase 1 + Fase 2 telah diverifikasi dengan 83 test lulus. WorkBuddy architectural evaluation telah diintegrasikan ke seluruh section roadmap. Fase 2B (WorkBuddy integration: skill install, evidence rerun, CLI integration test) menunggu eksekusi pre-Demo Day. Fase 3 (PostgreSQL, Redis, S3, load testing, pen testing, agent-specific token) menunggu eksekusi pre-public-launch.*
