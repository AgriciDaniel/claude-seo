---
name: seo-firecrawl
description: >
  Full-site crawling, scraping, and site mapping via Firecrawl MCP.
  Use when user says "crawl site", "map site", "full crawl",
  "find all pages", "broken links", "site structure",
  "discover pages", "JS rendering", or needs site-wide analysis.
user-invokable: true
argument-hint: "[command] <url>"
license: MIT
compatibility: "Requires Firecrawl MCP server"
metadata:
  author: AgriciDaniel
  version: "1.7.2"
  category: seo
---

# Firecrawl Extension for Claude SEO

This skill requires the Firecrawl extension to be installed:
```bash
./extensions/firecrawl/install.sh
```

**Check availability:** Before using any Firecrawl tool, verify the MCP server
is connected by checking if `firecrawl_scrape` or any Firecrawl tool
is available. If tools are not available, inform the user the extension is not
installed and provide install instructions.

## Quick Reference

| Command | Purpose |
|---------|---------|
| `/seo firecrawl crawl <url>` | Full-site crawl with content extraction |
| `/seo firecrawl map <url>` | Discover site structure (URLs only, fast) |
| `/seo firecrawl scrape <url>` | Single-page scrape with JS rendering |
| `/seo firecrawl search <query> <url>` | Search within a crawled site |

## Commands

### crawl -- Full-Site Crawl

Crawl an entire website starting from the given URL. Returns page content,
metadata, and links for all discovered pages.

**MCP Tool:** `firecrawl_crawl`

**Parameters:**
- `url` (required): Starting URL to crawl
- `limit`: Max pages to crawl (default: 100, max: 500)
- `maxDepth`: Max link depth from start URL (default: 3)
- `includePaths`: Array of glob patterns to include (e.g., `["/blog/*"]`)
- `excludePaths`: Array of glob patterns to exclude (e.g., `["/admin/*", "/api/*"]`)
- `scrapeOptions.formats`: Output formats -- `["markdown", "html", "links"]`

**SEO Usage Patterns:**
1. **Comprehensive audit crawl**: Crawl full site, extract all pages for subagent analysis
2. **Section-focused crawl**: Use `includePaths` to audit only `/blog/*` or `/products/*`
3. **Broken link detection**: Crawl with `["links"]` format, check all hrefs for 404s
4. **Content inventory**: Extract all page titles, meta descriptions, H1s at scale
5. **SPA/JS-rendered sites**: Firecrawl renders JavaScript, solving the Issue #11 problem

**Example orchestration for `/seo audit`:**
```
1. firecrawl_map(url) -> get all URLs (fast, no content)
2. Filter to top 50 most important pages (homepage, key sections)
3. firecrawl_crawl(url, limit=50) -> get full content
4. Feed content to seo-technical, seo-content, seo-schema agents
```

**Cost awareness:**
- Free tier: 500 credits/month
- 1 credit = 1 page crawled or scraped
- Map operations are cheaper (0.5 credits per URL discovered)
- Always inform user of estimated credit usage before large crawls

### map -- Site Structure Discovery

Discover all URLs on a website without fetching content. Fast and credit-efficient.

**MCP Tool:** `firecrawl_map`

**Parameters:**
- `url` (required): Website URL to map
- `limit`: Max URLs to discover (default: 5000)
- `search`: Optional search term to filter URLs

**SEO Usage Patterns:**
1. **Sitemap comparison**: Map site, compare discovered URLs vs XML sitemap
2. **Orphan page detection**: URLs in sitemap but not linked from any page
3. **Crawl budget analysis**: Total indexable pages vs pages linked from homepage
4. **URL pattern analysis**: Identify URL structure patterns, duplicates, parameter bloat
5. **Pre-audit discovery**: Run map first, then targeted crawl on key sections

**Output:** Array of URLs. Present as:
```
Site: example.com
Pages discovered: 342

URL Pattern Breakdown:
  /blog/*          - 128 pages (37%)
  /products/*      - 89 pages (26%)
  /category/*      - 45 pages (13%)
  /pages/*         - 32 pages (9%)
  / (root pages)   - 48 pages (14%)
```

### scrape -- Single-Page Deep Scrape

Scrape a single page with full JavaScript rendering. More thorough than
`fetch_page.py` because it executes JS and waits for dynamic content.

**MCP Tool:** `firecrawl_scrape`

**Parameters:**
- `url` (required): Page URL to scrape
- `formats`: Output formats -- `["markdown", "html", "links", "screenshot"]`
- `onlyMainContent`: Strip nav/footer/sidebar (default: true)
- `waitFor`: CSS selector or milliseconds to wait for content
- `timeout`: Request timeout in ms (default: 30000)
- `actions`: Browser actions before scraping (click, scroll, wait)

**SEO Usage Patterns:**
1. **SPA content extraction**: Scrape JS-rendered React/Vue/Angular pages
2. **Dynamic content audit**: Pages with lazy-loaded content below the fold
3. **Paywall/login detection**: Identify content behind authentication walls
4. **Main content extraction**: Use `onlyMainContent` for clean E-E-A-T analysis
5. **Screenshot capture**: Use `screenshot` format for visual analysis

**When to use scrape vs fetch_page.py:**
| Scenario | Use |
|----------|-----|
| Static HTML page | `fetch_page.py` (no API cost) |
| JS-rendered SPA | `firecrawl_scrape` (renders JS) |
| Need response headers | `fetch_page.py` (returns headers) |
| Need clean markdown | `firecrawl_scrape` (better extraction) |
| Rate-limited/blocked | `firecrawl_scrape` (handles anti-bot) |

### search -- Site-Scoped Search

Search within a website for specific content. Useful for finding pages
related to a topic without crawling everything.

**MCP Tool:** `firecrawl_search`

**Parameters:**
- `query` (required): Search query
- `url` (required): Website to search within
- `limit`: Max results (default: 10)
- `scrapeOptions.formats`: Output format for matched pages

**SEO Usage Patterns:**
1. **Content gap validation**: Search for a keyword on the site to check if content exists
2. **Internal linking opportunities**: Find pages mentioning a topic that could link to each other
3. **Duplicate content detection**: Search for key phrases to find near-duplicates
4. **Competitor content research**: Search competitor site for specific topics

## Cross-Skill Integration

### With seo-audit (full audit)
When Firecrawl is available during `/seo audit`:
1. Use `firecrawl_map` to discover all site URLs
2. Compare with XML sitemap (seo-sitemap) to find orphan/missing pages
3. Select top pages for deep analysis
4. Feed crawled content to all subagents (technical, content, schema, geo)
5. Report total crawlable pages, URL patterns, and crawl depth

### With seo-technical
- Broken link detection: crawl all internal links, check for 404s
- Redirect chain mapping: follow all redirects, flag chains > 2 hops
- Mixed content detection: check HTTP resources on HTTPS pages
- Canonical verification: compare canonical URLs with actual URLs

### With seo-sitemap
- Sitemap coverage: % of crawled pages present in sitemap
- Orphan pages: pages found by crawl but missing from sitemap
- Stale sitemap entries: URLs in sitemap that return 404/410

### With seo-content
- Content extraction: feed clean markdown to E-E-A-T analysis
- Thin content detection: identify pages with < 300 words at scale
- Duplicate content: compare content across pages for near-duplicates

### With seo-schema
- Schema extraction: pull JSON-LD from all crawled pages
- Schema coverage: % of pages with structured data
- Schema validation: batch-validate extracted schemas

## Error Handling

| Error | Cause | Resolution |
|-------|-------|-----------|
| `FIRECRAWL_API_KEY not set` | MCP not configured | Run `./extensions/firecrawl/install.sh` |
| `402 Payment Required` | Credits exhausted | Check usage at firecrawl.dev/app, upgrade plan |
| `429 Too Many Requests` | Rate limited | Wait 60s, reduce crawl concurrency |
| `408 Timeout` | Page too slow to render | Increase `timeout`, try without JS rendering |
| `403 Forbidden` | Site blocks crawling | Check robots.txt, may need to skip this site |

**Graceful fallback:** If Firecrawl is unavailable, inform the user and suggest:
1. Use `fetch_page.py` for single-page analysis (no API cost)
2. Use `WebFetch` tool for basic HTML retrieval
3. Install Firecrawl: `./extensions/firecrawl/install.sh`
