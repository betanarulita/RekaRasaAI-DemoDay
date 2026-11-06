# Image-to-image addition (2026-11-05)

ComfyUI now supports text-to-image, source-photo image-to-image with adjustable strength, and protected background editing. The installed checkpoint remains SD 1.5. See [handbook mapping and verification](CHALLENGE_C_IMPLEMENTATION_2026-11-05.md) for the 66 targeted tests and two actual local generations. Sections below record earlier setup passes; their verification limits describe those earlier passes.

# Optional Cloudflare text concepts (2026-11-05)

Cloudflare is an explicit additional choice, disabled until configured. ComfyUI remains the default. See [setup and limits](CLOUDFLARE_IMAGE_SETUP.md). No automatic provider fallback is used. Original-photo editing still uses ComfyUI; original-photo composition needs neither service.

# Default setup: local ComfyUI

The previous Agnes setup below is superseded. RekaRasa defaults to ComfyUI and supports explicitly selected Cloudflare text concepts after configuration. Agnes trial flags are disabled in the local configuration; its stored key is left untouched and unused. The old adapter is retained as inactive source, not imported or copied into the application Docker image.

## Local integration improvements

- Authenticated GET /api/image-status checks the service and configured checkpoint. The studio provides a connection-status message and Check connection action.
- Generation is serialized within each RekaRasa server process to reduce simultaneous GPU jobs. This is not a distributed GPU queue or durable job system.
- New concepts are sampled at SD 1.5 scale and resized to the requested canvas. Only final SaveImage node output is selected, and PNG dimensions are checked against the expected canvas.
- Reference edits resize the image and mask internally for inference, resize the edited result back, then composite against the original photo and original mask. Protected pixels come from the decoded original. The mask must match the original dimensions; each side is limited to 8192 pixels and total resolution to 24 megapixels. JPEG EXIF orientation and arbitrary uploads still require end-to-end verification.
- The previous requirement to manually upload a resized, divisible-by-eight copy is removed.
- Normal in-progress history messages are not mistaken for execution failure. GPU memory errors, missing models, offline service, and timeouts receive separate recovery messages. A timed-out job can still be running in ComfyUI, so retry is never automatic.
- Original-photo composition needs no image-generation service. Existing Project materials, versioned copy, review and separate human visual approval remain in place.

## Readiness observed

GET /system_stats and /object_info responded. Required ImageScale, MaskToImage, ImageToMask, VAEEncodeForInpaint, ImageCompositeMasked and SaveImage nodes are present. The installed checkpoint is v1-5-pruned-emaonly.safetensors. SD 1.5 remains a quality limitation: this integration change is not a model upgrade.

## Verification limits

The selected-image edit flow was verified with one real local ComfyUI job on 6 November 2026 using the installed `v1-5-pruned-emaonly.safetensors` checkpoint and an NVIDIA GeForce RTX 4050 Laptop GPU. The request supplied the selected composition raster and reached ComfyUI as an image-to-image reference; a new PNG and unapproved composition were persisted while the source image remained intact. The text planner was stubbed only in this harness to avoid external text-provider calls. Final visual quality still requires human inspection, and durable worker recovery remains separate engineering work.

---

# Historical setup (superseded): ComfyUI and Agnes

# Image providers: ComfyUI and Agnes

## Configuration

Pollinations and OpenAI Images routing have been removed. Existing saved images and audit history are retained. The local image configuration now defaults to ComfyUI at http://127.0.0.1:8188 with the installed v1-5-pruned-emaonly.safetensors checkpoint. Unrelated SMTP and text-model configuration is unchanged.

The image studio offers explicit ComfyUI/Agnes concept generation. Original-photo editing still uses the existing ComfyUI asset and protection-mask workflow. There is no automatic provider fallback or automatic retry of Agnes generation requests. WorkBuddy CLI accepts `generate-image --provider comfyui` or `--provider agnes`.

## ComfyUI

The installed workflow uses core SD checkpoint nodes, not Qwen or FLUX adapters. New concepts are sampled at a maximum 512px latent dimension and resized to the requested canvas. Resizing does not add native high-resolution detail. SD 1.5 quality limitations remain; original-photo composition is available without generation.

Start from PowerShell, provided port 8188 is not already occupied:

```powershell
Set-Location D:\AI-Experiments\ComfyUI
.\.venv\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188
```

Docker Desktop containers need a reachable host address such as `host.docker.internal`, rather than container loopback. Ensure the host ComfyUI listener and firewall permit the container connection without exposing the service publicly. Docker now copies the provider module and the existing agent module required by the backend.

## Agnes free access

[Official pricing](https://agnes-ai.com/en/docs/pricing), checked 2026-11-05, lists a zero-dollar image trial for default accounts. Agent Plan usage is excluded from model-level free promotions. Eligibility and actual billing remain provider-controlled.

Agnes stays blocked until a server-side key, `AGNES_FREE_TIER_CONFIRMED=1`, and an unexpired `AGNES_FREE_UNTIL` date are configured locally. Use YYYY-MM-DD; expiry is evaluated in UTC. Set a short recheck date after inspecting account eligibility and available provider spending controls. No key, free-account confirmation, or expiry date was invented during setup.

These local flags are an operator confirmation, not a provider-enforced zero-spend guarantee. If a no-paid-usage restriction cannot be established on the provider account, leave Agnes disabled and use ComfyUI. Promotions can change independently of application code.

Only `agnes-image-2.1-flash` is selected. Agnes reference editing is not enabled: the prototype ZIP guessed two edit formats and contained unreachable fallback logic. Model-specific edit documentation and a distinctive-reference canary are required before extending it.

Responses are bounded and validated as PNG/JPEG. Image URL downloads require HTTPS and an exact permitted hostname; redirects are refused and API credentials are not forwarded to image URLs. Set `AGNES_IMAGE_HOSTS` only for a verified CDN hostname returned by the provider. Provider failures never silently switch to another service.

## Existing workflow

Uploads remain in Project through the existing Excel/CSV/photo pipeline; no re-upload in WorkBuddy is needed. New generated images use existing task ownership, storage, audit, versioned composition, and human approval. Text review does not verify visual product identity or certification. Inspect every visual before approval/export.

## Validation limits

No Agnes requests or generation jobs were submitted during setup. Syntax checks are not proof of output quality or free billing. ComfyUI startup/readiness is recorded separately. The original Image Bridge ZIP and marketplace registration were not modified.

## Local startup result

ComfyUI was started as a hidden local process and GET /system_stats succeeded. It reports an NVIDIA GeForce RTX 4050 Laptop GPU with about 6 GiB VRAM. This confirms the server is reachable, not that a generation job has passed. Restart RekaRasa to load its updated provider module and configuration. Historical provider images remain accessible through history, but are not chosen as the default concept preview.
