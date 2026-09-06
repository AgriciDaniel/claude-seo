# Google Search Console Extension for Claude SEO

Live Search Console data — search analytics, URL inspection, and sitemap
status — via the [`google-searchconsole-mcp`](https://www.npmjs.com/package/google-searchconsole-mcp)
MCP server. Authenticates with a one-time OAuth browser flow: no Google Cloud
project or service account setup required.

## Prerequisites

- [Claude SEO](https://github.com/AgriciDaniel/claude-seo) installed
- Node.js 20+
- A Google account with access to at least one verified Search Console property

## Installation

### macOS / Linux

```bash
./extensions/google-search-console/install.sh
```

### Windows (PowerShell)

```powershell
.\extensions\google-search-console\install.ps1
```

The installer configures the MCP server, then a browser window opens the
first time a tool is called so you can sign in and grant read-only Search
Console access. Tokens are cached locally by the MCP server (under
`~/.gsc-mcp/tokens/`) and are never written into this repo or its settings
file.

## Commands

| Command | Purpose |
|---------|---------|
| `/seo gsc sites` | List verified Search Console properties |
| `/seo gsc analytics <url>` | Search analytics: clicks, impressions, CTR, position |
| `/seo gsc inspect <url>` | Live indexing status for a specific URL |
| `/seo gsc sitemaps <url>` | Submitted sitemaps and their processing status |

## Integration with Claude SEO

- **`/seo technical`**: confirms real indexing status via `inspect_url` instead of inferring it from crawlability heuristics alone
- **`/seo sitemap`**: cross-references submitted-vs-indexed counts per sitemap file
- **`/seo drift`**: feeds real clicks/impressions/position trend data into drift baselines
- **`/seo redirects`**: confirms canonical drift using the Google-selected canonical from URL inspection

## How this differs from `seo-google`

The existing `seo-google` skill covers PageSpeed Insights, CrUX, Search
Console, Indexing API, and GA4 through a 4-tier API-key/service-account
credential wizard (`/seo google setup`). This extension covers only Search
Console, but needs zero Google Cloud setup, just an OAuth sign-in. Use
whichever matches what you already have: this extension for the fastest path
to GSC data alone, `seo-google` when you want PageSpeed/CrUX/GA4 in the same
place.

## Troubleshooting

**No properties returned?**
- Confirm the site is verified under the Google account you authenticated with in Search Console
- Re-run the install script to trigger the OAuth flow again with a different account

**Token expired or revoked?**
- Delete `~/.gsc-mcp/tokens/` and re-run `./extensions/google-search-console/install.sh`

**MCP not connecting?**
- Check: `cat ~/.claude/settings.json | python3 -m json.tool | grep google-searchconsole`

## Uninstall

```bash
./extensions/google-search-console/uninstall.sh      # macOS/Linux
.\extensions\google-search-console\uninstall.ps1     # Windows
```

## Links

- [google-searchconsole-mcp on npm](https://www.npmjs.com/package/google-searchconsole-mcp)
- [Claude SEO](https://github.com/AgriciDaniel/claude-seo)
