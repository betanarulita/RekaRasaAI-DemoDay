"""Agnes transport; local eligibility confirmation is not a billing guarantee."""
from __future__ import annotations

import base64
import binascii
import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MODEL = "agnes-image-2.1-flash"
BASE = "https://apihub.agnes-ai.com/v1"
MAX_IMAGE = 15_000_000
MAX_JSON = 23_000_000


class AgnesError(Exception):
    def __init__(self, message: str, code: str, status: int = 503):
        super().__init__(message)
        self.code, self.status = code, status


def agnes_readiness() -> tuple[bool, str]:
    if not os.getenv("AGNES_API_KEY", "").strip():
        return False, "Set AGNES_API_KEY on the server."
    if os.getenv("AGNES_FREE_TIER_CONFIRMED", "0").strip() != "1":
        return False, "Confirm the default-account $0 trial in Agnes billing before enabling this provider. Agent Plan is excluded."
    try:
        expires = datetime.strptime(os.getenv("AGNES_FREE_UNTIL", ""), "%Y-%m-%d").date()
    except ValueError:
        return False, "Set AGNES_FREE_UNTIL to the last date you have confirmed $0 access (YYYY-MM-DD)."
    if datetime.now(timezone.utc).date() > expires:
        return False, "Agnes free-access confirmation expired. Recheck pricing and account eligibility."
    return True, "Account trial confirmed locally; provider billing remains authoritative. No automatic retries or provider fallback."


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_bounded(response, limit: int) -> bytes:
    raw = response.read(limit + 1)
    if len(raw) > limit:
        raise AgnesError("Agnes returned an oversized response.", "image_invalid", 502)
    return raw


def fetch_image(url: str) -> bytes:
    allowed = {"apihub.agnes-ai.com", "agnes-ai.com"}
    allowed.update(host.strip().lower() for host in os.getenv("AGNES_IMAGE_HOSTS", "").split(",") if host.strip())
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in allowed or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise AgnesError("Agnes returned an image host that is not allowed. Verify its CDN hostname and configure AGNES_IMAGE_HOSTS.", "image_download_host_blocked", 502)
    # Never forward the API key to an image URL or follow a redirect to another host.
    with build_opener(NoRedirect()).open(Request(url, headers={"Accept": "image/png,image/jpeg"}), timeout=30) as response:
        return read_bounded(response, MAX_IMAGE)


def generate_agnes(prompt: str, size: str) -> tuple[bytes, str]:
    ready, reason = agnes_readiness()
    if not ready:
        raise AgnesError(reason, "agnes_free_access_unconfirmed")
    if not isinstance(prompt, str) or not 1 <= len(prompt) <= 16000:
        raise AgnesError("Invalid image prompt.", "invalid_prompt", 400)
    if size not in {"1024x1024", "1024x1280", "1008x1792", "1344x768"}:
        raise AgnesError("Unsupported image size.", "invalid_size", 400)
    payload = {"model": MODEL, "prompt": prompt, "size": size}
    request = Request(BASE + "/images/generations", data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + os.environ["AGNES_API_KEY"].strip(), "Content-Type": "application/json"}, method="POST")
    try:
        with build_opener(NoRedirect()).open(request, timeout=120) as response:
            result = json.loads(read_bounded(response, MAX_JSON))
        if not isinstance(result, dict) or not isinstance(result.get("data"), list) or not result["data"] or not isinstance(result["data"][0], dict):
            raise AgnesError("Agnes did not return an image result.", "image_provider_malformed", 502)
        item = result["data"][0]
        if isinstance(item.get("b64_json"), str):
            raw = base64.b64decode(item["b64_json"], validate=True)
        elif isinstance(item.get("url"), str):
            raw = fetch_image(item["url"])
        else:
            raise AgnesError("Agnes returned no supported image payload.", "image_provider_malformed", 502)
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise AgnesError("Agnes rejected access. Check the key and account permissions.", "image_provider_auth", 502) from exc
        if exc.code in (402, 429):
            raise AgnesError("Agnes free access or quota is unavailable. No retry or fallback was attempted; choose ComfyUI.", "image_provider_quota", 503) from exc
        raise AgnesError("Agnes returned HTTP " + str(exc.code) + ". No automatic retry was attempted.", "image_provider_error", 502) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AgnesError("Agnes could not be reached. The request may have been accepted; inspect provider history before retrying.", "image_provider_unavailable", 502) from exc
    except (ValueError, TypeError, KeyError, binascii.Error) as exc:
        raise AgnesError("Agnes returned an unreadable image response.", "image_provider_malformed", 502) from exc
    if not raw or len(raw) > MAX_IMAGE:
        raise AgnesError("Agnes returned an empty or oversized image.", "image_invalid", 502)
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and b"IEND" in raw[-16:]:
        return raw, "image/png"
    if raw.startswith(b"\xff\xd8\xff") and raw.endswith(b"\xff\xd9"):
        return raw, "image/jpeg"
    raise AgnesError("Agnes did not return a supported PNG or JPEG image.", "image_invalid", 502)
