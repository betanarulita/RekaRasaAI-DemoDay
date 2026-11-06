const MODEL = '@cf/stabilityai/stable-diffusion-xl-base-1.0';
const PROTOCOL = 'rekarasa-image-v1';
const CANVASES = new Set(['1024x1024', '1024x1280', '1008x1792', '1344x768']);

async function boundedBytes(stream, maximum) {
  const reader = stream.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maximum) { await reader.cancel(); throw new Error('too_large'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return bytes;
}

export default {
  async fetch(request, env) {
    const requestId = crypto.randomUUID();
    const headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
      'X-RekaRasa-Protocol': PROTOCOL, 'X-Request-Id': requestId};
    const reply = (status, code, message) => Response.json({code, message, request_id: requestId},
      {status, headers: {...headers, ...(status === 429 ? {'Retry-After': '60'} : {})}});
    if (typeof env.API_KEY !== 'string' || env.API_KEY.length < 32)
      return reply(503, 'not_configured', 'Configure the server secret.');
    if (request.headers.get('Authorization') !== `Bearer ${env.API_KEY}`)
      return reply(401, 'unauthorized', 'Authentication required.');
    const path = new URL(request.url).pathname;
    const ready = typeof env.AI?.run === 'function' && typeof env.RATE_LIMITER?.limit === 'function';
    if (request.method === 'GET' && path === '/health')
      return Response.json({ready, model: MODEL, protocol: PROTOCOL, capabilities: ['concept']}, {headers});
    if (path !== '/generate') return reply(404, 'not_found', 'Route not found.');
    if (request.method !== 'POST') return reply(405, 'method_not_allowed', 'Use POST.');
    if (!ready) return reply(503, 'not_configured', 'Configure AI and RATE_LIMITER bindings.');
    if (request.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase() !== 'application/json')
      return reply(415, 'invalid_content_type', 'Use application/json.');
    let body;
    try {
      if (!request.body) return reply(400, 'invalid_body', 'A JSON body is required.');
      body = JSON.parse(new TextDecoder().decode(await boundedBytes(request.body, 100000)));
    } catch (error) {
      return reply(error.message === 'too_large' ? 413 : 400, 'invalid_body', 'Use a valid JSON body below 100 KB.');
    }
    if (!body || typeof body !== 'object' || Array.isArray(body)
      || Object.keys(body).some(key => !['prompt', 'width', 'height', 'mode'].includes(key))
      || body.mode !== 'concept' || typeof body.prompt !== 'string'
      || !body.prompt.trim() || body.prompt.length > 16000
      || !Number.isInteger(body.width) || !Number.isInteger(body.height)
      || !CANVASES.has(`${body.width}x${body.height}`))
      return reply(400, 'invalid_input', 'Supply a text concept and a supported canvas. Reference-photo editing is not supported.');
    try {
      const {success} = await env.RATE_LIMITER.limit({key: 'rekarasa-image-generation'});
      if (!success) return reply(429, 'rate_limited', 'Wait before requesting another image.');
      const output = await env.AI.run(MODEL, {
        prompt: body.prompt.trim(), width: body.width, height: body.height, num_steps: 20,
        negative_prompt: 'watermark, lettering, text, certification seal, distorted objects'
      });
      const bytes = await boundedBytes(output, 15000000);
      const png = bytes.length > 8 && [137,80,78,71,13,10,26,10].every((value,index) => bytes[index] === value);
      const jpeg = bytes.length > 3 && bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255;
      if (!png && !jpeg) return reply(502, 'invalid_output', 'Image service returned an invalid image.');
      return new Response(bytes, {headers: {...headers, 'Content-Type': png ? 'image/png' : 'image/jpeg'}});
    } catch (error) {
      const status = Number(error?.status ?? error?.statusCode);
      return reply(status === 429 ? 429 : 503, 'image_service_unavailable',
        'Image generation is unavailable. Check Workers AI usage and account limits before retrying.');
    }
  }
};
