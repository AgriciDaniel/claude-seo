---
name: seo-gsc-extension
description: >
  Query live Google Search Console data (search analytics, URL inspection,
  sitemap status, site list) via the google-searchconsole-mcp OAuth server.
  Use when user says "Search Console", "GSC", "indexing status",
  "search analytics", "impressions and clicks", or "inspect URL".
user-invocable: true
argument-hint: "[command] <url>"
license: MIT
compatibility: "Requires the Google Search Console MCP extension"
metadata:
  author: AgriciDaniel
  version: "2.3.0"
  category: seo
---

# Google Search Console Extension for Claude SEO

This skill requires the Google Search Console extension to be installed:
```bash
./extensions/google-search-console/install.sh
```

Unlike the other Google integrations documented under `seo-google` (which use
a PSI/GSC/GA4 API-key or service-account credential wizard), this extension
runs a dedicated MCP server that authenticates via a one-time OAuth browser
flow, no Google Cloud project or service account required. Prefer this
extension when the user wants fast, read-only GSC access without running
`/seo google setup`; prefer the `seo-google` credential-wizard path when the
user already has Tier 1+ Google API credentials configured, since that path
also unlocks PageSpeed, CrUX, and GA4 in the same setup.

**Check availability:** Before using any tool from this extension, verify the
MCP server is connected by checking whether `list_sites`, `search_analytics`,
`inspect_url`, or `list_sitemaps` are available. If not, inform the user the
extension is not installed and provide install instructions.

## Quick Reference

| Command | Purpose |
|---------|---------|
| `/seo gsc sites` | List Search Console properties the authenticated account can access |
| `/seo gsc analytics <url>` | Query search analytics (clicks, impressions, CTR, position) |
| `/seo gsc inspect <url>` | Inspect indexing status for a specific URL |
| `/seo gsc sitemaps <url>` | List submitted sitemaps and their processing status |

## Commands

### sites -- List Properties

**MCP Tool:** `list_sites`

Returns every Search Console property (domain or URL-prefix) the
authenticated Google account has at least read access to. Use this first to
confirm the target site is verified in Search Console before running other
commands.

### analytics -- Search Analytics Query

**MCP Tool:** `search_analytics`

**Parameters:**
- `siteUrl` (required): the verified property, matching a `sites` result
- `startDate` / `endDate`: date range (Search Console data lags ~2 days)
- `dimensions`: `["query", "page", "country", "device", "date"]`
- `rowLimit`: max rows returned

**SEO usage patterns:**
1. **Query-level performance**: dimension `query`, sorted by clicks, to find
   top-performing and declining queries
2. **Page-level performance**: dimension `page`, to cross-reference with
   `seo-page` and `seo-content` findings for underperforming URLs
3. **Position tracking**: compare average position over two adjacent date
   ranges to detect ranking drift (pairs well with `seo-drift`)
4. **Device/country breakdown**: dimension `device` or `country` to spot
   mobile-specific or geo-specific drops

### inspect -- URL Inspection

**MCP Tool:** `inspect_url`

**Parameters:**
- `siteUrl` (required)
- `inspectionUrl` (required): the specific URL to inspect

Returns live indexing status: whether the URL is indexed, the last crawl
date, the Google-selected canonical (compare against the page's declared
canonical for drift), mobile usability, and rich-result eligibility. Use
this to verify a fix landed instead of guessing from page-level signals
alone; note that Search Console index status can lag actual crawling.

### sitemaps -- Sitemap Status

**MCP Tool:** `list_sitemaps`

Returns submitted sitemaps, last-downloaded date, and per-sitemap
submitted-vs-indexed URL counts. Cross-reference with `seo-sitemap`'s
structural validation: a sitemap can be well-formed and still show a large
submitted/indexed gap, which is a content or indexability problem, not a
sitemap-format problem.

## Cross-Skill Integration

### With seo-technical
Use `inspect_url` to confirm indexing status directly instead of inferring it
from crawlability heuristics alone.

### With seo-sitemap
Use `sitemaps` to get the real submitted/indexed counts per sitemap file,
which the sitemap skill cannot see on its own since it only validates
structure.

### With seo-drift
Feed `search_analytics` date-range comparisons into drift baselines for a
real clicks/impressions/position trend line, not just structural snapshots.

### With seo-redirects
When `inspect_url` reports a Google-selected canonical that differs from the
live redirect target, treat it as confirmed canonical drift rather than a
suspected one.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|-----------|
| No sites returned | Account has no verified Search Console properties, or wrong Google account authenticated | Verify the property in Search Console; re-run the OAuth flow with the correct account |
| `403` on inspect/analytics | Authenticated account lacks permission on that property | Request access from the property owner in Search Console |
| Empty analytics rows | Date range too recent (GSC data lags ~2 days) or too narrow | Widen the date range; confirm the property has traffic |
| OAuth token expired/revoked | Local token cache invalidated | Re-run `./extensions/google-search-console/install.sh` to re-authenticate |

**Graceful fallback:** If this extension is unavailable, inform the user and
suggest the `seo-google` skill's API-key/service-account path instead
(`/seo google setup`), which covers Search Console plus PageSpeed, CrUX, and
GA4 in one credential wizard.
