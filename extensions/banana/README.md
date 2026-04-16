# Banana Image Generation Extension for Claude SEO

Generate production-ready SEO images using AI: OG/social previews, blog heroes,
product photography, infographics, and more. Powered by Google Gemini via the
banana Creative Director pipeline.

## Prerequisites

> This extension wraps [Claude Banana](https://github.com/AgriciDaniel/banana-claude)
> for SEO-specific use cases. Install the standalone skill for general-purpose image generation.

- **Claude SEO** installed (`~/.claude/skills/seo/`)
- **Node.js 18+** with npx
- **Google AI API key** (free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey))
- **ImageMagick** (optional, for post-processing)

## Installation

```bash
./extensions/banana/install.sh
```

The installer will:
1. Verify Claude SEO is installed
2. Prompt for your Google AI API key (if nanobanana-mcp not already configured)
3. Install the `seo-image-gen` skill and agent
4. Configure the MCP server in `~/.claude/settings.json`

## Commands

| Command | What it does |
|---------|-------------|
| `/seo image-gen og <description>` | OG/social preview image (1200x630 feel) |
| `/seo image-gen hero <description>` | Blog hero image (widescreen, dramatic) |
| `/seo image-gen product <description>` | Product photography (clean, white BG) |
| `/seo image-gen infographic <description>` | Infographic visual (vertical, data-heavy) |
| `/seo image-gen custom <description>` | Custom with full Creative Director pipeline |
| `/seo image-gen batch <description> [N]` | Generate N variations (default: 3) |

## Use Case Defaults

| Use Case | Aspect Ratio | Resolution | Domain Mode | Cost |
|----------|-------------|------------|-------------|------|
| OG/Social Preview | 16:9 | 1K | Product/UI | ~$0.04 |
| Blog Hero | 16:9 | 2K | Cinema/Editorial | ~$0.08 |
| Product Photo | 4:3 | 2K | Product | ~$0.08 |
| Infographic | 2:3 | 4K | Infographic | ~$0.16 |
| Social Square | 1:1 | 1K | UI/Web | ~$0.04 |
| Favicon/Icon | 1:1 | 512 | Logo | ~$0.02 |

## How It Works

Claude acts as a **Creative Director**. It never passes raw text to the API.
Instead, it analyzes your intent, selects the optimal domain mode, and constructs
an optimized prompt using a proven 6-component Reasoning Brief system:

1. **Subject** (30%):Physical specificity and micro-details
2. **Style** (25%):Camera specs, film stock, brand references
3. **Context** (15%):Location, time, weather, supporting elements
4. **Action** (10%):Pose, gesture, movement, state
5. **Composition** (10%):Shot type, framing, focal length
6. **Lighting** (10%):Direction, quality, color temperature

## Post-Generation SEO Checklist

After every generation, Claude provides:
- Alt text suggestion (keyword-rich, descriptive)
- SEO-friendly file naming convention
- WebP conversion command
- ImageObject schema snippet
- OG meta tag markup (for social previews)

## Audit Integration

During `/seo audit`, the extension optionally spawns an image analysis agent that:
- Audits existing OG/social images across the site
- Identifies missing or low-quality images
- Creates a prioritized generation plan with prompt suggestions
- Estimates total cost for the generation plan

The agent never auto-generates images. It produces a plan for your review.

## Uninstallation

```bash
./extensions/banana/uninstall.sh
```

This removes the skill and agent. If you also use [Claude Banana](https://github.com/AgriciDaniel/banana-claude),
the MCP server config is preserved.

## Troubleshooting

See [docs/BANANA-SETUP.md](docs/BANANA-SETUP.md) for detailed setup instructions
and common issues.
