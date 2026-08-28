# Outserp extension setup

Outserp (https://outserp.ai) measures how a brand actually appears in AI
answer engines — live ChatGPT / Perplexity answers, head-to-head
competitor appearance counts, citations over time — and carries a
production path (generate → optimize → publish articles). The hosted,
account-backed complement to claude-seo's local `seo-geo` analysis.

## Sign up

Create an account at https://outserp.ai and add your domain as a project.
Audits and content generation spend account credits.

## Install

```bash
./extensions/outserp/install.sh        # Linux / macOS
.\extensions\outserp\install.ps1       # Windows
```

Registers the remote MCP server `outserp` → `https://mcp.outserp.ai/mcp`
in `~/.claude/settings.json` (written atomically, mode 0o600). No
credential is stored unless you opt into the API-key fallback.

Equivalent manual registration:

```bash
claude mcp add --transport http outserp https://mcp.outserp.ai/mcp
```

## OAuth flow

The server authenticates via OAuth. In a new Claude Code session run
`/mcp`, select `outserp`, and complete the browser sign-in. Verify with:

```
/seo outserp whoami
```

## API-key alternative (REST fallback)

If you prefer not to use the MCP server, generate an API key in your
Outserp account and re-run the installer (it prompts for the key, stored
as `env.OUTSERP_API_KEY`). REST docs: https://outserp.ai/api-docs.

- Base URL: `https://outserp.ai/api/v1`
- Paths are relative to that base — do **not** repeat `/api/v1` in the
  path (`/api/v1/audit`, never `/api/v1/api/v1/audit`).

## Uninstall

```bash
./extensions/outserp/uninstall.sh
```

## When to use Outserp vs. Profound / SE Ranking

| Use Outserp | Use Profound / SE Ranking |
|---|---|
| Full audit: real engine answers + head-to-head competitor counts + gaps + briefs | Pure citation-rate time-series (Profound) or 5-platform SoV sampling (SE Ranking) |
| Closing the loop: generate / optimize / publish content from the same audit | Measurement only |
| Template-defect scanning + hosted SEO drift | Local drift via `/seo drift` |

The three are complementary; install what your workflow needs.
