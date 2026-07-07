# Claude SEO: Multi-Platform Agent Instructions

> For **Cursor**, **Cursor Cloud Agents**, **Google Antigravity**, **Gemini CLI**,
> **OpenAI Codex CLI**, **Cline**, **Aider**, and any other agent harness that
> reads project-root agent instructions.
>
> Claude Code users: see `CLAUDE.md` instead.

## Cross-platform portability (v2.0.0)

Every skill in `skills/*/SKILL.md` is authored to a portable subset of the
Claude Code skill spec. Validate compatibility with your harness via:

```bash
python3 scripts/portability_check.py
```

The check confirms each `SKILL.md` has the minimum frontmatter every harness
expects (`name`, `description`, optional `model`, optional `tools`) and warns
on Claude-Code-specific features (`maxTurns`, multi-line tool list with
descriptive comments) that other harnesses may ignore but do not reject.

### Per-harness notes

| Harness | How to load claude-seo |
|---|---|
| **Cursor** | Symlink or copy `skills/` and `agents/` into `.cursor/rules/`. Commands are invoked as text prompts; the harness reads `SKILL.md` body as system context. |
| **Cursor Cloud Agents** | Push the repo; Cloud Agents read `AGENTS.md` automatically at session start. |
| **Google Antigravity** | Point the workspace at this repo root; Antigravity reads `AGENTS.md` first, falls back to `skills/`. |
| **Gemini CLI** | `gemini init` in this repo loads `AGENTS.md`. Skills are activated via `activate_skill <name>` in conversation. |
| **OpenAI Codex CLI** | Reads `AGENTS.md` from project root. Bash tools work as documented; some Claude-specific tool names (Read/Write/Edit) are aliased to Codex equivalents transparently. |
| **Cline** | Loads `AGENTS.md` from project root. Skills appear as system messages; subagent delegation falls back to in-context expansion. |
| **Aider** | Reads `AGENTS.md` if present; otherwise falls back to README. Aider does not support sub-agent dispatch; the seo-* skills run inline. |

### Tool-name compatibility

Where claude-seo skills mention Claude Code tools (`Read`, `Write`, `Edit`,
`Bash`, `Glob`, `Grep`, `WebFetch`), each harness typically has an equivalent:

| Claude Code | Codex | Cline | Aider | Cursor / Antigravity |
|---|---|---|---|---|
| Read       | read_file        | read_file       | (inline)        | read |
| Write      | write_file       | write_file      | /add then edit  | write |
| Edit       | apply_diff       | replace_in_file | /edit           | edit |
| Bash       | bash             | execute_command | /run            | shell |
| Glob       | glob             | search_files    | (inline)        | find |
| Grep       | grep             | search_files    | /grep           | grep |
| WebFetch   | fetch / browse   | (browser tool)  | (n/a)           | fetch |

These mappings are automatic in most harnesses; we list them for transparency
in case a recipe needs a specific call.

## Overview

Claude SEO is a Tier 4 SEO analysis skill with 25 sub-skills (21 core + 1 orchestrator +
1 framework integration + 2 extension mirrors), 18 sub-agents (15 core + 1 framework
integration + 2 extension mirrors), and 50 Python execution scripts.

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
python3 scripts/fetch_page.py https://example.com

# HTML parsing for SEO elements
python3 scripts/parse_html.py https://example.com

# PageSpeed Insights
python3 scripts/pagespeed_check.py https://example.com --json

# Drift baseline
python3 scripts/drift_baseline.py https://example.com

# DataForSEO (requires credentials)
DATAFORSEO_USERNAME=user DATAFORSEO_PASSWORD=pass python3 scripts/dataforseo_merchant.py search "keyword"
```

**Cursor Cloud gotchas:**
- SSL certificates may not resolve for some domains. Investigate the certificate issue rather than disabling verification.
- PATH may not include Python venv. Use full path: `~/.claude/skills/seo/.venv/bin/python`
- Screenshots save to `/tmp/` not CWD. Check absolute paths.

## Using with Grok Build

Grok Build discovers this repo as a plugin via the existing
`.claude-plugin/plugin.json` manifest. It loads `skills/`, `agents/`,
and `hooks/hooks.json` natively, and substitutes `${CLAUDE_PLUGIN_ROOT}`
in hook commands.

Install the plugin:

```bash
grok plugin install AgriciDaniel/claude-seo --trust
```

Or from within the Grok Build CLI: run `/plugins`, press `a`, enter
`AgriciDaniel/claude-seo`, and submit.

For local development of a checkout, `grok --plugin-dir /path/to/claude-seo`
loads it for a single session.

Verify with `grok inspect` — skills and agents appear tagged
`[plugin: claude-seo]`. Hooks and MCP servers only execute once the plugin
is trusted (`--trust` at install time, or enable it in the `/plugins` modal).

Python scripts expect dependencies in `~/.claude/skills/seo/.venv/`
(create it with `python3 -m venv` + `pip install -r requirements.txt`),
or any interpreter pointed to by `CLAUDE_SEO_PYTHON`.

## Using with Google Antigravity

Antigravity discovers this project via `.claude-plugin/plugin.json`.
Place the repo in `~/.gemini/antigravity/plugins/claude-seo/` or install via:

```bash
bash install.sh
```

## Architecture

```
skills/                    # 25 sub-skills (auto-discovered)
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
agents/                    # 18 subagents
scripts/                   # 50 Python scripts
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
