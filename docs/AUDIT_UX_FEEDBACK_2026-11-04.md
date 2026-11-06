# Audit 13 feedback UX RekaRasa.ai

Tanggal: 4 November 2026. Scope: audit kode aktual dan observasi login di browser. Tidak ada perubahan aplikasi, konfigurasi, kredensial atau data pengguna. Hanya laporan ini ditambahkan.

## Ringkasan

Prioritas terbesar adalah brief yang belum aman saat pindah menu, pengelolaan lampiran, dan kejelasan langkah berikutnya. Font, warna biru dan animasi adalah arah desain; bukan penyebab utama alur gagal. Nama, logo dan Planner dipertahankan sesuai feedback.

## Metode dan batas bukti

- Membaca frontend, CSS, HTML, handler autentikasi, upload, asset API, navigasi, serta pola tes yang tersedia.
- Browser login aktif: memeriksa computed font, warna, layout password, keberadaan elemen animasi dan error CSP. Tidak login menggunakan kredensial baru.
- Tidak menjalankan test suite, upload file, email, model atau GPU dalam audit ini.
- Hasil tes terdahulu tidak diklaim sebagai hasil pengujian perubahan UX ini.
- Tidak mereproduksi kegagalan upload pengguna karena file, status sesi dan respons request yang gagal belum tersedia. Diagnosis upload di bawah membedakan fakta kode dari kemungkinan penyebab.

## Matriks feedback

| No. | Feedback | Kondisi aktual dan bukti | Penilaian / tindakan minimum |
|---|---|---|---|
| 1a | Font Poppins | Stack body DM Sans/Arial; heading Manrope/DM Sans; beberapa aksen Georgia. Browser tidak memiliki webfont terdaftar. Tidak ada font loader pada HTML. | Poppins belum tersedia. Pilih keluarga utama yang konsisten; lebih baik aset lokal dengan fallback. Logo tetap. |
| 1b | Password jangan terlalu panjang | Minimum 12, maksimum 256, pada login/register/reset. Show password dan autocomplete sudah ada. | Ini kebijakan autentikasi, bukan sekadar label UI. Jangan turunkan sepihak atau menambah OTP wajib untuk mengompensasi. Rapikan bantuan dan layout dahulu; kebijakan panjang dibahas terpisah sebelum perubahan. |
| 2 | Warna elegan, pilihan biru | Warna utama #087443; latar hijau muda/ivory dengan gradien. Browser mengonfirmasi gradient aktif. | Ketidakcocokan persepsi brand adalah feedback desain valid. Usulkan biru sebagai warna antarmuka dengan green logo tetap. Uji konsistensi dan kontras sebelum rollout. |
| 3 | Nama company oke | RekaRasa.ai dipakai di brand dan judul aplikasi. | Pertahankan. Tidak perlu penamaan ulang. |
| 4 | Logo oke | Logo asli digunakan di login/sidebar. | Pertahankan aset, proporsi dan keterbacaannya; jangan recolor tanpa keputusan desain. |
| 5 | Animasi creator saat login | Login berupa branding dan form; tidak ditemukan elemen video/Lottie atau animasi creator. Terdapat transisi UI dan aturan reduced motion. | Opsional setelah alur inti. Jika dibuat, gunakan animasi ringan yang membantu menjelaskan brief menjadi output, tidak menghalangi login, dan menghormati reduced motion. |
| 6 | Dashboard seperti chat, opsi lebih jelas | Home memakai hero, task list, library proyek dan catatan aturan. New chat masih berupa form dengan folder, audience, age, channel, tone, deadline dan output preferences. | Nama New chat menjanjikan percakapan, tetapi interaksi adalah form. Jadikan satu composer utama dan aksi lanjutkan pekerjaan; rincian opsional dibuka bertahap. Backend yang ada dapat dipertahankan. |
| 7 | Agent sebagai juru petunjuk | Rara/Reka/Raya sudah bernama dan memiliki tanda peran. Status serta pesan error ada, tetapi belum ada pemandu konsisten lintas halaman. | Gunakan petunjuk berbasis status nyata: isi brief, periksa rencana, revisi, beri approval. Tidak perlu agent baru atau panggilan model setiap pindah menu. |
| 8 | Bahasa friendly Inggris?Indo | Sebagian besar UI Inggris; bantuan Excel Indonesia; beberapa pesan teknis seperti project policy, image provider dan status hadir di alur. | Gunakan Bahasa Indonesia sebagai bahasa utama, istilah familiar seperti caption/brief tetap. Pilihan bahasa global dapat menyusul; jangan mencampur tanpa pola. Aturan lengkap tetap di detail. |
| 9 | Brief tidak hilang saat buka fitur lain | state.briefDraft diisi pada submit Plan. oninput brief hanya memperbarui penghitung. navigate mengganti halaman tanpa menangkap form. Restore memakai draft yang sudah ada saja. Tidak ditemukan sessionStorage/localStorage untuk draft. | Bug berprioritas tinggi. Tangkap seluruh isian saat berubah dan sebelum navigasi. Isolasi draft per akun/proyek. Ketahanan setelah refresh adalah cakupan tambahan yang harus eksplisit. |
| 10 | Belum bisa upload gambar | Handler memilih file dan POST /api/attachments tersedia; PNG/JPG/JPEG max 5 MB, foto disimpan pada project_assets; owner check dan preview endpoint tersedia. Folder wajib dipilih dulu. HEIC/WebP/PDF tidak didukung pada jalur ini. | Fitur ada; keberhasilan pada file pengguna belum diuji. Periksa pesan error, format, ukuran, sesi dan folder. Ada mismatch batch: UI menerima 20 file, rate limit backend 8 request/60 detik; katalog membutuhkan preview+confirm. |
| 11 | Upload tidak bisa dibatalkan/diganti | Foto langsung dipersist saat POST, tidak melalui preview confirmation seperti katalog. Tidak ditemukan AbortController/cancel antrean atau endpoint archive/remove foto. Hasil upload tampil di DOM, tidak dihidrasi ulang dari project.assets. Sumber teks punya archive, foto belum. | Gap terkonfirmasi. Bedakan batal sebelum tersimpan, melepas lampiran dari brief, dan mengarsip aset proyek. Penggantian perlu memperbarui referensi filename; aset yang dipakai revisi lama harus tetap dapat diaudit. |
| 12 | Audience / age range | Audience berupa teks opsional; age input+datalist menerima pilihan dan rentang custom. Age digabung menjadi Target age pada audience sebelum API. Validasi khusus rentang tidak terlihat. | Fitur ada tetapi perlu penjelasan fungsi. Tetap opsional; boleh diinferensikan dari brief. Usia target bukan statistik pengguna platform. Beri validasi ringan atau contoh yang jelas tanpa memaksa ulang input. |
| 13 | Planner oke | Satu brief ke task, preferensi opsional, editor rencana dan konfirmasi tersedia. Auto-confirm masih aktif untuk brief tanpa catalog_source_ids; brief katalog memakai proposal terpisah. | Pertahankan Planner. Ada ketidakkonsistenan: teks menjanjikan review rencana, tetapi sebagian brief auto-confirm. Tinjau transparansi konfirmasi tanpa membangun ulang Planner. |

## Temuan tambahan

### A. Layout password diblokir CSP

Browser melaporkan dua pelanggaran inline style di authPage. Wrapper input password meminta display:flex lewat atribut style, tetapi computed display adalah block. Pindahkan aturan ke class CSS; jangan melonggarkan CSP.

### B. Foto dan sumber fakta dicampur dalam petunjuk jumlah

updateBriefSourceHint menghitung project.sources saja. Foto tersimpan pada project.assets. Karena itu jumlah attached source(s) dapat tetap nol walau foto sudah diunggah. Bedakan sumber fakta dan foto secara ringkas agar pengguna tidak mengira upload gagal.

### C. Upload belum bertahan secara visual saat pindah halaman

GET /api/projects sudah membawa assets, tetapi brief tidak membangun ulang daftar upload dari data tersebut. File dapat masih ada di database sementara daftar lampiran di layar kosong. Ini masalah rehidrasi UI, bukan otomatis kehilangan file.

### D. Rate limit dan antrean batch tidak konsisten

Delapan request per menit dihitung per pengguna dan route. UI menerima 20 file; katalog memakai dua request per file. Batch besar yang cepat berpotensi menghasilkan 429. Menambah kapasitas tanpa membedakan operasi murah/upload dan operasi AI bukan solusi yang sudah dievaluasi. Selaraskan batas UI, antrean dan pesan error.

## Gap pengujian

Pencarian pada berkas test*.py dan frontend probe tidak menemukan referensi langsung ke /api/attachments, uploadBriefAttachments, briefDraft atau parse_catalog. Belum ditemukan tes khusus untuk kehilangan draft sebelum submit, upload lampiran katalog/foto dan pemulihan daftar lampiran. Ini hasil pencarian cakupan kode, bukan pengukuran coverage runtime.

## Urutan perbaikan yang disarankan

1. P0: Simpan draft selama mengetik dan sebelum navigasi; jangan menghapus draft hanya karena membuka menu lain.
2. P0: Pulihkan daftar foto dari backend; tampilkan status per file, retry dan error yang jelas; selaraskan batas batch.
3. P0: Batalkan file yang belum tersimpan; sediakan arsip/ganti aset yang aman untuk foto tersimpan dengan audit dan owner check.
4. P1: Home/composer berpusat pada brief dan pekerjaan yang dapat dilanjutkan; guide memakai status nyata dan satu aksi utama.
5. P1: Rapikan bahasa serta Audience/age; sederhanakan pilihan output tanpa mengurangi kemampuan Planner.
6. P1: Perbaiki class layout login yang diblokir CSP; pastikan password manager/paste tetap nyaman.
7. P2: Terapkan Poppins dan arah biru lewat token desain yang konsisten. Pertahankan nama serta logo. Tidak perlu mengganti framework.
8. P3: Pertimbangkan animasi creator setelah tugas inti dapat diselesaikan pengguna tanpa kebingungan.

Urutan ini adalah prioritas produk, bukan klaim semua langkah sudah diimplementasikan.

## Kriteria penerimaan sebelum menyatakan selesai

- Ketik brief, audience, usia, tone, deadline dan preferensi; buka Planner/Projects lalu kembali: isi sama.
- Tentukan secara terpisah apakah draft juga harus selamat setelah refresh, tab ditutup dan pergantian akun. Tidak boleh bocor antar akun.
- Upload PNG/JPEG valid, file format tak didukung, file >5 MB, batch besar, file duplikat dan sesi habis: hasil per file dapat dimengerti.
- Setelah pindah menu/refresh, foto tersimpan tampil lagi. Counter sumber fakta tidak menyamakan foto sebagai bukti klaim.
- Cancel sebelum upload tidak membuat asset; ganti setelah tersimpan mempertahankan riwayat aset yang sudah dipakai.
- Satu CTA utama tiap tahap: buat rencana, koreksi rencana, lihat draft, revisi/approve, salin caption atau buat visual.
- Pending/failed content tidak berubah menjadi approved karena perbaikan UI. Approval, ownership, audit dan batas revisi tetap berlaku.
- Font sungguh dimuat, bukan hanya disebut dalam stack. Warna dan fokus dicek kontrasnya. Reduced motion tetap dihormati.

## Bukti kode

- [Navigasi dan Home](../static/app.js): navigate, renderPage, homePage.
- [Login dan brief](../static/app.js): authPage, newPage, uploadBriefAttachments, updateBriefSourceHint, briefAudience, wrapper pemulihan briefDraft.
- [CSS](../static/styles.css) dan [HTML](../static/index.html): font, palette, CSP-related layout, reduced motion.
- [Backend](../app.py): register/login/reset, rate_limit, GET /api/projects, GET /api/project-asset, POST /api/attachments, archive sumber.
- [Batas berkas](../catalog_import.py): decode_file dan image_dimensions.
- Tes tersedia: [backend](../test_app.py), [workflow visual](../test_visual_content.py), [aksi proyek](../test_project_actions.py), [frontend probe](../probe_frontend.js). Tidak dijalankan dalam audit ini.


## Implementasi setelah audit - 4 November 2026

### Perubahan yang diterapkan

- Home menjadi composer brief dengan pekerjaan yang dapat dilanjutkan. Arahan Rara/Reka/Raya mengikuti tahap nyata; bukan indikator agent sedang bekerja.
- Brief disimpan dalam sessionStorage per akun dan tab. Brief, folder, audience, usia, deadline, tone, serta preferensi dipulihkan setelah navigasi dan refresh. Logout menghapus draft lokal. Menutup tab bukan jaminan penyimpanan permanen.
- Konteks tambahan dilipat sebagai pilihan opsional. Rentang usia bebas seperti 17-35 diterima; rentang terbalik ditolak. Tone tetap suara brand, kanal menentukan bentuk output.
- Planner tetap meminta konfirmasi sebelum pembuatan draft. Aturan review dan approval tidak diubah.
- Upload memiliki antrean/status per file, Batal, Coba lagi, Ganti, dan Arsipkan foto. Foto tersimpan dipulihkan dari backend, terpisah dari hitungan sumber fakta. Ganti mempertahankan nama logis untuk relasi image_filename katalog.
- Arsip mempertahankan byte foto asli dan riwayat; route original tetap memeriksa pemilik. Migrasi hanya menambah tabel archived_assets. Upload mendapat batas tersendiri 40 request/menit; batas request model tidak dinaikkan.
- Poppins disimpan lokal beserta lisensi OFL. Layout password menggunakan class CSS; Show/Hide dan password manager dipertahankan. Minimum 12 karakter tetap berlaku.
- Login memakai animasi dekoratif satu kali dengan reduced-motion. Warna mengikuti logo terbaru indigo-violet-pink. Bahasa alur utama dirapikan; rincian teknis dan sebagian halaman lanjutan masih berbahasa Inggris.

### Bukti validasi aktual

- Empat tes AttachmentUXTests dijalankan spesifik: 4 lulus.
- python scripts/run_tests.py: 165 tes, semuanya lulus, 40.158 detik. Termasuk FreshGlow, approval, revisi, owner boundary, workflow visual, serta empat tes attachment/font baru. Provider eksternal dan SMTP diisolasi.
- probe_frontend.js: seluruh pemeriksaan calendar/list/diff, pemulihan draft, isolasi akun, dan validasi usia lulus melalui runtime Node bawaan VS Code.
- Pemeriksaan syntax static/app.js: exit 0. git diff --check: tidak ada error whitespace; terdapat pemberitahuan normalisasi CRLF pada dua berkas yang sudah berubah sebelumnya.
- Browser pada server fixture 8014 dengan SQLite sementara, SMTP nonaktif, dan fake Planner: brief bertahan sesudah navigasi dan refresh; font Poppins benar-benar dimuat; penggantian foto menyisakan satu foto aktif dengan nama logis sama; pembatalan request menghasilkan ERR_ABORTED dan status Tidak diunggah.
- Browser pada lebar 390, 768, dan 1440 piksel: scrollWidth tidak melebihi viewport. Ini pemeriksaan overflow, bukan audit aksesibilitas menyeluruh.
- Tidak memakai Groq, GPU, email sungguhan, atau database pengguna untuk validasi tersebut.

### Batas dan aktivasi

Backend lama di port 8000 belum dapat direstart oleh sesi ini: Windows menolak penghentian proses. Pengguna perlu menghentikannya dari terminal sendiri dan menjalankan python app.py kembali; migrasi berjalan lewat mekanisme aplikasi. Frontend yang sudah tersaji tidak membuktikan backend baru aktif.

Belum diuji: pengiriman email nyata, generation live Groq/ComfyUI, seluruh screen reader, semua perangkat/browser, cancel tepat sesudah server commit, dan pemulihan draft sesudah tab ditutup. Cancel tidak menjanjikan rollback file yang sudah tersimpan; foto demikian tetap dapat diarsipkan. Tidak ada perubahan provider, kredensial, atau integrasi publikasi.


## Follow-up: Home prompt starters and signup OTP

The user subsequently requested English UI, logo-aligned colors, a Home menu of prompt examples, a minimum six-character password containing a letter and a number, and OTP verification during account creation. This supersedes the earlier decision to keep a 12-character minimum.

- Home now offers six prompt starters: marketplace, Instagram, TikTok/Reels text script, WhatsApp broadcast, poster/static ad, and campaign bundle. Clicking opens the brief with an editable example and matching preferences. Existing text requires confirmation before replacement; other draft details are retained. No generation runs automatically.
- Registration and password reset enforce 6-256 characters with at least one ASCII letter and one digit on client and server. Login accepts existing passwords without retroactively applying the new composition rule.
- Registration returns HTTP 202 and a challenge, without a session. Only POST /api/register/verify creates the account and session after a valid six-digit OTP. Pending password/code/challenge are hashed; no plain password or code is stored in SQLite. A challenge binds verification to the requesting signup form. Codes expire after 15 minutes, lock after five wrong attempts, and can be resent after 60 seconds subject to the existing credential rate limit.
- Migration 014 adds pending_registrations. Existing accounts, verification links, projects and approval records are retained. Registration does not depend on the legacy EMAIL_VERIFICATION_REQUIRED flag. Verified account creation records account.created, email.verification_sent and email.verified events.
- Signup fails with a delivery error when email cannot be sent. Loopback development may use the existing Local Mailbox, explicitly labelled as local preview. No SMTP credentials or environment configuration were changed.
- The existing test registration helper now captures fake delivery and completes OTP verification instead of assuming immediate account creation. Existing workflow assertions remain. No test suite was executed in this follow-up; the previous 165-pass result predates these authentication changes.

Actual manual validation used a separate SQLite database and local preview on port 8014: six-character mixed password accepted; letters-only password rejected (400); registration pending (202) with no authenticated session; successful OTP led to authenticated Home; immediate resend rejected (429); five wrong codes rejected and the correct code subsequently rejected as locked (400). Instagram starter populated the brief, Instagram channel and social-content preference. All six cards rendered without horizontal overflow at 390, 768 and 1440 pixels. Python/JavaScript syntax checks and scoped git diff --check passed.

Not validated: real SMTP delivery, automated regression suite after the auth contract change, OTP expiry after waiting 15 minutes, simultaneous registration requests, and live generation. Browser emitted an inline-style CSP warning while parsing the local mailbox HTML for manual verification; no CSP policy was relaxed. Backend port 8000 still needs a user-owned restart to load the new routes and migrations.


## Conversational brief - 5 November 2026

Implemented brief -> Rara understanding -> natural-language adjustment -> existing output editor -> explicit plan confirmation.

- The initial composer keeps uploads and project selection with the brief. Audience, age, tone, deadlines and output preferences remain available in a closed optional section. Upload help is collapsed. Existing file validation, cancel/replace/archive and draft persistence remain wired to their existing handlers.
- The understanding card shows the actual Planner objective, audience, constraints, proposed outputs, deadline, grounded facts, source names and essential missing information. It distinguishes planning from draft creation and does not claim photo perception.
- POST /api/plan additionally accepts revise_plan_id, plan_revision, adjustment, optional edited_tasks and deadline. It only updates a plan owned by the session user while it is proposed. Latest direction reaches the Writer via the persisted brief/audience. This is not a separate chat model or orchestrator.
- Each successful adjustment updates the existing plan/brief, appends a user/assistant message pair and records planner.adjusted. A revision check and conditional update reject stale or confirmed-plan edits. Existing catalog coverage and grounding checks remain in the Planner path. No database migration or provider change was required for this feature.
- The existing editor still controls title, format, channel, angle, goal and deadline. Its back action returns to understanding without another inference. Edited tasks are included when asking Rara for a further adjustment.

Manual validation used fake Planner services and a temporary SQLite database on 8014/8015, without live text/image providers or real email:

1. Initial brief produced an understanding card with two outputs and zero tasks.
2. A student/caption-only adjustment updated audience and deliverables, retained one proposed plan and one conversation, and created no tasks.
3. Simulated model failure returned 502; the stored plan remained at revision 1. Retry advanced it to revision 2 with no duplicate plan or conversation.
4. A fresh read-only SQLite connection observed one conversation, one brief, one plan, six messages, two planner.adjusted events and zero tasks before confirmation. The persisted Writer brief included the latest direction and audience was Students.
5. Calling the existing confirmation endpoint explicitly created one planned task. Further adjustment was rejected with 409. Writer/Reviewer execution was not invoked by this manual check.
6. The final edited_tasks branch retained a human-edited title through refinement; an outdated revision was rejected with 409.
7. Understanding layout had no horizontal overflow at widths 390, 768 and 1440. The existing output editor remained reachable with editable fields and an explicit confirmation button.
8. Python and JavaScript syntax checks and scoped git diff --check passed.

Limits: no automated suite was run in this follow-up; the prior 165-pass result is not a result for these changes. Live Groq quality, catalog refinement coverage, simultaneous requests, full Writer/Reviewer/approval regression and upload regression were not exercised here. Fake-provider output only proves plumbing and persistence. Port 8000 requires restart to load the changed backend; refresh alone only loads frontend changes.


### Visual correction: initial chat composer

The earlier conversational change still presented a form-like initial page. It has now been replaced visually with a Rara welcome message and one message composer. Attach, project selection, Preferences and Send share its toolbar. Optional audience/age/tone/channel/output/deadline controls move into a native modal dialog inside the same HTML form, preserving payload collection and existing upload/draft handlers. A badge shows active preferences; modal close restores focus, and an invalid hidden preference opens the dialog for correction. No backend change was needed in this follow-up.

Manual browser preview with synthetic state: composer had no horizontal overflow at 390/768/1440; Preferences opened as a native modal; values survived closing; captured request carried audience age, tone and Instagram channel with auto_confirm=false and reached the understanding card via a mocked response. A reversed age range was rejected and reopened Preferences. The captured request was intercepted: no user database or model call was involved. JavaScript syntax and scoped diff whitespace checks passed. Automated suite and live inference were not run.


### Attachment cancellation and removal

Queued/running files now use the explicit Cancel upload label. Failed/canceled rows can be dismissed. Saved photos use Remove (the existing archival endpoint); saved Excel/CSV files now also have Remove, covering all their grouped fact sources. The confirmation explains that removal affects project sources for future work and retains history.

The existing /api/remove-source route accepts a bounded source_ids list as well as the legacy source_id. It resolves every ID under the current owner and a single project before writing, then archives the group in one transaction. Frontend cleanup removes remembered catalog IDs and saved queue rows so a removed file does not reappear as Catalog saved.

Manual browser validation on a temporary database: queued cancellation changed status to canceled; a mixed-owner batch returned 404 with both owned sources unchanged; removing a two-group catalog cleared both active sources, catalog UI and remembered IDs; the original source remained readable. A new read-only DB connection found all three original sources retained, two archival rows and two source.archived audit events. Python/JavaScript syntax and scoped whitespace checks passed. No automated suite, real provider or user database was used. Cancellation after a server commit still requires Remove; it does not promise an upload rollback.


### New chat layout cleanup

Saved project files were previously embedded in the composer with a capped scroll area, which cut off photo rows. They now live in a separate native Project files disclosure below the composer, closed initially and without internal scrolling when opened. Current upload/error/cancel rows use a separate visible activity region, so Cancel upload remains available while saved files are collapsed. Existing file actions and backend handlers are retained.

The Send button inherited a 180px minimum width from the original form. Its chat-specific rule now resets that minimum and aligns label/icon without spreading them. Rara's heading aligns with the composer edge. Browser preview with eight fact groups in two catalogs and four photos showed a collapsed six-file disclosure, no files inside the message card, aligned heading, no horizontal overflow at 390/768/1440, and a Send width of 75-81px. No user data or provider was changed. JavaScript syntax and scoped whitespace checks passed; no automated suite or live generation was run.


### Staged attachments and project-only saved files (supersedes the disclosure above)

New chat now displays only temporarily selected attachments as compact chips with a remove button. Selecting or removing a pending file makes no API call. Send uploads the remaining files before requesting a plan. An upload failure or cancellation stops planning; failed files can be removed or explicitly retried. Saved project files are absent from New chat; a Project details shortcut opens their management view.

Project details groups JSON catalog sources by workbook filename and displays saved original photos. Content-group previews match image_filename against exact saved filenames within the same project; missing or ambiguous matches are disclosed rather than guessed. Removing a source also cleans its remembered draft source ID.

Manual browser preview used synthetic state and a replaced API function, with no database writes or inference. Two selected files made zero requests; removing the first left one chip and zero requests; Send then called attachment upload for only the remaining file followed by planning. A simulated failed upload blocked planning and its chip was removable. Project rendering showed one catalog group, one photo and the expected original-photo link. No horizontal overflow appeared at 390, 768 or 1440px. JavaScript syntax and scoped diff whitespace checks passed. No automated test suite or live provider was run.

The existing process on port 8000 still serves an older imported backend: its session response lacks the current email_delivery field and new font routes return 404. Restarting that backend is required for newly implemented routes, including archived-photo removal. Frontend removal of a selected, unsent attachment needs no such route.
