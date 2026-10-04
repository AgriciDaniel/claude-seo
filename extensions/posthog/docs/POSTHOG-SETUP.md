# PostHog extension setup

This extension lets claude-seo use the PostHog MCP server as an analytics source,
the same way the Matomo extension uses the Matomo Reporting API. It stores no
credentials: authentication belongs to the MCP server.

## 1. Install

```bash
./extensions/posthog/install.sh
```

Copies the `seo-posthog` skill to `~/.claude/skills/seo-posthog/` and the agent to
`~/.claude/agents/seo-posthog.md`. It then offers to register the MCP server with
`claude mcp add`.

## 2. Connect the MCP server

Manual equivalent:

```bash
claude mcp add --transport http posthog https://mcp.posthog.com/mcp
```

Then run `/mcp` inside Claude Code and authenticate. For EU Cloud or self-hosted
PostHog, use the matching MCP URL from the PostHog docs. Check the PostHog MCP
documentation for the current URL and auth options.

The server exposes one tool, `exec`, so it appears as `mcp__PostHog__exec` (or
`mcp__posthog__exec` when registered in lowercase). The agent's `tools`
allowlist accepts both spellings. Queries go through
`call execute-sql {"query": "..."}`.

## 3. Use

```
/seo posthog check
/seo posthog organic
/seo posthog referrers
```

During `/seo audit`, the agent is spawned when PostHog MCP tools are available.

## Limits

- Organic search uses `session.$channel_type = 'Organic Search'` (fallback:
  `$referring_domain`), so numbers will not match GA4 or Matomo exactly
- No organic keyword data (use Search Console via `seo-google`)
- Requires `$pageview` events with referrer properties captured
- Queries run as HogQL via `execute-sql`. Sub-tool names can change between
  PostHog MCP versions, so the agent runs `info` before each new tool

## Uninstall

```bash
./extensions/posthog/uninstall.sh
```
