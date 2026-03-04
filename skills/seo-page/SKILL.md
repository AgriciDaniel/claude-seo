---
name: seo-page
description: >
  Deep single-page SEO analysis covering on-page elements, content quality,
  technical meta tags, schema, images, and performance. Use when user says
  "analyze this page", "check page SEO", or provides a single URL for review.
---

# Single Page Analysis

## What to Analyze

### On-Page SEO
- Title tag: 50-60 characters, includes primary keyword, unique
- Meta description: 150-160 characters, compelling, includes keyword
- H1: exactly one, matches page intent, includes keyword
- H2-H6: logical hierarchy (no skipped levels), descriptive
- URL: short, descriptive, hyphenated, no parameters
- Internal links: sufficient, relevant anchor text, no orphan pages
- External links: to authoritative sources, reasonable count

### Content Quality
- Word count vs page type minimums (see quality-gates.md)
- Readability: Flesch Reading Ease score, grade level
- **Macro context focus**: Does the page have a single, clear primary topic? Mixed-intent pages fragment topical authority.
- **Entity-Attribute-Value (EAV) completeness**: Identify the primary entities on the page. Are their key attributes and values present? Missing EAV coverage = topical gaps that competitors can exploit.
- **Semantic field coverage**: Assess whether related terms, synonyms, and NLP-adjacent concepts are naturally present — not keyword density %, but the breadth of semantic coverage.
- **Extractive answer passages**: Are key questions answered with short (~40-word), self-contained passages that search engines and AI systems can extract?
- **H2s as user questions**: Do H2 headings reflect real user questions or subtopics — not generic label headings?
- E-E-A-T signals: author bio, credentials, first-hand experience markers
- Content freshness: publication date, last updated date

> **On keyword density:** Do NOT report a keyword density percentage as a target metric. Google does not use keyword density as a ranking factor. Focus on semantic completeness (EAV coverage, entity presence, related concept breadth) rather than repetition count.

### Technical Elements
- Canonical tag: present, self-referencing or correct
- Meta robots: index/follow unless intentionally blocked
- Open Graph: og:title, og:description, og:image, og:url
- Twitter Card: twitter:card, twitter:title, twitter:description
- Hreflang: if multi-language, correct implementation

### Schema Markup
- Detect all types (JSON-LD preferred)
- Validate required properties
- Identify missing opportunities
- NEVER recommend HowTo (deprecated) or FAQ (restricted to gov/health)

### Images
- Alt text: present, descriptive, includes keywords where natural
- File size: flag >200KB (warning), >500KB (critical)
- Format: recommend WebP/AVIF over JPEG/PNG
- Dimensions: width/height set for CLS prevention
- Lazy loading: loading="lazy" on below-fold images

### Core Web Vitals (reference only — not measurable from HTML alone)
- Flag potential LCP issues (huge hero images, render-blocking resources)
- Flag potential INP issues (heavy JS, no async/defer)
- Flag potential CLS issues (missing image dimensions, injected content)

## Output

### Page Score Card
```
Overall Score: XX/100

On-Page SEO:        XX/100  ████████░░
Content Quality:    XX/100  ██████████
Topical Authority:  XX/100  ██████░░░░
Technical:          XX/100  ███████░░░
Schema:             XX/100  █████░░░░░
Images:             XX/100  ████████░░
```

### Issues Found
Organized by priority: Critical → High → Medium → Low

### Recommendations
Specific, actionable improvements with expected impact

### Schema Suggestions
Ready-to-use JSON-LD code for detected opportunities
