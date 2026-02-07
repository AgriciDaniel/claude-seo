# Architecture

## Overview

Claude SEO follows Anthropic's official Claude Code skill specification with a modular, multi-skill architecture.

## Directory Structure

```
~/.claude/
├── skills/
│   ├── seo/              # Main orchestrator skill
│   │   ├── SKILL.md          # Entry point with routing logic
│   │   └── references/       # On-demand reference files
│   │       ├── cwv-thresholds.md
│   │       ├── schema-types.md
│   │       ├── eeat-framework.md
│   │       └── quality-gates.md
│   │
│   ├── seo-audit/            # Full site audit
│   ├── seo-page/             # Single page analysis
│   ├── seo-technical/        # Technical SEO
│   ├── seo-content/          # E-E-A-T analysis
│   ├── seo-schema/           # Schema markup
│   ├── seo-geo/              # AI search optimization
│   ├── seo-images/           # Image optimization
│   ├── seo-sitemap/          # Sitemap analysis/generation
│   └── seo-plan/             # Strategic planning
│       └── assets/           # Industry templates
│
└── agents/
    ├── seo-technical.md      # Technical SEO specialist
    ├── seo-content.md        # Content quality reviewer
    ├── seo-schema.md         # Schema markup expert
    ├── seo-sitemap.md        # Sitemap architect
    ├── seo-performance.md    # Performance analyzer
    └── seo-visual.md         # Visual analyzer
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
User Request
    │
    ▼
┌─────────────────┐
│   seo       │  ← Main orchestrator
│   (SKILL.md)    │
└────────┬────────┘
         │
         │  Detects business type
         │  Spawns subagents in parallel
         │
    ┌────┴────┬────────┬────────┬────────┬────────┐
    ▼         ▼        ▼        ▼        ▼        ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│tech   │ │content│ │schema │ │sitemap│ │perf   │ │visual │
│agent  │ │agent  │ │agent  │ │agent  │ │agent  │ │agent  │
└───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘
    │         │        │        │        │        │
    └─────────┴────────┴────┬───┴────────┴────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  Aggregate    │
                    │  Results      │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  Generate     │
                    │  Report       │
                    └───────────────┘
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

- Main SKILL.md is concise (<200 lines)
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
4. Update main `seo/SKILL.md` to route to new skill

### Adding a New Subagent

1. Create `agents/seo-newagent.md`
2. Add YAML frontmatter with name, description, tools
3. Write agent instructions
4. Reference from relevant skills

### Adding a New Reference File

1. Create file in appropriate `references/` directory
2. Reference in skill with load-on-demand instruction
