---
name: seo-atlas-image-gen
description: >
  Generate SEO images through Atlas Cloud, including social previews, blog
  heroes, product images, infographics, and custom visuals. Use when the user
  asks for Atlas Cloud image generation or an Atlas-backed SEO image workflow.
argument-hint: "[og|hero|product|infographic|custom] <description>"
user-invocable: true
license: MIT
compatibility: "Requires ATLASCLOUD_API_KEY and outbound HTTPS access"
metadata:
  author: binyangzhu000-sudo
  original_author: binyangzhu000-sudo
  version: "2.2.4"
  category: seo
---

# Atlas Cloud SEO Image Generation

Generate an SEO-ready image with Atlas Cloud while keeping each paid request
explicit. The bundled client performs one generation POST, bounded result
polling, and a credential-free media download.

## Prerequisites

Install the extension and export an API key in the current shell:

```bash
./extensions/atlas/install.sh
export ATLASCLOUD_API_KEY="..."
```

Do not print, persist, or place the key in command arguments. Confirm the user
wants a paid generation before running the command.

## Command

```bash
claude-seo run --extension atlas generate.py \
  --prompt "Editorial illustration of a technical SEO audit dashboard" \
  --size '1200*630'
```

The script returns JSON containing the prediction ID, status, output URLs, and
local paths. Generated files default to
`~/Documents/claude-seo/atlas-generated/`.

## Use-Case Defaults

Load `references/seo-image-presets.md` and select the closest preset. Ask for
clarification when brand, style, or required text is underspecified.

| Use case | Size | Prompt emphasis |
|---|---:|---|
| OG/social preview | `1200*630` | Clear focal point and safe text area |
| Blog hero | `1792*1024` | Editorial composition, no embedded text |
| Product image | `1536*1024` | Accurate object, clean controlled lighting |
| Infographic | `1024*1536` | Simple hierarchy and minimal generated text |
| Square social image | `1024*1024` | Centered composition and mobile legibility |

The default model is `qwen-image-3.0/text-to-image`. Before changing models,
query the live Atlas model catalog and inspect that model's current schema.

## Generation Workflow

1. Identify the target page, asset role, dimensions, brand constraints, and
   whether the image may contain text.
2. Write a concrete visual prompt. Describe subject, composition, lighting,
   palette, and the empty area required for later typography.
3. Show the proposed prompt, model, size, and number of images. Get approval
   before the paid request.
4. Run one `generate.py` command. Do not automatically retry a failed POST.
5. The client polls only the returned prediction ID with bounded backoff.
6. Verify the downloaded file, dimensions, and visual suitability before use.
7. Provide SEO metadata and placement guidance.

## Optional Parameters

```bash
# Reproducible single image
claude-seo run --extension atlas generate.py \
  --prompt "Minimal geometric illustration for a canonical tags guide" \
  --size '1200*630' --seed 42

# Keep only the temporary output URL
claude-seo run --extension atlas generate.py \
  --prompt "Clean product comparison hero" --no-download
```

Supported flags include `--model`, `--size`, `--count`, `--negative-prompt`,
`--seed`, `--no-prompt-extend`, `--output`, `--max-polls`, and
`--poll-seconds`.

## Post-Generation SEO Checklist

- Verify the asset matches the page intent and contains no unintended text.
- Write concise alt text that describes the image without keyword stuffing.
- Rename the file using a descriptive, stable slug.
- Convert to WebP or AVIF when the publishing stack supports it.
- Compress social and hero assets without visible quality loss.
- Add the final absolute URL to `og:image` and relevant `ImageObject` schema.
- Record width and height in metadata to prevent layout shift.

## Safety and Failure Handling

- The API key is sent only to `api.atlascloud.ai` generation and polling
  endpoints. It is never sent to output hosts.
- Generation POST requests are never retried automatically.
- Polling is bounded by `--max-polls`; timeout is reported as JSON.
- Redirects are blocked. Downloads require HTTPS and an allowlisted Atlas
  output host, enforce a byte limit, and validate image signatures.
- Treat output URLs as temporary and avoid logging signed query parameters.
- On HTTP 429 or 5xx, report the failure and let the user decide whether to
  submit a new paid request.

## Response Format

After a successful run, report:

1. Local image path and verified dimensions
2. Model, prompt, size, and seed if used
3. Suggested filename and alt text
4. Suggested `og:image` or `ImageObject` snippet
5. Any visible quality or brand-compliance concerns
