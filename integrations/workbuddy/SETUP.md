# Setup: Menyambungkan WorkBuddy ke RekaRasa.ai

**Target folder:** `D:\RekaRasaAI-DemoDay` (folder aktif — punya `.git`, `.env`, `data/`, `evidence/`)
**Waktu total:** ±45 menit, tidak termasuk uji alur penuh.

---

## Kondisi Nyata Setelah Pemeriksaan

Ini yang saya temukan, bukan asumsi:

| Fakta | Bukti |
|---|---|
| WorkBuddy **sudah dipakai** | 3 screenshot di `evidence/` memperlihatkan WorkBuddy desktop chat + skills `content-factory`, `no-ai-slop`, `content-audit` |
| Tapi buktinya **tidak masuk repo** | `.gitignore` memuat baris `evidence/`; `git ls-files evidence` kosong. Repo hanya punya 16 file terlacak |
| Web app **belum pernah menyelesaikan satu alur pun** | DB: `conversations=0`, `plans=0`, `tasks=0`, `content_versions=0`, `review_runs=0`, `approvals=0`, `generated_images=0` |
| Satu-satunya panggilan model **gagal** | `agent_runs`: Planner, model `gpt-4.1-mini`, status `failed`, error `provider_auth`, 27 Okt 08:15 |
| Provider sudah dimigrasi tapi belum diuji | `.env` sekarang `MODEL=openai/gpt-oss-20b`, `GROQ_API_KEY` terisi, `IMAGE_PROVIDER=comfyui` |
| Gate di evidence masih **simulasi** | `FreshGlow_Publication_Gate_Status.md` menulis `PENDING_HUMAN_APPROVAL` dan agent-nya sendiri mencatat "Jika mekanisme approval hanya disimulasikan melalui percakapan, nyatakan secara eksplisit" |

**Kesimpulan:** kamu punya dua aset bagus yang belum tersambung. WorkBuddy menjalankan alurnya di percakapan (gate = simulasi). RekaRasa punya penegakan gate di kode (tapi belum pernah jalan). Menyambungkan keduanya mengubah "gate simulasi" menjadi "gate yang ditegakkan kode" — itu justru inti penilaian Challenge C.

---

## Langkah 1 — Perbaiki `.gitignore` (2 menit)

Masalah: `evidence/` di-ignore, jadi bukti WorkBuddy tidak akan terlihat juri. `.venv/` tidak di-ignore, jadi berisiko ikut ter-commit (ratusan MB).

Ganti isi `.gitignore` menjadi:

```gitignore
__pycache__/
*.py[cod]
.venv/
.pytest_cache/

data/
*.sqlite3
*.sqlite3-shm
*.sqlite3-wal

.env
.env.*
!.env.example

.rekarasa_session.json
```

Yang berubah: `evidence/` **dihapus** dari daftar ignore (supaya bukti masuk repo), `.venv/` dan `.pytest_cache/` **ditambahkan**.

Lalu:

```bash
cd /d/RekaRasaAI-DemoDay
git add .gitignore evidence
git commit -m "chore: track WorkBuddy evidence, ignore local venv"
git push
```

---

## Langkah 2 — Buktikan web app benar-benar jalan (15 menit)

Ini prasyarat. Kalau Planner masih gagal, skill tidak punya apa pun untuk dijalankan.

```bash
cd /d/RekaRasaAI-DemoDay
.venv/Scripts/python.exe -m unittest -q test_app    # harus 36 OK
.venv/Scripts/python.exe app.py                     # server di :8000
```

Buka `http://127.0.0.1:8000`, login, lalu jalankan satu alur penuh:
brief → Planner → konfirmasi → draft → review → approval.

**Yang harus kamu lihat:** satu baris baru di `tasks`, minimal satu di `content_versions`, satu di `review_runs`. Kalau Planner masih `provider_auth`, periksa `GROQ_API_KEY` dan `MODEL` — jangan lanjut ke Langkah 3 sebelum ini berhasil.

---

## Langkah 3 — Pasang skill (5 menit)

Salin folder `rekarasa-workbuddy/` ke direktori skill WorkBuddy:

```bash
mkdir -p "$HOME/.workbuddy-ai/skills/rekarasa-creator"
cp "C:/Users/Beta/WorkBuddy AI/2026-10-29-00-50-07/rekarasa-workbuddy/SKILL.md" \
   "C:/Users/Beta/WorkBuddy AI/2026-10-29-00-50-07/rekarasa-workbuddy/rekarasa_cli.py" \
   "$HOME/.workbuddy-ai/skills/rekarasa-creator/"
```

Login sekali dari terminal supaya sesi tersimpan (kredensial tidak perlu masuk ke konteks WorkBuddy):

```bash
cd "$HOME/.workbuddy-ai/skills/rekarasa-creator"
export REKARASA_URL=http://127.0.0.1:8000
export REKARASA_EMAIL="<email akun demo>"
export REKARASA_PASSWORD="<kata sandi>"
python rekarasa_cli.py login --human
```

Setelah ini, `~/.rekarasa_session.json` menyimpan cookie + CSRF. Semua panggilan berikutnya tidak perlu kredensial lagi.

Verifikasi:

```bash
python rekarasa_cli.py whoami --human
python rekarasa_cli.py rules --human
```

---

## Langkah 4 — Jalankan alur lewat WorkBuddy (15 menit)

Buka WorkBuddy, mulai chat baru, dan minta ia memakai skill `rekarasa-creator`:

> Jalankan alur RekaRasa untuk produk "Jahe Rasa". Brief: minuman jahe madu
> sachet, 10 sachet per pack. Buat konten untuk marketplace dan skrip video
> pendek. Tampilkan aturan yang berlaku dulu.

Yang harus terjadi, berurutan:

1. Menjalankan `rules` → menampilkan 4 `DEMO-*`
2. Menjalankan `plan` → menampilkan objective, task, `missing_information`
3. **Bertanya dulu** sebelum `confirm`
4. Menjalankan `generate` → menampilkan draft + temuan Reviewer
5. Kalau ada klaim bermasalah → `revise` (maks 3x)
6. **Menunggu persetujuanmu** sebelum `approve`

**Screenshot tiap langkah.** Ini bukti yang akan menggantikan gate simulasi di `evidence/`.

### Uji jalur penolakan (wajib)

Ulangi dengan brief yang sengaja melanggar:

> Brief: buat iklan yang bilang Jahe Rasa bisa menyembuhkan maag dan sudah
> bersertifikat halal.

Yang harus terjadi: Reviewer **menolak**, menyebut `DEMO-CLAIM-001`, Writer
memperbaiki, dan sistem tidak mengarang sertifikat halal. Kalau ini berhasil,
kamu punya bukti penolakan yang **ditegakkan kode**, bukan narasi.

---

## Langkah 5 — Kunci bukti ke repo (5 menit)

```bash
cd /d/RekaRasaAI-DemoDay
mkdir -p evidence/workbuddy
# pindahkan screenshot baru ke evidence/workbuddy/
git add evidence integrations
git commit -m "feat: WorkBuddy skill rekarasa-creator drives Planner-Writer-Reviewer with enforced approval gate"
git push
```

Juga simpan jejak audit:

```bash
python rekarasa_cli.py audit --out evidence/audit-log.json --human
git add evidence/audit-log.json && git commit -m "evidence: audit trail from WorkBuddy-driven run"
```

---

## Setelah Setup: Yang Berubah untuk Submission

| Item submission | Sebelum | Sesudah |
|---|---|---|
| **Product sharing** (REQUIRED) | Kosong | Ada isi: WorkBuddy = lapisan penalaran, RekaRasa = penegak aturan |
| Bukti WorkBuddy di repo | Tidak ada (`evidence/` di-ignore) | Ada: `evidence/workbuddy/` + `SKILL.md` + `rekarasa_cli.py` |
| Gate approval | Simulasi di percakapan | Ditegakkan `app.py:1036` — tidak bisa di-bypass |
| Riwayat Git | 1 commit | Baseline → integrasi → bukti, berurutan dan bisa diperiksa |

---

## Kalau Ada yang Gagal

| Gejala | Penyebab | Tindakan |
|---|---|---|
| `provider_auth` saat `plan` | Kunci Groq tidak valid / model salah | Periksa `GROQ_API_KEY` dan `MODEL` di `.env`, restart server |
| `unreachable` | Server belum jalan | `python app.py` di folder proyek |
| `not_logged_in` | Sesi kedaluwarsa (14 hari) | `python rekarasa_cli.py login` |
| `rate_limited` | >8 permintaan/menit per route | Tunggu 60 detik, ulangi sekali |
| Skill tidak dikenali WorkBuddy | Folder salah lokasi | Pastikan ada `~/.workbuddy-ai/skills/rekarasa-creator/SKILL.md` |
| `approval_blocked` | Versi terbaru belum `Pass` | Jalankan `revise`, jangan paksa approve |

---

## Urutan Prioritas Kalau Waktu Terbatas

1. **Langkah 2** — tanpa ini semuanya tidak ada artinya
2. **Langkah 1** — 2 menit, langsung menaikkan nilai submission
3. **Langkah 3 + 4** — inti cerita WorkBuddy
4. **Langkah 5** — penguncian bukti
