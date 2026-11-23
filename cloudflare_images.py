"""Direct server-side client for Cloudflare Workers AI image generation."""

import base64
import json
import os
import re
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from catalog_import import image_dimensions

MODEL = "@cf/black-forest-labs/flux-1-schnell"
API_BASE = "https://api.cloudflare.com/client/v4/accounts"
MAX_RESPONSE_BYTES = 24_000_000
MAX_PROMPT_CHARS = 2048


class CloudflareImageError(Exception):
    def __init__(self, message, code="image_provider_unavailable", status=503):
        super().__init__(message)
        self.code, self.status = code, status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def configuration():
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not re.fullmatch(r"[a-fA-F0-9]{32}", account_id) or len(api_token) < 20:
        raise CloudflareImageError(
            "Set the Cloudflare account ID and Workers AI API token in the server environment.",
            "image_provider_unconfigured",
        )
    if os.getenv("CLOUDFLARE_WORKERS_FREE_CONFIRMED", "0") != "1":
        raise CloudflareImageError(
            "Confirm the Cloudflare Workers plan and usage limit in the server environment.",
            "image_free_plan_unconfirmed",
        )
    return account_id, api_token


def request_cloudflare(method, payload=None, timeout=15):
    account_id, api_token = configuration()
    model_path = quote(MODEL, safe="@/")
    url = f"{API_BASE}/{account_id}/ai/run/{model_path}"
    if method == "GET":
        url = f"{API_BASE}/{account_id}/ai/models/schema?{urlencode({'model': MODEL})}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers={
        "Authorization": "Bearer " + api_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "RekaRasaAI/1.0",
    }, method=method)
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
            if len(content) > MAX_RESPONSE_BYTES:
                raise CloudflareImageError("Cloudflare returned an oversized image response.", "image_provider_invalid_response")
            return json.loads(content)
    except HTTPError as exc:
        if exc.code == 429:
            raise CloudflareImageError("Cloudflare's rate limit or free daily allocation was reached. Check usage before retrying.", "image_provider_limit", 429) from None
        if exc.code in (401, 403):
            raise CloudflareImageError("Cloudflare rejected the API token or its Workers AI permissions.", "image_provider_auth", 503) from None
        if exc.code == 400:
            raise CloudflareImageError("Cloudflare rejected the FLUX prompt or request parameters.", "image_provider_invalid_request", 400) from None
        raise CloudflareImageError("Cloudflare Workers AI could not complete the image request.") from None
    except (URLError, OSError, TimeoutError):
        raise CloudflareImageError("Cloudflare Workers AI could not be reached. The previous request may still be processing.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise CloudflareImageError("Cloudflare returned an unreadable response.", "image_provider_invalid_response") from None


def status(check_remote=False):
    try:
        configuration()
        if check_remote:
            data = request_cloudflare("GET")
            if not data.get("success") or not isinstance(data.get("result", {}).get("input"), dict):
                raise CloudflareImageError("Cloudflare could not verify the configured FLUX model or token permissions.")
        return {
            "ready": True,
            "state": "ready" if check_remote else "configured",
            "message": "Cloudflare Workers AI is reachable. This check does not generate an image or verify remaining quota." if check_remote else "Cloudflare is configured; connection and quota have not been checked.",
        }
    except (CloudflareImageError, ValueError, TypeError, AttributeError) as exc:
        return {"ready": False, "state": "unavailable", "message": str(exc) if isinstance(exc, CloudflareImageError) else "Cloudflare returned an invalid model schema."}


def _decode_image(data):
    if not isinstance(data, dict) or not data.get("success"):
        raise CloudflareImageError("Cloudflare did not return a generated image.", "image_provider_invalid_response")
    result = data.get("result")
    encoded = result.get("image") if isinstance(result, dict) else None
    if not isinstance(encoded, str) or not encoded:
        raise CloudflareImageError("Cloudflare did not return a generated image.", "image_provider_invalid_response")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise CloudflareImageError("Cloudflare returned an invalid image encoding.", "image_provider_invalid_response") from None
    if len(content) > 15_000_000:
        raise CloudflareImageError("Cloudflare returned an oversized image.", "image_provider_invalid_response")
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return content, "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return content, "image/jpeg"
    raise CloudflareImageError("Cloudflare returned an unsupported image format.", "image_provider_invalid_response")


def _fit_canvas(content, media_type, width, height):
    try:
        from PIL import Image, ImageOps

        with Image.open(BytesIO(content)) as source:
            image = ImageOps.fit(source.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
            fitted = output.getvalue()
    except Exception:
        raise CloudflareImageError("The generated image could not be fitted to the selected canvas.", "image_provider_invalid_response") from None
    if image_dimensions(fitted, "image/jpeg") != (width, height):
        raise CloudflareImageError("Cloudflare returned an invalid canvas size.", "image_provider_invalid_response")
    return fitted, "image/jpeg"


def generate(prompt, size):
    try:
        width, height = map(int, size.split("x"))
    except (AttributeError, TypeError, ValueError):
        raise CloudflareImageError("Choose a supported image canvas.", "image_provider_invalid_request", 400) from None
    prompt = str(prompt or "").strip()
    if not prompt:
        raise CloudflareImageError("Add an image direction before generating.", "image_provider_invalid_request", 400)
    if len(prompt) > MAX_PROMPT_CHARS:
        raise CloudflareImageError("Shorten the image direction to 2,048 characters for FLUX.1 Schnell.", "image_prompt_too_long", 400)

    # FLUX.1 Schnell returns a square image; the application fits it to the requested canvas.
    data = request_cloudflare("POST", {"prompt": prompt, "steps": 4}, timeout=180)
    content, media_type = _decode_image(data)
    if media_type == "image/jpeg":
        try:
            dimensions = image_dimensions(content, media_type)
        except (ValueError, IndexError, TypeError):
            dimensions = None
        if dimensions == (width, height):
            return content, media_type
    return _fit_canvas(content, media_type, width, height)
