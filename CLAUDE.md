# Claude SEO: Universal SEO Analysis Skill

## Project Overview

This repository contains **Claude SEO**, a Tier 4 Claude Code skill for comprehensive
SEO analysis across all industries. It follows the Agent Skills open standard and the
3-layer architecture (directive, orchestration, execution). 20 core sub-skills (+ 3
extensions), 15 core subagents (+ 2 extension agents, 17 total), and an extensible reference
system cover technical SEO, content quality,
schema markup, image optimization, sitemap architecture, AI search optimization,
local SEO (GBP, citations, reviews, map pack), maps intelligence, semantic topic
clustering, search experience optimization (SXO), SEO drift monitoring, e-commerce
SEO, and international SEO with cultural adaptation profiles.

## Architecture

```
claude-seo/
  CLAUDE.md                          # Project instructions (this file)
  CONTRIBUTORS.md                    # Community credits (Pro Hub Challenge)
  AGENTS.md                          # Multi-platform agent instructions (Cursor, Antigravity)
  .claude-plugin/
    plugin.json                    # Plugin manifest (v1.9.0)
    marketplace.json               # Marketplace catalog for distribution
  skills/                            # 23 skills (auto-discovered)
    seo/                           # Main orchestrator skill
      SKILL.md                     # Entry point, routing table, core rules
      references/                  # On-demand knowledge files (12 files)
    seo-audit/SKILL.md            # Full site audit with parallel agents
    seo-page/SKILL.md            # Deep single-page analysis
    seo-technical/SKILL.md       # Technical SEO (9 categories)
    seo-content/SKILL.md         # E-E-A-T and content quality
    seo-schema/SKILL.md          # Schema.org markup detection/generation
    seo-sitemap/SKILL.md         # XML sitemap analysis/generation
    seo-images/SKILL.md          # Image optimization analysis
    seo-geo/SKILL.md             # AI search / GEO optimization
    seo-local/SKILL.md           # Local SEO (GBP, citations, reviews, map pack)
    seo-maps/SKILL.md            # Maps intelligence (geo-grid, GBP audit, reviews, competitors)
    seo-plan/SKILL.md            # Strategic SEO planning
    seo-programmatic/SKILL.md    # Programmatic SEO at scale
    seo-competitor-pages/SKILL.md # Competitor comparison pages
    seo-hreflang/SKILL.md       # International SEO / hreflang
    seo-google/                  # Google SEO APIs
      SKILL.md
      references/                # API reference files (10 files)
    seo-backlinks/SKILL.md      # Backlink profile analysis
    seo-cluster/                 # Semantic topic clustering (v1.9.0, by Lutfiya Miller)
      SKILL.md
      references/                # Clustering methodology, architecture, workflow
      templates/                 # cluster-map.html interactive visualization
    seo-sxo/                     # Search Experience Optimization (v1.9.0, by Florian Schmitz)
      SKILL.md
      references/                # Page-type taxonomy, user stories, personas, wireframes
    seo-drift/                   # SEO drift monitoring (v1.9.0, by Dan Colta)
      SKILL.md
      references/                # Comparison rules (17 rules, 3 severity levels)
    seo-ecommerce/               # E-commerce SEO (v1.9.0, by Matej Marjanovic)
      SKILL.md
      references/                # Marketplace API endpoints
    seo-dataforseo/SKILL.md     # Live SEO data via DataForSEO MCP (extension mirror)
    seo-image-gen/              # AI image generation for SEO assets (extension mirror)
      SKILL.md
      references/                # Image gen reference files (7 files)
  agents/                          # 17 subagents (auto-discovered)
    seo-technical.md             # Crawlability, indexability, security
    seo-content.md               # E-E-A-T, readability, thin content
    seo-schema.md                # Structured data validation
    seo-sitemap.md               # Sitemap quality gates
    seo-performance.md           # Core Web Vitals, page speed
    seo-visual.md                # Screenshots, mobile rendering
    seo-geo.md                   # AI crawler access, GEO, citability
    seo-local.md                 # GBP, NAP, citations, reviews, local schema
    seo-maps.md                  # Geo-grid, GBP audit, reviews, competitor radius
    seo-google.md                # Google API analyst (CrUX, GSC, GA4)
    seo-backlinks.md             # Backlink profile analyst (Moz, Bing, CC, verify)
    seo-dataforseo.md            # DataForSEO data analyst
    seo-image-gen.md             # SEO image audit analyst
    seo-cluster.md               # Semantic clustering analysis
    seo-sxo.md                   # Search experience optimization
    seo-drift.md                 # SEO drift monitoring
    seo-ecommerce.md             # E-commerce SEO analysis
  hooks/                           # Quality gate hooks
    hooks.json                   # PostToolUse schema validation
  scripts/                         # Python execution scripts (28 tracked + 2 dev-only)
    google_auth.py               # Credential management (OAuth, SA, API key, 4-tier detection)
    backlinks_auth.py            # Backlink API credential management (Moz, Bing)
    moz_api.py                   # Moz Link Explorer API (DA/PA, spam, domains, anchors)
    bing_webmaster.py            # Bing Webmaster Tools API (links, competitor comparison)
    commoncrawl_graph.py         # Common Crawl web graph parser (PageRank, in-degree)
    verify_backlinks.py          # Backlink existence verification crawler
    pagespeed_check.py           # PSI v5 + CrUX API
    crux_history.py              # CrUX History API (25-week trends)
    gsc_query.py                 # Search Console (queries, pages, sitemaps, sites)
    gsc_inspect.py               # URL Inspection (single + batch)
    indexing_notify.py           # Indexing API v3 (URL_UPDATED/URL_DELETED)
    ga4_report.py                # GA4 organic traffic reports
    google_report.py             # PDF/HTML report generator (WeasyPrint + matplotlib)
    youtube_search.py            # YouTube Data API v3
    nlp_analyze.py               # Cloud Natural Language API
    keyword_planner.py           # Google Ads Keyword Planner
    fetch_page.py                # Page fetcher with UA rotation
    parse_html.py                # HTML parser for SEO elements
    capture_screenshot.py        # Playwright screenshots
    analyze_visual.py            # Visual analysis helper
    drift_baseline.py            # SEO drift baseline capture (SQLite)
    drift_compare.py             # SEO drift comparison engine (17 rules)
    drift_report.py              # SEO drift HTML report generator
    drift_history.py             # SEO drift history query
    dataforseo_costs.py          # DataForSEO cost estimation and budget tracking
    dataforseo_merchant.py       # Google Shopping / Amazon data fetching
    dataforseo_normalize.py      # DataForSEO response normalization utility
    mobile_analysis.py           # Mobile rendering analysis (gitignored, dev-only)
  schema/                          # Schema.org JSON-LD templates
  extensions/                      # Optional add-on install helpers
    dataforseo/                  # DataForSEO MCP install scripts
    firecrawl/                   # Firecrawl MCP install scripts
    banana/                      # Banana MCP install scripts
  docs/                            # Extended documentation
```

## Commands

| Command | Purpose |
|---------|---------|
| `/seo audit <url>` | Full site audit with up to 15 parallel subagents |
| `/seo page <url>` | Deep single-page analysis |
| `/seo technical <url>` | Technical SEO audit (9 categories) |
| `/seo content <url>` | E-E-A-T and content quality analysis |
| `/seo schema <url>` | Schema.org detection, validation, generation |
| `/seo sitemap <url>` | XML sitemap analysis or generation |
| `/seo images <url or optimize>` | Image SEO: on-page audit, SERP analysis, file optimization |
| `/seo geo <url>` | AI search / Generative Engine Optimization |
| `/seo plan <type>` | Strategic SEO planning by industry |
| `/seo programmatic` | Programmatic SEO analysis and planning |
| `/seo competitor-pages` | Competitor comparison page generation |
| `/seo local <url>` | Local SEO analysis (GBP, citations, reviews, map pack) |
| `/seo maps [command] [args]` | Maps intelligence (geo-grid, GBP audit, reviews, competitors) |
| `/seo hreflang <url>` | International SEO / hreflang audit |
| `/seo google [command] [url]` | Google SEO APIs (GSC, PageSpeed, CrUX, Indexing, GA4) |
| `/seo backlinks <url>` | Backlink profile analysis (free: Moz, Bing, CC; premium: DataForSEO) |
| `/seo backlinks setup` | Setup instructions for free backlink APIs |
| `/seo backlinks verify <url>` | Verify known backlinks still exist |
| `/seo cluster <seed-keyword>` | SERP-based semantic clustering and content architecture |
| `/seo sxo <url>` | Search Experience Optimization: page-type analysis, personas |
| `/seo drift baseline <url>` | Capture SEO baseline for change monitoring |
| `/seo drift compare <url>` | Compare current state to stored baseline |
| `/seo drift history <url>` | Show drift history over time |
| `/seo ecommerce <url>` | E-commerce SEO: product schema, marketplace intelligence |
| `/seo firecrawl [command] <url>` | Full-site crawling and site mapping (extension) |
| `/seo dataforseo [command]` | Live SEO data via DataForSEO MCP (extension) |
| `/seo image-gen [use-case] <desc>` | AI image generation for SEO assets (extension) |

## Development Rules

- Keep SKILL.md files under 500 lines / 5000 tokens
- Reference files should be focused and under 200 lines
- Scripts must have docstrings, CLI interface, and JSON output
- Follow kebab-case naming for all skill directories
- Agents invoked via Agent tool, never via Bash
- Python dependencies install into `~/.claude/skills/seo/.venv/`
- Test with `python -m pytest tests/` after changes (if applicable)

## Security Rules

- **Never commit credentials**: `.env`, `client_secret*.json`, `oauth-token.json`, `service_account*.json` are all in `.gitignore`
- **URL validation**: All scripts that accept user URLs must call `validate_url()` from `google_auth.py` before making API calls. This blocks private IPs, loopback, and GCP metadata endpoints (SSRF protection).
- **OAuth tokens**: Never store `client_secret` in the token file. Read it from the client_secret.json file at runtime.
- **No hardcoded paths**: Use `os.path.dirname(os.path.abspath(__file__))` for relative paths, never `/home/username/...`
- **Config location**: `~/.config/claude-seo/google-api.json` and `~/.config/claude-seo/backlinks-api.json` (user-space, not in repo)

## Report Generation Rules

- **All SEO reports must use `scripts/google_report.py`** as the canonical report generator
- **Dependencies**: `matplotlib>=3.8.0` (charts) + `weasyprint>=61.0` (HTML-to-PDF), both in `requirements.txt`
- **Format**: A4 PDF via WeasyPrint + matplotlib charts at 200 DPI
- **Style**: Clean white title page with navy (#1e3a5f) accent, Times New Roman body font
- **Color palette**: Navy #1e3a5f (headers), dark gold #b8860b (accents), forest green #2d6a4f (pass), warm amber #d4740e (warnings), deep red #c53030 (fail), warm cream #faf9f7 (backgrounds)
- **Structure**: Title page → TOC with scores → Executive Summary → Data sections → Recommendations → Methodology
- **Charts**: 85% width, max-height 120mm, figure captions on every chart, saved to `charts/` at 200 DPI
- **No `page-break-inside: avoid`** on any element (causes white gaps in WeasyPrint)
- **Post-generation review**: `_review_pdf()` runs automatically, checking for empty images, thin sections, duplicates
- **Before presenting any PDF to the user**: verify the review passes (`"status": "PASS"`)
- **Cross-skill enforcement**: After completing ANY analysis command (audit, page, technical, content, schema, geo, local, maps), offer: "Generate a PDF report? Use `/seo google report`"
- **Google logo** appears on title page when using Google API data ("Powered by Google APIs")

## Ecosystem

Part of the Claude Code skill family:
- [Claude Banana](https://github.com/AgriciDaniel/banana-claude) -- standalone image gen (bundled as extension here)
- [Claude Blog](https://github.com/AgriciDaniel/claude-blog) -- companion blog engine, consumes SEO findings
- [AI Marketing Claude](https://github.com/zubair-trabzada/ai-marketing-claude) -- community marketing suite (copy, emails, ads, funnels, CRO)

## Key Principles

1. **Progressive Disclosure**: Metadata always loaded, instructions on activation, resources on demand
2. **Industry Detection**: Auto-detect SaaS, e-commerce, local, publisher, agency
3. **Parallel Execution**: Full audits spawn up to 15 subagents simultaneously
4. **Extension System**: DataForSEO MCP for live data, Firecrawl MCP for site crawling, Banana MCP for AI image generation

## Release Blog Post

After cutting a new release (git tag + `gh release create`), run:

```
/release-blog
```

This generates a blog post on https://claude-seo.md/blog/, handles cover image generation, SEO metadata, FAQ schema, internal linking, sitemap/llms.txt updates, Vercel deployment, and Google indexing.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health

