# Claude SEO: Multi-Platform Agent Instructions

> For **OpenCode**, **Cursor**, **Cursor Cloud Agents**, **Google Antigravity**,
> **Gemini CLI**, **OpenAI Codex CLI**, **Cline**, **Aider**, and any other agent
> harness that reads project-root agent instructions.
>
> Claude Code users: see `CLAUDE.md` instead.

## Overview

Claude SEO is a Tier 4 SEO analysis skill with 25 sub-skills (21 core + 1 orchestrator +
1 framework integration + 2 extension mirrors), 18 sub-agents (15 core + 1 framework
integration + 2 extension mirrors), and 50 Python execution scripts.

## Working on this repo (dev sessions)

`opencode.jsonc` holds the central project configuration (report styling, security, release flow).
The traps below are what CI actually enforces:

**Tests** — plain pytest, no pytest.ini/conftest:

```bash
pip install -r requirements.txt pytest   # tests import scripts/, which need full runtime deps at import time
pytest tests/ -v                         # full suite
pytest tests/test_url_safety.py -v       # single file
```

- `tests/test_sync_flow.py` hits the GitHub API via `gh`; authenticate `gh` (or set
  `GH_TOKEN`) to avoid anonymous rate-limit failures.
- CI (`.github/workflows/ci.yml`) = `py_compile` on all tracked `scripts/*.py` +
  pytest + a secret scan over tracked files. Ruff is configured in `pyproject.toml`
  (py310, line 100, E/F/W/I) but CI does not run it — run `ruff check scripts/` yourself.

**Manifest consistency is under test** (`tests/test_manifest_consistency.py`).
Adding/removing a skill, agent, or reference file requires lockstep updates:

- the literal phrase `25 sub-skills` (current count) within the first 120 lines of
  `README.md` and this file
- the numbered Sub-Skills list in `skills/seo/SKILL.md` (= `skills/*` minus `seo`;
  extension-only skills like firecrawl stay out of it)
- versions triangulate: `plugin.json` == `CITATION.cff` == `pyproject.toml`
- every `skills/*/references/*.md` must be cited by filename or `[[wikilink]]`
  somewhere in the repo (orphan check)

**Conventions**: SKILL.md < 500 lines; `references/*.md` < 200 lines; kebab-case dirs;
scripts need a docstring, CLI interface, and JSON output. Any user-supplied URL must
pass `validate_url()` — `scripts/url_safety.py` is the canonical module
(`google_auth.py` carries a legacy copy). Rendering scripts (`render_page.py`,
`capture_screenshot.py`) additionally need `playwright install chromium`.

**Git**: `origin` is the public, release-only repo — **never push to `origin/main`
autonomously**. Daily work goes to the private `aimh` remote (absent in fresh public
clones). Full flow: `docs/WORKFLOW-public-private.md` + "Repository Topology" in `CLAUDE.md`.

## Cross-platform portability

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
| **OpenCode** | Install via `bash install.sh` to `~/.config/opencode/`. Commands are invoked as `/seo-audit <url>` etc. Subagents defined via `opencode.jsonc` and `agents/` directory. Skills loaded from `~/.config/opencode/seo-skills/`. |

### Tool-name compatibility

Where claude-seo skills mention Claude Code tools (`Read`, `Write`, `Edit`,
`Bash`, `Glob`, `Grep`, `WebFetch`), each harness typically has an equivalent:

| Claude Code | OpenCode | Codex | Cline | Aider | Cursor / Antigravity |
|---|---|---|---|---|---|---|
| Read       | read | read_file        | read_file       | (inline)        | read |
| Write      | write | write_file       | write_file      | /add then edit  | write |
| Edit       | edit | apply_diff       | replace_in_file | /edit           | edit |
| Bash       | bash | bash             | execute_command | /run            | shell |
| Glob       | glob | glob             | search_files    | (inline)        | find |
| Grep       | grep | grep             | search_files    | /grep           | grep |
| WebFetch   | webfetch | fetch / browse   | (browser tool)  | (n/a)           | fetch |

These mappings are automatic in most harnesses; we list them for transparency
in case a recipe needs a specific call.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/seo audit <url>` | Full website audit with parallel subagent delegation |
| `/seo page <url>` | Deep single-page analysis |
| `/seo technical <url>` | Technical SEO audit (9 categories) |
| `/seo content <url>` | E-E-A-T and content quality analysis |
| `/seo content-brief <topic>` | Detailed SEO content brief: keywords, outline, internal links |
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
| `/seo flow <url>` | FLOW framework: staged prompts + search-and-conversion output |
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

## Using with OpenCode

OpenCode reads `AGENTS.md` automatically from the project root. Install via:

```bash
bash install.sh
```

Commands are invoked via `/seo-audit <url>`, `/seo-page <url>`, etc. The installer copies commands to `~/.config/opencode/commands/`, agents to `~/.config/opencode/agents/`, and skills to `~/.config/opencode/seo-skills/`.

Python venv path: `~/.config/opencode/seo-skills/.venv/bin/python`

## Architecture

```
commands/                  # 25 user-invocable /seo-* commands
  seo.md                  # Main orchestrator + routing
  seo-audit.md            # Full site audit
  seo-page.md             # Single-page analysis
  ...
agents/                    # 18 subagents (OpenCode frontmatter)
scripts/                   # 50 Python scripts
skills/                    # Reference content (references/*.md retained)
schema/                    # JSON-LD templates
extensions/                # Optional add-ons (DataForSEO, Firecrawl, Banana)
opencode.jsonc            # Central configuration
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
