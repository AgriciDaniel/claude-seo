# Ahrefs extension setup

Wires the official [`@ahrefs/mcp@0.0.11`](https://www.npmjs.com/package/@ahrefs/mcp)
server into your Claude Code session so the `seo-ahrefs` skill can call
live Ahrefs data.

## Install

```bash
./extensions/ahrefs/install.sh        # Linux / macOS
.\extensions\ahrefs\install.ps1       # Windows PowerShell
```

The installer:

1. Verifies Python 3 + Node 18+ are on `$PATH`.
2. Prompts for your Ahrefs API token (input is hidden).
3. Pre-warms the `@ahrefs/mcp@0.0.11` npm package via `npx --yes` so the first
   MCP call doesn't spend 10+ seconds downloading.
4. Copies `skills/seo-ahrefs/SKILL.md` into `~/.claude/skills/seo-ahrefs/`.
5. Atomically writes `mcpServers.ahrefs` into `~/.claude/settings.json`
   with your token in the `env` block. The settings file is `chmod 0o600`
   after the merge (same hardening as the OAuth token).

## Verify

Open a new Claude Code session and ask:

```
/seo ahrefs metrics https://example.com
```

If you see "Ahrefs MCP not connected", the npm package is not yet cached.
Re-run the installer to pre-warm or run `npx --yes --package=@ahrefs/mcp@0.0.11 mcp --help` manually.

## Rotate token

```bash
./extensions/ahrefs/install.sh   # re-runs the prompt; overwrites the env entry
```

The Python merge script is idempotent — re-running only replaces the
`mcpServers.ahrefs.env.AHREFS_API_TOKEN` value, leaving the rest of
`settings.json` intact.

## Uninstall

```bash
./extensions/ahrefs/uninstall.sh    # removes the skill + clears the MCP entry
```

## Cost model

Ahrefs charges per "unit". A unit covers most read endpoints (domain
metrics, backlink data) at 1 unit each; bulk endpoints cost more. The
`scripts/dataforseo_costs.py` cost tracker shipped with claude-seo
generalises across vendors — see the DataForSEO extension's
`references/cost-tiers.md` for the budget-preset pattern to mirror when
wiring Ahrefs accounting.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Error: AHREFS_API_TOKEN is empty` | Installer didn't capture input | Re-run installer; type token at the prompt, then press Enter |
| `npx: package not found` | Offline run / fresh machine | Run with internet on; the installer pre-warms but the cache needs network |
| 401 from any `/seo ahrefs *` command | Token revoked / expired | Generate a new token at https://ahrefs.com/api and re-run the installer |
