---
name: seo-images
description: >
  Image optimization analysis for SEO and performance. Checks alt text, file
  sizes, formats, responsive images, lazy loading, CLS prevention, image SERP
  rankings (via DataForSEO), and image file optimization (WebP/AVIF conversion,
  IPTC/XMP metadata injection). Use when user says "image optimization",
  "alt text", "image SEO", "image size", "image audit", "optimize images",
  "image metadata", "image SERP", "convert to webp", or "image file optimize".
user-invokable: true
argument-hint: "[url]"
license: MIT
metadata:
  author: AgriciDaniel
  version: "1.9.0"
  category: seo
---

# Image Optimization Analysis

## Checks

### Alt Text
- Present on all `<img>` elements (except decorative: `role="presentation"`)
- Descriptive: describes the image content, not "image.jpg" or "photo"
- Includes relevant keywords where natural, not keyword-stuffed
- Length: 10-125 characters

**Good examples:**
- "Professional plumber repairing kitchen sink faucet"
- "Red 2024 Toyota Camry sedan front view"
- "Team meeting in modern office conference room"

**Bad examples:**
- "image.jpg" (filename, not description)
- "plumber plumbing plumber services" (keyword stuffing)
- "Click here" (not descriptive)

### File Size

**Tiered thresholds by image category:**

| Image Category | Target | Warning | Critical |
|----------------|--------|---------|----------|
| Thumbnails | < 50KB | > 100KB | > 200KB |
| Content images | < 100KB | > 200KB | > 500KB |
| Hero/banner images | < 200KB | > 300KB | > 700KB |

Recommend compression to target thresholds where possible without quality loss.

### Format
| Format | Browser Support | Use Case |
|--------|-----------------|----------|
| WebP | 97%+ | Default recommendation |
| AVIF | 92%+ | Best compression, newer |
| JPEG | 100% | Fallback for photos |
| PNG | 100% | Graphics with transparency |
| SVG | 100% | Icons, logos, illustrations |

Recommend WebP/AVIF over JPEG/PNG. Check for `<picture>` element with format fallbacks.

#### Recommended `<picture>` Element Pattern

Use progressive enhancement with the most efficient format first:

```html
<picture>
  <source srcset="image.avif" type="image/avif">
  <source srcset="image.webp" type="image/webp">
  <img src="image.jpg" alt="Descriptive alt text" width="800" height="600" loading="lazy" decoding="async">
</picture>
```

The browser will use the first supported format. Current browser support: AVIF 93.8%, WebP 95.3%.

#### JPEG XL: Emerging Format

In November 2025, Google's Chromium team reversed its 2022 decision and announced it will restore JPEG XL support in Chrome using a Rust-based decoder. The implementation is feature-complete but not yet in Chrome stable. JPEG XL offers lossless JPEG recompression (~20% savings with zero quality loss) and competitive lossy compression. Not yet practical for web deployment, but worth monitoring for future adoption.

### Responsive Images
- `srcset` attribute for multiple sizes
- `sizes` attribute matching layout breakpoints
- Appropriate resolution for device pixel ratios

```html
<img
  src="image-800.jpg"
  srcset="image-400.jpg 400w, image-800.jpg 800w, image-1200.jpg 1200w"
  sizes="(max-width: 600px) 400px, (max-width: 1200px) 800px, 1200px"
  alt="Description"
>
```

### Lazy Loading
- `loading="lazy"` on below-fold images
- Do NOT lazy-load above-fold/hero images (hurts LCP)
- Check for native vs JavaScript-based lazy loading

```html
<!-- Below fold - lazy load -->
<img src="photo.jpg" loading="lazy" alt="Description">

<!-- Above fold - eager load (default) -->
<img src="hero.jpg" alt="Hero image">
```

### `fetchpriority="high"` for LCP Images

Add `fetchpriority="high"` to your hero/LCP image to prioritize its download in the browser's network queue:

```html
<img src="hero.webp" fetchpriority="high" alt="Hero image description" width="1200" height="630">
```

**Critical:** Do NOT lazy-load above-the-fold/LCP images. Using `loading="lazy"` on LCP images directly harms LCP scores. Reserve `loading="lazy"` for below-the-fold images only.

### `decoding="async"` for Non-LCP Images

Add `decoding="async"` to non-LCP images to prevent image decoding from blocking the main thread:

```html
<img src="photo.webp" alt="Description" width="600" height="400" loading="lazy" decoding="async">
```

### CLS Prevention
- `width` and `height` attributes set on all `<img>` elements
- `aspect-ratio` CSS as alternative
- Flag images without dimensions

```html
<!-- Good - dimensions set -->
<img src="photo.jpg" width="800" height="600" alt="Description">

<!-- Good - CSS aspect ratio -->
<img src="photo.jpg" style="aspect-ratio: 4/3" alt="Description">

<!-- Bad - no dimensions -->
<img src="photo.jpg" alt="Description">
```

### File Names
- Descriptive: `blue-running-shoes.webp` not `IMG_1234.jpg`
- Hyphenated, lowercase, no special characters
- Include relevant keywords

### CDN Usage
- Check if images served from CDN (different domain, CDN headers)
- Recommend CDN for image-heavy sites
- Check for edge caching headers

## Output

### Image Audit Summary

| Metric | Status | Count |
|--------|--------|-------|
| Total Images | - | XX |
| Missing Alt Text | ❌ | XX |
| Oversized (>200KB) | ⚠️ | XX |
| Wrong Format | ⚠️ | XX |
| No Dimensions | ⚠️ | XX |
| Not Lazy Loaded | ⚠️ | XX |

### Prioritized Optimization List

Sorted by file size impact (largest savings first):

| Image | Current Size | Format | Issues | Est. Savings |
|-------|--------------|--------|--------|--------------|
| ... | ... | ... | ... | ... |

### Recommendations
1. Convert X images to WebP format (est. XX KB savings)
2. Add alt text to X images
3. Add dimensions to X images
4. Enable lazy loading on X below-fold images
5. Compress X oversized images

---

## Image SERP Analysis

When DataForSEO MCP is available, enhance the image audit with competitive data.

### `/seo images serp <keyword>`

Cross-reference on-page images with Google Images SERP rankings.

**Workflow:**
1. Fetch Google Images results via `serp_google_images_live_advanced` (depth=100)
2. Extract: top domains, image types, alt text patterns
3. Output competitor image SERP landscape

**Output:**

| Rank | Domain | Title/Alt | Image URL | Page URL |
|------|--------|-----------|-----------|----------|
| 1 | example.com | "Blue running shoes..." | .../shoes.webp | /products/... |

**Analysis includes:**
- **Domain dominance**: which sites own the most image positions (top 10 by count)
- **Alt text patterns**: common title/alt patterns in top-ranking images
- **Format distribution**: WebP vs JPEG vs PNG in top results
- **Opportunity score**: keywords where you have page rankings but no image presence

If DataForSEO MCP is not available, inform user and suggest installing the extension.

---

## Image File Optimization

Optimize image files for SEO: format conversion, metadata injection, compression.

### `/seo images optimize <path>`

Optimize image file(s) for web and SEO. Converts to WebP/AVIF, injects IPTC
metadata, compresses, and generates responsive variants.

**Tools used (in order of preference):**
- `exiftool` -- EXIF/IPTC/XMP read/write (install: `sudo apt install libimage-exiftool-perl`)
- `cwebp` -- WebP conversion (install: `sudo apt install webp`)
- ImageMagick `convert` -- Format conversion, resizing (pre-installed on most systems)
- FFmpeg -- Fallback for format conversion (pre-installed)

**Before running:** Check which tools are available with `which exiftool cwebp convert ffmpeg`.

### Format Conversion

Convert images to modern formats with metadata preservation:

```bash
# WebP (recommended default) - with metadata preserved
cwebp -q 82 -metadata all input.jpg -o output.webp

# WebP via ImageMagick (fallback if cwebp not installed)
convert input.jpg -quality 82 output.webp

# AVIF via FFmpeg (slower encode, best compression)
ffmpeg -i input.jpg -c:v libaom-av1 -crf 30 -still-picture 1 output.avif

# Responsive variants (400w, 800w, 1200w)
convert input.jpg -resize 400x -quality 82 image-400.webp
convert input.jpg -resize 800x -quality 82 image-800.webp
convert input.jpg -resize 1200x -quality 82 image-1200.webp
```

### Metadata Injection (IPTC for Google Rich Results)

Google Images displays IPTC Creator, Credit Line, and Copyright in search results.
This is **NOT a ranking factor** but improves rich result display and brand attribution.

**With exiftool (preferred):**
```bash
# Read all metadata
exiftool image.jpg

# Inject IPTC + XMP metadata for Google Images rich results
exiftool \
  -IPTC:ObjectName="Product Photo Description" \
  -IPTC:Caption-Abstract="Detailed image description" \
  -IPTC:By-line="Brand Name Photography" \
  -IPTC:Credit="Brand Name" \
  -IPTC:CopyrightNotice="Copyright 2026 Brand Name" \
  -IPTC:Source="brandname.com" \
  -XMP:Title="Product Photo Description" \
  -XMP:Description="Detailed image description" \
  -XMP:Creator="Brand Name Photography" \
  -XMP:Rights="Copyright 2026 Brand Name" \
  image.jpg

# Batch inject to all images in directory
exiftool -overwrite_original \
  -IPTC:By-line="Brand Name" \
  -IPTC:CopyrightNotice="Copyright 2026 Brand Name" \
  *.jpg *.webp *.png
```

**With ImageMagick (fallback):**
```bash
identify -verbose image.jpg | head -50

convert input.jpg \
  -set comment "Product Photo Description" \
  -set IPTC:2:80 "Brand Name Photography" \
  -set IPTC:2:116 "Copyright 2026 Brand Name" \
  output.jpg
```

**IMPORTANT:** WebP supports EXIF and XMP but NOT IPTC natively. For WebP files,
use XMP fields instead of IPTC. exiftool handles this conversion automatically.

### Metadata Audit

```bash
# Quick audit with exiftool
exiftool -IPTC:all -XMP:all -EXIF:ImageDescription image.jpg

# Batch audit - find images missing IPTC Creator
exiftool -if 'not $IPTC:By-line' -filename *.jpg *.webp *.png
```

### Full Optimization Pipeline

For maximum image SEO, run this pipeline on each image:

1. **Audit existing metadata**: `exiftool -IPTC:all -XMP:all image.jpg`
2. **Inject IPTC/XMP metadata**: Creator, Copyright, Description
3. **Convert to WebP**: `cwebp -q 82 -metadata all image.jpg -o image.webp`
4. **Generate responsive variants**: 400w, 800w, 1200w
5. **Verify metadata preserved**: `exiftool image.webp`
6. **Generate `<picture>` HTML**: AVIF > WebP > JPEG fallback chain

### What Matters vs What Doesn't for Google Images

| Factor | Impact | Where to Set |
|--------|--------|--------------|
| Alt text | **CRITICAL** (ranking) | HTML `<img alt="">` |
| Filename | **HIGH** (ranking) | File system (descriptive, hyphenated) |
| Page context | **HIGH** (ranking) | Surrounding HTML content |
| File size/speed | **MEDIUM** (indirect via CWV) | Compression + format conversion |
| IPTC Creator/Copyright | **LOW** (display only) | Image file metadata |
| EXIF camera data | NONE | Irrelevant for SEO |
| IPTC Keywords | NONE | Google ignores these |

---

## Error Handling

| Scenario | Action |
|----------|--------|
| URL unreachable | Report connection error with status code. Suggest verifying URL and checking if site requires authentication. |
| No images found on page | Report that no `<img>` elements were detected. Suggest checking if images are loaded via JavaScript or CSS background-image. |
| Images behind CDN or authentication | Note that image files could not be directly accessed for size analysis. Report available metadata (alt text, dimensions, format from markup) and flag inaccessible resources. |
| exiftool not installed | Fall back to ImageMagick for metadata. Recommend: `sudo apt install libimage-exiftool-perl` |
| cwebp not installed | Fall back to ImageMagick or FFmpeg for WebP conversion. Recommend: `sudo apt install webp` |
| DataForSEO MCP not available | Skip Image SERP Analysis section. Note extension is not installed. |
