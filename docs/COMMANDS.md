# Commands Reference

## Overview

All Claude SEO commands start with `/seo` followed by a subcommand.

## Command List

### `/seo audit <url>`

Full website SEO audit with parallel analysis.

**Example:**
```
/seo audit https://example.com
```

**What it does:**
1. Crawls up to 500 pages
2. Detects business type
3. Delegates to 6 specialist subagents in parallel
4. Generates SEO Health Score (0-100)
5. Creates prioritized action plan

**Output:**
- `FULL-AUDIT-REPORT.md`
- `ACTION-PLAN.md`
- `screenshots/` (if Playwright available)

---

### `/seo page <url>`

Deep single-page analysis.

**Example:**
```
/seo page https://example.com/about
```

**What it analyzes:**
- On-page SEO (title, meta, headings, URLs)
- Content quality (word count, readability, E-E-A-T)
- Technical elements (canonical, robots, Open Graph)
- Schema markup
- Images (alt text, sizes, formats)
- Core Web Vitals potential issues

---

### `/seo technical <url>`

Technical SEO audit across 8 categories.

**Example:**
```
/seo technical https://example.com
```

**Categories:**
1. Crawlability
2. Indexability
3. Security
4. URL Structure
5. Mobile Optimization
6. Core Web Vitals (LCP, INP, CLS)
7. Structured Data
8. JavaScript Rendering

---

### `/seo content <url>`

E-E-A-T and content quality analysis.

**Example:**
```
/seo content https://example.com/blog/post
```

**What it evaluates:**
- Experience signals (first-hand knowledge)
- Expertise (author credentials)
- Authoritativeness (external recognition)
- Trustworthiness (transparency, security)
- AI citation readiness
- Content freshness

---

### `/seo schema <url>`

Schema markup detection, validation, and generation.

**Example:**
```
/seo schema https://example.com
```

**What it does:**
- Detects existing schema (JSON-LD, Microdata, RDFa)
- Validates against Google's requirements
- Identifies missing opportunities
- Generates ready-to-use JSON-LD

---

### `/seo geo <url>`

AI Overviews / Generative Engine Optimization.

**Example:**
```
/seo geo https://example.com/blog/guide
```

**What it analyzes:**
- Citability score (quotable facts, statistics)
- Structural readability (headings, lists, tables)
- Entity clarity (definitions, context)
- Authority signals (credentials, sources)
- Structured data support

---

### `/seo images <url>`

Image optimization analysis.

**Example:**
```
/seo images https://example.com
```

**What it checks:**
- Alt text presence and quality
- File sizes (flag >200KB)
- Formats (WebP/AVIF recommendations)
- Responsive images (srcset, sizes)
- Lazy loading
- CLS prevention (dimensions)

---

### `/seo sitemap <url>`

Analyze existing XML sitemap.

**Example:**
```
/seo sitemap https://example.com/sitemap.xml
```

**What it validates:**
- XML format
- URL count (<50k per file)
- URL status codes
- lastmod accuracy
- Deprecated tags (priority, changefreq)
- Coverage vs crawled pages

---

### `/seo sitemap generate`

Generate new sitemap with industry templates.

**Example:**
```
/seo sitemap generate
```

**Process:**
1. Select or auto-detect business type
2. Interactive structure planning
3. Apply quality gates (30/50 location page limits)
4. Generate valid XML
5. Create documentation

---

### `/seo plan <type>`

Strategic SEO planning.

**Types:** `saas`, `local`, `ecommerce`, `publisher`, `agency`

**Example:**
```
/seo plan saas
```

**What it creates:**
- Complete SEO strategy
- Competitive analysis
- Content calendar
- Implementation roadmap (4 phases)
- Site architecture design

---

## Quick Reference

| Command | Use Case |
|---------|----------|
| `/seo audit <url>` | Full website audit |
| `/seo page <url>` | Single page analysis |
| `/seo technical <url>` | Technical SEO check |
| `/seo content <url>` | E-E-A-T analysis |
| `/seo schema <url>` | Schema validation |
| `/seo geo <url>` | AI search optimization |
| `/seo images <url>` | Image optimization |
| `/seo sitemap <url>` | Sitemap validation |
| `/seo sitemap generate` | Create new sitemap |
| `/seo plan <type>` | Strategic planning |
