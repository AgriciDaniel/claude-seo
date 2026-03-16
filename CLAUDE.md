# Claude SEO — Universal SEO Analysis Skill

## Project Overview

This repository contains **Claude SEO**, a Tier 4 Claude Code skill for comprehensive
SEO analysis across all industries. It follows the Agent Skills open standard and the
3-layer architecture (directive, orchestration, execution). 13 sub-skills, 7 parallel
subagents, and an extensible reference system cover technical SEO, content quality,
schema markup, image optimization, sitemap architecture, and AI search optimization.

## Architecture

```
claude-seo/
  CLAUDE.md                          # Project instructions (this file)
  .claude-plugin/plugin.json         # Plugin manifest v1.5.0
  seo/                               # Main orchestrator skill
    SKILL.md                         # Entry point, routing table, core rules
    references/                      # On-demand knowledge files
  scripts/                           # Python execution scripts
  hooks/                             # Quality gate hooks
  schema/                            # Schema.org JSON-LD templates
  skills/                            # 12 specialized sub-skills
    seo-audit/SKILL.md              # Full site audit with parallel agents
    seo-page/SKILL.md              # Deep single-page analysis
    seo-technical/SKILL.md         # Technical SEO (9 categories)
    seo-content/SKILL.md           # E-E-A-T and content quality
    seo-schema/SKILL.md            # Schema.org markup detection/generation
    seo-sitemap/SKILL.md           # XML sitemap analysis/generation
    seo-images/SKILL.md            # Image optimization analysis
    seo-geo/SKILL.md               # AI search / GEO optimization
    seo-plan/SKILL.md              # Strategic SEO planning
    seo-programmatic/SKILL.md      # Programmatic SEO at scale
    seo-competitor-pages/SKILL.md  # Competitor comparison pages
    seo-hreflang/SKILL.md         # International SEO / hreflang
  agents/                            # 7 parallel subagents
    seo-technical.md               # Crawlability, indexability, security
    seo-content.md                 # E-E-A-T, readability, thin content
    seo-schema.md                  # Structured data validation
    seo-sitemap.md                 # Sitemap quality gates
    seo-performance.md             # Core Web Vitals, page speed
    seo-visual.md                  # Screenshots, mobile rendering
    seo-geo.md                     # AI crawler access, GEO, citability
  extensions/                          # Optional add-on capabilities
    dataforseo/                    # Live SEO data via DataForSEO MCP
    banana/                        # AI image generation via Gemini MCP
  docs/                              # Extended documentation
    ARCHITECTURE.md                # System design overview
    COMMANDS.md                    # Full command reference
    INSTALLATION.md                # Install guide
    MCP-INTEGRATION.md            # DataForSEO MCP setup
    TROUBLESHOOTING.md            # Common issues
```

## Commands

| Command | Purpose |
|---------|---------|
| `/seo audit <url>` | Full site audit with 7 parallel subagents |
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
| `/seo hreflang <url>` | International SEO / hreflang audit |
| `/seo image-gen [use-case] <desc>` | AI image generation for SEO assets (extension) |

## Development Rules

- Keep SKILL.md files under 500 lines / 5000 tokens
- Reference files should be focused and under 200 lines
- Scripts must have docstrings, CLI interface, and JSON output
- Follow kebab-case naming for all skill directories
- Agents invoked via Task tool with `context: fork`, never via Bash
- Python dependencies install into `~/.claude/skills/seo/.venv/`
- Test with `python -m pytest tests/` after changes (if applicable)

## Key Principles

1. **Progressive Disclosure**: Metadata always loaded, instructions on activation, resources on demand
2. **Industry Detection**: Auto-detect SaaS, e-commerce, local, publisher, agency
3. **Parallel Execution**: Full audits spawn 7 subagents simultaneously
4. **Extension System**: DataForSEO MCP for live data, Banana MCP for AI image generation
