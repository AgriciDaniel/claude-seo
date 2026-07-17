# Design: OpenCode-Native Rewrite of claude-seo

**Date:** 2026-07-17
**Status:** Approved
**Scope:** Full feature parity — all 25 sub-skills, 18 sub-agents, 50 scripts, 8 extensions

## Summary

Transform claude-seo from a Claude Code plugin into a fully OpenCode-native tool. All 50 Python scripts are reused unchanged. The skill/agent/command layer is rebuilt using OpenCode primitives: commands for user-invocable `/` entry points, agents for sub-dispatch, and `opencode.jsonc` for centralized configuration. Claude-specific files are removed.

## Architecture

```
~/.config/opencode/
├── opencode.jsonc              # Central config: skill paths, agents, commands, MCP, permissions
├── commands/                   # 25 user-invocable /seo-* commands
│   ├── seo.md                  # Orchestrator / routing entry
│   ├── seo-audit.md
│   ├── seo-page.md
│   ├── seo-technical.md
│   ├── seo-content.md
│   ├── seo-content-brief.md
│   ├── seo-schema.md
│   ├── seo-images.md
│   ├── seo-sitemap.md
│   ├── seo-geo.md
│   ├── seo-plan.md
│   ├── seo-programmatic.md
│   ├── seo-competitor-pages.md
│   ├── seo-hreflang.md
│   ├── seo-local.md
│   ├── seo-maps.md
│   ├── seo-google.md
│   ├── seo-backlinks.md
│   ├── seo-cluster.md
│   ├── seo-sxo.md
│   ├── seo-drift.md
│   ├── seo-ecommerce.md
│   ├── seo-flow.md
│   ├── seo-dataforseo.md
│   └── seo-image-gen.md
├── agents/                     # 18 subagents in OpenCode format
│   ├── seo-technical.md
│   ├── seo-content.md
│   ├── seo-schema.md
│   ├── seo-sitemap.md
│   ├── seo-performance.md
│   ├── seo-visual.md
│   ├── seo-geo.md
│   ├── seo-local.md
│   ├── seo-maps.md
│   ├── seo-google.md
│   ├── seo-backlinks.md
│   ├── seo-cluster.md
│   ├── seo-sxo.md
│   ├── seo-drift.md
│   ├── seo-ecommerce.md
│   ├── seo-flow.md
│   ├── seo-dataforseo.md
│   └── seo-image-gen.md
└── seo-skills/                 # Reference content + scripts
    ├── SKILL.md                # Main orchestrator reference
    ├── references/             # 13 shared reference files
    ├── seo-techical/references/
    ├── seo-geo/references/
    ├── seo-google/references/
    ├── seo-content-brief/references/
    ├── seo-cluster/references/
    ├── seo-sxo/references/
    ├── seo-drift/references/
    ├── seo-ecommerce/references/
    ├── seo-dataforseo/references/
    ├── scripts/                # 50 Python scripts (unchanged)
    ├── schema/                 # JSON-LD templates (unchanged)
    ├── extensions/             # 8 extension packages
    └── data/                   # Reference data (unchanged)
```

## Key Design Decisions

### 1. Commands replace skill routing

Each sub-skill's `SKILL.md` body becomes an OpenCode command body with a short `$ARGUMENTS` preamble. The existing `skills/seo/SKILL.md` orchestrator becomes the `/seo` command. Users invoke `/seo-audit <url>`, `/seo-page <url>`, etc. Each command body contains the full analysis instructions; no separate routing table needed.

### 2. Agents become OpenCode subagents

All 18 agent files' frontmatter is rewritten:
- Remove: `model: sonnet`, `maxTurns: N`, `tools: [...]`, `name:`
- Add: `mode: subagent`, `description:`
- Body (prompt): unchanged — references `python3 scripts/...` and tool names that map 1:1
- Two agents need path updates for `skills/seo-*/references/` references
- `seo-visual.md` needs `external_directory` permission for `/tmp/` screenshot output

### 3. Skills become reference material

Reference content (`skills/*/references/*.md`) moves to `~/.config/opencode/seo-skills/` and is loaded on demand via the `Read` tool. A single `SKILL.md` remains for the orchestrator.

### 4. Central configuration

One `opencode.jsonc` replaces `.claude-plugin/plugin.json`, `marketplace.json`, `CLAUDE.md`, and `hooks/hooks.json`. Contains agent definitions, command paths, MCP servers (Playwright, DataForSEO, Firecrawl), skill paths, and permissions.

### 5. Python scripts untouched

All 50 scripts are pure Python with no Claude dependencies. They stay in `scripts/` and are invoked identically: `python3 scripts/render_page.py <url>`.

### 6. Global install

Install target is `~/.config/opencode/`. `install.sh` copies commands, agents, reference skills, scripts, schema, extensions, and data. Python venv at `~/.config/opencode/seo-skills/.venv/`. API credentials remain at `~/.config/claude-seo/` (not Claude-specific, just a config path).

## File Changes

### Removed
- `.claude-plugin/` (plugin.json, marketplace.json)
- `CLAUDE.md`
- `marketplace.json` (root)
- `hooks/` (hooks.json, run-python-hook.js, validate-schema.py)
- `docs/MCP-INTEGRATION.md` (references Claude MCP path)

### Added
- `commands/` directory (25 command .md files)
- `agents/` directory (18 rewritten agent .md files)
- `opencode.jsonc` (central configuration)
- This design doc

### Updated
- `AGENTS.md` — add OpenCode row to harness table and tool-mapping table
- `README.md` — reflect OpenCode support
- `install.sh`, `install.ps1`, `uninstall.sh`, `uninstall.ps1` — target OpenCode paths
- `docs/COMMANDS.md` — update for OpenCode command format
- `tests/test_manifest_consistency.py` — update for OpenCode file structure
- Sub-skill reference file paths in agent bodies (2 agents)

### Untouched
- `scripts/` (50 files), `schema/`, `data/`, `extensions/`, `assets/`, `screenshots/`
- `CITATION.cff`, `CHANGELOG.md`, `CONTRIBUTORS.md`, `pyproject.toml`, `requirements.txt`
- `.github/`, `tests/` (except manifest consistency)
- `pdf/`, `docs/` (except MCP-INTEGRATION.md, COMMANDS.md)

## Agent Frontmatter: Before/After

**Before** (Claude Code):
```yaml
name: seo-technical
description: Technical SEO specialist...
model: sonnet
maxTurns: 20
tools: Read, Bash, Write, Glob, Grep
```

**After** (OpenCode):
```yaml
mode: subagent
description: Technical SEO specialist. Analyzes crawlability, indexability, security, URL structure, mobile optimization, Core Web Vitals, and JavaScript rendering.
```

## Command Body: Before/After

**Before** (`skills/seo-page/SKILL.md`):
```yaml
name: seo-page
description: Deep single-page SEO analysis...
user-invocable: true
argument-hint: "[url]"
license: MIT
metadata:
  author: AgriciDaniel
  version: "2.2.0"
  category: seo
---
# Single Page Analysis
...analysis body...
```

**After** (`commands/seo-page.md`):
```yaml
description: Deep single-page SEO analysis covering on-page elements, content quality, technical meta tags, schema, images, and performance.
agent: general
---
The user ran /seo-page with argument: $ARGUMENTS

Run a comprehensive single-page SEO analysis on the provided URL.

---

# Single Page Analysis
...analysis body (unchanged)...
```

## Install Script Path Mappings

| Was (Claude) | Becomes (OpenCode) |
|---|---|
| `~/.claude/skills/seo/` | `~/.config/opencode/seo-skills/` |
| `~/.claude/skills/seo-*/` | `~/.config/opencode/seo-skills/` |
| `~/.claude/agents/seo-*.md` | `~/.config/opencode/agents/seo-*.md` |
| `~/.claude/settings.json` | `~/.config/opencode/opencode.jsonc` (merge) |
| `~/.config/claude-seo/` | `~/.config/claude-seo/` (unchanged) |

## opencode.jsonc Structure

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": ["AGENTS.md"],
  "skills": {
    "paths": ["~/.config/opencode/seo-skills"]
  },
  "agent": {
    "seo-technical": { "mode": "subagent", "description": "..." },
    "seo-content": { "mode": "subagent", "description": "..." }
    // ... 16 more agents
  },
  "mcp": {
    "playwright": {
      "type": "local",
      "command": ["npx", "-y", "@playwright/mcp"],
      "enabled": true,
      "env": { "BROWSER": "chromium" }
    }
  },
  "permission": {
    "bash": { "python3 scripts/*": "allow", "*": "ask" },
    "external_directory": { "/tmp/*": "allow" },
    "edit": "ask",
    "webfetch": "allow"
  }
}
```

## Open-Ended Decisions (TBD During Implementation)

- Whether to define agents inline in `opencode.jsonc` or as separate files in `agents/` (or both — file-based for body, inline for registration)
- Whether DataForSEO and Firecrawl MCP servers work with the same manifest format or need adaptation
- Exact `permission` rules needed once we test with all 50 scripts
