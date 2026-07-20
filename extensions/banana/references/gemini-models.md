# Gemini Image Generation Models

> Last updated: 2026-07-10
> Verify model availability against Google-owned docs before use.

## Model Source Check

Do not treat this reference as the source of truth for current image model IDs.
Before generation, verify the model against:
- Current models: https://ai.google.dev/gemini-api/docs/models
- Deprecations: https://ai.google.dev/gemini-api/docs/deprecations

Set the verified model explicitly with `NANOBANANA_MODEL`, MCP `set_model`, or
script `--model`.

## Aspect Ratios

Availability varies by model. Check the current Google model docs before using
any ratio with `set_aspect_ratio`.

| Ratio | Orientation | Use Cases |
|-------|-------------|-----------|
| `1:1` | Square | Social posts, avatars, thumbnails |
| `16:9` | Landscape | Blog headers, YouTube thumbnails, presentations |
| `9:16` | Portrait | Stories, Reels, TikTok, mobile |
| `4:3` | Landscape | Product shots, classic display |
| `3:4` | Portrait | Book covers, portrait framing |
| `2:3` | Portrait | Pinterest pins, posters |
| `3:2` | Landscape | DSLR standard, photo prints |
| `4:5` | Portrait | Instagram portrait, social |
| `5:4` | Landscape | Large format photography |
| `1:4` | Tall strip | Vertical banners, side panels |
| `4:1` | Wide strip | Website banners, headers |
| `1:8` | Extreme tall | Narrow vertical strips |
| `8:1` | Extreme wide | Ultra-wide banners |
| `21:9` | Ultra-wide | Cinematic, film-grade, ultra-wide monitors |

## Resolution Tiers

Control output resolution with the `imageSize` parameter. Note the **uppercase K** requirement.

| `imageSize` Value | Pixel Range | Model Availability | Use Case |
|-------------------|-------------|-------------------|----------|
| `512` | Up to 512×512 | Verify in current model docs | Drafts, quick iteration, low bandwidth |
| `1K` (default) | Up to 1024×1024 | Verify in current model docs | Standard web use, social media |
| `2K` | Up to 2048×2048 | Verify in current model docs | Quality assets, detailed work |
| `4K` | Up to 4096×4096 | Verify in current model docs | Print production, hero images, final assets |

**Notes:**
- Actual pixel dimensions depend on aspect ratio (e.g., 4K at 16:9 = 4096×2304)
- Higher resolutions consume more tokens and cost more
- Default is `1K` if `imageSize` is not specified

## API Configuration

### Endpoint
```
https://generativelanguage.googleapis.com/v1beta/models/{model-id}:generateContent
```

### Required Parameters
```json
{
  "contents": [{"parts": [{"text": "your prompt here"}]}],
  "generationConfig": {
    "responseModalities": ["TEXT", "IMAGE"],
    "imageConfig": {
      "aspectRatio": "16:9",
      "imageSize": "1K"
    }
  }
}
```

### Image-Only Output Mode
Force the model to return only an image (no text response):
```json
{
  "generationConfig": {
    "responseModalities": ["IMAGE"]
  }
}
```

### Thinking Level
Control how much the model "thinks" before generating. Higher levels improve complex compositions but increase latency:
```json
{
  "generationConfig": {
    "thinkingConfig": {
      "thinkingLevel": "medium"
    }
  }
}
```
Levels: `minimal`, `low`, `medium`, `high`

### Google Search Grounding
Ground generation in real-world visual references. Availability depends on the verified model:
```json
{
  "tools": [{"googleSearch": {}}]
}
```
**Prompt pattern:** `[Search/source request] + [Analytical task] + [Visual translation]`

Example: "Search for the latest SpaceX Starship design, analyze its proportions and markings, then generate a photorealistic image of it at sunset on the launch pad."

### Multi-Image Input
Up to 14 reference images can be provided:
- **10 object references**: for style, composition, or visual matching
- **4 character references**: assign distinct names to preserve features across generations

Useful for character consistency, style transfer, and brand-aligned generation.

## Rate Limits by Tier

Verify current rate limits in Google-owned docs before planning batch work.

## Pricing

Do not use hard-coded pricing assumptions. Verify current pricing at
https://ai.google.dev/gemini-api/docs/pricing and store dated values in
`~/.banana/pricing.json` for `scripts/cost_tracker.py`.

## Image Output Specs

| Property | Value |
|----------|-------|
| **Format** | PNG |
| **Max Resolution** | Depends on verified model and configured resolution tier |
| **Color Space** | sRGB |
| **Text Rendering** | Supported - best under 25 characters |
| **Style Control** | Via prompt engineering |

## Safety Filters

Gemini uses a two-layer safety architecture:

1. **Input filters**: block prompts containing prohibited content before generation
2. **Output filters**: analyze generated images and block unsafe results

| `finishReason` | Meaning | Retryable? |
|----------------|---------|:----------:|
| `STOP` | Successful generation | N/A |
| `IMAGE_SAFETY` | Output blocked by safety filter | Rephrase prompt |
| `PROHIBITED_CONTENT` | Content policy violation | No - topic is blocked |
| `SAFETY` | General safety block | Rephrase prompt |
| `RECITATION` | Detected copyrighted content | Rephrase prompt |

**Known issue:** Filters are known to be overly cautious. Benign prompts may be blocked. Iterate with rephrased wording if this happens.

## Content Credentials

- **SynthID watermarks** are always embedded in generated images (invisible, machine-readable)
- **C2PA metadata** is included on Pro/paid outputs (verifiable provenance chain)

## Key Limitations
- No video generation (image only)
- No transparent backgrounds (PNG but always with background)
- Text rendering quality varies; keep text under 25 characters for best results
- Safety filters may block some prompts (violence, NSFW, public figures), known to be overly cautious
- Session context resets between Claude Code conversations
- `imageSize` and thinking level depend on MCP package version support
