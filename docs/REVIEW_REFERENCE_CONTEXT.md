# Rujukan resmi untuk pemeriksaan konten

Pembaruan: 4 November 2026.

## Alur

- Rulebook proyek tetap memakai ID dan versi yang sama; teks aturan dan temuan lama tidak ditulis ulang.
- Reviewer menerima `regulatory_context` berisi peta rujukan terkurasi. Sumber produk tetap terpisah dari sumber aturan.
- Pemetaan tidak menjadikan seluruh pasal berlaku untuk setiap produk. Konteks kosmetik hanya digunakan jika kategori produk didukung sumber.
- Review baru menyimpan snapshot peta, hash, ID review dan versi konten melalui audit event `review.reference_context` dalam transaksi review.
- Detail temuan menampilkan tautan rujukan terkontrol dari backend. Link itu bukan pasal hasil karangan model.
- Review lama tanpa snapshot diberi penanda `current_links_for_legacy_review`; tautan tersebut merupakan konteks saat ini, bukan dasar hukum historis yang diklaim telah digunakan.

## Rujukan yang diperiksa

Lihat [references.json](../governance/references.json): PerBPOM 18/2024 Pasal 2(3), 5, 13, 17 dan bagian terkait Lampiran VI; UU 8/1999 Pasal 9(1) dan 10. Parafrasa disertai lokasi ketentuan dan tautan dokumen resmi. Tanggal pemeriksaan dokumen tidak berarti seluruh perubahan peraturan telah diverifikasi.

## Batas

- Tidak ada autentikasi atau pencarian sertifikat/notifikasi secara langsung ke BPOM/BPJPH.
- Sumber unggahan belum membuktikan keaslian, pemegang, cakupan produk atau status terkini sertifikat.
- Aturan penolakan deterministik, batas revisi, kepemilikan data, approval manusia dan ekspor tetap memakai alur yang ada.
- Penilaian semantik model belum menjamin setiap ketentuan hukum telah dipenuhi. Tidak ada sertifikat atau putusan hukum otomatis.
- OCR, pemeriksaan logo pada foto dan audit kepatuhan semua sektor belum tersedia. OJK tidak diterapkan ke produk umum tanpa scope dan rujukan yang diperiksa.

## Pemeriksaan manual

Buka detail task, perluas Content checks, lalu perluas Official references. Periksa cakupan produk, lokasi ketentuan, tautan dokumen dan sumber produk. Tidak perlu membuat draft baru hanya untuk melihat rujukan pada review lama.

## Validasi aktual

- `python scripts/run_tests.py test_app test_evidence_binding`: 125 tes lulus (78,562 detik), sebelum dua tes baru ditambahkan.
- `python scripts/run_tests.py test_evidence_binding.RegulatoryContextTests`: 2 tes baru lulus; cakupan referensi dan snapshot melalui koneksi baru, termasuk simulasi perubahan peta referensi.
- Sintaks Python, JSON, JavaScript dan `git diff --check` lulus.
- Browser: task lama menampilkan tautan terkurasi dengan penanda legacy; status approval serta tombol copy tetap tersedia.
- Tidak menjalankan review Groq live, verifikasi sertifikat eksternal, atau pengujian kelengkapan seluruh aturan hukum. Suite lengkap lintas semua modul tidak diulang dalam perubahan ini.
