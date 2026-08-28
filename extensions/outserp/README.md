# Outserp Extension for Claude SEO

AI answer-engine visibility measurement and a content production engine,
powered by [Outserp](https://outserp.ai). Audits how a domain actually
appears in ChatGPT and Perplexity answers (head-to-head vs. competitors),
tracks citations and mentions over time, scans template defects and SEO
drift, and can generate, optimize, and publish articles.

> Disclosure: this extension is contributed and maintained by the Outserp
> team. Outserp is a commercial platform; audits and generation spend
> account credits.

## Prerequisites

- [Claude SEO](https://github.com/AgriciDaniel/claude-seo) installed
- An Outserp account ([sign up](https://outserp.ai))

## Installation

### macOS / Linux

```bash
./extensions/outserp/install.sh
```

### Windows (PowerShell)

```powershell
.\extensions\outserp\install.ps1
```

The installer registers the remote MCP server
(`https://mcp.outserp.ai/mcp`). Authentication is OAuth: run `/mcp` in a
new Claude Code session and sign in. An API key for the REST fallback
(https://outserp.ai/api-docs, base URL `https://outserp.ai/api/v1`) can
be provided optionally at install time.

## Commands

| Command | Purpose |
|---------|---------|
| `/seo outserp whoami` | Account, plan, credit balance, projects |
| `/seo outserp audit <domain>` | AI-search visibility audit: real engine answers, head-to-head competitor counts, gaps, briefs |
| `/seo outserp visibility <brand>` | Mention rate per engine + trend |
| `/seo outserp citations <brand>` | URLs the engines actually cite |
| `/seo outserp mentions <brand>` | Raw brand/competitor mentions per prompt |
| `/seo outserp defects <domain>` | Template-defect scanner + SEO drift |
| `/seo outserp context [update]` | Shared project memory + research log |
| `/seo outserp write <keyword>` | Generate an article draft |
| `/seo outserp optimize <article>` | Re-optimize an existing article |
| `/seo outserp publish <article>` | Publish to the connected CMS |

## Integration with Claude SEO

- **`/seo geo`** scores on-page citability locally; Outserp reports the
  actual engine answers and citations for the same pages.
- **`/seo profound`** / **`/seo seranking`**: triangulate Outserp's
  measurements against independent vendors.
- **`/seo drift`** keeps local baselines; `/seo outserp defects` adds the
  hosted, scheduled template-defect + drift view.
- **`/seo content`**: run E-E-A-T review on drafts before
  `/seo outserp publish`.

## Cost

Read-only calls (whoami, summaries, citations, mentions, context) are
cheap or free; audits, generation, optimization, and publishing spend
account credits. The skill calls `whoami` first and confirms before any
credit-spending operation. Pricing: https://outserp.ai/pricing.

## Troubleshooting

**MCP not connecting?**
- Check: `cat ~/.claude/settings.json | python3 -m json.tool | grep outserp`
- Re-run `/mcp` in Claude Code to complete OAuth
- Manual config: see [OUTSERP-SETUP.md](docs/OUTSERP-SETUP.md)

**REST 404s?**
- The base URL is `https://outserp.ai/api/v1` — do not repeat `/api/v1`
  in tool paths.

**Insufficient credits?**
- Check `/seo outserp whoami`, top up at https://outserp.ai

## Uninstall

```bash
./extensions/outserp/uninstall.sh
```

## Links

- [Outserp](https://outserp.ai)
- [API docs](https://outserp.ai/api-docs)
- [Claude SEO](https://github.com/AgriciDaniel/claude-seo)
