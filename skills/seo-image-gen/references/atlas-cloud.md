# Atlas Cloud (optional, no-MCP image provider)

The banana / Gemini MCP server is the default and recommended path for this skill.
This reference documents an **optional HTTP fallback** for environments where an MCP
server cannot be installed (CI runners, containers, locked-down machines) — the case
the `MCP unavailable` row in `SKILL.md` currently has no answer for.

[Atlas Cloud](https://www.atlascloud.ai/?utm_source=github&utm_medium=link&utm_campaign=claude-seo)
exposes text-to-image generation over a plain REST API (submit a job, poll for the
result), so it needs no MCP server and no extra dependency beyond `curl` / `requests`.

Nothing here changes the skill's defaults: use it only when the banana MCP tools
(`gemini_generate_image`, `set_aspect_ratio`) are not available.

## Configuration

```bash
export ATLASCLOUD_API_KEY=<atlascloud-api-key>     # https://www.atlascloud.ai/console
export ATLASCLOUD_IMAGE_MODEL=alibaba/wan-2.7/text-to-image   # optional default
```

Keys live in the environment only — never commit one, and never inline one into a
generated snippet.

## Generation pipeline (submit -> poll -> download)

Step 1 — submit the job:

```bash
curl -sS -X POST https://api.atlascloud.ai/api/v1/model/generateImage \
  -H "Authorization: Bearer $ATLASCLOUD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "alibaba/wan-2.7/text-to-image",
    "prompt": "<Reasoning Brief from references/prompt-engineering.md>",
    "size": "1280*720"
  }'
```

Response carries the prediction id:

```json
{"code":200,"data":{"id":"16e3ef7b...","status":"processing",
 "urls":{"get":"https://api.atlascloud.ai/api/v1/model/prediction/16e3ef7b..."}}}
```

Step 2 — poll until `status` is `completed` (bounded: stop after ~2 minutes):

```bash
curl -sS https://api.atlascloud.ai/api/v1/model/prediction/<id> \
  -H "Authorization: Bearer $ATLASCLOUD_API_KEY"
```

`data.outputs[0]` is the image URL. `status` is one of `processing`, `completed`,
`failed`; on `failed` read `data.error`.

Step 3 — download the result. Output URLs are short-lived, so save the file straight
away. Any script that fetches a URL in this repo must go through
`scripts/url_safety.py` (`validate_url()` / `safe_requests_session()`) — that applies
here too, even though the URL comes back from the API rather than from the user.

## Notes that differ from the MCP path

- `size` uses `width*height` (an asterisk), **not** `1024x1024`.
- Aspect ratio is expressed through `size` directly; there is no `set_aspect_ratio`
  step.
- Generation is asynchronous — a submit returns immediately with `processing`.
- The download URL expires; convert to WebP and store locally as usual (see
  `references/post-processing.md`).

## SEO use case -> size mapping

Mirrors the use case table in `SKILL.md`:

| Use case | Aspect ratio | `size` |
|----------|--------------|--------|
| OG / social preview | 16:9 | `1280*720` |
| Blog hero | 16:9 | `1920*1080` |
| Schema image | 4:3 | `1024*768` |
| Social square | 1:1 | `1024*1024` |
| Product photo | 4:3 | `1600*1200` |
| Infographic | 2:3 | `1024*1536` |
| Favicon / icon | 1:1 | `512*512` |
| Pinterest pin | 2:3 | `1024*1536` |

## Models

Verified working default: `alibaba/wan-2.7/text-to-image` ($0.03 / image).

<details>
<summary>All Atlas Cloud text-to-image models (36)</summary>

| Model | Name | Ref. price |
|-------|------|-----------|
| `alibaba/qwen-image/text-to-image-max` | Qwen-Image Text-to-image Max | $0.052 |
| `alibaba/qwen-image/text-to-image-plus` | Qwen-Image Text-to-image Plus | $0.021 |
| `alibaba/wan-2.5/text-to-image` | Wan-2.5 Text-to-image | $0.021 |
| `alibaba/wan-2.6/text-to-image` | Wan-2.6 Text-to-image | $0.021 |
| `alibaba/wan-2.7-pro/text-to-image` | Wan-2.7 Pro Text-to-image | $0.075 |
| `alibaba/wan-2.7/text-to-image` | Wan-2.7 Text-to-image | $0.03 |
| `atlascloud/qwen-image/text-to-image` | Qwen Image Text-to-image | $0.024 |
| `baidu/ERNIE-Image-Turbo/text-to-image` | Baidu ERNIE Image Turbo | — |
| `black-forest-labs/flux-2-flex/text-to-image` | FLUX.2 Flex | $0.05 |
| `black-forest-labs/flux-2-pro/text-to-image` | FLUX.2 Pro | $0.03 |
| `black-forest-labs/flux-dev` | Flux Dev | $0.012 |
| `black-forest-labs/flux-dev-lora` | Flux Dev Lora | $0.015 |
| `black-forest-labs/flux-schnell` | Flux Schnell | $0.003 |
| `bytedance/seedream-v4` | Seedream v4 | $0.027 |
| `bytedance/seedream-v4.5` | Seedream v4.5 | $0.036 |
| `bytedance/seedream-v4.5/sequential` | Seedream v4.5 Sequential | $0.036 |
| `bytedance/seedream-v4/sequential` | Seedream v4 Sequential | $0.027 |
| `bytedance/seedream-v5.0-lite` | Seedream v5.0 Lite | $0.032 |
| `bytedance/seedream-v5.0-lite/sequential` | Seedream v5.0 Lite Sequential | $0.032 |
| `google/imagen3` | Imagen3 | $0.04 |
| `google/imagen3-fast` | Imagen3 Fast | $0.02 |
| `google/imagen4` | Imagen4 | $0.04 |
| `google/imagen4-fast` | Imagen4 Fast | $0.02 |
| `google/imagen4-ultra` | Imagen4 Ultra | $0.06 |
| `google/nano-banana-2/text-to-image` | Nano Banana 2 | $0.048 |
| `google/nano-banana-pro/text-to-image` | Nano Banana Pro | $0.084 |
| `google/nano-banana-pro/text-to-image-ultra` | Nano Banana Pro Ultra | $0.15 |
| `google/nano-banana/text-to-image` | Nano Banana | $0.038 |
| `openai/gpt-image-1-mini/text-to-image` | GPT Image-1 Mini | $0.004 |
| `openai/gpt-image-1.5/text-to-image` | GPT Image-1.5 | $0.008 |
| `openai/gpt-image-1/text-to-image` | GPT Image-1 | $0.009 |
| `openai/gpt-image-2/text-to-image` | GPT Image 2 | $0.009 |
| `qwen/qwen-image-2.0-pro/text-to-image` | Qwen Image 2.0 Pro | $0.06 |
| `qwen/qwen-image-2.0/text-to-image` | Qwen Image 2.0 | $0.028 |
| `xai/grok-imagine-image-quality/text-to-image` | Grok Imagine Quality | $0.06 |
| `z-image/turbo` | Z-Image Turbo | $0.01 |

</details>

Prices are per image and are the vendor's published reference prices; confirm current
pricing at [atlascloud.ai/models](https://www.atlascloud.ai/models) before quoting a
cost to the user, exactly as the `Cost Awareness` section of `SKILL.md` requires.

## Error handling

| Error | Resolution |
|-------|-----------|
| `401` | `ATLASCLOUD_API_KEY` missing or revoked |
| `400 invalid size` | Use `width*height`, not `width x height` |
| `data.status = failed` | Read `data.error`; rephrase the prompt and resubmit |
| Poll never completes | Stop after ~2 minutes and report the prediction id |
| Expired output URL | Re-run the job; URLs are short-lived by design |
