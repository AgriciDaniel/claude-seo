# Coupler.io extension setup

Wires the hosted [Coupler.io MCP server](https://github.com/coupler-io/coupler-io-mcp-server)
(`https://mcp.coupler.io/mcp`) into your Claude Code session so the
`seo-coupler` skill can read your Coupler.io data flows: Google Ads, Search
Console, GA4, Shopify, HubSpot, Stripe and other sources, side by side.

## Install

```bash
./extensions/coupler/install.sh        # Linux / macOS
.\extensions\coupler\install.ps1       # Windows PowerShell
```

The installer:

1. Verifies the claude-seo base plugin is installed (the `.sh` installer also
   verifies Python 3, used only for its `~/.claude.json` merge script; the
   `.ps1` installer merges natively with `ConvertTo-Json` and needs no Python).
2. Copies `skills/seo-coupler/SKILL.md` into `~/.claude/skills/seo-coupler/`.
3. Atomically writes `mcpServers.coupler-io` (`type: http`,
   `url: https://mcp.coupler.io/mcp`) into `~/.claude.json`. The `.sh`
   installer sets the file to `chmod 0o600` after the merge.

No API key is asked for or stored. The server uses OAuth, and Claude Code
keeps the sign-in.

## Connect your data

1. Create a Coupler.io account at https://www.coupler.io.
2. Create and run a data flow with **Claude** as the destination for each
   source you want to use. The MCP server only sees data flows sent to the
   connected AI tool.
   - `/seo coupler overlap`: a Google Ads **search terms** report and a
     Search Console report with the `query` dimension, over the same dates.
   - `/seo coupler revenue`: GA4 (sessions and key events by landing page
     and source) plus a store, CRM or billing source.
3. Open a new Claude Code session, run `/mcp`, select **coupler-io** and
   choose **Authenticate**. Sign in to Coupler.io in the browser.

## Verify

```
/seo coupler sources
```

It lists the connected data flows and which commands they support.

## Uninstall

```bash
./extensions/coupler/uninstall.sh    # removes the skill + clears the MCP entry
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Coupler.io tools not available | Session started before install, or not authenticated | Open a new session, run `/mcp`, select coupler-io, choose Authenticate |
| `list-dataflows` returns nothing | No data flow has Claude as its destination | Add Claude as the destination in Coupler.io and run the data flow |
| `get-data` fails on a data flow | The data flow has not run yet | Run it once in Coupler.io, then retry |
| 401 from the server | Sign-in expired or revoked | Run `/mcp` and authenticate again |
