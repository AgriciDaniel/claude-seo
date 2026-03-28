# AGENTS.md

This file provides project instructions for AI coding agents (Cursor, Cursor Cloud).
Claude Code users: see `CLAUDE.md` for the equivalent instructions in Claude Code's native format.

## Project Overview

**Claude SEO** is a comprehensive SEO analysis skill/plugin. It is not a standalone web
application — there is no build step, no server to run, and no database. The product
consists of Markdown skill files, subagent definitions, Python helper scripts, JSON schema
templates, and shell install scripts.

The skill follows the Agent Skills open standard and a 3-layer architecture
(directive → orchestration → execution): 14 core sub-skills (+ 2 extensions),
9 core subagents (+ 2 extension agents), and an extensible reference system covering
technical SEO, content quality, schema markup, image optimization, sitemap architecture,
AI search optimization, local SEO, and maps intelligence.

## Architecture

```
claude-seo/
  CLAUDE.md                        # Project instructions (Claude Code)
  AGENTS.md                        # Project instructions (Cursor / Cursor Cloud)
  .claude-plugin/
    plugin.json                    # Plugin manifest (v1.6.1)
    marketplace.json               # Marketplace catalog for distribution
  skills/                          # 17 skills (auto-discovered by Claude Code)
    seo/                           # Main orchestrator skill
      SKILL.md                     # Entry point, routing table, core rules
      references/                  # On-demand knowledge files (10 files)
    seo-audit/SKILL.md             # Full site audit with parallel agents
    seo-page/SKILL.md              # Deep single-page analysis
    seo-technical/SKILL.md         # Technical SEO (9 categories)
    seo-content/SKILL.md           # E-E-A-T and content quality
    seo-schema/SKILL.md            # Schema.org markup detection/generation
    seo-sitemap/SKILL.md           # XML sitemap analysis/generation
    seo-images/SKILL.md            # Image optimization analysis
    seo-geo/SKILL.md               # AI search / GEO optimization
    seo-local/SKILL.md             # Local SEO (GBP, citations, reviews)
    seo-maps/SKILL.md              # Maps intelligence (geo-grid, GBP audit)
    seo-plan/SKILL.md              # Strategic SEO planning
    seo-programmatic/SKILL.md      # Programmatic SEO at scale
    seo-competitor-pages/SKILL.md  # Competitor comparison pages
    seo-hreflang/SKILL.md          # International SEO / hreflang
    seo-dataforseo/SKILL.md        # Live SEO data via DataForSEO MCP
    seo-image-gen/                 # AI image generation for SEO assets
      SKILL.md
      references/                  # Image gen reference files (7 files)
  agents/                          # 11 subagents (auto-discovered by Claude Code)
    seo-technical.md               # Crawlability, indexability, security
    seo-content.md                 # E-E-A-T, readability, thin content
    seo-schema.md                  # Structured data validation
    seo-sitemap.md                 # Sitemap quality gates
    seo-performance.md             # Core Web Vitals, page speed
    seo-visual.md                  # Screenshots, mobile rendering
    seo-geo.md                     # AI crawler access, GEO, citability
    seo-local.md                   # GBP, NAP, citations, reviews, local schema
    seo-maps.md                    # Geo-grid, GBP audit, reviews, competitor radius
    seo-dataforseo.md              # DataForSEO data analyst
    seo-image-gen.md               # SEO image audit analyst
  hooks/                           # Quality gate hooks
    hooks.json                     # PostToolUse schema validation (Claude Code)
    validate-schema.py             # Schema.org JSON-LD validator
    pre-commit-seo-check.sh        # Pre-commit SEO validation for HTML files
  scripts/                         # Python execution scripts
    fetch_page.py                  # Fetch web pages with SSRF protection
    parse_html.py                  # Extract SEO-relevant elements from HTML
    capture_screenshot.py          # Capture page screenshots via Playwright
    analyze_visual.py              # Above-fold, mobile, typography analysis
  schema/                          # Schema.org JSON-LD templates
  extensions/                      # Optional add-on install helpers
    dataforseo/                    # DataForSEO MCP install scripts
    banana/                        # Banana MCP install scripts (AI images)
  docs/                            # Extended documentation
```

## Commands

These commands are invoked as `/seo <command>` in Claude Code. In Cursor, the same
analyses can be performed by asking the agent to run the equivalent Python scripts
or by referencing the skill/agent markdown files as context.

| Command | Purpose |
|---------|---------|
| `/seo audit <url>` | Full site audit with 9 parallel subagents |
| `/seo page <url>` | Deep single-page analysis |
| `/seo technical <url>` | Technical SEO audit (9 categories) |
| `/seo content <url>` | E-E-A-T and content quality analysis |
| `/seo schema <url>` | Schema.org detection, validation, generation |
| `/seo sitemap <url>` | XML sitemap analysis or generation |
| `/seo images <url>` | Image optimization analysis |
| `/seo geo <url>` | AI search / Generative Engine Optimization |
| `/seo plan <type>` | Strategic SEO planning by industry |
| `/seo programmatic` | Programmatic SEO analysis and planning |
| `/seo competitor-pages` | Competitor comparison page generation |
| `/seo local <url>` | Local SEO analysis (GBP, citations, reviews) |
| `/seo maps [command] [args]` | Maps intelligence (geo-grid, GBP audit) |
| `/seo hreflang <url>` | International SEO / hreflang audit |
| `/seo image-gen [use-case] <desc>` | AI image generation for SEO assets (extension) |

## Development Rules

- Keep `SKILL.md` files under 500 lines / 5000 tokens
- Reference files should be focused and under 200 lines
- Scripts must have docstrings, CLI interface, and JSON output
- Follow kebab-case naming for all skill directories
- Python: follow PEP 8; use `ruff check` before submitting
- Shell: use `set -euo pipefail` and quote all variables
- Markdown: keep lines under 120 characters where practical
- Python dependencies install into `~/.claude/skills/seo/.venv/` (Claude Code) or
  the system/user site-packages (Cursor Cloud)

## Key Principles

1. **Progressive Disclosure**: Metadata always loaded, instructions on activation, resources on demand
2. **Industry Detection**: Auto-detect SaaS, e-commerce, local, publisher, agency
3. **Parallel Execution**: Full audits spawn up to 11 subagents simultaneously
4. **Extension System**: DataForSEO MCP for live data, Banana MCP for AI image generation

## Ecosystem

Part of the Claude Code skill family:
- [Claude Banana](https://github.com/AgriciDaniel/banana-claude) — standalone image gen (bundled as extension here)
- [Claude Blog](https://github.com/AgriciDaniel/claude-blog) — companion blog engine, consumes SEO findings

## Development Environment

### Prerequisites

- Python 3.10+ (pyproject.toml specifies ≥3.11)
- pip
- Optional: Playwright + Chromium for visual analysis scripts
- Optional: Node.js 20+ / npx for MCP extensions (DataForSEO, Banana)

### Setup

```bash
pip install -r requirements.txt
python3 -m playwright install --with-deps chromium   # optional
```

### Development Commands

| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements.txt` |
| Install Playwright | `python3 -m playwright install --with-deps chromium` |
| CI lint (syntax) | `python3 -m py_compile scripts/fetch_page.py && python3 -m py_compile scripts/parse_html.py && python3 -m py_compile scripts/analyze_visual.py && python3 -m py_compile scripts/capture_screenshot.py` |
| Ruff lint | `ruff check scripts/ hooks/` |
| Fetch a page | `python3 scripts/fetch_page.py <url>` |
| Parse HTML | `python3 scripts/parse_html.py <file> --url <base-url> --json` |
| Visual analysis | `python3 scripts/analyze_visual.py <url> --json` |
| Screenshot capture | `python3 scripts/capture_screenshot.py <url> --output screenshots` |

See `CONTRIBUTING.md` for full code style guidelines and PR process.

### CI Pipeline

The GitHub Actions CI (`.github/workflows/ci.yml`) runs `py_compile` syntax checks on
the 4 core scripts. There is no pytest suite — `CLAUDE.md` mentions `python -m pytest tests/`
but no `tests/` directory exists.

### Hooks

- `hooks/hooks.json` — Claude Code PostToolUse hook that runs `validate-schema.py` on
  edited files to catch invalid JSON-LD. In Cursor, run `python3 hooks/validate-schema.py <file>`
  manually or integrate into your workflow.
- `hooks/pre-commit-seo-check.sh` — Validates staged HTML files for SEO issues (placeholder
  text, title length, missing alt text, deprecated schema). Can be wired as a standard
  git pre-commit hook.

## Cursor Cloud specific instructions

### Gotchas

- The environment's default `pip install` may install to `~/.local/bin` (user site-packages).
  Ensure `$HOME/.local/bin` is on `PATH` when invoking `playwright` CLI directly.
- HTTPS may fail with SSL certificate errors inside some sandbox environments.
  Use `http://` URLs for testing when HTTPS is unavailable.
- `capture_screenshot.py` enforces output paths within CWD or `$HOME`; use relative paths
  like `screenshots/` rather than `/tmp/`.
- The 3 ruff warnings in `extensions/banana/scripts/setup_mcp.py` (F541 — f-strings without
  placeholders) are pre-existing in the repository.
