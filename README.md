<!-- Updated: 2026-03-28 -->

![Claude SEO](screenshots/cover-image.jpeg)

# Claude SEO - SEO Audit Skill for Claude Code, Cursor & Antigravity

Comprehensive SEO analysis skill for Claude Code — also compatible with Cursor, Cursor Cloud, and Google Deepmind Antigravity (Gemini). Covers technical SEO, on-page analysis, content quality (E-E-A-T), schema markup, image optimization, sitemap architecture, AI search optimization (GEO), local SEO, maps intelligence, Google SEO APIs (Search Console, PageSpeed, CrUX, GA4), PDF report generation, and strategic planning.

![SEO Command Demo](screenshots/seo-command-demo.gif)

[![CI](https://github.com/AgriciDaniel/claude-seo/actions/workflows/ci.yml/badge.svg)](https://github.com/AgriciDaniel/claude-seo/actions/workflows/ci.yml)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-blue)](https://claude.ai/claude-code)
[![Cursor Compatible](https://img.shields.io/badge/Cursor-Compatible-purple)](https://cursor.sh)
[![Antigravity Plugin](https://img.shields.io/badge/Antigravity-Plugin-green)](https://github.com/AgriciDaniel/claude-seo)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/github/v/release/AgriciDaniel/claude-seo)](https://github.com/AgriciDaniel/claude-seo/releases)

## Table of Contents

- [Installation](#installation)
- [Cursor / Cursor Cloud](#cursor--cursor-cloud)
- [Antigravity / Gemini](#antigravity--gemini)
- [Quick Start](#quick-start)
- [Commands](#commands)
- [Features](#features)
- [Architecture](#architecture)
- [Extensions](#extensions)
- [Ecosystem](#ecosystem)
- [Documentation](#documentation)
- [Requirements](#requirements)
- [Uninstall](#uninstall)
- [Contributing](#contributing)

## Installation

### Recommended Install (Unix/macOS/Linux)

```bash
git clone --depth 1 https://github.com/AgriciDaniel/claude-seo.git
bash claude-seo/install.sh
```

<details>
<summary>One-liner (curl)</summary>

```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash
```

Or via [install.cat](https://install.cat):

```bash
curl -fsSL install.cat/AgriciDaniel/claude-seo | bash
```

Prefer to review the script before running?

```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh > install.sh
cat install.sh        # review
bash install.sh       # run when satisfied
rm install.sh
```

</details>

### Windows (PowerShell)

```powershell
git clone --depth 1 https://github.com/AgriciDaniel/claude-seo.git
powershell -ExecutionPolicy Bypass -File claude-seo\install.ps1
```

> **Why git clone instead of `irm | iex`?** Claude Code's own security guardrails flag `irm ... | iex` as a supply chain risk (downloading and executing remote code with no verification). The git clone approach lets you inspect the script at `claude-seo\install.ps1` before running it.


## Cursor / Cursor Cloud

This repository is fully compatible with **Cursor** and **Cursor Cloud** in addition to Claude Code.

### How it works

| Environment | Instructions File | How skills are loaded |
|-------------|-------------------|----------------------|
| **Claude Code** | `CLAUDE.md` | Skills and agents auto-discovered from `~/.claude/skills/` and `~/.claude/agents/` after running `install.sh` |
| **Cursor / Cursor Cloud** | `AGENTS.md` | Agent reads `AGENTS.md` for project context; Python scripts run directly from the repo |
| **Antigravity / Gemini** | `AGENTS.md` + `plugin.json` | Plugin auto-discovered via root `plugin.json`; `skills/` and `agents/` loaded natively |

### Development setup (Cursor / Cursor Cloud)

No `install.sh` needed — work directly from the cloned repo:

```bash
pip install -r requirements.txt
python3 -m playwright install --with-deps chromium   # optional, for visual analysis
```

### Using the Python scripts

The core analysis scripts can be invoked directly:

```bash
python3 scripts/fetch_page.py https://example.com --output page.html
python3 scripts/parse_html.py page.html --url https://example.com --json
python3 scripts/capture_screenshot.py https://example.com --output screenshots
python3 scripts/analyze_visual.py https://example.com --json
```

### Using skills and agents as context

The `skills/` and `agents/` directories contain rich SEO knowledge in Markdown. In Cursor,
reference these files as context (e.g. `@skills/seo/SKILL.md`) to give the agent access to
the same routing logic, quality gates, and SEO expertise that Claude Code uses natively.

See `AGENTS.md` for the full project overview, commands, development rules, and environment-specific gotchas.

## Antigravity / Gemini

This repository is a native **Antigravity plugin**. The root `plugin.json` allows Antigravity to auto-discover all skills and agents.

### How it works

Antigravity natively understands the Agent Skills open standard used by this repository:
- **`plugin.json`** at the root declares the plugin metadata.
- **`skills/`** directory contains all `SKILL.md` files, auto-loaded as skills.
- **`agents/`** directory contains all subagent definitions, auto-loaded as subagents.
- **`AGENTS.md`** provides project-level instructions (shared with Cursor).

### Installation (Antigravity)

The `install.sh` / `install.ps1` scripts automatically detect Antigravity and install the plugin if `~/.gemini/antigravity/plugins/` exists.

Alternatively, clone or symlink the repo directly:

```bash
# Option A: Clone into the Antigravity plugins directory
git clone --depth 1 https://github.com/AgriciDaniel/claude-seo.git \
  ~/.gemini/antigravity/plugins/claude-seo

# Option B: Symlink an existing clone
ln -s /path/to/claude-seo ~/.gemini/antigravity/plugins/claude-seo
```

Once installed, Antigravity will automatically load all SEO skills and agents. Ask Gemini to run any SEO analysis by referencing the skill names (e.g., "run a full SEO audit on https://example.com").

## Quick Start

```bash
# Start Claude Code
claude

# Run a full site audit
/seo audit https://example.com

# Analyze a single page
/seo page https://example.com/about

# Check schema markup
/seo schema https://example.com

# Generate a sitemap
/seo sitemap generate

# Optimize for AI search
/seo geo https://example.com
```
### Demo:
[Watch the full demo on YouTube](https://www.youtube.com/watch?v=COMnNlUakQk)

**`/seo audit`: full site audit with parallel subagents:**

![SEO Audit Demo](screenshots/seo-audit-demo.gif)

## Commands

| Command | Description |
|---------|-------------|
| `/seo audit <url>` | Full website audit with parallel subagent delegation |
| `/seo page <url>` | Deep single-page analysis |
| `/seo sitemap <url>` | Analyze existing XML sitemap |
| `/seo sitemap generate` | Generate new sitemap with industry templates |
| `/seo schema <url>` | Detect, validate, and generate Schema.org markup |
| `/seo images <url>` | Image optimization analysis |
| `/seo technical <url>` | Technical SEO audit (9 categories) |
| `/seo content <url>` | E-E-A-T and content quality analysis |
| `/seo geo <url>` | AI Overviews / Generative Engine Optimization |
| `/seo plan <type>` | Strategic SEO planning (saas, local, ecommerce, publisher, agency) |
| `/seo programmatic <url>` | Programmatic SEO analysis and planning |
| `/seo competitor-pages <url>` | Competitor comparison page generation |
| `/seo local <url>` | Local SEO analysis (GBP, citations, reviews, map pack) |
| `/seo maps [command]` | Maps intelligence (geo-grid, GBP audit, reviews, competitors) |
| `/seo hreflang <url>` | Hreflang/i18n SEO audit and generation |
| `/seo google [command] [url]` | Google SEO APIs (GSC, PageSpeed, CrUX, Indexing, GA4) |
| `/seo google report [type]` | Generate PDF/HTML report with charts (cwv-audit, gsc-performance, full) |

### `/seo programmatic [url|plan]`
**Programmatic SEO Analysis & Planning**

Build SEO pages at scale from data sources with quality safeguards.

**Capabilities:**
- Analyze existing programmatic pages for thin content and cannibalization
- Plan URL patterns and template structures for data-driven pages
- Internal linking automation between generated pages
- Canonical strategy and index bloat prevention
- Quality gates: WARNING at 100+ pages, HARD STOP at 500+ without audit

### `/seo competitor-pages [url|generate]`
**Competitor Comparison Page Generator**

Create high-converting "X vs Y" and "alternatives to X" pages.

**Capabilities:**
- Structured comparison tables with feature matrices
- Product schema markup with AggregateRating
- Conversion-optimized layouts with CTA placement
- Keyword targeting for comparison intent queries
- Fairness guidelines for accurate competitor representation

### `/seo hreflang [url]`
**Hreflang / i18n SEO Audit & Generation**

Validate and generate hreflang tags for multi-language sites.

**Capabilities:**
- Generate hreflang tags (HTML, HTTP headers, or XML sitemap)
- Validate self-referencing tags, return tags, x-default
- Detect common mistakes (missing returns, invalid codes, HTTP/HTTPS mismatch)
- Cross-domain hreflang support
- Language/region code validation (ISO 639-1 + ISO 3166-1)

## Features

### Core Web Vitals (Current Metrics)
- **LCP** (Largest Contentful Paint): Target < 2.5s
- **INP** (Interaction to Next Paint): Target < 200ms
- **CLS** (Cumulative Layout Shift): Target < 0.1

> Note: INP replaced FID on March 12, 2024. FID was fully removed from all Chrome tools on September 9, 2024.

### E-E-A-T Analysis
Updated to September 2025 Quality Rater Guidelines:
- **Experience**: First-hand knowledge signals
- **Expertise**: Author credentials and depth
- **Authoritativeness**: Industry recognition
- **Trustworthiness**: Contact info, security, transparency

### Schema Markup
- Detection: JSON-LD (preferred), Microdata, RDFa
- Validation against Google's supported types
- Generation with templates
- Deprecation awareness:
  - HowTo: Deprecated (Sept 2023)
  - FAQ: Restricted to gov/health sites (Aug 2023)
  - SpecialAnnouncement: Deprecated (July 2025)

### AI Search Optimization (GEO)
New for 2026 - optimize for:
- Google AI Overviews
- ChatGPT web search
- Perplexity
- Other AI-powered search

### Google SEO APIs (New in v1.7.0)
Direct integration with Google's SEO data:
- **PageSpeed Insights + CrUX**: Lab and field Core Web Vitals data
- **Search Console**: Top queries, URL inspection, sitemap status
- **Indexing API**: Notify Google of new/updated/removed URLs
- **GA4**: Organic traffic, top landing pages, device/country breakdown
- **PDF Reports**: Enterprise A4 reports with charts via WeasyPrint + matplotlib

4-tier credential system — get value at every level:
| Tier | Auth | APIs |
|------|------|------|
| 0 | API key | PSI, CrUX, CrUX History |
| 1 | + OAuth/SA | + GSC, URL Inspection, Indexing |
| 2 | + GA4 config | + GA4 organic traffic |
| 3 | + Ads token | + Keyword Planner |

### Local SEO & Maps Intelligence (New in v1.6.0)
- Google Business Profile optimization
- NAP consistency auditing
- Citation and review analysis
- Geo-grid rank tracking and competitor radius mapping

### Quality Gates
- Warning at 30+ location pages
- Hard stop at 50+ location pages
- Thin content detection per page type
- Doorway page prevention

## Architecture

```
~/.claude/skills/seo/         # Main orchestrator skill
~/.claude/skills/seo-*/       # Sub-skills (15 + 2 extensions)
~/.claude/agents/seo-*.md     # Subagents (10 + 2 extensions)
```

### Video & Live Schema (New)
Additional schema types for video content, live streaming, and key moments:
- VideoObject: Video page markup with thumbnails, duration, upload date
- BroadcastEvent: LIVE badge support for live streaming content
- Clip: Key moments / chapters within videos
- SeekToAction: Enable seek functionality in video rich results
- SoftwareSourceCode: Open source and code repository pages

See `schema/templates.json` for ready-to-use JSON-LD snippets.

### Recently Added
- Programmatic SEO skill (`/seo programmatic`)
- Competitor comparison pages skill (`/seo competitor-pages`)
- Multi-language hreflang validation (`/seo hreflang`)
- Video & Live schema types (VideoObject, BroadcastEvent, Clip, SeekToAction)
- Google SEO quick-reference guide

## Requirements

- Python 3.10+
- Claude Code CLI, Cursor, Cursor Cloud, or Antigravity/Gemini
- Optional: Playwright for screenshots
- Optional: Google API credentials for enriched data (see `/seo google setup`)

## Uninstall

```bash
git clone --depth 1 https://github.com/AgriciDaniel/claude-seo.git
bash claude-seo/uninstall.sh
```

<details>
<summary>One-liner (curl)</summary>

```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/uninstall.sh | bash
```

</details>

### MCP Integrations

Integrates with MCP servers for live SEO data, including official servers from **Ahrefs** (`@ahrefs/mcp`) and **Semrush**, plus community servers for Google Search Console, PageSpeed Insights, and DataForSEO. See [MCP Integration Guide](docs/MCP-INTEGRATION.md) for setup.

## Extensions

Optional add-ons that integrate external data sources via MCP servers.

### DataForSEO

Live SERP data, keyword research, backlinks, on-page analysis, content analysis, business listings, AI visibility checking, and LLM mention tracking. 22 commands across 9 API modules.

```bash
# Install (requires DataForSEO account)
./extensions/dataforseo/install.sh
```

```bash
# Example commands
/seo dataforseo serp best coffee shops
/seo dataforseo keywords seo tools
/seo dataforseo backlinks example.com
/seo dataforseo ai-mentions your brand
/seo dataforseo ai-scrape your brand name
```

See [DataForSEO Extension](extensions/dataforseo/README.md) for full documentation.

### Banana (AI Image Generation)

Generate SEO images (OG previews, blog heroes, product photos, infographics) using the
[Claude Banana](https://github.com/AgriciDaniel/banana-claude) Creative Director pipeline.

```bash
# Install extension
./extensions/banana/install.sh
```

```bash
# Example commands
/seo image-gen og "Professional SaaS dashboard"
/seo image-gen hero "AI-powered content creation"
/seo image-gen batch "Product photography" 3
```

See [Banana Extension](extensions/banana/README.md) for full documentation.
Already using standalone Claude Banana? The extension reuses your existing nanobanana-mcp setup.

## Ecosystem

Claude SEO is part of a family of Claude Code skills that work together:

| Skill | What it does | How it connects |
|-------|-------------|-----------------|
| [Claude SEO](https://github.com/AgriciDaniel/claude-seo) | SEO analysis, audits, schema, GEO | Core -- analyzes sites, generates action plans |
| [Claude Blog](https://github.com/AgriciDaniel/claude-blog) | Blog writing, optimization, scoring | Companion -- write content optimized by SEO findings |
| [Claude Banana](https://github.com/AgriciDaniel/banana-claude) | AI image generation via Gemini | Shared -- generates images for SEO assets and blog posts |

**Workflow example:**
1. `/seo audit https://example.com` -- identify content gaps and image issues
2. `/blog write "target keyword"` -- create SEO-optimized blog posts
3. `/seo image-gen hero "blog topic"` -- generate hero images (banana extension)
4. `/seo geo https://example.com/blog/post` -- optimize for AI citations

## Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Commands Reference](docs/COMMANDS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [MCP Integration](docs/MCP-INTEGRATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting PRs.

---

Built for Claude Code, Cursor & Antigravity by [@AgriciDaniel](https://github.com/AgriciDaniel)
