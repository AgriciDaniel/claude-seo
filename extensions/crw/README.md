# fastCRW Extension for Claude SEO

Full-site crawling, scraping, and site mapping powered by [fastCRW](https://fastcrw.com/) -- a Firecrawl-compatible web scraper in a single ~8MB Rust binary. Self-host (free, AGPL open core) or use the managed cloud. Enables comprehensive site-wide SEO analysis with JavaScript rendering support.

## Prerequisites

- [Claude SEO](https://github.com/AgriciDaniel/claude-seo) installed
- Node.js 20+
- A fastCRW endpoint, either:
  - **Managed cloud:** an API key from [fastcrw.com](https://fastcrw.com)
  - **Self-host (free, AGPL):** your own engine; set `CRW_API_URL` (key optional)

## Installation

### macOS / Linux

```bash
./extensions/crw/install.sh
```

### Windows (PowerShell)

```powershell
.\extensions\crw\install.ps1
```

The installer prompts for your `CRW_API_KEY` and configures the MCP server automatically. To target a self-hosted engine, set `CRW_API_URL` before running (e.g. `CRW_API_URL=http://localhost:3000 ./extensions/crw/install.sh`).

## Commands

| Command | Purpose |
|---------|---------|
| `/seo crw crawl <url>` | Full-site crawl with content extraction |
| `/seo crw map <url>` | Discover site structure (URLs only) |
| `/seo crw scrape <url>` | Single-page deep scrape with JS rendering |
| `/seo crw search <query> <url>` | Search within a site (cloud) |

## Integration with Claude SEO

When installed, other Claude SEO skills automatically leverage fastCRW:

- **`/seo audit`**: Uses `map` to discover all pages, then `crawl` for deep analysis
- **`/seo technical`**: Broken link detection across entire site
- **`/seo sitemap`**: Compare XML sitemap vs actual crawlable pages
- **`/seo content`**: Thin content detection at scale

## Why fastCRW

Firecrawl-compatible web scraper; single ~8MB Rust binary; self-host or cloud. Because the REST API is Firecrawl-compatible, this extension reuses the same MCP client and simply points its base URL at fastCRW (`https://fastcrw.com/api` by default, or your self-hosted engine).

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `CRW_API_KEY` | _(prompted)_ | Bearer auth for the managed cloud (optional for self-host without auth) |
| `CRW_API_URL` | `https://fastcrw.com/api` | Base URL; override for self-host (e.g. `http://localhost:3000`) |

## Troubleshooting

**MCP not connecting?**
- Check: `cat ~/.claude/settings.json | python3 -m json.tool | grep crw`
- Manual config: See [CRW-SETUP.md](docs/CRW-SETUP.md)

**Auth errors?**
- Verify your `CRW_API_KEY` at https://fastcrw.com
- Self-host engines may not require a key; leave it empty and set `CRW_API_URL`

**Site blocking crawls?**
- Some sites block automated crawling via robots.txt or Cloudflare
- Try `scrape` (single page) instead of `crawl` (full site)
- Fall back to `fetch_page.py` for basic HTML retrieval

## Uninstall

```bash
./extensions/crw/uninstall.sh      # macOS/Linux
.\extensions\crw\uninstall.ps1     # Windows
```

## Links

- [fastCRW](https://fastcrw.com/)
- [fastCRW REST API docs](https://fastcrw.com/docs/rest-api)
- [Claude SEO](https://github.com/AgriciDaniel/claude-seo)
