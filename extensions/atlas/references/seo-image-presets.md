# Atlas Cloud SEO Image Presets

These presets are prompt and output defaults. Confirm current model support
through the Atlas Cloud model catalog before using a different model or field.

## OG / Social Preview

- Size: `1200*630`
- Model: `qwen-image-3.0/text-to-image`
- Composition: one clear subject, high contrast, quiet area for later title text
- Prompt suffix: `editorial social preview, clean hierarchy, no embedded text`

## Blog Hero

- Size: `1792*1024`
- Model: `qwen-image-3.0/text-to-image`
- Composition: wide editorial framing, visual depth, important details near center
- Prompt suffix: `widescreen editorial illustration, no logo, no embedded text`

## Product Image

- Size: `1536*1024`
- Model: `qwen-image-3.0/text-to-image`
- Composition: accurate product silhouette, clean background, controlled lighting
- Prompt suffix: `professional product photography, accurate materials, clean background`

## Infographic Base

- Size: `1024*1536`
- Model: `qwen-image-3.0/text-to-image`
- Composition: simple sections, icons, generous space for real typography added later
- Prompt suffix: `structured infographic base, minimal generated text, clear visual grouping`

## Square Social Image

- Size: `1024*1024`
- Model: `qwen-image-3.0/text-to-image`
- Composition: centered focal point, bold silhouette, legible at thumbnail size
- Prompt suffix: `square social image, centered composition, no embedded text`

## Prompt Template

```text
[asset role] for [page topic]. Subject: [concrete subject]. Composition:
[camera/framing and safe area]. Style: [specific visual style]. Palette: [brand
colors]. Lighting: [lighting]. Avoid: logos, watermarks, unreadable text, and
unrelated interface elements.
```
