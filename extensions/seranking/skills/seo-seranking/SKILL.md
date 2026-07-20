---
name: seo-seranking
description: SE Ranking AI visibility analyst (extension). Tracks AI Share-of-Voice across ChatGPT, Gemini, Perplexity, AI Overviews, and AI Mode in a single query.
metadata:
  version: "2.2.3"
compatibility: "Requires an SE Ranking API key (set SERANKING_API_KEY by running extensions/seranking/install.sh)."
---

# seo-seranking

Live AI visibility tracking via the SE Ranking REST API.

## Prerequisites

- Run `extensions/seranking/install.sh` (or `install.ps1`).
- An SE Ranking API key (https://seranking.com/api.html).
- Before any call, verify `SERANKING_API_KEY` is present in `~/.claude/settings.json` under `env.`. If absent, tell the user to run the installer.

## Routing

| Command | Purpose |
|---|---|
| `/seo seranking ai-visibility <brand>` | Share-of-voice for `brand` across ChatGPT, Gemini, Perplexity, AI Overviews, AI Mode |
| `/seo seranking serp <keyword>` | Top 100 organic positions + SERP features |
| `/seo seranking backlinks <url>` | Backlink profile (alternative vendor source to Ahrefs / DataForSEO) |
| `/seo seranking competitors <url>` | Top 10 organic competitors and shared-keyword gaps |

## AI Share-of-Voice scoring

SE Ranking samples each AI platform's responses for brand mentions
across a configurable prompt set. The scorer is the same logic used
by Profound / Peec AI but bundled into one MCP/API. Output fields:

- `chatgpt_sov`: % of sampled prompts where the brand appears in the response.
- `gemini_sov`: same, against Google Gemini.
- `perplexity_sov`: same, against Perplexity.
- `ai_overviews_sov`: brand citation rate inside Google AI Overviews.
- `ai_mode_sov`: brand citation rate inside Google AI Mode (US English first).

Report each as a percentage with a confidence note based on sample size.

## Cost guardrails

SE Ranking API uses unit accounting. Single AI visibility query is
~5 units (1 per platform). Use `scripts/dataforseo_costs.py` to log
spend across vendors.

## Cross-skill delegation

- For traditional backlinks + content audit, fall back to `seo-backlinks` / `seo-content`.
- For platform-specific deep-dives (ChatGPT only, Perplexity only), prefer the dedicated `seo-geo` skill which has Brand Mention Correlation guidance.
