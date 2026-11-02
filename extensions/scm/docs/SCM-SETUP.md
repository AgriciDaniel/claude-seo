# SEO Content Machine Setup Guide

## 1. Install SEO Content Machine

1. Start a [14-day free trial](https://seocontentmachine.com/members/signup/trial?utm_source=claude-seo&utm_medium=extension&utm_campaign=claude-seo&utm_content=setup), no card needed.
2. Download and open the app (Windows, Mac or Linux) and log in.
3. Set up an AI service in SCM's settings. SCM writes pages with it.

SCM's MCP server runs inside the app at `http://localhost:8008/mcp`. It needs no API key while SCM's Api secret key (Settings > App) is blank, which is the default.

## 2. Run the Installer

```bash
./extensions/scm/install.sh
```

It installs the skill and adds the MCP server.

## 3. Manual MCP Configuration

If the installer fails, run:

```bash
claude mcp add scm -- npx -y seo-content-machine-mcp@1.1.1
```

or add this to `~/.claude.json`:

```json
{
  "mcpServers": {
    "scm": {
      "command": "npx",
      "args": ["-y", "seo-content-machine-mcp@1.1.1"]
    }
  }
}
```

If SCM's API is not on port 8008, add `"env": {"SCM_API_URL": "http://localhost:<port>"}`.

## 4. Verify Installation

Open SCM, start Claude Code and try:

```
/seo scm status
```

Claude should list your SCM tasks. If it says the tools are not available, check that SCM is open, then restart Claude Code to reload MCP servers.

## 5. A First Cluster

```
/seo cluster plan "emergency plumber"
/seo scm execute
```

Claude shows the page list and the token estimate and asks before it writes. The drafts appear in the SEO Workspace named after the seed keyword.
