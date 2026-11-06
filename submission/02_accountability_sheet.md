# Accountability Sheet — RekaRasa.ai

**Dokumen penyerahan Challenge C · Bertanggung jawab: Tim RekaRasa.ai · Versi: 2026-11-04**

Lembar ini menjelaskan secara transparan cakupan tanggung jawab agent RekaRasa.ai
supaya juri dan penguji memahami dengan tepat apa yang sistem lakukan, apa yang
tidak dilakukannya, dan di mana keputusan hukum akhir berada. Dokumen ini
mengubah keterbatasan menjadi bukti maturitas tata kelola AI: sebuah sistem yang
menyatakan batasnya sendiri lebih dapat dipercaya daripada yang mengklaim
menyelesaikan segalanya.

## 1. Cakupan Batas Kepatuhan Hukum (Legal Compliance Disclaimer)

Verifikasi yang dilakukan RekaRasa.ai saat ini beroperasi pada tingkat
**pencocokan aturan tekstual (*rulebook-based matching*)** dan **pangkalan data
referensi lokal**, bukan otorisasi hukum resmi dari instansi pemerintah. Dengan
kata lain, sistem memeriksa apakah draf konten memenuhi aturan proyek
(`DEMO-*`), pola klaim terlarang, dan apakah nomor registrasi BPOM / sertifikat
halal BPJPH yang dikutip muncul di pangkalan data tiruan lokal
(`data/cert_registry_mock.csv`). Sistem **tidak** melakukan:

- pencarian langsung ke pangkalan data resmi BPOM (pom.go.id) atau BPJPH
  (bpjph.halal.go.id);
- verifikasi notifikasi kosmetik secara *real-time* terhadap server BPOM;
- konfirmasi keabsahan sertifikat halal terhadap register BPJPH;
- penilaian hukum pasal-demi-pasal terhadap PerBPOM 18/2024, UU 8/1999, atau
  peraturan sektoral lainnya.

Referensi regulasi di `governance/references.json` adalah **rujukan editorial
yang diparafrasekan**, bukan temuan pelanggaran statutory otomatis. Sebuah
`Pass` dari Reviewer berarti draf memenuhi aturan proyek dan bukti yang
dilampirkan mendukung klaimnya — bukan sertifikasi legal bahwa konten tersebut
patuh sepenuhnya terhadap hukum yang berlaku.

## 2. Posisi Agent: *First-Line Compliance Filter*

RekaRasa.ai dirancang sebagai **penyaring lini pertama (*first-line compliance
filter*)** yang membantu kreator meminimalkan risiko pelanggaran sebelum konten
dipublikasikan. Tiga agen (Planner, Writer, Reviewer) mengusulkan; kode
deterministik di `save_review()` yang memutuskan; manusia yang menyetujui.
Model tidak pernah menjadi kata akhir.

Tugas agent pada lapisan ini adalah:

| Lapisan | Tugas | Bisa diakali? |
|---|---|---|
| **Model** (Groq) | Mengusulkan temuan dan draf | Ya — komponen ini diasumsikan bisa salah |
| **Kode** (`save_review`) | Memutuskan apakah temuan valid | Tidak — tidak dari klien mana pun |
| **Verifikasi sertifikat** | Memeriksa nomor BPOM/Halal di registri lokal | Tidak — deterministik |
| **Manusia** | Menyetujui publikasi | Itulah intinya |

Persetujuan akhir hukum tetap berada di tangan **Penanggung Jawab / Tim Legal**
perusahaan. Agent tidak menggantikan fungsi hukum; agent memastikan bahwa saat
konten sampai ke tim legal, masalah-masalah yang bisa dideteksi secara tekstual
sudah disaring.

## 3. Apa yang diverifikasi secara deterministik

Berikut adalah pemeriksaan yang berjalan di kode, bukan di prompt, dan dapat
diaudit ulang oleh siapa pun yang membaca `save_review()`:

1. `rule_id` yang tidak ada di registry proyek tidak dapat mendukung `Pass`.
2. `source_id` yang tidak dilampirkan ke proyek ini tidak dapat mendukung `Pass`.
3. `Pass` pada aturan faktual wajib menyebut sumber yang menyatakan fakta itu.
4. Aturan yang tidak diberi temuan oleh Reviewer dicatat `Needs Evidence`,
   bukan diam-dulu sebagai `Pass` senyap.
5. Klaim penyembuhan penyakit atau klaim halal tanpa dokumentasi ditangkap oleh
   *regex guard* meskipun Reviewer mengatakan `Pass`.
6. Nomor BPOM (`NA…`) dan sertifikat halal BPJPH (`ID…`) yang dikutip di draf
   diverifikasi terhadap `data/cert_registry_mock.csv`; nomor yang kedaluwarsa,
   dicabut, atau tidak terdaftar menambah temuan `Fail`.
7. Setiap `Pass`/`Fail` wajib memiliki `document_id`, `span_start`, `span_end`
   — verdict tanpa lokasi tidak dapat tersimpan (*evidence binding*).
8. Draf di bawah batas karakter format dan draf tanpa blok wajib (TITLE,
   DESCRIPTION, HEADLINE, BODY, CTA) tidak dianggap *deliverable*.

## 4. Apa yang TIDAK diverifikasi

- **Tidak ada OCR/vision compliance** pada gambar dasar. Manusia memeriksa gambar
  dan teks render sebelum approval visual.
- **Tidak ada verifikasi resmi BPOM/BPJPH.** Pangkalan data sertifikat adalah
  tiruan lokal (`cert_registry_mock.csv`).
- **Tidak ada integrasi publikasi** ke platform (TikTok, Instagram, Marketplace).
  Copy melewati Reviewer; publikasi tetap manual.
- **Tidak ada penilaian statutory pasal-demi-pasal.** Referensi regulasi adalah
  konteks editorial, bukan temuan pelanggaran hukum otomatis.
- **Tidak ada penilaian semantik *entailment*.** Validasi klaim memeriksa
  identitas dan lokasi sumber, bukan pembuktian bahwa sumber tersebut secara
  semantik menyiratkan klaim.
- **Klasifikasi `verdict_basis`/`instrument_id` pada `rule_registry` belum
  diisi.** Penegakan instrumen POLICY ada tetapi dorman sampai aturan
  diklasifikasikan — keputusan produk/legal yang belum tersedia.

## 5. Maturitas Tata Kelola AI

Pernyataan batas ini bukan kelemahan; ini adalah bukti maturitas. Sistem yang
menyatakan dengan jelas apa yang tidak dapat dilakukannya:

- **Transparansi (SE Menkominfo 9/2023):** operator dan pengguna tahu
  persis cakupan dan batas agent.
- **Akuntabilitas:** verdict memiliki `rule_id`, `document_id`, dan span —
  setiap keputusan dapat ditelusuri ulang.
- **Keamanan & privasi (UU 27/2022):** data pengguna terisolasi per akun;
  tidak ada kredensial yang dibundle.
- **Human-in-the-loop:** tidak ada publikasi otomatis; gerbang approval manusia
  adalah titik kontrol akhir.

Mengubah keterbatasan menjadi pernyataan eksplisit adalah praktik *Responsible
AI* yang diperingatkan oleh SE Menkominfo 9/2023: agent AI harus jujur tentang
kapabilitasnya, dan manusia harus tetap bertanggung jawab atas keputusan
akhirnya.

## 6. Penerimaan dan Persetujuan

Dengan menggunakan RekaRasa.ai, operator dan kreator memahami bahwa:

- Verifikasi tekstual dan sertifikat lokal adalah **penyaring awal**, bukan
  persetujuan hukum.
- **Penanggung Jawab / Tim Legal** perusahaan tetap menjadi otoritas akhir untuk
  menyetujui konten sebelum dipublikasikan.
- Perubahan regulasi AI dan halal harus diperiksa ulang sebelum deployment; tidak
  ada klaim kelengkapan regulasi *current* yang dibuat oleh sistem ini.

---

*Lampiran: `governance/references.json` (pemetaan referensi regulasi),
`data/cert_registry_mock.csv` (pangkalan data sertifikat tiruan),
`tests/run_live_reviewer.py` (metrik akurasi Reviewer).*
