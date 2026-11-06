# Project Lead Roadmap — RekaRasa.ai Accountable AI Creator Agent

**Tanggal:** 1 November 2026  
**Role:** Project Lead  
**Tujuan:** Mengembangkan aplikasi yang sudah ada menjadi Accountable AI Creator Agent — bukan membangun ulang.  
**Basis:** Repository `D:\RekaRasaAI-DemoDay` (2,233 baris `app.py`, 88 test, 8 migrasi, monolit Python stdlib + waitress).  
**Audit referensi:** `docs/TECHNICAL_LEAD_AUDIT_2026-11-01.md`

---

## Prinsip Pengembangan

1. **Preservasi invarian yang sudah terbukti.** Trust boundary `save_review()` (7 guard deterministik), state machine guards, dan human approval gate tidak boleh dilemahkan oleh perubahan apa pun.
2. **Additive, bukan rewrite.** Setiap fase menambah lapisan di atas kode yang ada. Tidak ada "rebuild from scratch."
3. **Product Owner adalah acceptance gate akhir.** Automated test memvalidasi mekanisme; keputusan konten tetap manusia.
4. **Anti scope-creep.** Setiap deliverable harus dapat ditelusuri ke salah satu dari 7 scope. Fitur di luar scope ditolak atau ditunda.
5. **Jangan sentuh kode sebelum arsitektur disetujui.** Fase 0 menghasilkan dokumen arsitektur, bukan kode.

---

## Status Repository Aktual (Fakta Kode)

| Komponen | Status Aktual | Bukti Kode |
|---|---|---|
| Trust boundary | 7 guard deterministik berfungsi | `save_review()` `app.py:1016-1098` |
| Rules | 4 DEMO rules hardcoded di Python | `RULES` `app.py:221-226`, `kind='demo'` |
| Rule registry | DB-backed, versioned, tetapi source-of-truth adalah kode | `rule_registry` tabel, `init_db()` reseed setiap startup `app.py:335-343` |
| Applicability engine | **Tidak ada** — semua rule global untuk semua project | Tidak ada filter berdasarkan produk/platform |
| LLM payload logging | Summary terpotong 3000 char | `record_agent()` `app.py:911` |
| Provenance | `source_ids` disimpan di `content_versions`, tetapi tidak ada hash konten source | `migrations/001` baris 13, `store_draft()` `app.py:1180` |
| Audit trail | 15+ event types, termasuk `approval.blocked` | `audit()` `app.py:348-349` |
| Actor identification | Tidak ada — server tidak bedakan manusia vs agent | Diakui di `REBUILD_PROMPT.md:170-173` |
| DB | SQLite WAL, single-instance | `connect()` `app.py:298-304` |
| Rate limiting | In-process `defaultdict(deque)` | `app.py:495-509` |
| Testing | 88 test, fake provider, CI GitHub Actions | `test_app.py`, `.github/workflows/ci.yml` |
| PDP compliance | Honest disclosure, tetapi eksplisit "not UU PDP compliance" | `privacy_disclosure()` `app.py:1106-1168` |

---

## Pemecahan Scope → Fase → Deliverable

### FASE 0 — Arsitektur & Persetujuan (BLOCKER untuk semua fase)

**Tujuan:** Menghasilkan dokumen arsitektur yang disetujui Product Owner sebelum kode ditulis.

| Deliverable | Deskripsi | Output |
|---|---|---|
| 0.1 Architecture Decision Record (ADR) | Dokumen yang menentukan: struktur tabel regulatory KB, mekanisme applicability engine, format LLM payload logging, strategi actor identification, dan kebijakan data retention. Setiap keputusan dengan rasional dan trade-off. | `docs/ADR_001_architecture.md` |
| 0.2 Data contract changes spec | Perubahan schema untuk: `sources` (hash), `content_versions` (source snapshot), `agent_interactions` (full payload), `sessions` (actor_type), `audit_events` (actor_type, model_version). | `docs/DATA_CONTRACT_CHANGES.md` |
| 0.3 Test strategy document | Test matrix baru: concurrent test, regulatory applicability test, provenance test, governance test. Definisi acceptance criteria per fase. | `docs/TEST_STRATEGY.md` |

**Dependency:** Tidak ada — ini adalah prasyarat.  
**Acceptance gate:** Product Owner meninjau dan menyetujui ADR. Tidak ada fase lain dimulai sebelum ini.

---

### FASE 1 — Regulatory Knowledge Base & Verifikasi Sumber Hukum

**Scope:** #1 (Regulatory KB) + #2 sebagian (struktur rule untuk applicability)

**Kondisi aktual:** Rules di-hardcode sebagai tuple Python di `app.py:221-226`. `rule_registry` tabel ada tetapi di-reseed dari kode setiap startup (`init_db()`, `app.py:335-343`). Tidak ada mekanisme untuk menambah rule tanpa deploy kode baru.

| Deliverable | Deskripsi | Prioritas | Dependency |
|---|---|---|---|
| 1.1 Migrasi: tabel `regulation_sources` | Menyimpan referensi regulasi eksternal dengan metadata: nama, otoritas (BPOM/Kominfo/dll), yurisdiksi, URL sumber resmi, tanggal verifikasi, status (verified/pending/superseded). | P0 | Fase 0 |
| 1.2 Migrasi: tabel `regulation_rules` | Rule yang terhubung ke `regulation_sources`. Memiliki: rule_text, rule_type (prohibition/requirement/procedural), requires_evidence, enforcement_pattern (regex untuk guard deterministik). Composite key (id, version). | P0 | 1.1 |
| 1.3 Migrasi: tabel `rule_applicability` | Mapping project → rule yang berlaku. Menyimpan: project_id, rule_id, rule_version, applied_reason, applied_at. | P0 | 1.2 |
| 1.4 Migrasi DEMO rules ke struktur baru | 4 rule DEMO-* yang ada dipindahkan ke `regulation_rules` dengan `regulation_sources.id = 'internal-demo-policy'`. Perilaku `save_review()` tidak boleh berubah. | P0 | 1.2 |
| 1.5 API: CRUD regulation rules (admin) | Endpoint untuk menambah/membaca/mengubah rule tanpa deploy kode. Memerlukan admin role (belum ada — lihat Risiko R-3). | P1 | 1.2, Fase 0 |
| 1.6 **Verifikasi sumber hukum** | Input dari pihak berwenang secara hukum untuk mengisi `regulation_sources` dengan regulasi aktual. Auditor tidak mengarang isi regulasi. | P0 | 1.1, **keputusan Product Owner** |

**Catatan kritis:** Deliverable 1.6 adalah blocker eksternal. Engineer tidak dapat mengisi konten regulasi. Product Owner harus menentukan: (a) sumber otoritas yang akan dipakai, (b) siapa yang melakukan verifikasi, (c) kategori produk mana yang akan didukung pertama.

**Out of scope untuk Fase 1:** Implementasi applicability engine logic (Fase 2), UI untuk rule management.

---

### FASE 2 — Applicability & Risk Engine

**Scope:** #2 (Applicability & Risk Engine)

**Kondisi aktual:** `save_review()` (`app.py:1017`) mengambil SEMUA rule dengan `WHERE kind='demo'`. Reviewer menerima semua rule terlepas dari jenis produk. Tidak ada filtering.

| Deliverable | Deskripsi | Prioritas | Dependency |
|---|---|---|---|
| 2.1 Project metadata extension | Field baru pada project: `product_type` (enum: cosmetic/food/supplement/other), `claims_category` (array), `target_platforms` (array). Disimpan di tabel `projects` atau tabel baru `project_metadata`. | P0 | Fase 1 |
| 2.2 Applicability engine function | Function `applicable_rules(db, project_id)` yang mengembalikan rule yang berlaku berdasarkan metadata project. Logika: match `regulation_rules.applicable_product_types` dengan `project_metadata.product_type`. | P0 | 2.1, 1.3 |
| 2.3 Update `save_review()` | Ganti `SELECT ... WHERE kind='demo'` (`app.py:1017`) dengan `applicable_rules(db, task["project_id"])`. Rule coverage check (`app.py:1077-1080`) hanya untuk rule yang applicable. | P0 | 2.2 |
| 2.4 Update Reviewer payload | `review_draft()` (`app.py:1199-1205`) dan `demo_rules()` (`app.py:1101-1103`) menggunakan applicable rules, bukan global. | P0 | 2.2 |
| 2.5 Risk scoring (optional) | Setiap finding dapat memiliki `risk_level` (low/medium/high) berdasarkan rule type dan claim severity. Tidak menggantikan verdict; hanya metadata untuk human reviewer. | P2 | 2.3 |

**Risiko kritis Fase 2:** Mengubah `save_review()` adalah operasi berisiko tinggi. Function ini adalah trust boundary utama. Setiap perubahan harus:
1. Tidak mengubah logika 7 guard yang ada.
2. Tidak melemahkan rule coverage check.
3. Ditest dengan test suite yang ada (88 test) sebelum dan sesudah perubahan.
4. Product Owner melakukan acceptance test pada alur lengkap.

---

### FASE 3 — AI Governance & PDP Assessment

**Scope:** #3 (AI Governance dan PDP assessment)

**Kondisi aktual:** LLM input/output tidak disimpan lengkap (`summary[:3000]` di `app.py:911`). Tidak ada model version pinning per review cycle. Tidak ada data retention auto-deletion. `privacy_disclosure()` eksplisit menyatakan "not UU PDP compliance."

| Deliverable | Deskripsi | Prioritas | Dependency |
|---|---|---|---|
| 3.1 Migrasi: tabel `agent_interactions` | Menyimpan full LLM payload: run_id, system_prompt, user_payload (JSON), raw_response, response_status. Terhubung ke `agent_runs` via FK. | P0 | Fase 0 |
| 3.2 Update `llm_json()` untuk log payload | Sebelum return, simpan input dan output lengkap ke `agent_interactions`. Tidak menggantikan `agent_messages` — keduanya ada. | P0 | 3.1 |
| 3.3 Model version pinning per review cycle | Saat task mulai generate/revise, catat model version di task atau review context. Semua LLM calls dalam satu cycle (Writer + Reviewer) menggunakan model yang sama. | P1 | 3.1 |
| 3.4 PDP assessment document | Dokumen yang memetakan: data apa yang diproses, siapa pengendali data, siapa pemroses data (Groq), apa basis hukum pemrosesan, apa hak subjek data, berapa retensi. **Bukan legal advice — input untuk konsultan hukum.** | P0 | **keputusan Product Owner** |
| 3.5 Data retention policy implementation | Auto-expiry untuk: audit events (>90 hari), agent interactions (>30 hari raw payload), expired sessions (sudah ada). Draft dan review tidak expire (catatan kreatif pengguna). | P1 | 3.1 |
| 3.6 Actor type differentiation | `sessions.actor_type` ('human'/'agent'). CLI bridge mengirim `actor_type=agent`. `audit_events` mencatat actor_type dari session. Approval gate tetap sama untuk semua actor. | P1 | Fase 0 |
| 3.7 Content safety filter (post-LLM) | Filter tambahan setelah Writer output, sebelum `store_draft()`. Memeriksa: hate speech, harassment, misleading content. Tidak menggantikan Reviewer — lapisan tambahan. | P2 | 3.2 |
| 3.8 Per-user token budget | Batas harian token LLM per user. Default generous, dapat diatur oleh admin. | P2 | 3.1 |

**Catatan PDP:** Deliverable 3.4 adalah assessment, bukan compliance statement. Product Owner harus menentukan apakah sistem ini berperan sebagai pengendali data (data controller) atau pemroses data (data processor), dan apa implikasinya. Ini memerlukan input hukum.

---

### FASE 4 — Perbaikan Data Contract Planner, Writer, Reviewer

**Scope:** #4 (Data contract improvements)

**Kondisi aktual:** Schema validation ada (`validate_schema_value()` `app.py:563-588`). Writer dan Reviewer menerima payload yang sudah well-structured. Namun: source content tidak di-snapshot per version, dan agent payload tidak disimpan lengkap.

| Deliverable | Deskripsi | Prioritas | Dependency |
|---|---|---|---|
| 4.1 Source content hash | Kolom `content_hash` (SHA-256) di tabel `sources`. Dihitung saat upload. Memungkinkan deteksi jika source berubah antara draft creation dan review. | P1 | Fase 0 |
| 4.2 Source snapshot per version | Saat `store_draft()` (`app.py:1171`), simpan snapshot source content (atau hash set) yang digunakan Writer. Disimpan di `content_versions` atau tabel baru `version_source_snapshots`. | P1 | 4.1 |
| 4.3 Planner contract: holiday context versioning | Holiday context yang diinjeksi ke Planner (`app.py:1927`) harus dicatat. Saat ini hanya string yang diappend. Tambahkan tanggal generasi dan version dataset. | P2 | Fase 0 |
| 4.4 Writer contract: review context enrichment | Writer remediation payload (`app.py:2026`) sudah menerima `prior_draft` dan `review_findings`. Tambahkan: applicable rules, source snapshots, dan model version. | P1 | Fase 2, 4.2 |
| 4.5 Reviewer contract: applicable rules + context | Reviewer payload (`app.py:1197-1205`) sudah menerima rules. Perubahan: rules yang dikirim adalah applicable rules (dari Fase 2), bukan global. Tambahkan product metadata untuk context-aware review. | P0 | Fase 2 |
| 4.6 Contract validation tests | Test yang memverifikasi: setiap field yang dikirim ke LLM ada di data contract doc, setiap field yang dikembalikan divalidasi, dan tidak ada field yang "bocor" (mis. account_id tidak ada di payload). | P1 | 4.1-4.5 |

---

### FASE 5 — Evidence Provenance & Context-Aware Review

**Scope:** #5 (Evidence provenance dan context-aware review)

**Kondisi aktual:** `content_versions.source_ids` menyimpan JSON array UUID. `findings.evidence_source_id` menyimpan UUID. Tetapi tidak ada snapshot konten source — jika source dihapus/ditambah ulang, provenance draft v1 tidak bisa diverifikasi.

| Deliverable | Deskripsi | Prioritas | Dependency |
|---|---|---|---|
| 5.1 Provenance chain document | Dokumen yang mendefinisikan: apa yang dimaksud "provenance" dalam sistem ini, bagaimana chain-of-custody dilacak dari brief → source → draft → review → approval, dan apa yang dapat/diverifikasi pasca-fakto. | P0 | Fase 0 |
| 5.2 Source snapshot implementation | Implementasi dari 4.2 — snapshot source content (atau hash) saat draft dibuat. Memungkinkan verifikasi: "draft v1 dibuat berdasarkan source dengan hash X." | P1 | 4.2 |
| 5.3 Review context snapshot | Saat review berjalan, snapshot: applicable rules (id+version), source content (hash), model version, reviewer instructions. Disimpan di `review_runs` atau tabel `review_context`. | P1 | 4.5, 3.3 |
| 5.4 Context-aware review enhancement | Reviewer menerima context tambahan: product_type, target_platforms, claims_category dari project metadata. Reviewer instructions diperkaya: "For cosmetic products, check for BPOM registration claims." (Tidak mengarang regulasi — menggunakan rule yang sudah diverifikasi di Fase 1). | P1 | Fase 2, 5.3 |
| 5.5 Provenance verification API | `GET /api/provenance?version_id=X` mengembalikan: source snapshot, review context, model version, actor_type, timestamp untuk setiap langkah dalam lifecycle version tersebut. | P2 | 5.2, 5.3 |

---

### FASE 6 — State Machine, Remediation, Escalation, Human Approval

**Scope:** #6

**Kondisi aktual:** State machine sudah kuat. `MAX_ITERATIONS=3` (`app.py:164`), `ACTIONABLE_REVIEW`, `RETRYABLE_REVIEW`, `REVIEWABLE_STATUS` (`app.py:928-930`). Approval gate menolak jika verdict != Pass atau status != approved_pending_human (`app.py:2128`). Blocked decision dicatat sebelum raise (`app.py:2107-2119`).

| Deliverable | Deskripsi | Prioritas | Dependency |
|---|---|---|---|
| 6.1 State machine documentation | Dokumen formal: semua state, semua transisi legal, semua guard, semua pre-condition. Diagram state machine yang dapat diaudit. | P0 | — |
| 6.2 Escalation workflow improvement | Saat `status="escalated"` (remediation limit tercapai atau human reject), tidak ada mekanisme lanjutan selain human edit. Tambahkan: notification (opsional), escalation reason di audit, dan path "human override" yang tercatat. | P1 | 6.1 |
| 6.3 Concurrent access hardening | Test dan (jika perlu) lock improvement untuk: dua request generate pada task yang sama, approve sementara review berjalan, edit sementara revise berjalan. Saat ini `require_review_settled()` (`app.py:951`) menangani sebagian, tetapi tidak ada test concurrent. | P1 | Fase 7 |
| 6.4 Approval authenticity (future) | Token per-actor untuk membedakan manusia vs agent secara cryptographic. Diakui sebagai gap di `REBUILD_PROMPT.md:170-173`. Solusi penuh memerlukan infrastructure change. | P3 | Fase 3.6, riset tambahan |

**Catatan:** State machine saat ini sudah memenuhi 6 dari 7 invarian di `REBUILD_PROMPT.md` bagian 3. Fase 6 sebagian besar adalah dokumentasi dan hardening, bukan redesign.

---

### FASE 7 — Audit Trail & Backend Testing

**Scope:** #7

**Kondisi aktual:** 88 test dengan fake provider. CI di GitHub Actions. Audit trail 15+ event types. Tetapi: tidak ada concurrent test, tidak ada security test suite, test output tidak disimpan sebagai artifact.

| Deliverable | Deskripsi | Prioritas | Dependency |
|---|---|---|---|
| 7.1 Concurrent test suite | Test yang mensimulasikan: 2 request generate pada task yang sama, approve + revise concurrent, edit + review concurrent. Menggunakan threading di unittest. | P0 | — |
| 7.2 Regulatory applicability test | Test yang memverifikasi: rule A berlaku untuk cosmetic, rule B tidak; rule C berlaku untuk food+marketplace, tidak untuk social media only. | P0 | Fase 2 |
| 7.3 Provenance verification test | Test yang memverifikasi: source snapshot tersimpan, hash cocok, provenance API mengembalikan chain lengkap. | P1 | Fase 5 |
| 7.4 Security test suite | Test untuk: SQL injection (parameterized query sudah dipakai, tetapi test eksplisit), XSS di draft content, path traversal di image file access. | P1 | — |
| 7.5 Test output persistence | CI mengupload test output + coverage report sebagai artifact. Memenuhi syarat REBUILD_PROMPT: "Simpan output test ke evidence/." | P1 | — |
| 7.6 Audit trail completeness test | Test yang memverifikasi: setiap state transition menghasilkan audit event, setiap blocked attempt tercatat, actor_type tercatat (setelah Fase 3.6). | P1 | Fase 3.6 |
| 7.7 Performance baseline test | Test yang mengukur: latency plan→generate→review untuk 1 task, throughput 10 concurrent users, DB query time untuk audit list. Bukan SLA — baseline untuk deteksi regression. | P2 | — |

---

## Dependency Graph

```
FASE 0 (Arsitektur & Persetujuan)
  │
  ├──→ FASE 1 (Regulatory KB) ──────────────┐
  │                                          │
  ├──→ FASE 3 (Governance & PDP) ───────────┤
  │                                          │
  └──→ FASE 4 (Data Contracts) ─────────────┤
                                             │
                          FASE 2 (Applicability) ←── FASE 1
                                             │
                          FASE 5 (Provenance) ←── FASE 2, FASE 4
                                             │
                          FASE 6 (State Machine) ←── (sebagian independen)
                                             │
                          FASE 7 (Testing) ←── semua fase
```

**Paralelisasi yang mungkin:**
- Fase 1, 3, 4 dapat berjalan paralel setelah Fase 0 selesai.
- Fase 2 membutuhkan Fase 1 (rule structure) selesai.
- Fase 5 membutuhkan Fase 2 (applicable rules) dan Fase 4 (source hash).
- Fase 6 sebagian besar independen — dapat dimulai paralel dengan Fase 1.
- Fase 7 berjalan throughout, tetapi test spesifik (7.2, 7.3) membutuhkan fase terkait.

---

## Prioritas Matrix

| Prioritas | Definisi | Deliverables |
|---|---|---|
| **P0** | Blocker untuk "Accountable AI" claim. Tanpa ini, sistem tidak dapat menyandang label. | 0.1-0.3, 1.1-1.4, 1.6, 2.1-2.4, 3.1-3.2, 3.4, 4.5, 5.1, 6.1, 7.1-7.2 |
| **P1** | Diperlukan untuk production readiness. Tanpa ini, sistem siap demo tetapi tidak siap produksi. | 1.5, 2.5, 3.3, 3.5-3.6, 4.1-4.2, 4.4, 4.6, 5.2-5.4, 6.2-6.3, 7.3-7.6 |
| **P2** | Meningkatkan kualitas dan maintainability. Nice-to-have untuk fase awal. | 3.7-3.8, 4.3, 5.5, 7.7 |
| **P3** | Riset masa depan. Tidak blocking untuk versi 1.0 production. | 6.4 |

---

## Keputusan yang Harus Diambil Product Owner

### D-1: Kategori produk yang didukung di fase awal

**Pertanyaan:** Apakah sistem akan mendukung semua kategori produk (kosmetik, makanan, suplemen, obat) sekaligus, atau dimulai dengan satu kategori?

**Dampak:** Menentukan scope verifikasi regulasi (Fase 1.6). Jika satu kategori, verifikasi lebih cepat dan fokus. Jika semua, membutuhkan riset regulasi yang lebih luas.

**Rekomendasi:** Mulai dengan satu kategori (mis. kosmetik atau food supplement) yang paling relevan untuk use case demo. Tambahkan kategori lain secara bertahap.

### D-2: Sumber otoritas regulasi

**Pertanyaan:** Sumber resmi mana yang akan dijadikan referensi untuk mengisi `regulation_sources`?

**Dampak:** Menentukan kredibilitas regulatory KB. Tanpa sumber yang diverifikasi, rule tidak bisa diklaim sebagai "compliance."

**Rekomendasi:** Tentukan daftar sumber resmi (BPOM, Kemendag, Kominfo) dan pihak yang akan melakukan verifikasi (internal legal team atau konsultan eksternal).

### D-3: Peran sistem dalam UU PDP

**Pertanyaan:** Apakah RekaRasa.ai berperan sebagai pengendali data (data controller) atau pemroses data (data processor) dalam konteks UU PDP?

**Dampak:** Menentukan kewajiban kepatuhan yang berbeda. Controller memiliki kewajiban lebih banyak (consent, DPO, DPIA). Processor fokus pada instruksi controller.

**Rekomendasi:** Konsultasi dengan legal. Assessment di Fase 3.4 akan memetakan ini, tetapi keputusan final adalah Product Owner.

### D-4: DPA dengan LLM provider

**Pertanyaan:** Apakah akan menandatangani Data Processing Agreement dengan Groq, atau mencari provider alternatif yang menawarkan DPA?

**Dampak:** Tanpa DPA, data pengguna diproses oleh provider tanpa kontrak formal. `privacy_disclosure()` sudah mengakui ini secara jujur.

**Rekomendasi:** Jika Groq tidak menawarkan DPA pada free tier, pertimbangkan: (a) tetap di free tier dengan disclosure jujur (status quo), (b) upgrade ke tier berbayar yang menawarkan DPA, (c) self-host model (open weights) untuk data sensitive.

### D-5: Kapan beralih dari SQLite ke PostgreSQL

**Pertanyaan:** Apakah migrasi database dilakukan sebelum atau sesudah fitur inti (Fase 1-5) selesai?

**Dampak:** SQLite membatasi ke concurrent writers. Jika testing concurrent (Fase 7.1) menunjukkan masalah, migrasi mendesak. Tetapi migrasi adalah pekerjaan besar yang dapat menunda fitur.

**Rekomendasi:** Tunda migrasi sampai Fase 1-5 selesai dan concurrent test (Fase 7.1) menunjukkan kebutuhan. SQLite WAL dengan single instance memadai untuk development dan demo.

### D-6: Scope "context-aware review"

**Pertanyaan:** Seberapa kaya context yang diberikan ke Reviewer? Apakah cukup product_type + platform, atau perlu juga: target audience demographics, geographic scope, regulatory jurisdiction?

**Dampak:** Context yang lebih kaya = review yang lebih tepat, tetapi juga kompleksitas yang lebih tinggi dan potensi false positive.

**Rekomendasi:** Mulai dengan product_type + platform (Fase 2.1). Tambahkan audience/jurisdiction di iterasi berikutnya jika dibutuhkan.

---

## Risk Identification & Mitigation Plans

### R-1: Perubahan `save_review()` merusak guard yang ada

**Severity:** CRITICAL  
**Probability:** MEDIUM  
**Dampak:** Jika 7 guard deterministik berhenti berfungsi, trust boundary hilang. Sistem tidak lagi "accountable."

**Mitigation:**
1. Sebelum perubahan: jalankan 88 test yang ada, simpan hasil sebagai baseline.
2. Setelah perubahan: jalankan 88 test yang sama, verifikasi semua masih lulus.
3. Tambahkan test baru yang eksplisit memverifikasi setiap guard secara individual (bukan hanya integration test).
4. Product Owner melakukan acceptance test: buat draft dengan cure claim, verifikasi ditolak; buat draft dengan halal claim tanpa source, verifikasi ditolak.
5. Code review oleh kedua mata: Technical Lead + Product Owner.

### R-2: Regulatory KB diisi dengan konten yang tidak diverifikasi

**Severity:** CRITICAL  
**Probability:** MEDIUM  
**Dampak:** Rule yang salah → false positive/negative → konten yang tidak compliant lolos, atau konten yang compliant ditolak. Klaim "compliance" tanpa dasar.

**Mitigation:**
1. `regulation_sources.status` dimulai sebagai `pending`. Rule dengan source `pending` tidak aktif sampai diverifikasi.
2. Verifikasi harus dilakukan oleh pihak yang berwenang (bukan engineer).
3. Setiap rule mencatat `verified_at` dan `verified_by`.
4. UI/API menampilkan status verifikasi secara transparan.
5. Disclaimer tetap ada: rule yang verified bukan legal advice.

### R-3: Admin role belum ada untuk rule management

**Severity:** HIGH  
**Probability:** CERTAIN (tidak ada admin role di kode saat ini)  
**Dampak:** API CRUD untuk regulation rules (1.5) membutuhkan admin role. Tanpa itu, semua user bisa mengubah rule.

**Mitigation:**
1. Tambahkan `is_admin` flag di tabel `users` (migrasi baru).
2. Rule management endpoint memeriksa `is_admin`.
3. Untuk fase awal, rule management bisa dilakukan via direct DB access oleh operator (bukan user-facing API).
4. API CRUD dapat ditunda ke P1 jika admin role belum prioritas.

### R-4: Applicability engine mengeluarkan rule yang seharusnya berlaku

**Severity:** HIGH  
**Probability:** MEDIUM  
**Dampak:** Jika applicability engine salah mengecualikan rule DEMO-CLAIM-001 untuk produk tertentu, cure claim bisa lolos.

**Mitigation:**
1. DEMO-* rules tetap global (applicable untuk semua product types) sebagai baseline.
2. Regulatory rules dari Fase 1 yang applicable berdasarkan product type adalah tambahan, bukan pengganti.
3. Test 7.2 memverifikasi: DEMO rules selalu applicable; regulatory rules applicable berdasarkan metadata.
4. Product Owner acceptance test: buat project dengan product_type=cosmetic, verifikasi rule kosmetik muncul + DEMO rules tetap muncul.

### R-5: Concurrent access menyebabkan data corruption

**Severity:** HIGH  
**Probability:** LOW (SQLite + single instance + thread pool waitress)  
**Dampak:** Dua request pada task yang sama bisa menyebabkan inconsistent state.

**Mitigation:**
1. Fase 7.1: concurrent test suite yang mensimulasikan race condition.
2. `BEGIN IMMEDIATE` sudah dipakai di `/api/revise` (`app.py:2012, 2036`).
3. `require_review_settled()` (`app.py:951`) menolak mutasi saat review berjalan.
4. Jika test menunjukkan masalah: tambahkan application-level lock per task_id (dictionary dengan threading.Lock).

### R-6: LLM payload logging menyebabkan storage overflow

**Severity:** MEDIUM  
**Probability:** MEDIUM  
**Dampak:** Full payload (system prompt + user payload + raw response) per LLM call bisa mencapai 50-100KB. Dengan 3 calls per task, 100 task/hari = ~15MB/hari.

**Mitigation:**
1. Retention policy: raw payload dihapus setelah 30 hari (Fase 3.5).
2. Metadata (run_id, role, status, token count) tetap permanent.
3. `/api/disk-usage` sudah memantau storage. Tambahkan alerting.
4. Jika mendesak: kompresi payload (gzip sebelum store) atau pindah ke object storage.

### R-7: Scope creep — fitur di luar 7 scope

**Severity:** MEDIUM  
**Probability:** HIGH  
**Dampak:** Penambahan fitur (mis. multi-tenant, RBAC lengkap, scheduled publishing, platform integration) menunda deliverable inti.

**Mitigation:**
1. Setiap permintaan fitur baru dievaluasi terhadap 7 scope.
2. Jika tidak cocok: dicatat di backlog, bukan diimplementasi.
3. Roadmap ini adalah kontrak. Perubahan scope memerlukan persetujuan Product Owner dan revisi roadmap.
4. Review scope setiap fase completion: "Apakah yang kita bangun adalah yang kita sepakati?"

### R-8: Verifikasi hukum membutuhkan waktu lebih lama dari estimasi

**Severity:** MEDIUM  
**Probability:** HIGH  
**Dampak:** Fase 1.6 tertunda → Fase 2 (applicability engine yang bergantung pada rule structure) bisa mulai tetapi tidak bisa diisi dengan rule aktual.

**Mitigation:**
1. Struktur tabel dan engine logic (1.1-1.4, 2.1-2.4) dapat dibangun tanpa konten regulasi aktual. DEMO rules tetap berfungsi.
2. Verifikasi hukum (1.6) berjalan paralel dengan development engineering.
3. Sistem dapat deploy dengan DEMO rules + struktur regulatory KB kosong. Rule diverifikasi ditambahkan secara inkremental.
4. Tidak mengklaim "compliance" sampai minimal satu regulasi terverifikasi dan aktif.

### R-9: Migrasi SQLite → PostgreSQL di tengah development

**Severity:** LOW (jika ditunda) / HIGH (jika terpaksa)  
**Probability:** LOW  
**Dampak:** Migrasi membutuhkan: perubahan SQL dialect, connection pooling, data migration, test rewrite.

**Mitigation:**
1. Tunda migrasi sampai Fase 1-5 selesai (D-5).
2. Gunakan SQL yang portable (hindari SQLite-specific functions).
3. Test dengan SQLite dan PostgreSQL jika memungkinkan.
4. Backup database sebelum migrasi (`scripts/backup_db.py`).

### R-10: Actor identification (Fase 3.6) memberikan false sense of security

**Severity:** MEDIUM  
**Probability:** MEDIUM  
**Dampak:** `actor_type` di session adalah kontrol prosedural, bukan cryptographic. Agent dengan cookie stolen dari human session masih bisa approve sebagai "human."

**Mitigation:**
1. Dokumentasi eksplisit: actor_type adalah metadata untuk audit, bukan security boundary.
2. Approval gate tetap sama untuk semua actor types.
3. Solusi cryptographic (per-actor token signing, Fase 6.4) dicatat sebagai P3 future work.
4. Tidak mengklaim "human provenance guaranteed" — hanya "actor type recorded."

---

## Acceptance Criteria per Fase

| Fase | Acceptance Criteria | Validator |
|---|---|---|
| 0 | ADR disetujui Product Owner. Data contract spec disetujui. Test strategy disetujui. | Product Owner |
| 1 | DEMO rules berfungsi dari struktur baru. Tabel regulatory KB ada dan dapat diisi. Minimal 1 regulasi terverifikasi (jika sumber sudah ada). | Product Owner + Technical Lead |
| 2 | Applicable rules berbeda untuk product_type yang berbeda. DEMO rules tetap global. `save_review()` menggunakan applicable rules. 88 test lulus. | Product Owner (acceptance test) + Automated test |
| 3 | LLM payload tersimpan lengkap. PDP assessment document ada. Actor type tercatat di audit. | Product Owner + Technical Lead |
| 4 | Source hash tersimpan. Writer/Reviewer menerima applicable rules + context. Contract validation test lulus. | Automated test + Technical Lead |
| 5 | Provenance chain dapat diverifikasi via API/test. Source snapshot tersimpan per version. | Product Owner (acceptance test) + Automated test |
| 6 | State machine terdokumentasi. Concurrent test lulus. Escalation workflow jelas. | Technical Lead + Automated test |
| 7 | Concurrent test lulus. Security test lulus. Test output tersimpan sebagai artifact. | Automated test + Technical Lead |

---

## Out of Scope (Ditolak atau Ditunda)

| Item | Alasan | Status |
|---|---|---|
| Multi-tenant collaboration | Tidak ada di 7 scope. Single-user per account memadai untuk fase ini. | Backlog |
| Scheduled publishing | Tidak ada di 7 scope. Publishing integration tidak diimplementasi. | Backlog |
| Platform publishing (TikTok/Shopee API) | Tidak ada di 7 scope. Output adalah copy text, bukan auto-publish. | Backlog |
| PDF source extraction | Tidak ada di 7 scope. Source hanya .txt/.md. | Backlog |
| Multi-language support | Tidak ada di 7 scope. Indonesia + English sudah didukung oleh LLM. | Backlog |
| Full RBAC (role-based access control) | Hanya admin flag untuk rule management. RBAC lengkap adalah scope creep. | Backlog |
| Real-time collaboration | Tidak ada di 7 scope. Single-user editing. | Backlog |
| Model fine-tuning | Tidak ada di 7 scope. Menggunakan model yang ada. | Backlog |
| Cost tracking/pricing | Token usage sudah dicatat. Estimasi biaya adalah nice-to-have, bukan inti. | Backlog |

---

## Red Team Critique

**Kelemahan terbesar dari roadmap ini sendiri:** Roadmap mengasumsikan bahwa struktur dan engine dapat dibangun terlebih dahulu, dengan konten regulasi ditambahkan belakangan. Ini benar secara engineering, tetapi berisiko: struktur yang dibangun tanpa konten aktual mungkin tidak fit ketika regulasi diverifikasi. Misalnya, jika regulasi BPOM memiliki struktur hierarki (bab/pasal/ayat) yang tidak cocok dengan flat `regulation_rules` table, redesign dibutuhkan. Mitigasi:libatkan pihak hukum SECEPAT mungkin dalam Fase 1 untuk validasi struktur, bahkan jika konten belum lengkap.

**Kelemahan terbesar dari sistem yang akan dibangun:** Roadmap ini menambah kompleksitas (regulatory KB, applicability engine, provenance chain, actor identification) di atas monolit 2,233 baris yang sudah berfungsi. Setiap lapisan baru adalah permukaan serangan baru dan potensi bug baru. Jika kompleksitas ini tidak diimbangi dengan test yang memadai (Fase 7), sistem yang dimaksudkan untuk "accountable" justru menjadi sulit diaudit karena terlalu banyak moving parts. Mitigasi: setiap fase harus lulus acceptance criteria sebelum fase berikutnya dimulai. Tidak ada paralelisasi yang mengorbankan kualitas.

---

**Roadmap selesai. Menunggu persetujuan Product Owner sebelum memulai Fase 0.**
