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
3. Delegates to 7 specialist subagents in parallel
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

Technical SEO audit across 9 categories.

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
9. IndexNow Protocol

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

### `/seo competitor-pages [url|generate]`

Competitor comparison page generation.

**Examples:**
```
/seo competitor-pages https://example.com/vs/competitor
/seo competitor-pages generate
```

**Capabilities:**
- Generate "X vs Y" comparison page layouts
- Create "Alternatives to X" page structures
- Build feature comparison matrices with scoring
- Generate Product + AggregateRating schema markup
- Apply conversion-optimized CTA placement
- Enforce fairness guidelines (accurate data, source citations)

---

### `/seo hreflang [url]`

Hreflang and international SEO audit and generation.

**Example:**
```
/seo hreflang https://example.com
```

**Capabilities:**
- Validate self-referencing hreflang tags
- Check return tag reciprocity (A→B requires B→A)
- Verify x-default tag presence
- Validate ISO 639-1 language and ISO 3166-1 region codes
- Check canonical URL alignment with hreflang
- Detect protocol mismatches (HTTP vs HTTPS)
- Generate correct hreflang link tags and sitemap XML

---

### `/seo programmatic [url|plan]`

Programmatic SEO analysis and planning for pages generated at scale.

**Examples:**
```
/seo programmatic https://example.com/tools/
/seo programmatic plan
```

**Capabilities:**
- Assess data source quality (CSV, JSON, API, database)
- Plan template engines with unique content per page
- Design URL pattern strategies (`/tools/[tool-name]`, `/[city]/[service]`)
- Automate internal linking (hub/spoke, related items, breadcrumbs)
- Enforce thin content safeguards (quality gates, word count thresholds)
- Prevent index bloat (noindex low-value, pagination, faceted nav)

---

### `/seo dataforseo [command]`

Live SEO data via DataForSEO MCP server (extension). 22 commands across 9 API modules.

**Prerequisites:** DataForSEO extension installed (`./extensions/dataforseo/install.sh`)

**SERP Analysis:**
```
/seo dataforseo serp <keyword>              # Google organic results (also Bing/Yahoo)
/seo dataforseo serp-youtube <keyword>      # YouTube search results
/seo dataforseo youtube <video_id>          # YouTube video deep analysis
```

**Keyword Research:**
```
/seo dataforseo keywords <seed>             # Keyword ideas and suggestions
/seo dataforseo volume <keywords>           # Search volume metrics
/seo dataforseo difficulty <keywords>       # Keyword difficulty scores
/seo dataforseo intent <keywords>           # Search intent classification
/seo dataforseo trends <keyword>            # Google Trends data
```

**Domain & Competitors:**
```
/seo dataforseo backlinks <domain>          # Full backlink profile
/seo dataforseo competitors <domain>        # Competitor analysis
/seo dataforseo ranked <domain>             # Ranked keywords
/seo dataforseo intersection <domains>      # Keyword/backlink overlap
/seo dataforseo traffic <domains>           # Traffic estimation
/seo dataforseo subdomains <domain>         # Subdomains with ranking data
/seo dataforseo top-searches <domain>       # Top queries mentioning domain
```

**Technical / On-Page:**
```
/seo dataforseo onpage <url>                # On-page analysis (Lighthouse)
/seo dataforseo tech <domain>               # Technology detection
/seo dataforseo whois <domain>              # WHOIS data
```

**Content & Business Data:**
```
/seo dataforseo content <keyword/url>       # Content analysis and trends
/seo dataforseo listings <keyword>          # Business listings search
```

**AI Visibility / GEO:**
```
/seo dataforseo ai-scrape <query>           # ChatGPT web scraper for GEO
/seo dataforseo ai-mentions <keyword>       # LLM mention tracking
```

---

### `/seo image-gen [use-case] <description>`

AI image generation for SEO assets (extension). Powered by Gemini via nanobanana-mcp.

**Prerequisites:** Banana extension installed (`./extensions/banana/install.sh`)

**Use Cases:**
```
/seo image-gen og <description>          # OG/social preview image (16:9, 1K)
/seo image-gen hero <description>        # Blog hero image (16:9, 2K)
/seo image-gen product <description>     # Product photography (4:3, 2K)
/seo image-gen infographic <description> # Infographic visual (2:3, 4K)
/seo image-gen custom <description>      # Custom with full Creative Director pipeline
/seo image-gen batch <description> [N]   # Generate N variations (default: 3)
```

**Example:**
```
/seo image-gen og "Professional SaaS analytics dashboard with clean UI"
/seo image-gen hero "Dramatic sunset over modern city skyline"
/seo image-gen product "Wireless noise-canceling headphones on marble surface"
```

**What it does:**
1. Maps SEO use case to optimized domain mode, aspect ratio, and resolution
2. Constructs 6-component Reasoning Brief (Creative Director pipeline)
3. Generates image via Gemini API
4. Provides SEO checklist (alt text, file naming, WebP, schema markup)

---

## Quick Reference

| Command | Use Case |
|---------|----------|
| `/seo audit <url>` | Full website audit |
| `/seo competitor-pages [url\|generate]` | Competitor comparison pages |
| `/seo content <url>` | E-E-A-T analysis |
| `/seo geo <url>` | AI search optimization |
| `/seo hreflang [url]` | Hreflang/i18n SEO audit |
| `/seo images <url>` | Image optimization |
| `/seo image-gen [use-case] <desc>` | AI image generation (extension) |
| `/seo page <url>` | Single page analysis |
| `/seo plan <type>` | Strategic planning |
| `/seo programmatic [url\|plan]` | Programmatic SEO analysis |
| `/seo schema <url>` | Schema validation |
| `/seo sitemap <url>` | Sitemap validation |
| `/seo sitemap generate` | Create new sitemap |
| `/seo technical <url>` | Technical SEO check |
| `/seo dataforseo [command]` | Live SEO data (extension) |
