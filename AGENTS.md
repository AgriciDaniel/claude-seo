# Claude SEO — Multi-Platform Agent Instructions

> For **Cursor**, **Cursor Cloud Agents**, **Google Antigravity**, and **Gemini CLI**.
> Claude Code users: see `CLAUDE.md` instead.

## Overview

Claude SEO is a Tier 4 SEO analysis skill with 20 core sub-skills (+ 3 extensions),
15 core subagents (+ 2 extension agents, 17 total), and 30 Python execution scripts.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/seo audit <url>` | Full website audit with parallel subagent delegation |
| `/seo page <url>` | Deep single-page analysis |
| `/seo technical <url>` | Technical SEO audit (9 categories) |
| `/seo content <url>` | E-E-A-T and content quality analysis |
| `/seo schema <url>` | Schema.org detection, validation, generation |
| `/seo sitemap <url>` | XML sitemap analysis or generation |
| `/seo images <url>` | Image SEO: on-page audit, SERP analysis, file optimization |
| `/seo geo <url>` | AI Overviews / Generative Engine Optimization |
| `/seo plan <type>` | Strategic SEO planning |
| `/seo cluster <keyword>` | SERP-based semantic clustering and content architecture |
| `/seo sxo <url>` | Search Experience Optimization: page-type analysis, personas |
| `/seo drift baseline <url>` | Capture SEO baseline for change monitoring |
| `/seo drift compare <url>` | Compare current state to stored baseline |
| `/seo drift history <url>` | Show drift history over time |
| `/seo ecommerce <url>` | E-commerce SEO: product schema, marketplace intelligence |
| `/seo programmatic [url]` | Programmatic SEO at scale |
| `/seo competitor-pages [url]` | Competitor comparison pages |
| `/seo local <url>` | Local SEO analysis (GBP, citations, reviews) |
| `/seo maps [cmd] [args]` | Maps intelligence (geo-grid, GBP audit, competitors) |
| `/seo hreflang <url>` | Hreflang/i18n SEO audit, cultural profiles, content parity |
| `/seo google [cmd] [url]` | Google SEO APIs (GSC, PageSpeed, CrUX, Indexing, GA4) |
| `/seo backlinks <url>` | Backlink profile analysis |
| `/seo backlinks setup` | Setup free backlink APIs |
| `/seo backlinks verify <url>` | Verify known backlinks still exist |
| `/seo dataforseo [cmd]` | Live SEO data via DataForSEO (extension) |
| `/seo image-gen [use-case]` | AI image generation for SEO assets (extension) |
| `/seo firecrawl [cmd] <url>` | Full-site crawling and site mapping (extension) |

## Using with Cursor / Cursor Cloud

Cursor reads this file automatically. All SKILL.md files contain the full
analysis logic as natural language instructions. Python scripts in `scripts/`
provide execution capabilities.

**Running scripts directly** (Cursor doesn't have MCP):
```bash
# Page fetching with SSRF protection
python scripts/fetch_page.py https://example.com

# HTML parsing for SEO elements
python scripts/parse_html.py https://example.com

# PageSpeed Insights
python scripts/pagespeed_check.py https://example.com --json

# Drift baseline
python scripts/drift_baseline.py https://example.com

# DataForSEO (requires credentials)
DATAFORSEO_USERNAME=user DATAFORSEO_PASSWORD=pass python scripts/dataforseo_merchant.py search "keyword"
```

**Cursor Cloud gotchas:**
- SSL certificates may not resolve for some domains — investigate the certificate issue rather than disabling verification
- PATH may not include Python venv — use full path: `~/.claude/skills/seo/.venv/bin/python`
- Screenshots save to `/tmp/` not CWD — check absolute paths

## Using with Google Antigravity

Antigravity discovers this project via `plugin.json` at the repo root.
Place the repo in `~/.gemini/antigravity/plugins/claude-seo/` or install via:

```bash
bash install.sh
```

## Architecture

```
skills/                    # 23 skills (auto-discovered)
  seo/SKILL.md            # Main orchestrator + routing
  seo-cluster/            # Semantic clustering (v1.9.0)
  seo-sxo/                # Search Experience Optimization (v1.9.0)
  seo-drift/              # SEO drift monitoring (v1.9.0)
  seo-ecommerce/          # E-commerce SEO (v1.9.0)
  seo-audit/              # Full site audit
  seo-page/               # Single-page analysis
  seo-technical/          # Technical SEO
  seo-content/            # E-E-A-T quality
  seo-schema/             # Schema.org markup
  seo-sitemap/            # XML sitemaps
  seo-images/             # Image optimization
  seo-geo/                # AI search / GEO
  seo-local/              # Local SEO
  seo-maps/               # Maps intelligence
  seo-plan/               # Strategic planning
  seo-hreflang/           # International SEO
  seo-google/             # Google APIs
  seo-backlinks/          # Backlink analysis
  seo-programmatic/       # Programmatic SEO
  seo-competitor-pages/   # Competitor pages
  seo-dataforseo/         # DataForSEO (extension)
  seo-image-gen/          # AI images (extension)
agents/                    # 17 subagents
scripts/                   # 30 Python scripts
schema/                    # JSON-LD templates
extensions/                # Optional add-ons (DataForSEO, Firecrawl, Banana, ASO)
```

## Key Principles

1. **Progressive Disclosure**: Read SKILL.md for routing, load references on demand
2. **Industry Detection**: Auto-detect SaaS, e-commerce, local, publisher, agency
3. **Security**: All scripts call `validate_url()` for SSRF protection
4. **Config location**: `~/.config/claude-seo/` for API credentials

## Credits

Created by [@AgriciDaniel](https://github.com/AgriciDaniel).
v1.9.0 community contributions by Lutfiya Miller, Chris Muller, Florian Schmitz,
Dan Colta, and Matej Marjanovic. See [CONTRIBUTORS.md](CONTRIBUTORS.md).
