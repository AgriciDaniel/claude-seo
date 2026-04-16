# Gemini Image Generation Models

> Last updated: 2026-03-13
> Aligned with Google's March 2026 API state

## Available Models

### gemini-3.1-flash-image-preview (Recommended)
| Property | Value |
|----------|-------|
| **Model ID** | `gemini-3.1-flash-image-preview` |
| **Tier** | Nano Banana 2 (Flash) |
| **Speed** | Fast - optimized for high-volume use |
| **Aspect Ratios** | All 14 ratios (see table below) |
| **Max Resolution** | Up to 4096×4096 (4K tier) |
| **Features** | Google Search grounding (web + image), thinking levels, image-only output, extreme aspect ratios |
| **Rate Limits (Free)** | ~10 RPM / ~500 RPD (per Google Cloud project, resets midnight Pacific) |
| **Output Tokens** | ~1,290 output tokens per image |
| **Best For** | Most use cases, rapid iteration, batch generation |

### gemini-2.5-flash-image
| Property | Value |
|----------|-------|
| **Model ID** | `gemini-2.5-flash-image` |
| **Tier** | Nano Banana 2 (Flash, previous gen) |
| **Speed** | Fast |
| **Aspect Ratios** | 1:1, 16:9, 9:16, 4:3, 3:4 |
| **Max Resolution** | Up to 1024×1024 (1K tier) |
| **Rate Limits (Free)** | ~10 RPM / ~500 RPD |
| **Best For** | Stable fallback, proven quality |

## Deprecated Models (DO NOT USE)

### gemini-3-pro-image-preview
- **Status:** Base model deprecated March 9, 2026. **Image generation variant may still be accessible**. Use at your own discretion via `set_model`. Prefer 3.1 Flash.
- **Was:** Nano Banana Pro tier (professional asset production, 4K output, 14 reference images)
- **Migration:** Use `gemini-3.1-flash-image-preview` instead

### gemini-2.0-flash-exp
- **Status:** Deprecated, replaced by gemini-2.5-flash-image

## Aspect Ratios

All 14 supported ratios. Availability varies by model:

| Ratio | Orientation | Use Cases | 3.1 Flash | 2.5 Flash |
|-------|-------------|-----------|:---------:|:---------:|
| `1:1` | Square | Social posts, avatars, thumbnails | ✅ | ✅ |
| `16:9` | Landscape | Blog headers, YouTube thumbnails, presentations | ✅ | ✅ |
| `9:16` | Portrait | Stories, Reels, TikTok, mobile | ✅ | ✅ |
| `4:3` | Landscape | Product shots, classic display | ✅ | ✅ |
| `3:4` | Portrait | Book covers, portrait framing | ✅ | ✅ |
| `2:3` | Portrait | Pinterest pins, posters | ✅ | ❌ |
| `3:2` | Landscape | DSLR standard, photo prints | ✅ | ❌ |
| `4:5` | Portrait | Instagram portrait, social | ✅ | ❌ |
| `5:4` | Landscape | Large format photography | ✅ | ❌ |
| `1:4` | Tall strip | Vertical banners, side panels | ✅ | ❌ |
| `4:1` | Wide strip | Website banners, headers | ✅ | ❌ |
| `1:8` | Extreme tall | Narrow vertical strips | ✅ | ❌ |
| `8:1` | Extreme wide | Ultra-wide banners | ✅ | ❌ |
| `21:9` | Ultra-wide | Cinematic, film-grade, ultra-wide monitors | ✅ | ❌ |

## Resolution Tiers

Control output resolution with the `imageSize` parameter. Note the **uppercase K** requirement.

| `imageSize` Value | Pixel Range | Model Availability | Use Case |
|-------------------|-------------|-------------------|----------|
| `512` | Up to 512×512 | All models | Drafts, quick iteration, low bandwidth |
| `1K` (default) | Up to 1024×1024 | All models | Standard web use, social media |
| `2K` | Up to 2048×2048 | 3.1 Flash | Quality assets, detailed work |
| `4K` | Up to 4096×4096 | 3.1 Flash | Print production, hero images, final assets |

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
Ground generation in real-world visual references. Supports web and image search (3.1 Flash):
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

| Tier | RPM | RPD | Notes |
|------|-----|-----|-------|
| Free | ~10 | ~500 | Per Google Cloud project, resets midnight Pacific. Reduced Dec 2025. |
| Pay-as-you-go | 30 | 10,000 | Production workloads |
| Enterprise | Custom | Custom | Contact Google |

## Pricing

| Model | Resolution | Cost per Image | Notes |
|-------|-----------|---------------|-------|
| 3.1 Flash | 1K | ~$0.039 | Standard |
| 3.1 Flash | 2K | ~$0.078 | 2× standard |
| 3.1 Flash | 4K | ~$0.156 | 4× standard |
| 2.5 Flash | 1K | ~$0.039 | Standard |
| Batch API | Any | 50% discount | Asynchronous, higher latency |

Pricing is approximate and based on ~1,290 output tokens per image.
Research suggests NB2 pricing may be ~$0.067/img (vs documented $0.039). Verify current pricing at https://ai.google.dev/gemini-api/docs/pricing

## Image Output Specs

| Property | Value |
|----------|-------|
| **Format** | PNG |
| **Max Resolution** | Up to 4096×4096 (4K tier, 3.1 Flash) |
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
