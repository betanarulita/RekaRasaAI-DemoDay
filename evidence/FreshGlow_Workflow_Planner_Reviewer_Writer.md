# FreshGlow — Workflow AI Creator Agent: Planner → Reviewer → Writer → Reviewer

## Pemetaan Peran ke Skill yang Digunakan

| Peran | Skill yang benar-benar dijalankan | Fungsi |
|---|---|---|
| **Planner** | (Manusia/orkestrator — tidak ada Skill khusus yang dijalankan) | Menetapkan fakta sumber, aturan pemeriksaan, dan batas iterasi. |
| **Reviewer** | `no-ai-slop` (mode review-only) + `content-audit` (audit skor) | Memeriksa draft, menolak klaim tanpa bukti, menyebutkan aturan yang dilanggar, memberi skor per dimensi. |
| **Writer** | `no-ai-slop` (mode rewrite) + prinsip dari `content-factory` (Writer agent) | Memperbaiki draft hanya menggunakan fakta yang diizinkan. |

> **Pernyataan jujur:** Hanya tiga Skill yang benar-benar dimuat dan dijalankan dalam sesi ini: `no-ai-slop`, `content-audit`, dan `content-factory`. Peran Planner dijalankan oleh orkestrator (manusia + sistem) berdasarkan brief yang diberikan. Tidak ada Skill khusus "Planner" yang dipanggil.

---

## FAKTA PRODUK YANG DIIZINKAN (dari brief)

1. FreshGlow adalah pelembap wajah untuk penggunaan harian.
2. Teksturnya ringan.

## DRAFT AWAL YANG SENGAJA BERMASALAH

> "FreshGlow terbukti menyembuhkan jerawat dalam 7 hari! Teruji klinis, bersertifikat halal, dan aman untuk semua jenis kulit. Teksturnya ringan dan cepat meresap."

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## PERAN 1: PLANNER
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Fakta Sumber (Source of Truth)

| # | Fakta | Boleh Dipakai? |
|---|---|---|
| F1 | Pelembap wajah untuk penggunaan harian | ✅ YA |
| F2 | Tekstur ringan | ✅ YA |

### Klaim yang TIDAK Didukung Fakta (dilarang)

| # | Klaim | Dilarang Karena |
|---|---|---|
| K1 | "terbukti menyembuhkan jerawat dalam 7 hari" | Tidak ada data uji klinis. Jerawat = kondisi medis. Kosmetik tidak boleh mengklaim menyembuhkan. |
| K2 | "teruji klinis" | Tidak ada protokol uji, lembaga, jumlah subjek, atau laporan hasil. |
| K3 | "bersertifikat halal" | Tidak ada sertifikat BPJPH/MUI. Klaim halal tanpa sertifikat melanggar UU JPH. |
| K4 | "aman untuk semua jenis kulit" | Tidak ada uji patch test / RIPT pada panel multi-jenis kulit. |
| K5 | "cepat meresap" | Tidak ada data formulasi atau uji. "Tekstur ringan" tidak secara otomatis membuktikan "cepat meresap". |

### Aturan Pemeriksaan (Review Rules)

1. Setiap pernyataan dalam draft harus dapat ditelusuri ke F1 atau F2.
2. Jika sebuah pernyataan TIDAK dapat ditelusuri ke F1/F2 → REJECT.
3. "Cepat meresap" secara eksplisit TIDAK diizinkan — tekstur ringan ≠ bukti cepat meresap.
4. Tidak boleh mengarang sumber, sertifikasi, hasil uji, atau bukti.
5. Placeholder (BPOM, isi gr) boleh ditandai kosong, tidak boleh dikarang.
6. Maksimal 3 iterasi. Jika belum lolos setelah iterasi ke-3, eskalasi kepada manusia.
7. Persetujuan Reviewer ≠ izin publikasi. Konten akhir tetap butuh persetujuan manusia.

### Kriteria APPROVE

Draft dinyatakan APPROVE jika:
- Setiap klaim dapat ditelusuri ke F1 atau F2 saja.
- Tidak ada K1–K5 yang tersisa.
- Tidak ada sumber/sertifikasi/hasil uji yang dikarang.
- Tidak ada klaim keamanan, efikasi, atau penyembuhan.

### Kriteria REJECT

Draft dinyatakan REJECT jika:
- Masih ada satu atau lebih klaim dari K1–K5.
- Ada pernyataan yang tidak dapat ditelusuri ke F1/F2.
- Ada sumber/sertifikasi/hasil uji yang dikarang.

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## PERAN 2: REVIEWER — Iterasi 1 (Pemeriksaan Draft Awal)
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Metode
Skill `no-ai-slop` (mode review-only) + `content-audit` (audit skor).

### Inventaris Fakta (Fact Lock — read-only)

Proposisi yang dapat dipertahankan dari draft:
- "Teksturnya ringan" → dapat ditelusuri ke F2. ✅
- Sisanya: klaim yang TIDAK dapat ditelusuri ke fakta yang diizinkan.

### Diagnosis no-ai-slop (review-only)

```
Diagnosis: Draft mengandung 5 klaim yang melampaui fakta yang diizinkan (F1, F2). Empat klaim medis/regulatori dan satu klaim deskriptif yang tidak terbukti.
1. [KRITIS] "terbukti menyembuhkan jerawat dalam 7 hari" — Inflated claim + klaim medis tanpa bukti. Jerawat adalah kondisi medis; kosmetik tidak boleh mengklaim menyembuhkan. Repair: hapus seluruhnya.
2. [KRITIS] "teruji klinis" — Inflated claim tanpa data. Klaim "teruji klinis" membutuhkan protokol, lembaga, dan laporan. Repair: hapus seluruhnya.
3. [KRITIS] "bersertifikat halal" — Inflated claim tanpa sertifikat. Repair: hapus seluruhnya.
4. [KRITIS] "aman untuk semua jenis kulit" — Inflated claim keamanan tanpa uji. Repair: hapus seluruhnya.
5. [SEDANG] "cepat meresap" — Inflated claim deskriptif. Tekstur ringan tidak membuktikan kecepatan penyerapan. Repair: hapus atau ganti dengan deskripsi yang hanya menyebut "tekstur ringan".
Keep: "teksturnya ringan" — ini satu-satunya proposisi yang dapat dipertahankan dari draft.
```

### Audit content-audit

```
Content Audit — Iterasi 1
Scope: body (caption singkat, tanpa headline terpisah, tanpa platform eksplisit)

| Dimension | Score | Note |
|---|---|---|
| Hook strength | 2/5 | Hook mengandalkan klaim medis palsu ("terbukti menyembuhkan jerawat dalam 7 hari") |
| Structure clarity | 2/5 | Struktur kalimat run-on, tumpang tindih klaim |
| Voice/register fit | 2/5 | Register terlalu promosi-hyperbolic untuk pelembap harian |
| Anti-slop | 1/5 | "terbukti", "teruji klinis", "aman untuk semua jenis kulit" = pola inflated claim |
| Factual risk | 1/5 | 5 klaim tanpa bukti; 4 di antaranya medis/regulatori |
| CTA/payoff clarity | 1/5 | Tidak ada CTA yang jujur; seluruh "payoff" adalah klaim palsu |

Prioritas perbaikan:
1. Hapus "terbukti menyembuhkan jerawat dalam 7 hari" — klaim medis tanpa bukti — pakai no-ai-slop (rewrite)
2. Hapus "teruji klinis", "bersertifikat halal", "aman untuk semua jenis kulit" — klaim tanpa sertifikasi — pakai no-ai-slop (rewrite)
3. Hapus "cepat meresap" — tidak terbukti oleh fakta tekstur ringan — pakai no-ai-slop (rewrite)

Catatan: audit ini read-only, tidak ada draft yang diubah.
```

### Keputusan Reviewer — Iterasi 1

**REJECT**

#### Aturan yang Dilanggar

| Klaim | Aturan yang Dilanggar |
|---|---|
| "terbukti menyembuhkan jerawat dalam 7 hari" | Aturan #1 (tidak dapat ditelusuri ke F1/F2); Aturan #4 (klaim penyembuhan tanpa bukti); K1 |
| "teruji klinis" | Aturan #1; Aturan #4 (klaim uji tanpa data); K2 |
| "bersertifikat halal" | Aturan #1; Aturan #4 (klaim sertifikasi tanpa sertifikat); K3 |
| "aman untuk semua jenis kulit" | Aturan #1; Aturan #4 (klaim keamanan tanpa uji); K4 |
| "cepat meresap" | Aturan #1; Aturan #3 (tekstur ringan ≠ bukti cepat meresap); K5 |

#### Alasan Penolakan

Draft melanggar 5 dari 5 aturan pemeriksaan. Hanya satu proposisi yang bertahan: "teksturnya ringan" (F2). Draft harus ditulis ulang dari awal hanya dengan F1 dan F2.

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## PERAN 3: WRITER — Iterasi 1 (Revisi)
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Metode
Skill `no-ai-slop` (mode rewrite) + prinsip Writer agent dari `content-factory`.

### Inventaris Fakta (Fact Lock)

Proposisi yang dapat dipertahankan: HANYA F1 (pelembap harian) dan F2 (tekstur ringan).

### Diagnosis sebelum rewrite

```
Diagnosis: 5 finding kritis (lihat Reviewer Iterasi 1). Strategi: hapus semua klaim K1–K5, tulis ulang hanya dengan F1 + F2.
```

### Draft Revisi 1

> "FreshGlow adalah pelembap wajah untuk penggunaan harian dengan tekstur ringan."

### Integrity Check (no-ai-slop rewrite)

```
Integrity check:
- facts: PASS — hanya F1 (pelembap harian) dan F2 (tekstur ringan), keduanya dari brief.
- stance: PASS — deskriptif, tidak ada klaim efikasi/keamanan/penyembuhan.
- structure/metadata: PASS — satu kalimat, tidak ada metadata fiktif.
- voice: PASS — netral-deskriptif, tidak ada hyperbolic.
```

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## PERAN 4: REVIEWER — Iterasi 1 (Pemeriksaan Ulang Revisi 1)
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Metode
Skill `no-ai-slop` (mode review-only) + `content-audit`.

### Diagnosis no-ai-slop (review-only) — Revisi 1

```
Diagnosis: Draft revisi hanya berisi dua proposisi, keduanya dapat ditelusuri ke fakta yang diizinkan. Tidak ada pola slop, tidak ada inflated claim, tidak ada klaim tanpa bukti.
1. Tidak ada temuan kritis.
Keep: Kesederhanaan draft — hanya mengatakan apa yang dapat dibuktikan.
```

### Audit content-audit — Revisi 1

```
Content Audit — Iterasi 1 (Pemeriksaan Ulang)
Scope: body (satu kalimat deskriptif)

| Dimension | Score | Note |
|---|---|---|
| Hook strength | 3/5 | Tidak ada hook palsu, tapi juga tidak ada daya tarik — dapat diperbaiki di versi final tanpa menambah klaim |
| Structure clarity | 4/5 | Satu kalimat, satu ide, jelas |
| Voice/register fit | 5/5 | Netral-deskriptif, sesuai untuk caption produk yang jujur |
| Anti-slop | 5/5 | Tidak ada pola slop sama sekali |
| Factual risk | 5/5 | Setiap kata dapat ditelusuri ke F1 atau F2; tidak ada klaim tanpa bukti |
| CTA/payoff clarity | 3/5 | Tidak ada CTA eksplisit — dapat ditambah tanpa menambah klaim |

Prioritas perbaikan:
1. Tambah CTA yang tidak mengandung klaim — pakai no-ai-slop (rewrite)
2. Pertimbangkan hook yang jujur (bukan klaim) — pakai content-factory (Writer)

Catatan: audit ini read-only, tidak ada draft yang diubah.
```

### Pemeriksaan Klaim per Aturan

| Proposisi dalam Revisi 1 | Dapat ditelusuri ke? | Aturan Dilanggar? |
|---|---|---|
| "pelembap wajah" | F1 | Tidak |
| "penggunaan harian" | F1 | Tidak |
| "tekstur ringan" | F2 | Tidak |

K1–K5: Tidak ada yang tersisa.

### Keputusan Reviewer — Pemeriksaan Ulang Iterasi 1

**APPROVE** ✅

#### Alasan Persetujuan

1. Setiap proposisi dalam draft revisi dapat ditelusuri ke F1 atau F2.
2. Tidak ada K1–K5 yang tersisa.
3. Tidak ada sumber/sertifikasi/hasil uji yang dikarang.
4. Tidak ada klaim keamanan, efikasi, atau penyembuhan.
5. Integrity check: semua PASS.

#### Catatan Reviewer

Persetujuan ini hanya untuk kesesuaian fakta. Audit mencatat bahwa draft dapat diperkaya dengan hook dan CTA yang jujur (tanpa menambah klaim) untuk versi final. Namun dari segi kepatuhan fakta, draft sudah lolos.

> ⚠️ **Persetujuan Reviewer BUKAN izin mempublikasikan.** Konten akhir tetap memerlukan persetujuan manusia sebelum dipublikasikan.

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## RINGKASAN WORKFLOW
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Alur Iterasi

| Iterasi | Peran | Tindakan | Hasil |
|---|---|---|---|
| 1 | Reviewer | Periksa draft awal | REJECT (5 klaim dilanggar) |
| 1 | Writer | Tulis ulang hanya dengan F1 + F2 | Draft revisi 1 dihasilkan |
| 1 | Reviewer | Periksa ulang revisi 1 | **APPROVE** ✅ |

### Jumlah Iterasi

**1 iterasi** (dari maksimal 3).

Siklus berhenti setelah iterasi 1 karena Reviewer menyatakan APPROVE. Tidak perlu iterasi ke-2 atau ke-3.

### Draft Awal

> "FreshGlow terbukti menyembuhkan jerawat dalam 7 hari! Teruji klinis, bersertifikat halal, dan aman untuk semua jenis kulit. Teksturnya ringan dan cepat meresap."

### Klaim yang Ditolak dan Aturan yang Dilanggar

| Klaim | Aturan | Alasan |
|---|---|---|
| "terbukti menyembuhkan jerawat dalam 7 hari" | K1, Aturan #1, #4 | Klaim medis tanpa data uji; jerawat = kondisi medis |
| "teruji klinis" | K2, Aturan #1, #4 | Klaim uji klinis tanpa protokol/lembaga/laporan |
| "bersertifikat halal" | K3, Aturan #1, #4 | Klaim sertifikasi tanpa sertifikat BPJPH/MUI |
| "aman untuk semua jenis kulit" | K4, Aturan #1, #4 | Klaim keamanan tanpa uji patch test |
| "cepat meresap" | K5, Aturan #1, #3 | Tekstur ringan ≠ bukti cepat meresap |

### Revisi

> "FreshGlow adalah pelembap wajah untuk penggunaan harian dengan tekstur ringan."

### Hasil Pemeriksaan Ulang

**APPROVE** — setiap proposisi dapat ditelusuri ke F1/F2; tidak ada klaim tanpa bukti; tidak ada pengarangan.

### Keputusan Akhir

**APPROVE — lolos iterasi 1.**

> ⚠️ Persetujuan Reviewer bukan izin publikasi. Konten akhir tetap memerlukan persetujuan manusia sebelum dipublikasikan.

---

## PERNYATAAN INTEGRITAS

- **Tidak ada sumber, hasil uji, sertifikasi, atau bukti yang dikarang.**
- Draft revisi hanya mengandung dua fakta dari brief: pelembap harian + tekstur ringan.
- "Cepat meresap" secara eksplisit dihapus karena tekstur ringan tidak membuktikan kecepatan penyerapan.
- Placeholder tidak digunakan dalam draft revisi karena draft tidak menyebut BPOM/isi.
- Skill yang benar-benar dijalankan: `no-ai-slop` (review + rewrite), `content-audit` (audit skor), `content-factory` (prinsip Writer agent).
- Peran Planner dijalankan oleh orkestrator berdasarkan brief — tidak ada Skill khusus "Planner" yang dipanggil.
