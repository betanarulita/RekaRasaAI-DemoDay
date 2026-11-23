# RekaRasa.ai — Dokumentasi Teknis

**Status dokumen:** snapshot implementasi yang diperiksa pada 21 November 2026. Source di repository menjadi acuan untuk detail teknis; status provider, runtime, dan layanan lokal dapat berubah setelah dokumen ini dibuat.

## 1. Ringkasan sistem

RekaRasa.ai adalah aplikasi web Python dengan frontend JavaScript statis dan backend WSGI. Alur kerja konten utamanya adalah:

```text
Chat Brief atau Excel Campaign Brief
                 ↓
        Planner (Rara) → rencana
                 ↓ konfirmasi
        Writer (Reka) → versi draft
                 ↓
        Reviewer (Raya) → findings dan verdict
                 ↓ Pass
     approved_pending_human
                 ↓ tindakan manusia eksplisit
          human_approved
```

Planner dan Writer menghasilkan output terstruktur melalui provider LLM. Reviewer memeriksa brief, rencana, draft, sumber proyek, Product Catalog, Brand Memory, dan rulebook. Approval manusia merupakan keputusan terpisah. Source yang diperiksa tidak menyediakan alur publish eksternal otomatis.

## 2. Komponen repository

| Komponen | Lokasi | Tanggung jawab |
|---|---|---|
| Backend, route WSGI, persistence, agent orchestration | [`app.py`](../app.py) | Konfigurasi, API, database SQLite, Planner/Writer/Reviewer, approval, visual generation |
| Frontend | [`static/app.js`](../static/app.js), [`static/styles.css`](../static/styles.css) | Navigasi, form brief, project/workbench, history, temuan dan status |
| Migrasi database | [`migrations/`](../migrations/) | Perubahan skema bernomor dan tercatat di `schema_migrations` |
| Parser brief dan katalog | [`campaign_brief_import.py`](../campaign_brief_import.py), [`catalog_import.py`](../catalog_import.py) | Pembacaan dan normalisasi file campaign brief serta Product Catalog |
| Integrasi visual | [`comfy_workflows.py`](../comfy_workflows.py), [`visual_content.py`](../visual_content.py), [`cloudflare_images.py`](../cloudflare_images.py) | Penyusunan workflow, validasi/penanganan visual, dan integrasi provider gambar opsional |
| Aturan kebijakan | [`governance_policy.py`](../governance_policy.py), `governance/references.json` | Pemeriksaan kebijakan dan referensi yang dipakai Reviewer |
| Dependensi Python | [`requirements.txt`](../requirements.txt) | Waitress, Sentry SDK, Pillow, dan PyMuPDF dengan rentang versi |
| Contoh konfigurasi | [`.env.example`](../.env.example) | Nama variabel konfigurasi tanpa kredensial aktif |
| Test runner aman | [`scripts/run_tests.py`](../scripts/run_tests.py) | Mengosongkan kredensial test dan memblokir koneksi eksternal |

Backend dan frontend berada dalam aplikasi yang sama; tidak ada service/API terpisah untuk tiap agent. Routing utama ditangani oleh fungsi `application()` di `app.py`.

## 3. Siklus request dan workflow

### Brief dan Planner

- Brief dapat dimasukkan lewat percakapan atau diimpor melalui endpoint `/api/brief-import`. Parser dan normalisasi berada pada modul campaign brief import.
- Endpoint `/api/plan` mengirim konteks brief, preferensi, sumber proyek, serta Product Catalog yang dipilih ke Planner.
- Pengguna meninjau dan mengonfirmasi rencana sebelum draft dibuat. Endpoint konfirmasi rencana memvalidasi state plan.
- Product Catalog adalah sumber konteks terstruktur yang opsional. Katalog tidak menggantikan campaign brief; pemilihan sumber katalog dibatasi ke sumber proyek yang valid.

### Writer, versi, dan remediation

- `/api/generate` menerima task dari plan terkonfirmasi. Writer output divalidasi terhadap skema Writer, task ID, isi draft, dan source IDs sebelum draft disimpan.
- Draft disimpan sebagai `content_versions`; revisi membuat versi baru dan mempertahankan versi sebelumnya.
- `/api/revise` hanya dapat berjalan jika task membutuhkan revisi, temuan terbaru actionable, dan `remediation_count` masih di bawah `MAX_ITERATIONS` (3).
- Writer menerima draft sebelumnya, temuan Reviewer, dan sumber terkait untuk menyusun revisi. Hasilnya tetap menjalani review; Writer tidak dapat menganggap hasilnya lolos.

### Reviewer V2

Implementasi Reviewer berada terutama pada `REVIEWER_INSTRUCTIONS`, `REVIEW_SCHEMA`, `normalize_reviewer_v2()`, `ensure_content_quality_assessment()`, `reviewer_validation_diagnostic()`, `review_draft()`, dan `save_review()` di `app.py`.

Kontrak provider V2 mensyaratkan:

- Tujuh key assessment kualitas yang tetap dan wajib: Brief fit, Target audience fit, Brand voice consistency, Platform fit, Format compliance, Clarity, dan Copy quality.
- Temuan rule dan temuan tambahan dipisahkan menjadi `findings.rules` dan `findings.additional`; provider tidak memberi verdict akhir.
- Temuan tambahan dibatasi maksimal enam. Validasi lokal tetap menegakkan batas tersebut meskipun batasan tertentu dibuang saat membentuk wire schema untuk provider.
- Duplicate JSON object keys dideteksi pada parsing.

`normalize_reviewer_v2()` mengadaptasi output terstruktur menjadi finding list internal yang dipakai oleh penyimpanan lama: rule findings dalam urutan rule konfigurasi, tujuh assessment kualitas dalam urutan tetap, lalu additional findings. Adapter tidak membuat assessment yang hilang. `save_review()` tetap menghitung verdict dan menerapkan validasi rule ID, sumber/evidence, claim grounding, coverage rule, serta guardrail deterministic.

Untuk rule yang tidak dikembalikan model, perilaku saat ini menambahkan `Rule coverage: Needs Evidence`; ini merupakan fallback coverage yang disengaja. Itu berbeda dari penghilangan salah satu assessment wajib, yang ditolak saat validasi.

Claim faktual diperiksa terhadap draft dan sumber yang relevan. Peran sumber membedakan setidaknya Product Catalog dan Brand Memory. Kehadiran kata/produk yang sama saja tidak cukup untuk membuat sumber menjadi evidence yang mendukung. Ketidakpastian evidence tidak boleh disamakan dengan fakta salah; konflik sumber dan klaim tanpa dukungan diperlakukan berbeda sesuai validator.

Verdict dihitung aplikasi dari hasil findings yang telah dinormalisasi dan divalidasi: `Fail` jika ada finding Fail; selain itu `Needs Evidence` jika masih ada finding Needs Evidence; selain itu `Pass`. Jika model gagal menghasilkan respons valid, review/findings tidak disimpan sebagai review sukses; status error dan rekaman agent/audit mengikuti jalur kegagalan yang tersedia.

### Human approval

- Reviewer Pass mengubah state menjadi `approved_pending_human`; versi belum dianggap disetujui manusia.
- `/api/approve` mensyaratkan review Pass untuk versi terbaru dan state pending approval. Approval eksplisit dicatat di `approvals` dan audit event; versi ditandai `human_approved`.
- `/api/reject` mencatat keputusan manusia sebagai penolakan/escalation sesuai state machine.
- UI memberi affordance approval sesuai state, tetapi pemeriksaan otoritatif berada di backend.
- Tidak ada endpoint publish eksternal dalam route yang diperiksa. Persetujuan bukan bukti bahwa konten sudah dipublikasikan.

## 4. API utama

Endpoint berikut adalah ringkasan route aplikasi; autentikasi dan validasi state tetap berlaku.

| Metode/path | Fungsi |
|---|---|
| `GET /api/health` | Health dan kesiapan database/provider/image provider |
| `POST /api/brief-import` | Preview/import campaign brief, katalog, atau attachment sesuai format |
| `POST /api/plan` | Membuat atau memperbarui rencana Planner |
| Route konfirmasi plan | Mengonfirmasi plan sebelum generation |
| `POST /api/generate` | Membuat draft Writer pertama, menyimpan versi, lalu menjalankan Reviewer |
| `POST /api/revise` | Remediation Writer dengan batas iterasi |
| `POST /api/review-edit` | Reviewer pada versi tersimpan terbaru yang eligible |
| `POST /api/approve`, `POST /api/reject` | Keputusan manusia atas versi terbaru yang sudah direview |
| `GET /api/history`, `GET /api/conversation` | History dan detail percakapan, plan, task, serta versi terkait |
| `GET /api/image-status` | Status provider gambar yang diminta |
| `POST /api/generate-image` | Membuat output visual melalui provider gambar aktif |

Route dapat berubah seiring implementasi. Untuk payload dan status code yang tepat, periksa kondisi route langsung di `application()`; tabel ini bukan OpenAPI specification.

## 5. Model data dan penyimpanan

Database utama adalah SQLite. Koneksi memakai foreign keys, WAL mode, dan timeout 15 detik. Migrasi SQL berurutan ditemukan di [`migrations/`](../migrations/) dan statusnya disimpan pada tabel `schema_migrations`.

Kelompok tabel inti mencakup:

- Identitas dan sesi: `users`, `sessions`.
- Project dan sumber: `projects`, `sources`, serta arsip sumber/aset.
- Brief dan planning: `conversations`, `messages`, `briefs`, `plans`, `tasks`.
- Draft dan review: `content_versions`, `review_runs`, `findings`, `rule_registry`, `agent_runs`, `agent_messages`.
- Approval dan jejak: `approvals`, `audit_events`, `usage_records`.
- Media: generated images, visual compositions, project assets, dan tabel terkait yang ditambahkan migrasi.

Pembuatan versi bersifat historis: revisi menambah version record. Temuan Reviewer tersimpan terkait review/version; history menggabungkan conversation, brief, plan, dan task.

**Peringatan operasional:** `app.py` memanggil `init_db()` saat modul aplikasi dimuat sebagai entrypoint. Fungsi ini membuat struktur dasar, menjalankan migrasi yang belum tercatat, melakukan backfill metadata task tertentu, dan menyelaraskan rule registry. Karena itu, menjalankan server terhadap SQLite produksi bukan operasi read-only. Backup dan verifikasi path `DATABASE_PATH` wajib dilakukan sebelum startup atau deployment.

## 6. Konfigurasi dan menjalankan lokal

Variabel utama dijelaskan di [`.env.example`](../.env.example):

| Variabel | Default/contoh | Keterangan |
|---|---|---|
| `HOST`, `PORT` | `127.0.0.1`, `8000` | Bind server Waitress |
| `DATABASE_PATH` | `./data/rekarasa.sqlite3` | File SQLite; path relatif ditafsirkan dari working directory |
| `IMAGE_STORAGE_PATH` | default di samping DB | Direktori file gambar |
| `MODEL` | `openai/gpt-oss-20b` | Model teks Groq |
| `GROQ_API_KEY` | kosong di template | Secret provider, hanya sisi server |
| `IMAGE_PROVIDER` | source saat ini memilih ComfyUI | Provider gambar aktif pada source saat ini |
| `COMFYUI_URL` | `http://127.0.0.1:8188` | URL service ComfyUI |
| `COMFYUI_CHECKPOINT`, `COMFYUI_TIMEOUT` | checkpoint SD, `300` | Pengaturan workflow gambar |
| `CLOUDFLARE_IMAGE_URL`, `CLOUDFLARE_IMAGE_API_KEY` | kosong | Integrasi gambar opsional yang harus dikonfigurasi eksplisit |
| `SMTP_*`, `APP_BASE_URL` | SMTP kosong | Email opsional dan URL dasar aplikasi |
| `SENTRY_DSN`, `LOG_LEVEL` | kosong, `INFO` | Observability opsional |

Loader `.env` memakai `os.environ.setdefault`, sehingga variabel dari environment proses mengungguli nilai `.env`. Jangan menyimpan credential di frontend, commit, output terminal, atau dokumentasi.

Contoh menjalankan pada Windows CMD (pastikan path DB dan image adalah path yang memang dimaksud):

```bat
cd /d D:\RekaRasaAI-DemoDay
set HOST=127.0.0.1
set PORT=8000
set DATABASE_PATH=D:\RekaRasaAI-DemoDay\data\rekarasa.sqlite3
set IMAGE_STORAGE_PATH=D:\RekaRasaAI-DemoDay\data\generated-images
python -u app.py
```

Server berjalan di foreground; hentikan dari terminal yang sama dengan `Ctrl+C`. Untuk pengujian, gunakan salinan database dan direktori media terisolasi, bukan database runtime lain.

## 7. Image generation

Provider gambar source saat ini adalah ComfyUI dengan URL default `127.0.0.1:8188`. Aplikasi memiliki endpoint status, generate, edit, serta penyimpanan metadata dan file output. File gambar disimpan pada `IMAGE_STORAGE_PATH`; default-nya mengikuti direktori database. Cloudflare merupakan opsi terpisah dengan konfigurasi eksplisit, bukan fallback otomatis. Periksa [`docs/IMAGE_PROVIDER_SETUP.md`](./IMAGE_PROVIDER_SETUP.md) sebelum mengaktifkan provider.

HTTP 200 dari endpoint image-status hanya menyatakan endpoint aplikasi menjawab; nilai `ready/state` di body yang menentukan kesiapan provider. Pada pemeriksaan runtime 8003 yang tersedia dalam sesi sebelumnya, status ComfyUI dilaporkan `offline`; keadaan itu harus dicek ulang di lingkungan yang akan dipakai.

## 8. Test dan verifikasi

Test runner [`scripts/run_tests.py`](../scripts/run_tests.py) memuat test backend (`test_app`, `test_evidence_binding`, `test_visual_content`, `test_image_modes`, `test_claim_evaluation`, `test_project_actions` secara default). Runner menyingkirkan credential provider/email, mengarahkan ComfyUI ke loopback port yang tidak aktif, dan menolak koneksi jaringan non-loopback.

Contoh:

```bat
python scripts\run_tests.py
```

Jalankan test dengan interpreter/environment proyek yang sama. Jika test tambahan belum tercantum pada daftar default, berikan nama modulnya secara eksplisit. Hasil suite hanya membuktikan test otomatis yang berjalan; hasil mock tidak membuktikan ketersediaan provider live atau kesiapan layanan eksternal.

## 9. Runtime dan batas lingkungan

Port lokal yang pernah dipakai pada sesi pengembangan:

| Port | Tujuan historis | Batas interpretasi |
|---|---|---|
| `8000` | Runtime utama | Database dan image storage milik runtime ini; jangan menganggap source di disk sama dengan kode yang sudah dimuat proses |
| `8001` | Isolated/UAT runtime | Memakai path database/media terisolasi jika environment prosesnya dikonfigurasi demikian |
| `8003` | Candidate runtime | Kandidat untuk pengujian; tidak otomatis berarti sama dengan 8000/8001 atau siap hosting |

Port saja tidak membuktikan isolasi. Sebelum menggunakan runtime, periksa PID/listener, command line, working directory, environment proses (`DATABASE_PATH`, `IMAGE_STORAGE_PATH`), dan status health. Untuk kandidat berbasis salinan production, pastikan jalur aplikasi hanya menunjuk ke salinan kandidat dan tidak menulis ke database/media sumber.

### Snapshot kesiapan yang diketahui

- Reviewer Chat Brief pernah berhasil pada UAT sebelumnya; hasil itu tidak membuktikan semua brief atau provider selalu berhasil.
- UAT Excel sebelumnya tertunda setelah provider mengembalikan HTTP 503/rate limit; belum dinyatakan lulus.
- Pada pemeriksaan akun Groq yang dibagikan pengguna, terlihat sejumlah respons 429 `rate_limit_exceeded`; dashboard juga menunjukkan tier Developer sementara tidak tersedia. Status itu dapat berubah dan perlu dicek langsung sebelum pengujian provider.
- ComfyUI pada runtime kandidat 8003 terakhir dilaporkan `offline`. Konektivitas ComfyUI dan image generation end-to-end belum dapat dianggap lulus berdasarkan status aplikasi saja.
- Kandidat 8003 yang diuji lokal belum sama dengan hosting publik. Domain, TLS, reverse proxy, persistent storage, secret management, akses pengguna, dan backup/restore hosting perlu diverifikasi sebelum dipakai untuk grand final.

## 10. Checklist sebelum demo atau deployment

1. Pastikan source revision yang dijalankan, direktori kerja, PID, port, dan konfigurasi proses.
2. Pastikan DB dan image storage persisten serta terpisah antara dev/UAT/production.
3. Backup SQLite dengan mekanisme konsisten; verifikasi backup dapat dibuka sebelum migrasi.
4. Periksa status provider LLM dan image secara terpisah. Jangan mengulang workflow saat provider terkena rate limit.
5. Jalankan suite backend lokal dengan network external diblokir.
6. Verifikasi brief → plan → draft → review → human approval pada data UAT baru.
7. Uji history setelah reload, file image hasil generate, dan perilaku error tanpa menganggap HTTP 200 sebagai keberhasilan seluruh workflow.
8. Pastikan approval tidak otomatis dan tidak ada publikasi eksternal tanpa integrasi serta tindakan eksplisit.
9. Untuk hosting, atur HTTPS, secret server-side, persistent volume, backup terjadwal, logging yang tidak memuat raw prompt/output sensitif, serta prosedur rollback.

Dokumen ini mendeskripsikan implementasi source yang diperiksa dan status historis yang tersedia. Ia bukan sertifikasi keamanan, bukti seluruh acceptance test lulus, atau pernyataan bahwa runtime lokal sudah siap produksi.
