# SE Ranking extension setup

SE Ranking's API exposes traditional SEO data (SERP, backlinks,
competitors) plus AI Share-of-Voice across 5 AI platforms.

## Install

```bash
./extensions/seranking/install.sh        # Linux / macOS
.\extensions\seranking\install.ps1       # Windows
```

The installer prompts for an API key (hidden input), copies
`SKILL.md` into `~/.claude/skills/seo-seranking/`, and writes
`env.SERANKING_API_KEY` into `~/.claude/settings.json` with mode 0o600.

## Get an API key

https://seranking.com/api.html — pricing is unit-based; the AI visibility
endpoint costs ~5 units per query (1 per platform).

## Verify

```
/seo seranking ai-visibility "Claude SEO"
```

Expected output: percentages per platform (ChatGPT, Gemini, Perplexity,
AI Overviews, AI Mode) with sample-size confidence notes.

## Rotate key

Re-run the installer; it overwrites `env.SERANKING_API_KEY` atomically
(tempfile + replace) without touching other settings.

## Uninstall

```bash
./extensions/seranking/uninstall.sh
```
