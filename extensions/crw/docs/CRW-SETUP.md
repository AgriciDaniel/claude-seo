# fastCRW Setup Guide

## 1. Choose Your Endpoint

fastCRW is a Firecrawl-compatible web scraper. You can run it two ways:

- **Managed cloud:** sign up at [fastcrw.com](https://fastcrw.com), create an API
  key, and use the default base URL `https://fastcrw.com/api`.
- **Self-host (free, AGPL):** run the ~8MB Rust binary yourself and point the
  extension at it with `CRW_API_URL` (e.g. `http://localhost:3000`). Self-host
  engines may run without auth, so the key can be left empty.

## 2. Run the Installer

The installer handles everything automatically:

```bash
./extensions/crw/install.sh
```

It prompts for your `CRW_API_KEY` and configures the MCP server. For self-host:

```bash
CRW_API_URL=http://localhost:3000 ./extensions/crw/install.sh
```

## 3. Manual MCP Configuration

If the installer fails, add this to `~/.claude/settings.json` manually. fastCRW is
Firecrawl API-compatible, so the firecrawl-mcp client works once its base URL is
pointed at fastCRW:

```json
{
  "mcpServers": {
    "crw-mcp": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp@3.11.0"],
      "env": {
        "FIRECRAWL_API_URL": "https://fastcrw.com/api",
        "FIRECRAWL_API_KEY": "your-crw-api-key-here"
      }
    }
  }
}
```

For self-host without auth, drop `FIRECRAWL_API_KEY` and set `FIRECRAWL_API_URL`
to your engine.

## 4. Verify Installation

Start Claude Code and try:

```
/seo crw map https://example.com
```

You should see a list of discovered URLs. If you get a "tool not available" error,
restart Claude Code to reload MCP servers.

## 5. REST API Reference

fastCRW exposes a Firecrawl-compatible REST API under the base URL:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/scrape` | Single-page scrape |
| POST | `/v1/crawl` | Start a full-site crawl (async job) |
| GET | `/v1/crawl/{id}` | Poll crawl status / results |
| POST | `/v1/map` | Discover all URLs |
| POST | `/v1/search` | Search the web (cloud) |
| GET | `/health` | Health check |

Auth is `Authorization: Bearer <CRW_API_KEY>`. Responses use a `{ success, ... }`
envelope (on failure, `error` and `error_code` are set). Full docs:
https://fastcrw.com/docs/rest-api
