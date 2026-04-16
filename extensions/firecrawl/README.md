# Firecrawl Extension for Claude SEO

Full-site crawling, scraping, and site mapping powered by [Firecrawl](https://www.firecrawl.dev/). Enables comprehensive site-wide SEO analysis with JavaScript rendering support.

## Prerequisites

- [Claude SEO](https://github.com/AgriciDaniel/claude-seo) installed
- Node.js 20+
- Firecrawl API key ([sign up](https://www.firecrawl.dev/app/sign-up) -- free tier: 500 credits/month)

## Installation

### macOS / Linux

```bash
./extensions/firecrawl/install.sh
```

### Windows (PowerShell)

```powershell
.\extensions\firecrawl\install.ps1
```

The installer will prompt for your Firecrawl API key and configure the MCP server automatically.

## Commands

| Command | Purpose | Credits |
|---------|---------|---------|
| `/seo firecrawl crawl <url>` | Full-site crawl with content extraction | 1 per page |
| `/seo firecrawl map <url>` | Discover site structure (URLs only) | 0.5 per URL |
| `/seo firecrawl scrape <url>` | Single-page deep scrape with JS rendering | 1 |
| `/seo firecrawl search <query> <url>` | Search within a site | 1 per result |

## Integration with Claude SEO

When installed, other Claude SEO skills automatically leverage Firecrawl:

- **`/seo audit`**: Uses `map` to discover all pages, then `crawl` for deep analysis
- **`/seo technical`**: Broken link detection across entire site
- **`/seo sitemap`**: Compare XML sitemap vs actual crawlable pages
- **`/seo content`**: Thin content detection at scale

## Cost

| Plan | Credits/month | Price |
|------|--------------|-------|
| Free | 500 | $0 |
| Hobby | 3,000 | $16/mo |
| Standard | 100,000 | $83/mo |
| Growth | 500,000 | $333/mo |

1 credit = 1 page crawled or scraped. Map operations use 0.5 credits per URL.

## Troubleshooting

**MCP not connecting?**
- Check: `cat ~/.claude/settings.json | python3 -m json.tool | grep firecrawl`
- Manual config: See [FIRECRAWL-SETUP.md](docs/FIRECRAWL-SETUP.md)

**Credits exhausted?**
- Check usage: https://www.firecrawl.dev/app
- Upgrade plan or wait for monthly reset

**Site blocking crawls?**
- Some sites block automated crawling via robots.txt or Cloudflare
- Try `scrape` (single page) instead of `crawl` (full site)
- Fall back to `fetch_page.py` for basic HTML retrieval

## Uninstall

```bash
./extensions/firecrawl/uninstall.sh      # macOS/Linux
.\extensions\firecrawl\uninstall.ps1     # Windows
```

## Links

- [Firecrawl Documentation](https://docs.firecrawl.dev/)
- [Firecrawl MCP Server](https://www.npmjs.com/package/firecrawl-mcp)
- [Claude SEO](https://github.com/AgriciDaniel/claude-seo)
