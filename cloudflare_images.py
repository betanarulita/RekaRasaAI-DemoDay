"""Server-side client for the separately deployed RekaRasa image Worker."""

import json
import os
import struct
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from catalog_import import image_dimensions

MODEL = "@cf/stabilityai/stable-diffusion-xl-base-1.0"
PROTOCOL = "rekarasa-image-v1"
MAX_BYTES = 15_000_000


class CloudflareImageError(Exception):
    def __init__(self, message, code="image_provider_unavailable", status=503):
        super().__init__(message)
        self.code, self.status = code, status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def configuration():
    url = os.getenv("CLOUDFLARE_IMAGE_URL", "").strip().rstrip("/")
    key = os.getenv("CLOUDFLARE_IMAGE_API_KEY", "").strip()
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise CloudflareImageError("Use the HTTPS workers.dev URL without a path.", "image_provider_unconfigured") from None
    if (parsed.scheme != "https" or not parsed.hostname
            or not parsed.hostname.endswith(".workers.dev")
            or parsed.username or parsed.password or parsed.netloc != parsed.hostname
            or parsed.path or parsed.query or parsed.fragment or len(key) < 32):
        raise CloudflareImageError("Configure the Worker HTTPS URL and its secret on the server.", "image_provider_unconfigured")
    if os.getenv("CLOUDFLARE_WORKERS_FREE_CONFIRMED", "0") != "1":
        raise CloudflareImageError("Confirm Workers Free in Cloudflare before enabling this option.", "image_free_plan_unconfirmed")
    return url, key


def request_worker(path, payload=None):
    url, key = configuration()
    request = Request(url + path, data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=180 if payload else 10) as response:
            limit = MAX_BYTES if payload else 32768
            content = response.read(limit + 1)
            if len(content) > limit or response.headers.get("X-RekaRasa-Protocol") != PROTOCOL:
                raise CloudflareImageError("Worker response is incompatible. Deploy the supplied RekaRasa Worker.", "image_worker_protocol")
            return content, response.headers.get_content_type()
    except HTTPError as exc:
        if exc.code == 429:
            raise CloudflareImageError("Cloudflare's request limit or free allocation was reached. Check the dashboard before retrying.", "image_provider_limit", 429) from None
        if exc.code in (401, 403):
            raise CloudflareImageError("The Worker rejected authentication. Check the server-side secret.", "image_provider_auth") from None
        raise CloudflareImageError("Cloudflare could not complete the request. Check Worker bindings and usage; no fallback was used.") from None
    except (URLError, OSError, TimeoutError, ValueError):
        raise CloudflareImageError("Cloudflare could not be reached. Check its dashboard before retrying; the previous job may still finish.") from None


def status(check_remote=False):
    try:
        configuration()
        if check_remote:
            content, media_type = request_worker("/health")
            data = json.loads(content)
            if media_type != "application/json" or data.get("model") != MODEL or data.get("protocol") != PROTOCOL or not data.get("ready"):
                raise CloudflareImageError("Worker setup is incomplete. Check its AI and RATE_LIMITER bindings.")
        return {"ready": True, "state": "ready" if check_remote else "configured",
                "message": "Cloudflare Worker is reachable. This check does not generate an image or verify remaining quota." if check_remote else "Cloudflare is configured; connection and quota have not been checked."}
    except (CloudflareImageError, ValueError, TypeError, AttributeError) as exc:
        return {"ready": False, "state": "unavailable", "message": str(exc) if isinstance(exc, CloudflareImageError) else "Worker health response is invalid."}


def generate(prompt, size):
    width, height = map(int, size.split("x"))
    content, media_type = request_worker("/generate", {"prompt": prompt, "width": width, "height": height, "mode": "concept"})
    if media_type not in ("image/png", "image/jpeg"):
        raise CloudflareImageError("Cloudflare did not return an image.", "image_provider_invalid_response")
    try:
        if media_type == "image/png" and (not content.startswith(b"\x89PNG\r\n\x1a\n") or content[12:16] != b"IHDR"):
            raise ValueError("Invalid PNG")
        if media_type == "image/jpeg" and not content.startswith(b"\xff\xd8\xff"):
            raise ValueError("Invalid JPEG")
        dimensions = image_dimensions(content, media_type)
    except (ValueError, IndexError, TypeError, struct.error):
        dimensions = None
    if dimensions != (width, height):
        raise CloudflareImageError("Cloudflare returned an invalid image or canvas size.", "image_provider_invalid_response")
    return content, media_type
