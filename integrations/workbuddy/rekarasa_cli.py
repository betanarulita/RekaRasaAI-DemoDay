#!/usr/bin/env python3
"""
rekarasa_cli.py — jembatan CLI antara WorkBuddy dan API RekaRasa.ai.

Dipakai oleh skill `rekarasa-creator`. Hanya stdlib, Python 3.10+.

Semua perintah mencetak JSON ke stdout agar mudah dibaca agent.
Tambahkan --human untuk ringkasan yang enak dibaca manusia (bagus untuk screenshot).

Konfigurasi lewat environment (jangan pernah hardcode):
    REKARASA_URL       default http://127.0.0.1:8000
    REKARASA_EMAIL     email akun demo
    REKARASA_PASSWORD  kata sandi (minimal 12 karakter)

Sesi disimpan di ~/.rekarasa_session.json (mode 0600) supaya tidak perlu
login ulang tiap perintah. Hapus dengan `logout`.

Contoh:
    python rekarasa_cli.py login
    python rekarasa_cli.py rules --human
    python rekarasa_cli.py plan --project <id> --brief "..." --human
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = os.getenv("REKARASA_URL", "http://127.0.0.1:8000").rstrip("/")
SESSION_FILE = Path(
    os.getenv("REKARASA_SESSION_FILE", str(Path.home() / ".rekarasa_session.json"))
)
TIMEOUT = float(os.getenv("REKARASA_TIMEOUT", "120"))
HUMAN = False


class CLIError(Exception):
    def __init__(self, message: str, code: str = "cli_error", status: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


# ---------------------------------------------------------------------------
# Sesi
# ---------------------------------------------------------------------------
def load_session() -> dict | None:
    if not SESSION_FILE.is_file():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) and data.get("cookie") else None


def save_session(cookie: str, csrf: str, email: str) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(
        json.dumps({"cookie": cookie, "csrf": csrf, "email": email}, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(SESSION_FILE, 0o600)
    except OSError:
        pass


def clear_session() -> None:
    try:
        SESSION_FILE.unlink()
    except FileNotFoundError:
        pass


def extract_cookie(headers) -> str | None:
    for raw in headers.get_all("Set-Cookie") or []:
        if raw.startswith("rr_session="):
            return raw.split(";", 1)[0].split("=", 1)[1]
    return None


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def call(method: str, path: str, body: dict | None = None, auth: bool = True) -> dict:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if auth:
        session = load_session()
        if not session:
            raise CLIError(
                "Belum login. Jalankan: python rekarasa_cli.py login", "not_logged_in"
            )
        headers["Cookie"] = "rr_session=" + session["cookie"]
        if method == "POST":
            headers["X-CSRF-Token"] = session["csrf"]

    request = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read()
    except HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        message = payload.get("error") or f"HTTP {exc.code}"
        code = payload.get("code") or "http_error"
        if exc.code == 401:
            message = "Sesi tidak valid atau kedaluwarsa. Jalankan ulang: login"
        elif exc.code == 429:
            message = (
                "Kena batas laju (8 permintaan/menit per route). "
                "Tunggu ~60 detik lalu ulangi."
            )
        raise CLIError(message, code, exc.code)
    except URLError as exc:
        raise CLIError(
            f"Tidak bisa menghubungi RekaRasa di {BASE} ({exc.reason}). "
            "Pastikan server berjalan: python app.py",
            "unreachable",
        )
    except TimeoutError:
        raise CLIError(f"Permintaan melebihi {TIMEOUT:.0f} detik.", "timeout")

    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise CLIError("Respons server bukan JSON yang valid.", "malformed_response")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def emit(payload, human: str | None = None) -> None:
    if HUMAN and human:
        print(human)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def review_lines(review: dict | None) -> list[str]:
    if not review:
        return ["  (belum ada review)"]
    out = [f"  Verdict: {review.get('verdict', '?')}"]
    for item in review.get("findings", []):
        rule = item.get("rule_id") or "—"
        result = item.get("result", "?")
        claim = (item.get("claim") or "").strip()
        line = f"  [{result}] {rule}"
        if claim:
            line += f" · klaim: {claim[:80]}"
        out.append(line)
        explanation = (item.get("explanation") or "").strip()
        if explanation:
            out.append(f"      {explanation[:180]}")
    return out


def task_human(task: dict) -> str:
    lines = [
        f"Task   : {task.get('title', '?')} ({task.get('format', '?')} / {task.get('platform', '?')})",
        f"Status : {task.get('status', '?')}",
        f"Remediasi terpakai: {task.get('remediation_count', 0)}/3",
    ]
    versions = task.get("versions") or []
    lines.append(f"Versi  : {len(versions)}")
    if versions:
        latest = versions[-1]
        lines.append(f"  v{latest.get('version')} · review_status={latest.get('review_status')} · approved={bool(latest.get('human_approved'))}")
        lines.append("  --- draft terbaru ---")
        content = (latest.get("content") or "").strip()
        lines.extend("  " + row for row in content.splitlines()[:20])
        lines.append("  --- temuan ---")
        lines.extend(review_lines(latest.get("review")))
    return "\n".join(lines)


def plan_human(plan: dict) -> str:
    lines = [
        f"Objective : {plan.get('objective', '?')}",
        f"Audience  : {plan.get('audience', '?')}",
    ]
    facts = plan.get("product_facts") or []
    lines.append(f"Fakta didukung sumber ({len(facts)}):")
    lines.extend(f"  - {fact}" for fact in facts) if facts else lines.append("  (tidak ada)")
    gaps = plan.get("missing_information") or []
    if gaps:
        lines.append("Informasi yang belum ada:")
        lines.extend(f"  ! {gap}" for gap in gaps)
    tasks = plan.get("tasks") or []
    lines.append(f"\nDeliverable ({len(tasks)}):")
    for index, task in enumerate(tasks, 1):
        lines.append(f"  {index}. {task.get('title')} — {task.get('format')} / {task.get('platform')}")
        lines.append(f"     angle : {task.get('angle')}")
        lines.append(f"     goal  : {task.get('goal')}")
        lines.append(f"     alasan: {task.get('selection_reason')}")
    return "\n".join(lines)


def find_task(task_id: str) -> dict:
    home = call("GET", "/api/home")
    for task in home.get("tasks", []):
        if task.get("id") == task_id:
            return task
    for project in call("GET", "/api/projects").get("projects", []):
        for task in project.get("tasks", []):
            if task.get("id") == task_id:
                return task
    raise CLIError(f"Task {task_id} tidak ditemukan di akun ini.", "not_found")


# ---------------------------------------------------------------------------
# Perintah
# ---------------------------------------------------------------------------
def cmd_login(args) -> None:
    email = args.email or os.getenv("REKARASA_EMAIL")
    password = args.password or os.getenv("REKARASA_PASSWORD")
    if not email or not password:
        raise CLIError(
            "Set REKARASA_EMAIL dan REKARASA_PASSWORD lebih dulu "
            "(atau pakai --email/--password).",
            "missing_credentials",
        )
    payload = {"email": email, "password": password}
    request = Request(
        BASE + "/api/login",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            body = json.loads(response.read())
            cookie = extract_cookie(response.headers)
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read())
        except (json.JSONDecodeError, UnicodeDecodeError):
            detail = {}
        raise CLIError(
            detail.get("error") or f"Login gagal (HTTP {exc.code}).",
            detail.get("code") or "login_failed",
            exc.code,
        )
    except URLError as exc:
        raise CLIError(f"Server tidak bisa dihubungi ({exc.reason}).", "unreachable")
    if not cookie:
        raise CLIError("Login berhasil tetapi cookie sesi tidak diterima.", "no_cookie")
    save_session(cookie, body["csrf"], body["user"]["email"])
    emit(
        {"ok": True, "email": body["user"]["email"], "csrf_received": bool(body.get("csrf"))},
        f"Login berhasil sebagai {body['user']['email']}.\nSesi disimpan di {SESSION_FILE}",
    )


def cmd_logout(args) -> None:
    try:
        call("POST", "/api/logout", {})
    except CLIError:
        pass
    clear_session()
    emit({"ok": True}, "Logout. Sesi lokal dihapus.")


def cmd_whoami(args) -> None:
    data = call("GET", "/api/session")
    user = data.get("user") or {}
    emit(
        data,
        f"Akun        : {user.get('email', '(belum login)')}\n"
        f"Provider    : {data.get('provider')}\n"
        f"Terkonfigurasi: {data.get('provider_configured')}\n"
        f"Status      : {data.get('provider_status')}\n"
        f"Model       : {data.get('model')}",
    )


def cmd_projects(args) -> None:
    data = call("GET", "/api/projects")
    projects = data.get("projects", [])
    lines = [f"Proyek: {len(projects)}"]
    for project in projects:
        lines.append(
            f"  {project.get('id')}  {project.get('name')}  "
            f"({len(project.get('sources', []))} sumber, {len(project.get('tasks', []))} task)"
        )
    emit(data, "\n".join(lines))


def cmd_project_create(args) -> None:
    data = call("POST", "/api/projects", {"name": args.name})
    emit(data, f"Proyek dibuat: {data.get('name')} ({data.get('id')})")


def cmd_source_add(args) -> None:
    if args.file:
        path = Path(args.file)
        if not path.is_file():
            raise CLIError(f"File tidak ditemukan: {path}", "file_missing")
        content = path.read_text(encoding="utf-8")
        name = args.name or path.name
    elif args.content:
        content = args.content
        name = args.name or "Source.md"
    else:
        raise CLIError("Isi --file atau --content.", "missing_content")

    if not name.lower().endswith((".txt", ".md", ".markdown")):
        raise CLIError(
            "Nama sumber harus berakhiran .txt / .md / .markdown "
            "(batasan server).", "unsupported_media"
        )
    media = "text/plain" if name.lower().endswith(".txt") else "text/markdown"
    data = call(
        "POST",
        "/api/sources",
        {"project_id": args.project, "name": name, "content": content, "media_type": media},
    )
    emit(data, f"Sumber ditambahkan: {data.get('name')} ({data.get('id')})")


def cmd_plan(args) -> None:
    if args.brief_file:
        brief = Path(args.brief_file).read_text(encoding="utf-8")
    elif args.brief:
        brief = args.brief
    else:
        raise CLIError("Isi --brief atau --brief-file.", "missing_brief")

    body = {
        "brief": brief,
        "project_id": args.project,
        "audience": args.audience or "",
        "tone": args.tone or "",
    }
    if args.prefer:
        body["output_preferences"] = args.prefer
    if args.platforms:
        body["platform_preferences"] = args.platforms
    if args.custom:
        body["custom_format"] = args.custom
    if args.conversation:
        body["conversation_id"] = args.conversation

    data = call("POST", "/api/plan", body)
    emit(
        data,
        f"plan_id: {data.get('plan_id')}\nconversation_id: {data.get('conversation_id')}\n\n"
        + plan_human(data.get("plan", {})),
    )


def cmd_confirm(args) -> None:
    body = {"plan_id": args.plan}
    if args.tasks_file:
        body["tasks"] = json.loads(Path(args.tasks_file).read_text(encoding="utf-8"))
    data = call("POST", "/api/confirm-plan", body)
    tasks = data.get("tasks", [])
    lines = [f"Task dibuat: {len(tasks)}"]
    for task in tasks:
        lines.append(f"  {task.get('id')}  {task.get('title')} — {task.get('format')}")
    emit(data, "\n".join(lines))


def cmd_generate(args) -> None:
    data = call("POST", "/api/generate", {"task_id": args.task})
    emit(data, task_human(data.get("task", {})))


def cmd_revise(args) -> None:
    data = call("POST", "/api/revise", {"task_id": args.task})
    emit(
        data,
        f"Percobaan {data.get('attempt')}/{data.get('max_attempts')}\n\n"
        + task_human(data.get("task", {})),
    )


def cmd_task(args) -> None:
    task = find_task(args.task)
    emit(task, task_human(task))


def cmd_decide(args, decision: str) -> None:
    path = "/api/approve" if decision == "approve" else "/api/reject"
    data = call("POST", path, {"task_id": args.task, "note": args.note or ""})
    emit(
        data,
        f"Keputusan: {data.get('decision')}\nStatus task: {data.get('task', {}).get('status')}",
    )


def cmd_audit(args) -> None:
    data = call("GET", "/api/audit")
    events = data.get("events", [])
    if args.out:
        Path(args.out).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    lines = [f"Event audit: {len(events)}"]
    for event in events:
        lines.append(
            f"  {event.get('created_at', '?')[:19]}  {event.get('event', '?'):<24} "
            f"{event.get('project_name') or '-'}"
        )
    if args.out:
        lines.append(f"\nDisimpan ke {args.out}")
    emit(data, "\n".join(lines))


def cmd_rules(args) -> None:
    data = call("GET", "/api/rules")
    lines = [f"Aturan demo terdaftar: {len(data.get('rules', []))}"]
    for rule in data.get("rules", []):
        lines.append(f"  {rule.get('id')} v{rule.get('version')}")
        lines.append(f"     {rule.get('text')}")
    lines.append(f"\n{data.get('notice', '')}")
    emit(data, "\n".join(lines))


def cmd_usage(args) -> None:
    data = call("GET", "/api/usage")
    emit(
        data,
        f"Panggilan model : {data.get('calls')}\n"
        f"Input token     : {data.get('input_tokens')}\n"
        f"Output token    : {data.get('output_tokens')}",
    )


def cmd_holidays(args) -> None:
    data = call("GET", "/api/holidays")
    holidays = data.get("holidays", [])
    if not holidays:
        emit(data, "Tidak ada hari besar dalam 30 hari ke depan.")
        return
    lines = [f"Hari besar Indonesia (30 hari ke depan): {len(holidays)}"]
    for h in holidays:
        relative = "hari ini" if h.get("days_until") == 0 else f"{h.get('days_until')} hari lagi"
        lines.append(f"  {h.get('date')}  {h.get('name')}  [{h.get('type')}]  ({relative})")
    emit(data, "\n".join(lines))


def cmd_home(args) -> None:
    data = call("GET", "/api/home")
    counts = data.get("counts", {})
    lines = [
        f"Perlu revisi     : {counts.get('needs_review')}",
        f"Menunggu approval: {counts.get('awaiting_human')}",
        f"Sudah disetujui  : {counts.get('approved')}",
        "",
    ]
    for task in data.get("tasks", []):
        lines.append(
            f"  {task.get('id')}  [{task.get('status')}]  {task.get('title')}"
        )
    emit(data, "\n".join(lines))


def cmd_edit(args) -> None:
    """Simpan suntingan manusia sebagai versi baru (status kembali needs_revision)."""
    if args.content_file:
        content = Path(args.content_file).read_text(encoding="utf-8")
    elif args.content:
        content = args.content
    else:
        raise CLIError("Isi --content atau --content-file.", "missing_content")
    data = call("POST", "/api/edit", {"task_id": args.task, "content": content})
    task = data.get("task", {})
    versions = task.get("versions") or []
    latest = versions[-1] if versions else {}
    emit(
        data,
        f"Versi baru disimpan: v{latest.get('version')}\n"
        f"Status task: {task.get('status')}\n"
        f"review_status: {latest.get('review_status')} — jalankan `review-edit` untuk memeriksanya.",
    )


def cmd_review_edit(args) -> None:
    """Jalankan Reviewer pada versi hasil suntingan manusia / setelah review_error."""
    data = call("POST", "/api/review-edit", {"task_id": args.task})
    emit(data, task_human(data.get("task", {})))


def cmd_set_dates(args) -> None:
    body = {"task_id": args.task, "deadline": args.deadline, "publish_at": args.publish_at}
    data = call("POST", "/api/set-dates", body)
    task = data.get("task", {})
    emit(
        data,
        f"deadline   : {task.get('deadline')}\n"
        f"publish_at : {task.get('publish_at')}",
    )


def cmd_images(args) -> None:
    data = call("GET", "/api/images?task_id=" + args.task)
    images = data.get("images", [])
    lines = [f"Gambar tersimpan: {len(images)}"]
    for image in images:
        lines.append(
            f"  {image.get('id')}  {image.get('provider')}/{image.get('model')}  "
            f"{image.get('size')}  {image.get('created_at')}"
        )
    lines.append("\nPrompt default tersedia di field default_prompt.")
    for composition in data.get("compositions", []):
        lines.append(f"  Komposisi {composition['id']}: {composition['status']} (copy {composition['version_id']})")
    emit(data, "\n".join(lines))


def cmd_compose_visual(args) -> None:
    data = call("POST", "/api/compose-visual", {"image_id": args.image, "version_id": args.version})
    composition = data["composition"]
    emit(data, f"Komposisi: {composition['id']}\nStatus: {composition['status']}\nBuka workbench untuk pemeriksaan dan approval manusia. Komposisi tidak disetujui oleh agent.")


def cmd_generate_image(args) -> None:
    body = {"task_id": args.task, "prompt": args.prompt, "ratio": args.ratio}
    body["mode"] = args.mode
    if args.asset:
        body["asset_id"] = args.asset
    if args.strength is not None:
        body["strength"] = args.strength
    if args.seed is not None:
        body["seed"] = args.seed
    if getattr(args, "provider", None):
        body["provider"] = args.provider
    data = call("POST", "/api/generate-image", body)
    image = data.get("image", {})
    note = ""
    if data.get("prompt_filtered"):
        # Tell the caller instead of letting them assume their full direction
        # reached the model. The stored prompt shows exactly what replaced it.
        note = "\nCatatan: sebagian arahan prompt difilter sebagai instruksi sistem. Lihat prompt tersimpan untuk teks final."
    emit(
        data,
        f"Gambar dibuat: {image.get('id')}\n"
        f"provider/model: {image.get('provider')}/{image.get('model')}\n"
        f"ukuran: {image.get('size')}\n"
        f"URL   : {image.get('media_url')}"
        f"{note}",
    )


def cmd_rename_project(args) -> None:
    data = call(
        "POST", "/api/rename-project", {"project_id": args.project, "name": args.name}
    )
    emit(data, f"Proyek diganti nama menjadi: {data.get('name')}")



# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    # --human / --base-url harus diterima BAIK sebelum maupun sesudah
    # subcommand. default=SUPPRESS mencegah subparser menimpa nilai yang
    # sudah diisi parser induk.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--human", action="store_true", default=argparse.SUPPRESS,
                        help="Ringkasan ramah manusia")
    common.add_argument("--base-url", default=argparse.SUPPRESS,
                        help="Override REKARASA_URL")

    parser = argparse.ArgumentParser(
        prog="rekarasa_cli",
        description="Jembatan CLI WorkBuddy → RekaRasa.ai (Challenge C).",
    )
    parser.add_argument("--human", action="store_true", help="Ringkasan ramah manusia")
    parser.add_argument("--base-url", help="Override REKARASA_URL")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str):
        return sub.add_parser(name, parents=[common], help=help_text)

    p = add("login", "Masuk dan simpan sesi")
    p.add_argument("--email")
    p.add_argument("--password")
    p.set_defaults(func=cmd_login)

    add("logout", "Hapus sesi lokal").set_defaults(func=cmd_logout)
    add("whoami", "Status akun & provider").set_defaults(func=cmd_whoami)
    add("projects", "Daftar proyek").set_defaults(func=cmd_projects)
    add("home", "Ringkasan task & hitungan status").set_defaults(func=cmd_home)
    add("rules", "Registry aturan demo").set_defaults(func=cmd_rules)
    add("usage", "Pemakaian token").set_defaults(func=cmd_usage)
    add("holidays", "Hari besar Indonesia (30 hari ke depan)").set_defaults(func=cmd_holidays)

    p = add("project-create", "Buat proyek baru")
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_project_create)

    p = add("rename-project", "Ganti nama proyek")
    p.add_argument("--project", required=True)
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_rename_project)

    p = add("source-add", "Tambah sumber teks/markdown")
    p.add_argument("--project", required=True)
    p.add_argument("--file", help="Path file .md/.txt")
    p.add_argument("--content", help="Isi langsung")
    p.add_argument("--name", help="Nama sumber (default: nama file)")
    p.set_defaults(func=cmd_source_add)

    p = add("plan", "Jalankan Planner")
    p.add_argument("--project", required=True)
    p.add_argument("--brief")
    p.add_argument("--brief-file")
    p.add_argument("--audience")
    p.add_argument("--tone")
    p.add_argument("--prefer", nargs="*", help="Preferensi output (opsional)")
    p.add_argument("--platforms", nargs="*", choices=["Instagram", "TikTok", "Facebook", "Threads", "X", "Marketplace"], help="Preferensi kanal (opsional)")
    p.add_argument("--custom", help="Format custom (opsional)")
    p.add_argument("--conversation", help="Lanjutkan conversation_id")
    p.set_defaults(func=cmd_plan)

    p = add("confirm", "Konfirmasi rencana → buat task")
    p.add_argument("--plan", required=True)
    p.add_argument("--tasks-file", help="JSON array task hasil edit manusia")
    p.set_defaults(func=cmd_confirm)

    p = add("generate", "Writer + Reviewer untuk satu task")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_generate)

    p = add("revise", "Remediasi Writer (maks 3x)")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_revise)

    p = add("edit", "Simpan suntingan manusia sebagai versi baru")
    p.add_argument("--task", required=True)
    p.add_argument("--content")
    p.add_argument("--content-file")
    p.set_defaults(func=cmd_edit)

    p = add("review-edit", "Reviewer pada versi hasil suntingan / setelah review_error")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_review_edit)

    p = add("task", "Detail task: versi, review, temuan")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_task)

    p = add("set-dates", "Atur deadline & waktu publikasi")
    p.add_argument("--task", required=True)
    p.add_argument("--deadline", help="ISO date/datetime")
    p.add_argument("--publish-at", help="ISO date/datetime")
    p.set_defaults(func=cmd_set_dates)

    p = add("images", "Daftar gambar tersimpan untuk task")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_images)

    p = add("generate-image", "Create an image concept (ComfyUI or configured Cloudflare)")
    p.add_argument("--provider", choices=["comfyui", "cloudflare"], help="Image provider; no automatic fallback")
    p.add_argument("--mode", choices=["concept", "img2img"], default="concept")
    p.add_argument("--asset", help="Existing Project photo ID for image-to-image")
    p.add_argument("--strength", type=float, help="Image-to-image change strength, 0.1 to 0.85")
    p.add_argument("--seed", type=int, help="Optional reproducible sampling seed")
    p.add_argument("--task", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--ratio", default="square", choices=["square", "portrait", "story", "landscape"])
    p.set_defaults(func=cmd_generate_image)

    p = add("compose-visual", "Tempatkan copy versi terbaru pada gambar; approval tetap di workbench")
    p.add_argument("--image", required=True)
    p.add_argument("--version")
    p.set_defaults(func=cmd_compose_visual)

    p = add("approve", "Approval manusia (butuh verdict Pass)")
    p.add_argument("--task", required=True)
    p.add_argument("--note")
    p.set_defaults(func=lambda a: cmd_decide(a, "approve"))

    p = add("reject", "Minta perubahan / eskalasi")
    p.add_argument("--task", required=True)
    p.add_argument("--note")
    p.set_defaults(func=lambda a: cmd_decide(a, "reject"))

    p = add("audit", "Jejak audit")
    p.add_argument("--out", help="Simpan JSON ke file")
    p.set_defaults(func=cmd_audit)

    return parser



def main() -> int:
    global HUMAN, BASE
    args = build_parser().parse_args()
    HUMAN = args.human
    if args.base_url:
        BASE = args.base_url.rstrip("/")
    try:
        args.func(args)
        return 0
    except CLIError as exc:
        print(
            json.dumps(
                {"error": exc.message, "code": exc.code, "status": exc.status},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
