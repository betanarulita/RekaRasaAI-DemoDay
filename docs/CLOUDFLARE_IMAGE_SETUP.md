# Cloudflare Workers AI image generation

RekaRasa's backend calls Cloudflare Workers AI directly. **No separate Cloudflare Worker deployment is required.** When configured, ComfyUI remains the primary provider and Cloudflare is used automatically for text-to-image concepts if ComfyUI returns an upstream/unavailable error. Image-to-image and background editing continue to require ComfyUI. Cloudflare can also be selected explicitly for text-to-image concepts.

The configured model is `@cf/black-forest-labs/flux-1-schnell`. Cloudflare documents a maximum prompt length of 2,048 characters and returns the generated image as base64. The model generates a square source image; RekaRasa fits that image to the selected canvas, which can crop some edges on portrait or landscape canvases. This integration does not edit uploaded reference images.

## Cloudflare account setup

1. In the Cloudflare dashboard, open **Workers AI** and review the current plan and usage allocation. Workers AI currently documents 10,000 Neurons per day at no charge on Workers Free. Quota is shared across the account, resets at 00:00 UTC, and requests can fail after it is exhausted. Confirm current pricing before enabling generation; the confirmation flag in RekaRasa does not enforce a billing cap.
2. Create a Cloudflare API token for Workers AI. Use the permissions Cloudflare documents for the model-run API (Workers AI Read; the dashboard's Workers AI token template may include both Read and Edit).
3. Copy the account ID from the dashboard. Keep the API token private; never put it in browser code, Git, or chat.

## Local development

Set these variables in the local server environment:

```dotenv
IMAGE_PROVIDER=comfyui
IMAGE_PROVIDER_FALLBACK=cloudflare
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_private_api_token
CLOUDFLARE_WORKERS_FREE_CONFIRMED=1
```

`IMAGE_PROVIDER=comfyui` keeps local ComfyUI as the primary provider. `IMAGE_PROVIDER_FALLBACK=cloudflare` enables automatic fallback for text-to-image concepts when ComfyUI is busy or returns a 429, 502, 503, or 504 provider error. It does not change image editing. Cloudflare can also be selected directly in the image studio. Restart the backend after changing environment variables. The Cloudflare connection check reads the model schema and does not generate an image or check remaining quota.

## WorkBuddy hosting

Set the same server-side variables in the existing WorkBuddy app's environment settings. For ComfyUI-primary with Cloudflare fallback, use `IMAGE_PROVIDER=comfyui` and `IMAGE_PROVIDER_FALLBACK=cloudflare`. Because WorkBuddy cannot reach ComfyUI on the developer's PC, hosted text-to-image requests will use Cloudflare when ComfyUI is unavailable. Add the Account ID and API token as private environment variables, and set the confirmation flag only after checking the account plan. Redeploy/restart the existing app after updating its environment; preserve its current app URL and database settings.

Cloudflare receives the image prompt directly from the RekaRasa backend. Do not send API tokens to the frontend. Fallback occurs only for ComfyUI busy/rate-limit/unavailable errors; invalid user input and editing requests do not fallback. For Cloudflare error `429`, check Workers AI quota/rate limits; for `401` or `403`, verify token permissions and Account ID.

## References

- [FLUX.1 Schnell model and input/output format](https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/)
- [Workers AI pricing and free allocation](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [Workers AI REST API setup](https://developers.cloudflare.com/workers-ai/get-started/rest-api/)
