# Creaitor extension setup

Registers Creaitor's remote MCP server (`https://app.creaitor.ai/api/v2/mcp`)
with Claude Code as `creaitor-geo`, so the `seo-creaitor` skill can read live
AI-search visibility, LLM citations, audits, and recommendations for the domains
configured in your Creaitor workspace.

## 1. Create a token

At https://app.creaitor.ai/user/api-tokens, create a personal access token with
the abilities you need:

| Ability | Grants |
|---|---|
| `geo:read` | Every non-export read command: overview, visibility, citations, sources, prompts, audits, recommendations, competitors, health |
| `geo:write` | Adding/editing tracked prompts, updating recommendation status |
| `geo:execute` | `audit --run`, `prompts --run`, `llms-txt`, and citations `--export` (execute-tier API operations) |

`geo:read` alone is enough for every default read command. Grant
`geo:execute` only if you want Claude to trigger runs, generation, or exports.

## 2. Install

Quit all running Claude Code sessions first so they cannot overwrite
`~/.claude.json` on exit. Then run:

```bash
./extensions/creaitor/install.sh        # macOS / Linux
.\extensions\creaitor\install.ps1       # Windows PowerShell
```

The installer:

1. Verifies Python 3 is on `PATH` and that the claude-seo base plugin is installed.
2. Prompts for the token with the input hidden — it is never echoed, never
   written to your shell history, and never printed back.
3. Copies `skills/seo-creaitor/SKILL.md` into `~/.claude/skills/seo-creaitor/`.
4. Merges this entry into `~/.claude.json` (the Claude user config, where remote
   MCP servers live — not `settings.json`):

```json
{
  "mcpServers": {
    "creaitor-geo": {
      "type": "http",
      "url": "https://app.creaitor.ai/api/v2/mcp",
      "headers": {
        "Authorization": "Bearer <your token>",
        "Content-Type": "application/json"
      }
    }
  }
}
```

The merge is atomic (temp file + `os.replace`) and the result is `chmod 0600` on
Unix, matching how claude-seo stores OAuth tokens. Everything else in
`~/.claude.json` is preserved; if the file is not readable as a JSON object the
installer aborts rather than replacing it.

### Self-hosted / staging endpoint

```bash
CREAITOR_MCP_URL=https://staging.example.com/api/v2/mcp ./extensions/creaitor/install.sh
```

The same variable works for `install.ps1` (`$env:CREAITOR_MCP_URL`).

## 3. Verify

Open a **new** Claude Code session (MCP servers are read at startup) and run:

```
/seo creaitor domains
```

You should get the domains configured in your Creaitor workspace. Then:

```
/seo creaitor overview https://example.com
```

## Rotate the token

Re-run the installer. It replaces only the `creaitor-geo` entry, leaving the
rest of `~/.claude.json` intact. Revoke the old token in the Creaitor app.

## Uninstall

```bash
./extensions/creaitor/uninstall.sh
```

Removes `~/.claude/skills/seo-creaitor/` and the `mcpServers.creaitor-geo` key.
No other config is touched. Revoke the token in the Creaitor app afterwards.

## Cost model

Read commands (`geo:read`) return stored data and do not consume run quota.
`audit --run`, `prompts --run`, and `llms-txt` execute quota-consuming work;
citations `--export` is also execute-tier. The skill only calls these on the
matching explicit command, never as a follow-up to a read command or as part of
`/seo audit`. MCP can queue `llms-txt` generation but cannot poll its status;
retrieve the completed content in Creaitor.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/seo creaitor` says the extension is not installed | Session started before the config was written | Restart Claude Code; MCP servers are loaded at startup |
| 401 from every command | Token revoked, expired, or mistyped | Mint a new token and re-run the installer |
| 403 on one command only | Token lacks that ability | Re-mint with `geo:write` / `geo:execute` as needed |
| "domain not configured in Creaitor" | The URL's host is not in the workspace | Add the domain in the Creaitor app; the skill never creates domains |
| Installer aborts with "not valid JSON" | `~/.claude.json` is corrupted | Fix or restore the file; the installer will not overwrite it |
