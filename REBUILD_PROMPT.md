# PROMPT — Bangun Ulang "RekaRasa.ai" dari Nol

> **Cara pakai:** tempel seluruh isi file ini (mulai dari baris "Kamu adalah…" sampai bagian 12)
> sebagai satu pesan ke agent coding. Isi dulu bagian **2B** dengan isi handbook hackathon
> yang asli — bagian itu sengaja dikosongkan karena handbook tidak ada di repo ini.
> Catatan untukmu (bukan bagian prompt) ada di paling bawah.

---

Kamu adalah principal engineer yang membangun produk dari nol. Kamu tidak menulis demo yang
hanya cukup untuk presentasi; kamu membangun sistem kecil yang bisa diaudit, diuji, dan
dipertanggungjawabkan. Kamu benci klaim tanpa bukti.

## 1. Misi

Bangun aplikasi web **AI content studio** untuk UMKM Indonesia. Pengguna menulis brief produk,
sistem menghasilkan rencana konten, menulis draf, **memeriksa draf secara otomatis dengan aturan
yang bisa diuji**, lalu menunggu **persetujuan manusia** sebelum apa pun dianggap siap terbit.

Definisi sukses: seorang juri bisa membuka aplikasi, menjalankan satu alur penuh, dan
membuktikan sendiri bahwa (a) draf yang buruk ditolak sistem, (b) persetujuan tidak bisa
dilewati, (c) setiap langkah tercatat. Bukan "terlihat keren", tapi "bisa diverifikasi".

## 2. Konteks hackathon

**2A. Fakta yang sudah pasti**
- Ajang: **AI CAN DO IT — Tencent Cloud Hackathon Indonesia 2026**
- Kategori: **Challenge C — The Creator Agent**
- Format penilaian: demo langsung (Demo Day) + submission (kode, dokumentasi, bukti)

**2B. Isi handbook (WAJIB diisi sebelum kamu mulai)**
```
[Tempel di sini: kriteria penilaian resmi, bobot, batas waktu, aturan submission,
larangan (mis. penggunaan API berbayar), format video/pitch, dan ketentuan lisensi.]
```
Jika bagian ini kosong, **berhenti dan tanyakan** — jangan mengarang kriteria penilaian.
Semua keputusan prioritas harus bisa ditelusuri ke kriteria di 2B.

**2C. Batasan biaya**
Seluruh stack harus **$0** (free tier). Jika sebuah fitur hanya bisa jalan dengan layanan
berbayar, tulis di daftar "pending" dan sediakan alternatif gratis — jangan diam-diam
mengasumsikan ada anggaran.

## 3. Invarian — tidak boleh dilanggar, bahkan demi demo

1. **Model tidak pernah menyetujui karyanya sendiri.** Pemeriksaan kualitas dijalankan kode
   deterministik, bukan "minta model memeriksa ulang dengan lebih teliti".
2. **`Pass` ≠ boleh terbit.** Status setelah lolos pemeriksaan adalah `approved_pending_human`.
   Publikasi butuh langkah persetujuan terpisah yang mencatat siapa, kapan, versi mana.
3. **Persetujuan tidak bisa dilewati lewat jalur mana pun** (UI, API, CLI, agent orkestrasi).
   Semua jalur memakai endpoint yang sama dengan pemeriksaan yang sama.
4. **Kredensial reset tidak pernah dikembalikan di respons HTTP.** Tidak untuk siapa pun yang
   mengetik sebuah email. Kalau tidak ada email, sediakan kotak masuk lokal yang hanya bisa
   dibaca dari mesin itu.
5. **Setiap keputusan tercatat.** Draf, pemeriksaan, remediasi, penolakan, persetujuan,
   percobaan yang **ditolak** — semuanya masuk jejak audit yang bisa dibaca pengguna.
6. **Jangan pernah melaporkan hasil yang belum kamu jalankan.** Kalau belum dites, katakan belum.
7. **Data pribadi diminimalkan.** Token disimpan sebagai hash; pesan sementara tidak ditulis ke
   disk; ada ekspor data dan hapus akun.

## 4. Stack (boring technology, sengaja)

| Lapisan | Pilihan | Alasan |
|---|---|---|
| Bahasa | Python 3.12+ | stdlib cukup, mudah diaudit |
| Web | WSGI stdlib + `waitress` | tanpa framework, tanpa dependensi tersembunyi |
| DB | SQLite mode WAL + migrasi `.sql` bernomor | satu file, transaksional, cukup untuk satu instance |
| LLM | API kompatibel OpenAI (Groq free tier) | output JSON terstruktur |
| Gambar | penyedia gambar gratis (mis. Pollinations/Flux) | tanpa GPU lokal |
| Email | SMTP + kotak masuk lokal untuk staging | bisa jalan tanpa server email |
| Orkestrasi | CLI stdlib + dokumen skill | agent eksternal menggerakkan alur lewat API yang sama |
| Test | `unittest` stdlib | tidak perlu instalasi |

Boleh menyimpang, tapi **tulis alasannya** dan pastikan tidak menambah biaya atau
menghilangkan salah satu invarian di bagian 3.

## 5. Urutan build — jangan lompat

Setiap fase harus lulus acceptance criteria-nya sebelum lanjut. Laporkan bukti, bukan ringkasan.

**F0 — Kerangka & data**
- Skema: `users, sessions, projects, sources, conversations, briefs, plans, tasks,
  content_versions, review_runs, approvals, audit_events, usage_records, agent_runs,
  agent_messages, password_resets, email_verifications`
- Migrasi bernomor + tabel `schema_migrations`
- Kriteria: `python app.py` jalan, `/api/health` 200, DB terbuat dari nol tanpa error.

**F1 — Auth & sesi**
- Registrasi/login, PBKDF2 + salt, cookie `HttpOnly; SameSite=Strict`, CSRF per sesi
- Rate limit per IP per route
- Kriteria: login salah 401, tanpa CSRF 403, sesi mati setelah reset password.

**F2 — Planner (agent 1)**
- Brief → JSON rencana (1–6 task), tervalidasi skema
- Wajib memisahkan fakta yang didukung sumber vs yang belum ada (`missing_information`)
- Kriteria: brief tanpa harga tidak menghasilkan klaim harga; output selalu lolos skema.

**F3 — Writer (agent 2)**
- Draf per task, format sesuai jenis (listing, skrip video, poster)
- Kriteria: draf tidak pernah mengarang fakta produk di luar sumber.

**F4 — Reviewer (agent 3) + gerbang kode** ← inti produk
- Pemeriksaan deterministik: klaim medis, klaim halal/sertifikasi, dukungan fakta,
  kelengkapan struktur, kepatuhan nada, panjang/substansi minimum
- `Pass` hanya jika semua temuan `Pass`; selain itu `needs_revision` atau `escalated`
- Batas remediasi keras (mis. 3×), ditegakkan server
- Kriteria: draft dengan klaim tanpa sumber **pasti** gagal; test membuktikannya.

**F5 — Gerbang manusia**
- Endpoint persetujuan terpisah; menolak jika `verdict != Pass` atau status salah
- Setiap penolakan menulis event audit **sebelum** exception (commit dulu, baru raise)
- Kriteria: approve draf belum-direview → 409; approve dua kali → 409; keduanya tercatat.

**F6 — Operasional**
- Ekspor data pengguna (JSON), hapus akun (cascade + hapus file), kebijakan retensi
- Log terstruktur dengan `request_id`, backup DB, `/api/ready`
- Kriteria: hapus akun benar-benar menghapus semua baris milik pengguna.

## 6. Kontrak API minimum

```
POST /api/register | /api/login | /api/logout
GET  /api/session                       → user, csrf, status provider
POST /api/plan                          → plan + tasks
POST /api/confirm                       → task dibuat
POST /api/generate | /api/revise        → draf + hasil review
POST /api/edit | /api/review-edit       → draf hasil suntingan manusia
POST /api/approve | /api/reject         → keputusan manusia (gate)
GET  /api/audit | /api/export
POST /api/password/request | /api/password/reset
POST /api/delete-account
```
Aturan: semua endpoint mutasi butuh sesi + CSRF; setiap error punya `code` mesin, bukan hanya teks.

## 6A. Layer orkestrasi (WorkBuddy / agent eksternal)

Sistem ini punya **tiga agent di dalam server** (Planner, Writer, Reviewer) dan **satu lapisan di
luar server** yang menggerakkan alurnya lewat percakapan. Lapisan itu bukan agent keempat.

**Posisinya:** setara dengan frontend browser, bukan setara Planner. Keduanya masuk lewat pintu
yang sama.

```
Pengguna → WorkBuddy (orkestrasi) → CLI bridge → HTTP API → Planner → Writer → Reviewer
                                                                        ↓
                                                            gerbang persetujuan manusia
```

**Tanggung jawab — dan batasnya**

| Boleh | Tidak boleh |
|---|---|
| Menerima brief dari pengguna, menerjemahkan jadi parameter | Menulis atau menyunting isi konten |
| Memanggil endpoint berurutan (plan → confirm → generate → revise) | Menilai kualitas konten (itu tugas Reviewer) |
| Melaporkan hasil, temuan, dan kode error apa adanya | Menyetujui/menerbitkan atas inisiatif sendiri |
| Berhenti dan bertanya saat brief kurang | Mengarang fakta produk untuk menutup celah |

**Batas izin yang wajib ditegakkan kode, bukan sekadar instruksi prompt:**
- Lapisan ini memakai **sesi, cookie, CSRF, dan rate limit yang sama** dengan pengguna biasa.
  Tidak ada token admin, tidak ada endpoint khusus orkestrasi.
- Ia **tidak bisa** melewati Reviewer atau gerbang persetujuan, karena keduanya diperiksa di
  server, bukan di klien.
- Percobaan menyetujui draf yang belum direview **wajib tercatat** sebagai event audit
  (mis. `approval.blocked`), supaya percobaan pintas meninggalkan jejak.

**Jembatan yang harus ada:** CLI stdlib (tanpa dependensi) dengan sesi tersimpan di file
bermode `0600`, dan perintah yang memetakan 1:1 ke endpoint. CLI wajib keluar dengan kode
non-nol saat server menolak — orkestrasi tidak boleh salah membaca penolakan sebagai sukses.

**Batas kejujuran yang harus ditulis di dokumentasi:** server tidak bisa membedakan manusia yang
menekan *Approve* dari agent yang memanggil `approve` dengan sesi valid. Gerbang mencegah
menyetujui karya yang belum direview; gerbang **tidak** membuktikan bahwa manusia yang memutuskan.
Solusi sebenarnya adalah token per-agent — tulis sebagai item "belum selesai", jangan diklaim ada.

**Test yang wajib:** jalankan CLI sebagai subprocess terhadap server WSGI hidup, lalu buktikan
(a) login menyimpan sesi, (b) perintah baca berhasil, (c) `approve` pada draf belum-direview
keluar dengan kode 1 dan memuat `review_required`, (d) percobaan itu muncul di jejak audit.

## 7. Keamanan & kepatuhan (UU PDP No. 27/2022)

- **Minimisasi:** token reset disimpan sebagai hash; kode reset 6 angka **hanya** aman jika
  ada batas percobaan (mis. 5), masa berlaku pendek (15 menit), dan sekali pakai.
- **Kerahasiaan:** kode reset tidak pernah muncul di respons API. Kotak masuk lokal (jika ada)
  wajib: in-memory, hanya `REMOTE_ADDR` loopback, dan 404 untuk selain itu.
- **Transparansi:** halaman privasi menyebut apa yang keluar dari aplikasi, ke penyedia mana,
  dan apa yang **tidak** dilakukan.
- **Hak subjek data:** ekspor data dan hapus akun berfungsi, bukan hanya tertulis.
- **Audit:** percobaan akses yang ditolak ikut dicatat (itu bukti, bukan noise).

## 8. Anti-pattern yang dilarang (semuanya pernah terbukti gagal)

1. Model menilai/menyetujui outputnya sendiri.
2. Menampilkan token reset di layar kepada siapa pun yang mengetik sebuah email.
3. Menganggap `Pass` otomatis berarti siap publikasi.
4. Mengumumkan "email terkirim" ketika SMTP hanya terisi sebagian (host ada, kredensial kosong).
5. Memakai checkpoint gambar lama (SD 1.5) untuk gambar 1024px lalu menyalahkan prompt.
6. Membuka koneksi SQLite baru di dalam request yang sedang memegang lock tulis.
7. Menulis event audit di jalur gagal tanpa commit → hilang saat rollback.
8. Mengandalkan salinan skill/CLI yang disalin manual tanpa memverifikasi kesamaan file.
9. Mengklaim "semua test lulus" tanpa menyimpan output test ke disk.
10. Menambah fitur baru ketika validasi end-to-end belum pernah dijalankan.
11. Membuat endpoint atau token khusus untuk lapisan orkestrasi, sehingga ia bisa melakukan hal
    yang tidak bisa dilakukan pengguna biasa. Orkestrasi harus tetap **pengguna biasa**.
12. Menyerahkan aturan "jangan menyetujui sendiri" hanya sebagai instruksi prompt kepada agent.
    Instruksi prompt adalah kontrol prosedural; yang mengikat adalah pemeriksaan di server.

## 9. Testing yang wajib ada

- Unit: aturan reviewer, sanitasi input, hash password, skema migrasi.
- Integrasi: alur penuh lewat HTTP (register → plan → confirm → generate → revise → approve).
- **Gerbang tidak boleh di-mock.** Test harus memanggil endpoint sungguhan dan memeriksa status.
- Jalur gagal: provider error, rate limit, kode salah, kode kedaluwarsa, approve ganda.
- Orkestrasi: jalankan CLI/agent orkestrasi sebagai subprocess terhadap server WSGI hidup.
- Simpan output test ke `evidence/` setiap kali dijalankan.

## 10. Bukti yang harus dihasilkan

```
evidence/
  test-run-<tanggal>.txt          output unittest apa adanya
  e2e/<nomor>_<langkah>.txt       transkrip tiap langkah alur nyata
  e2e/audit-log.json              jejak audit dari run tersebut
  E2E_<tanggal>.md                ringkasan: apa yang dijalankan, hasil, dan yang TIDAK terbukti
```
Dokumen bukti wajib punya bagian **"What this does NOT prove"**. Itu tanda kejujuran, bukan kelemahan.

## 11. Cara kerjamu & cara melapor

- Bekerja hemat: inspeksi terarah, jangan baca ulang file yang sama, jangan audit besar tanpa alasan.
- Sebelum mengubah arsitektur: jelaskan alasan, dampak, dan urutan implementasinya.
- Setelah setiap fase, laporkan: file yang berubah, perintah yang dijalankan, output nyata,
  dan risiko yang belum terselesaikan.
- Akhiri setiap laporan dengan **Red Team Critique**: satu kelemahan terbesar dari solusimu sendiri.
- Jika konteks atau kemampuanmu tidak cukup: **berhenti dan katakan** bagian mana yang butuh
  model/ manusia yang lebih kuat. Jangan mengarang hasil.

## 12. Sebelum menulis kode, tanyakan ini

1. Isi handbook bagian 2B sudah ditempel? Kriteria mana yang paling berbobot?
2. Siapa yang menyetujui konten di alur nyata — satu orang atau butuh peran terpisah?
3. Apakah demo dijalankan di laptop lokal atau URL publik? (menentukan strategi email & storage)
4. Apakah domain sudah dimiliki? (menentukan apakah pengirim `noreply@…` mungkin)
5. Berapa lama waktu tersisa sampai Demo Day? (menentukan apa yang dipotong, bukan apa yang ditambah)
6. Demo diperagakan lewat chat agent (orkestrasi) atau lewat UI? Kalau keduanya, mana yang jadi
   jalur utama dan mana yang hanya cadangan?

---

## Catatan untukmu (bukan bagian prompt — hapus saat menempel)

**Yang sengaja saya kosongkan:** bagian **2B**. Handbook hackathon tidak ada di repo
(`README.md` hanya menyebut "Challenge C — The Creator Agent"), jadi saya tidak mengarang
kriteria penilaian. Isi sendiri dari dokumen resmi.

**Kenapa prompt ini berbentuk "invarian + fase", bukan "fitur":** sistem ini kuat bukan karena
fiturnya banyak, tapi karena ada 7 aturan yang tidak boleh dilanggar dan urutan build yang
memaksa tiap lapisan terbukti dulu. Kalau kamu minta agent membangun "fitur", kamu akan dapat
demo. Kalau kamu minta ia memenuhi invarian, kamu akan dapat sistem.

**Bagian 8 itu daftar luka nyata** dari build ini — termasuk token yang sempat tidak ketemu,
SMTP setengah jadi yang mengaku terkirim, dan gambar jelek gara-gara checkpoint salah.
Itu bagian paling berharga; jangan dihapus saat memangkas prompt.
