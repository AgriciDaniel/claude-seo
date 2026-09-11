# MentionAgent extension setup

MentionAgent (https://mentionagent.ai) is a link building outreach agent: it
finds sites worth a link, drafts the outreach, warms the sending inbox and
delivers. This extension runs the review half from Claude Code, through the
MentionAgent remote MCP server. It is the action side of `seo-backlinks`: that
skill measures the link profile, this one grows it.

## Install

```bash
./extensions/mentionagent/install.sh        # Linux / macOS
.\extensions\mentionagent\install.ps1       # Windows
```

You will be asked for a MentionAgent API key. Create one in the dashboard under
Settings, Agent access; it is shown once and looks like `ma_live_...`.

The installer writes a remote server entry to `~/.claude.json`:

```json
{
  "mcpServers": {
    "mentionagent": {
      "type": "http",
      "url": "https://mentionagent.ai/mcp",
      "headers": { "Authorization": "Bearer ma_live_..." }
    }
  }
}
```

No package is installed and nothing runs locally; the client speaks Streamable
HTTP to the URL directly. The skill is copied to `~/.claude/skills/seo-mentionagent/`.

## Verify

Open a new Claude Code session and run:

```
/seo mentionagent status
```

It calls `get_status` and lists the sites on the account with what is waiting.

## What the key can reach

The 20 published tools and nothing else: it cannot see mailbox credentials,
billing, domain transfer or account deletion. Two tools send email
(`approve_batch`, `send_reply`) and the skill will not call either until you
have seen the exact text and said yes. `send_reply` has no recipient field; the
address comes from the thread. Keys can be revoked from the dashboard at any
time.

Reading works on any account. Starting new prospecting runs needs an active
plan or trial; sending needs a paid plan.

## Uninstall

```bash
./extensions/mentionagent/uninstall.sh
```

Removes the skill folder and the `mentionagent` entry from `~/.claude.json`.

## Reference

- Tool list and limits: https://mentionagent.ai/mcp/
- Standalone Claude Code plugin (same server, no claude-seo required):
  https://github.com/BuildsbyMatt/mentionagent-claude-skill
