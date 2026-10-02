---
name: seo-posthog
description: PostHog MCP extension. PostHog analytics as a GA4 alternative or complement. Organic traffic, landing pages, device / country breakdowns, referrers, via the PostHog MCP server. Triggers on "PostHog", "posthog analytics", "GA4 alternative", "product analytics SEO".
metadata:
  version: "2.4.1"
compatibility: "Requires the PostHog MCP server (https://mcp.posthog.com/mcp) connected to Claude Code. No local credentials are stored by this extension. Run extensions/posthog/install.sh to install the skill and agent."
---

# seo-posthog

Use PostHog as a GA4 alternative or complement when the user already tracks
their site with PostHog. All data comes from the PostHog MCP server; this
extension ships no script and stores no token.

## Prerequisites

- Run `extensions/posthog/install.sh` (it can also register the MCP server).
- The PostHog MCP server connected and authenticated (`/mcp` in Claude Code).
- The site sends `$pageview` events to PostHog (web snippet or SDK).

## Routing

| Command | What it does |
|---|---|
| `/seo posthog check` | Confirm the PostHog MCP is connected and the project has `$pageview` events |
| `/seo posthog organic` | Per-day organic search visits |
| `/seo posthog top-pages` | Top organic landing pages |
| `/seo posthog device` | Organic traffic by device type |
| `/seo posthog country` | Organic traffic by country |
| `/seo posthog referrers` | Referrer / channel breakdown |

Each command delegates to the `seo-posthog` agent, which runs HogQL queries
through the MCP `exec` tool (`call execute-sql`). Options: days (default 28) and limit (default 50).

## When this skill applies

- The user says "PostHog" or wants analytics data without GA4
- The user has the PostHog MCP connected and asks for organic traffic context
- For Search Console, CrUX, indexing, and search queries, route to `seo-google`.
  PostHog has no keyword data
- For AI Overview / GEO work, route to `seo-geo`

## Cross-skill delegation

During `/seo audit`, the orchestrator spawns the `seo-posthog` agent when
the PostHog MCP `exec` tool (`mcp__PostHog__exec`) is available. It can run alongside
`seo-google` and `seo-matomo`.

## Error Handling

- No PostHog MCP tools: tell the user to connect the server (see
  `extensions/posthog/docs/POSTHOG-SETUP.md`). Do not invent data
- Query errors: surface verbatim
- Empty results: verify project, window, and that `$referring_domain` is
  captured before reporting zero organic traffic

## Output Formatting

- Tables for time-series, device, and country data
- Critical / High / Medium / Low priority for cross-skill actions
- Label the data source "PostHog MCP (live)"
