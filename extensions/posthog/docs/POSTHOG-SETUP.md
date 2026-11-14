# PostHog extension setup

This extension lets claude-seo use the PostHog MCP server as an analytics source,
the same way the Matomo extension uses the Matomo Reporting API. It stores no
credentials: authentication belongs to the MCP server.

> **Use read-only access.** The PostHog MCP `exec` tool can read data and also
> create, update and delete PostHog objects (insights, dashboards, feature
> flags and more). claude-seo only ever needs to read, and its read-only rule is
> an instruction to the agent, not a technical limit. Authenticate the MCP
> server with a read-only scoped personal API key, or sign in as a member whose
> access to the project is read-only, so a write cannot succeed.

## 1. Install

```bash
./extensions/posthog/install.sh
```

On Windows, run `.\extensions\posthog\install.ps1` in PowerShell.

The `seo-posthog` skill and agent ship with the claude-seo plugin, so on a
plugin install the installer copies nothing; run it from the plugin or repository
folder. On a manual install (`~/.claude/skills/seo`) it copies the skill to
`~/.claude/skills/seo-posthog/` and the agent to `~/.claude/agents/seo-posthog.md`.
In both cases it then offers to register the MCP server with `claude mcp add`.

## 2. Connect the MCP server

Manual equivalent:

```bash
claude mcp add --transport http posthog https://mcp.posthog.com/mcp
```

Then run `/mcp` inside Claude Code and authenticate, with the read-only login
or key recommended above. For EU Cloud or self-hosted PostHog, use the matching
MCP URL from the PostHog docs. Check the PostHog MCP documentation for the
current URL, auth options and how to scope a key to read-only.

The server exposes one tool, `exec`. Registered as `posthog` (the command
above, and what the installer runs) it appears as `mcp__posthog__exec`;
registered as `PostHog` it appears as `mcp__PostHog__exec`. The agent's `tools`
allowlist and the audit orchestrator accept both spellings. Queries go through
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

On a manual install this removes the copied skill and agent. On a plugin install
both stay, because the plugin provides them. The MCP server registration is not
touched; remove it with `claude mcp remove posthog`.
