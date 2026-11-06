# Cloudflare text concepts for RekaRasa

## What this enables

An explicit Cloudflare option in the image studio's **New image from text** mode. ComfyUI stays the default, including the automatic brief-to-image path. Original-photo composition and protected background editing retain their existing paths. Cloudflare receives the concept prompt, including brief/source context and Writer visual direction; it does not receive uploaded photos in this integration.

Images use the existing private storage, Project ownership checks, provider/model audit record, versioned copy composition and human visual approval. Text compliance review does not validate visual product identity. No automatic fallback or generation retry is introduced.

## Free allocation and limits

Keep the Cloudflare account on **Workers Free**. Workers AI documents a free allocation of **10,000 Neurons per day**, resetting at 00:00 UTC. On Workers Free, requests fail when that allocation is exceeded; extra usage requires Workers Paid. The repo's claim of 100,000 AI calls daily is not the Workers AI allocation.

The model is fixed to `@cf/stabilityai/stable-diffusion-xl-base-1.0`. Its availability, beta status and pricing can change. This setup does not promise a fixed number of free images or detect later account plan changes. Check billing before enabling it; do not upgrade to Paid if the goal is no usage charges.

The supplied rate limiter targets two generation requests per minute **per Cloudflare location**. It is approximate, not a global daily quota or spending cap. Missing limiter bindings block generation. Health checks do not invoke the model and do not measure remaining allocation.

## Worker setup

Files are in [integrations/cloudflare-image](../integrations/cloudflare-image/):

- [worker.js](../integrations/cloudflare-image/worker.js): server endpoint, authentication, bounded input/output, fixed model and safe errors.
- [wrangler.jsonc](../integrations/cloudflare-image/wrangler.jsonc): Worker name, AI binding and rate limiter.

The most reproducible path is Wrangler 4.36 or newer, because the rate limiter needs binding configuration. Installing/running Wrangler and deployment are operator actions; they have not been run here.

1. Verify **Workers Free** in the Cloudflare dashboard.
2. If you already created a Hello World Worker, change `name` in the config to that exact Worker name. Otherwise choose an unused name.
3. Open a terminal in the integration folder and authenticate:

   ```powershell
   cd D:\RekaRasaAI-DemoDay\integrations\cloudflare-image
   npx wrangler@4 login
   ```

4. Generate a random secret locally. Save it in your password manager and the application's local environment; never paste it in chat or frontend code. For example:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

5. Create the Worker secret. Paste the generated value at the hidden prompt:

   ```powershell
   npx wrangler@4 secret put API_KEY
   ```

6. Deploy the supplied config and code:

   ```powershell
   npx wrangler@4 deploy
   ```

   If Wrangler asks to create the named Worker during secret setup, ensure it is the intended account and name. Do not accept a paid-plan upgrade. The namespace ID `10427` should be changed if another limiter in your account already uses it and you do not intend to share counters.

For the manual dashboard flow, **Start with Hello World** creates the Worker, and its code editor accepts the supplied Worker code. Add `API_KEY` as a **Secret** and a **Workers AI** binding named `AI`. The `RATE_LIMITER` binding must also be configured with limit 2, period 60 and a unique namespace ID. If that binding is not offered by the dashboard, use the supplied Wrangler config; pasting code alone is not the complete setup. No API token should be embedded in the Worker source.

## Application configuration

In the local environment file, add these settings yourself:

```dotenv
IMAGE_PROVIDER=comfyui
CLOUDFLARE_IMAGE_URL=https://YOUR-WORKER.YOUR-SUBDOMAIN.workers.dev
CLOUDFLARE_IMAGE_API_KEY=THE_SAME_SECRET_AS_WORKER_API_KEY
CLOUDFLARE_WORKERS_FREE_CONFIRMED=1
```

The confirmation flag records your manual check, not a billing guarantee. Until URL, secret (at least 32 characters), and confirmation are configured, the Cloudflare choice is disabled. The client accepts a root HTTPS `workers.dev` URL only; redirects are rejected so credentials are not forwarded elsewhere.

Restart RekaRasa to reload backend and environment changes, then refresh the browser. In the image studio choose **New image from text**, select **Cloudflare - text concepts**, and use **Check connection**. Only pressing **Generate new concept** invokes generation. Use ComfyUI's photo editing or original-photo composition for actual product photos.

The WorkBuddy CLI also accepts `generate-image --provider cloudflare`. Omitting the provider keeps ComfyUI. Old image history is preserved and is not proof of the active provider.

## Failure handling

- **Setup required:** missing URL, secret or Free-plan confirmation.
- **Authentication rejected:** application secret and Worker `API_KEY` differ.
- **Setup incomplete:** missing `AI` or `RATE_LIMITER` binding, or an incompatible old Worker.
- **429:** local rate limit or upstream allocation/rate limit. Inspect usage before retrying.
- **503:** generation unavailable, potentially including an upstream quota failure. Inspect Worker usage and configuration; the application does not switch providers.
- **Timeout:** the upstream job may still finish. No automatic retry is made.

Worker logs and API errors deliberately omit the secret and prompt. Cloudflare itself receives the prompt as the selected processor. Never expose this secret in browser requests or commit local environment files.

## Implementation status

Local integration prepared. No deployment, live Cloudflare authentication, quota verification, image generation or automated tests have been performed in this pass. Syntax and whitespace checks are separate from live verification. Existing HTTP generation remains synchronous; durable background jobs are separate work.

## Official references

- [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [SDXL base model and input schema](https://developers.cloudflare.com/workers-ai/models/stable-diffusion-xl-base-1.0/)
- [Rate limiting bindings and accuracy](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/)
- [Reference repository](https://github.com/saurav-z/free-image-generation-api) (reviewed as an example; its Worker is not copied unchanged)
