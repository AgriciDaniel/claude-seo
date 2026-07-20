# Architecture

## Overview

Claude SEO follows Anthropic's official Claude Code skill specification with a modular, multi-skill architecture.

## Directory Structure

The plugin ships 25 sub-skills (21 core + 1 orchestrator + 1 framework integration + 2 extension mirrors) and 18 sub-agents (15 core + 1 framework integration + 2 extension mirrors).

```
~/.claude/plugins/.../claude-seo/
├── skills/
│   ├── seo/                    # Main orchestrator
│   │   ├── SKILL.md
│   │   └── references/         # On-demand reference files (13 files)
│   │
│   ├── seo-audit/              # Full site audit (parallel subagents)
│   ├── seo-page/               # Single page analysis
│   ├── seo-technical/          # Technical SEO (9 categories)
│   ├── seo-content/            # E-E-A-T and content quality
│   ├── seo-content-brief/      # Competitive content brief generation
│   ├── seo-schema/             # Schema markup detection and generation
│   ├── seo-sitemap/            # XML sitemap analysis and generation
│   ├── seo-images/             # Image optimization analysis
│   ├── seo-geo/                # AI search optimization (GEO)
│   ├── seo-local/              # Local SEO (GBP, citations, reviews)
│   ├── seo-maps/               # Maps intelligence (geo-grid, GBP audit)
│   ├── seo-backlinks/          # Backlink profile analysis
│   ├── seo-cluster/            # Semantic topic clustering (SERP-based)
│   ├── seo-sxo/                # Search Experience Optimization
│   ├── seo-drift/              # SEO drift monitoring (baselines)
│   ├── seo-ecommerce/          # E-commerce SEO (product schema, marketplaces)
│   ├── seo-hreflang/           # International SEO and hreflang
│   ├── seo-plan/               # Strategic SEO planning (industry templates)
│   ├── seo-programmatic/       # Programmatic SEO at scale
│   ├── seo-competitor-pages/   # Competitor comparison page generation
│   ├── seo-google/             # Google SEO APIs (GSC, PSI, CrUX, GA4)
│   ├── seo-flow/               # FLOW framework integration (CC BY 4.0)
│   ├── seo-dataforseo/         # DataForSEO MCP mirror (extension surface)
│   └── seo-image-gen/          # Banana MCP mirror (extension surface)
│
└── agents/
    ├── seo-technical.md        # Crawlability, indexability, security
    ├── seo-content.md          # E-E-A-T, readability, thin content
    ├── seo-schema.md           # Structured data validation
    ├── seo-sitemap.md          # Sitemap quality gates
    ├── seo-performance.md      # Core Web Vitals
    ├── seo-visual.md           # Screenshots, mobile rendering
    ├── seo-geo.md              # AI crawler access, citability
    ├── seo-local.md            # GBP signals, NAP, reviews
    ├── seo-maps.md             # Geo-grid, competitor radius mapping
    ├── seo-backlinks.md        # Moz, Bing Webmaster, Common Crawl
    ├── seo-cluster.md          # Semantic clustering analysis
    ├── seo-sxo.md              # Page-type, user stories, personas
    ├── seo-drift.md            # Baseline comparison, regression detection
    ├── seo-ecommerce.md        # Product schema, marketplace intelligence
    ├── seo-google.md           # GSC, PSI, CrUX, GA4 analyst
    ├── seo-flow.md             # FLOW framework prompt selection
    ├── seo-dataforseo.md       # DataForSEO MCP mirror
    └── seo-image-gen.md        # Banana MCP mirror
```

## Component Types

### Skills

Skills are markdown files with YAML frontmatter that define capabilities and instructions.

**SKILL.md Format:**
```yaml
---
name: skill-name
description: >
  When to use this skill. Include activation keywords
  and concrete use cases.
---

# Skill Title

Instructions and documentation...
```

### Subagents

Subagents are specialized workers that can be delegated tasks. They have their own context and tools.

**Agent Format:**
```yaml
---
name: agent-name
description: What this agent does.
tools: Read, Bash, Write, Glob, Grep
---

Instructions for the agent...
```

### Reference Files

Reference files contain static data loaded on-demand to avoid bloating the main skill.

## Orchestration Flow

### Full Audit (`/seo audit`)

```
User request
    │
    ▼
┌──────────────────┐
│   seo            │  Main orchestrator (skills/seo/SKILL.md)
└────────┬─────────┘
         │  Detects business type and signals
         │  Spawns subagents in parallel
         │
    ┌────┴────┬────────┬────────┬────────┬────────┬────────┐
    ▼         ▼        ▼        ▼        ▼        ▼        ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│tech   │ │content│ │schema │ │sitemap│ │perf   │ │visual │ │geo    │
└───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘
    │         │         │         │         │         │         │
    └─────────┴─────────┴────┬────┴─────────┴─────────┴─────────┘
                             │
                             │  Conditional spawns:
                             │  - seo-google     (Google API creds detected)
                             │  - seo-local      (local business detected)
                             │  - seo-maps       (local + DataForSEO MCP)
                             │  - seo-backlinks  (Moz/Bing/CC available)
                             │  - seo-cluster    (content strategy signals)
                             │  - seo-sxo        (always in full audits)
                             │  - seo-drift      (baseline exists for URL)
                             │  - seo-ecommerce  (e-commerce detected)
                             ▼
                    ┌────────────────┐
                    │  Aggregate     │
                    │  Results       │
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Generate      │
                    │  Health Score  │
                    │  + Action Plan │
                    └────────────────┘
```

### Individual Command

```
User Request (e.g., /seo page)
    │
    ▼
┌─────────────────┐
│   seo       │  ← Routes to sub-skill
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   seo-page      │  ← Sub-skill handles directly
│   (SKILL.md)    │
└─────────────────┘
```

## Design Principles

### 1. Progressive Disclosure

- Main SKILL.md stays under 500 lines (per the development rules)
- Reference files loaded on-demand
- Detailed instructions in sub-skills

### 2. Parallel Processing

- Subagents run concurrently during audits
- Independent analyses don't block each other
- Results aggregated after all complete

### 3. Quality Gates

- Built-in thresholds prevent bad recommendations
- Location page limits (30 warning, 50 hard stop)
- Schema deprecation awareness
- FID → INP replacement enforced

### 4. Industry Awareness

- Templates for different business types
- Automatic detection from homepage signals
- Tailored recommendations per industry

## File Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Skill | `seo-{name}/SKILL.md` | `seo-audit/SKILL.md` |
| Agent | `seo-{name}.md` | `seo-technical.md` |
| Reference | `{topic}.md` | `cwv-thresholds.md` |
| Script | `{action}_{target}.py` | `fetch_page.py` |
| Template | `{industry}.md` | `saas.md` |

## Extension Points

### Adding a New Sub-Skill

1. Create `skills/seo-newskill/SKILL.md`
2. Add YAML frontmatter with name and description
3. Write skill instructions
4. Update main `skills/seo/SKILL.md` to route to new skill

### Adding a New Subagent

1. Create `agents/seo-newagent.md`
2. Add YAML frontmatter with name, description, tools
3. Write agent instructions
4. Reference from relevant skills

### Adding a New Reference File

1. Create file in appropriate `references/` directory
2. Reference in skill with load-on-demand instruction

## Extensions

Extensions are opt-in add-ons that integrate external data sources via MCP servers. They live in `extensions/<name>/` and ship their own install / uninstall scripts.

```
extensions/
├── dataforseo/               # DataForSEO MCP integration
│   ├── README.md
│   ├── install.sh
│   ├── install.ps1
│   ├── uninstall.sh
│   ├── uninstall.ps1
│   ├── field-config.json
│   ├── skills/seo-dataforseo/SKILL.md
│   ├── agents/seo-dataforseo.md
│   └── docs/DATAFORSEO-SETUP.md
│
├── banana/                   # AI image generation via Gemini
│   ├── README.md
│   ├── install.sh
│   ├── uninstall.sh
│   ├── skills/seo-image-gen/SKILL.md
│   ├── agents/seo-image-gen.md
│   ├── scripts/              # Python fallback scripts (stdlib only)
│   ├── references/           # 7 reference files (prompt engineering, models, presets)
│   └── docs/BANANA-SETUP.md
│
├── firecrawl/                # Firecrawl MCP for full-site crawling
│   ├── README.md
│   ├── install.sh
│   ├── install.ps1
│   ├── uninstall.sh
│   ├── uninstall.ps1
│   └── skills/seo-firecrawl/SKILL.md
│
├── ahrefs/                   # Ahrefs MCP for backlinks + organic data
│   ├── install.sh
│   ├── install.ps1
│   ├── uninstall.sh
│   ├── skills/seo-ahrefs/SKILL.md
│   └── docs/AHREFS-SETUP.md
│
├── seranking/                # SE Ranking AI Share-of-Voice tracking
│   ├── install.sh
│   ├── install.ps1
│   ├── uninstall.sh
│   ├── skills/seo-seranking/SKILL.md
│   └── docs/SERANKING-SETUP.md
│
├── profound/                 # Profound LLM citation tracking
│   ├── install.sh
│   ├── install.ps1
│   ├── uninstall.sh
│   ├── skills/seo-profound/SKILL.md
│   └── docs/PROFOUND-SETUP.md
│
├── bing-webmaster/           # Bing Webmaster Tools + IndexNow
│   ├── install.sh
│   ├── install.ps1
│   ├── uninstall.sh
│   ├── skills/seo-bing/SKILL.md
│   └── docs/BING-WEBMASTER-SETUP.md
│
└── unlighthouse/             # Multi-page Lighthouse runner (local)
    ├── install.sh
    ├── install.ps1
    ├── uninstall.sh
    ├── skills/seo-unlighthouse/SKILL.md
    └── docs/UNLIGHTHOUSE-SETUP.md
```

### Available Extensions

| Extension | Package (pinned) | What it adds |
|-----------|------------------|--------------|
| **DataForSEO** | `dataforseo-mcp-server@2.8.10` | Live SERP data, keyword research, backlinks, on-page analysis, business listings, AI visibility, LLM mention tracking |
| **Banana Image Gen** | `@ycse/nanobanana-mcp@1.1.1` | AI image generation for SEO assets via Gemini (OG images, hero images, product photos, infographics, batch) |
| **Firecrawl** | `firecrawl-mcp@3.11.0` | Full-site crawling and URL discovery for audits |
| **Ahrefs** | `@ahrefs/mcp@0.0.11` | Backlinks and organic keyword data via the official `@ahrefs/mcp` server |
| **SE Ranking** | SE Ranking API | AI Share-of-Voice across ChatGPT, Gemini, Perplexity, AI Overviews, and AI Mode |
| **Profound** | Profound API | LLM citation tracking with time-series data |
| **Bing Webmaster** | Bing Webmaster Tools API | Bing Webmaster Tools + IndexNow URL submission |
| **Unlighthouse** | `unlighthouse@0.13.5` | Multi-page Lighthouse runner, runs locally |

### Extension Convention

1. Self-contained in `extensions/<name>/`
2. Own `install.sh` (and `install.ps1` where Windows is supported) that copies files and configures MCP (where applicable)
3. Own `uninstall.sh` (and `uninstall.ps1` where present) that reverses installation
4. Installs the sub-skill mirror to the plugin's skill directory
5. Installs the sub-agent mirror to the plugin's agent directory (extensions that ship one; lighter extensions are skill-only)
6. Merges MCP config into `~/.claude/settings.json` non-destructively
7. MCP server versions are pinned (`@<version>`) for supply-chain stability
