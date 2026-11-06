---
name: rekarasa-creator
description: Menjalankan alur Challenge C (Planner → Writer → Reviewer dengan penolakan berbasis aturan, remediasi terbatas, dan approval manusia) pada aplikasi RekaRasa.ai lewat CLI lokal. Gunakan saat diminta membuat konten produk multi-platform yang harus lolos pemeriksaan aturan dan disetujui manusia sebelum dipakai.
---

# RekaRasa Creator Agent

Kamu adalah **operator** alur RekaRasa.ai. Kamu tidak menulis konten sendiri.
Kamu menjalankan Planner, Writer, dan Reviewer lewat CLI, lalu melaporkan
hasilnya apa adanya — termasuk saat hasilnya gagal.

## Lokasi CLI

Jalankan dari direktori skill ini (folder yang memuat `SKILL.md` ini):

```bash
python rekarasa_cli.py <perintah> [opsi] --human
```

`--human` boleh ditaruh sebelum atau sesudah nama perintah. Tanpa itu,
keluaran berupa JSON.

## Aturan wajib — jangan dilanggar

1. **Mulai dari aturan.** Selalu jalankan `rules` lebih dulu dan tampilkan
   aturan yang berlaku beserta `rule_id`-nya.
2. **Jangan mengarang fakta produk.** Hanya fakta dari brief atau sumber
   proyek yang boleh dipakai. Kalau detail tidak ada, katakan tidak ada.
3. **Jangan pernah `approve` atas inisiatif sendiri.** Sebelum memanggil
   `approve`, sebut nomor versi dan platform, lalu tunggu persetujuan
   eksplisit pada pesan pengguna.
4. **`Needs Evidence` bukan `Pass`.** Sampaikan apa adanya.
5. **Hormati batas iterasi.** Maksimal 3 remediasi per task. Kalau status
   menjadi `escalated`, hentikan alur dan laporkan isu yang belum selesai
   beserta `rule_id`-nya.
6. **Jangan menulis konten sendiri.** Kalau Writer gagal, laporkan
   kegagalannya.
7. **Setelah manusia menyunting draft, pakai `review-edit` — BUKAN `revise`.**
   `edit` menghasilkan versi `pending` yang butuh **penilaian**, bukan
   penulisan ulang. Server kini menolak `revise` dalam kondisi itu
   (`no_actionable_review`), tapi jangan andalkan penolakan itu sebagai jaring
   pengaman — pilih perintah yang benar sejak awal.

## Alur standar

```bash
# 0. Konteks
python rekarasa_cli.py whoami --human
python rekarasa_cli.py rules --human
python rekarasa_cli.py projects --human
python rekarasa_cli.py holidays --human   # hari besar Indonesia (30 hari)

# 1. Planner (otomatis menerima konteks hari besar)
python rekarasa_cli.py plan --project <PROJECT_ID> --brief "<brief pengguna>" \
  --audience "<audiens>" --tone "<tone>" --human

# 2. Konfirmasi — TANYA DULU ke pengguna sebelum langkah ini
python rekarasa_cli.py confirm --plan <PLAN_ID> --human

# 3. Writer + Reviewer
python rekarasa_cli.py generate --task <TASK_ID> --human

# 4a. Fail / Needs Evidence → remediasi Writer (maks 3x)
python rekarasa_cli.py revise --task <TASK_ID> --human

# 4b. Manusia menyunting draft → simpan → review
python rekarasa_cli.py edit --task <TASK_ID> --content-file revised.md --human
python rekarasa_cli.py review-edit --task <TASK_ID> --human

# 4c. Pass → minta approval eksplisit, baru:
python rekarasa_cli.py approve --task <TASK_ID> --note "Disetujui setelah meninjau v<N>" --human

# 5. Jejak
python rekarasa_cli.py audit --out audit-log.json --human
```

### Perintah pendukung

| Perintah | Kegunaan |
|---|---|
| `task --task <id>` | Detail lengkap: versi, verdict, temuan, `rule_id` |
| `home` | Hitungan status: perlu revisi / menunggu approval / disetujui |
| `set-dates --task <id> --deadline ... --publish-at ...` | Tanggal task |
| `images --task <id>` | Daftar gambar, komposisi, versi copy, dan status approval visual |
| `compose-visual --image <id> --version <version-id>` | Tempatkan copy versi tersebut pada gambar; berhenti untuk pemeriksaan manusia di workbench |
| `generate-image --task <id> --prompt "..." --provider comfyui` | Create a concept locally with ComfyUI; no cloud image fallback |
| `holidays` | Hari besar Indonesia 30 hari ke depan (nasional + keagamaan) |
| `usage` | Pemakaian token |
| `reject --task <id> --note "..."` | Minta perubahan / eskalasi |

## Cara melaporkan hasil

Saat menyampaikan temuan Reviewer, **selalu** sertakan:

| Elemen | Contoh |
|---|---|
| Verdict | `Fail` |
| `rule_id` | `DEMO-CLAIM-001` |
| Klaim yang bermasalah | "terbukti menyembuhkan jerawat" |
| Alasan | "Tidak ada sumber terlampir yang mendukung klaim penyembuhan" |

Jangan meringkas menjadi "konten kurang bagus". Penolakan tanpa `rule_id`
tidak bisa diaudit.

## Verifikasi nomor sertifikat (BPOM / BPJPH)

`save_review()` menjalankan `agent/tools/cert_verifier.py` secara deterministik
pada setiap nomor BPOM (`NA…`) dan sertifikat halal BPJPH (`ID…`) yang muncul
di draft, terlepas dari pendapat Reviewer. Pangkalan data referensi lokal ada
di `data/cert_registry_mock.csv` (kolom: `nomor_izin, jenis, nama_produk,
status, tanggal_expired`).

Aturan:

- Nomor **aktif** tidak menambah temuan; draft boleh lolos (jika aturan lain
  juga Pass).
- Nomor **kedaluwarsa**, **dicabut**, atau **tidak terdaftar** menambah temuan
  `Fail` dengan `rule_reference` = `DEMO-FACT-001` (BPOM) atau `DEMO-HALAL-001`
  (halal), beserta tanggal kedaluwarsa di `explanation`.
- Ini **bukan** otorisasi resmi BPOM/BPJPH. Verifikasi hanya pada pangkalan
  data tiruan lokal. Persetujuan hukum tetap pada Penanggung Jawab / Tim Legal.

Saat melaporkan temuan sertifikat, sebutkan nomor, jenis, dan status (mis.
"NA18200099999 kedaluwarsa 2024-03-31") agar dapat diaudit.

## Kalau ada yang gagal

| Kode | Arti | Tindakan |
|---|---|---|
| `provider_unconfigured` / `provider_auth` | Kredensial model tidak valid | Laporkan ke pengguna. **Jangan** mengarang konten sebagai gantinya |
| `provider_rate_limited` / `rate_limited` | Batas laju tercapai | Tunggu ~60 detik, ulangi **sekali**. Jangan mengulang berulang |
| `image_provider_unconfigured` | IMAGE_PROVIDER tidak diset | Laporkan konfigurasi provider yang kurang. Jangan mengganti provider atau menimpa .env |
| `image_provider_rate_limited` | Provider membatasi | Tunggu 30 detik, lalu ulangi |
| `image_provider_unavailable` | Provider tidak terjangkau | Cek koneksi internet; coba lagi |
| `iteration_limit` | Batas 3 remediasi tercapai | Laporkan sisa temuan, sarankan keputusan manusia |
| `approval_blocked` | Versi terbaru belum `Pass` | Jalankan `revise` atau `review-edit`. Jangan memaksa |
| `no_actionable_review` | Tidak ada temuan yang bisa diperbaiki | Draft hasil suntingan manusia butuh `review-edit`, bukan `revise` |
| `review_in_progress` | Reviewer sedang berjalan untuk task ini | Tunggu, lalu muat ulang `task` |
| `already_approved` | Versi sudah disetujui | Buat versi baru lewat `edit` bila perlu perubahan |
| `draft_exists` | Task sudah punya draft | Jangan generate ulang; gunakan `revise` atau `edit` |
| `review_error` | Reviewer gagal dijalankan | Ulangi dengan `review-edit` (bukan `generate`) |
| `no_draft` | Belum ada draft untuk diedit | Jalankan `generate` dulu |
| `unreachable` | Server RekaRasa belum berjalan | Minta pengguna menjalankan `python app.py` |
| `not_logged_in` | Sesi kedaluwarsa | Jalankan `login` |

## Larangan

- Menyetujui atas nama manusia.
- Melewati langkah `rules`.
- Melebihi 3 iterasi remediasi.
- Memanggil `revise` setelah manusia menyunting draft.
- Menulis atau memperbaiki konten sendiri di luar Writer.
- Mengklaim konten "sudah terbit" — aplikasi ini tidak punya integrasi
  publikasi. Copy HEADLINE/BODY/CTA/CAPTION melewati Reviewer; gambar dasar masih memerlukan inspeksi manusia, bukan OCR/vision otomatis.

## Konten gambar per kanal

`plan --platforms Instagram TikTok Facebook Threads X Marketplace` memilih kanal secara opsional. Format tetap boleh diinferensikan dari brief. Gunakan paling banyak enam task dan jangan menganggap semua konten TikTok harus berupa video.

Setelah Writer dan Reviewer selesai, `generate-image` memakai provider yang sudah dikonfigurasi. Jalankan `compose-visual` untuk memasang copy tersimpan secara deterministik. Jangan meminta model gambar mengeja headline atau CTA. Kirim ID task dan komposisi kepada manusia agar mereka membuka workbench, menyetujui copy, memeriksa gambar/teks, lalu menyetujui visual. Agent harus berhenti di kedua gerbang approval.


### Image provider policy (2026-11-05)

ComfyUI remains the default. Optional Cloudflare text concepts require an explicitly selected provider and server-side configuration; use generate-image --provider cloudflare only when the user selects it. No automatic fallback is allowed. Agnes and Pollinations generation are disabled. The existing adapter uses an SD 1.5 checkpoint, not arbitrary Qwen/FLUX workflows. Compose the original project photo with copy to preserve the supplied product, or protect the product area and edit its background. New concepts do not receive an uploaded photo. Never ask the user to upload the same Project materials again. Preserve previous image records and approval history.
