# Google Search Console API Reference

## Table of Contents
1. [Search Analytics API](#search-analytics-api)
2. [URL Inspection API](#url-inspection-api)
3. [Sitemaps API](#sitemaps-api)
4. [Sites API](#sites-api)

---

## Search Analytics API

**Endpoint:** `POST https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/searchAnalytics/query`

### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `startDate` | string | Required. YYYY-MM-DD format. |
| `endDate` | string | Required. YYYY-MM-DD format. |
| `dimensions` | string[] | `query`, `page`, `country`, `device`, `date`, `searchAppearance` |
| `type` | string | `web` (default), `image`, `video`, `news`, `discover`, `googleNews` |
| `dimensionFilterGroups` | object[] | Array of filter groups (see below) |
| `aggregationType` | string | `auto` (default), `byPage`, `byProperty`, `byNewsShowcasePanel` |
| `rowLimit` | int | 1-25000 (default: 1000) |
| `startRow` | int | Pagination offset (default: 0) |
| `dataState` | string | `final` (default), `all`, `hourly_all` |

### Dimension Filters

```json
{
  "dimensionFilterGroups": [{
    "filters": [{
      "dimension": "query",
      "operator": "contains",
      "expression": "seo"
    }]
  }]
}
```

**Operators:** `contains`, `equals`, `notContains`, `notEquals`, `includingRegex`, `excludingRegex`
- Regex uses RE2 syntax, max 4096 characters

### Response

```json
{
  "rows": [
    {
      "keys": ["seo tools", "https://example.com/tools"],
      "clicks": 150,
      "impressions": 5000,
      "ctr": 0.03,
      "position": 4.2
    }
  ],
  "responseAggregationType": "byPage"
}
```

### Important Notes
- Data has a **2-3 day lag**. Available for approximately 16 months.
- `discover` and `googleNews` types do not support `query` dimension or `position` metric.
- Country codes are **ISO 3166-1 alpha-3** (e.g., `USA`, `GBR`, `DEU`).
- Pagination: increment `startRow` by `rowLimit` until fewer rows returned.

### Rate Limits
- 1,200 QPM per user
- 1,200 QPM per site
- 40,000 QPM / 30,000,000 QPD per project

---

## URL Inspection API

**Endpoint:** `POST https://searchconsole.googleapis.com/v1/urlInspection/index:inspect`

### Request

```json
{
  "inspectionUrl": "https://example.com/page",
  "siteUrl": "sc-domain:example.com",
  "languageCode": "en"
}
```

### Response Fields

**`indexStatusResult`:**

| Field | Values |
|-------|--------|
| `verdict` | `PASS`, `FAIL`, `NEUTRAL`, `PARTIAL`, `VERDICT_UNSPECIFIED` |
| `coverageState` | Human-readable coverage description |
| `robotsTxtState` | `ALLOWED`, `DISALLOWED` |
| `indexingState` | `INDEXING_ALLOWED`, `BLOCKED_BY_META_TAG`, `BLOCKED_BY_HTTP_HEADER` |
| `pageFetchState` | `SUCCESSFUL`, `SOFT_404`, `BLOCKED_ROBOTS_TXT`, `NOT_FOUND`, `ACCESS_DENIED`, `SERVER_ERROR`, `REDIRECT_ERROR`, `ACCESS_FORBIDDEN`, `BLOCKED_4XX`, `INTERNAL_CRAWL_ERROR`, `INVALID_URL` |
| `lastCrawlTime` | ISO 8601 timestamp |
| `googleCanonical` | URL Google selected as canonical |
| `userCanonical` | URL declared canonical by the page |
| `crawledAs` | `DESKTOP`, `MOBILE` |

**`richResultsResult`:** Verdict + detected rich result types (FAQPage, HowTo, etc.)

### Rate Limits
- 2,000 QPD / 600 QPM per site
- 10,000,000 QPD / 15,000 QPM per project

---

## Sitemaps API

**Base:** `https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/sitemaps`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sitemaps` | List all sitemaps |
| `GET` | `/sitemaps/{feedpath}` | Get specific sitemap |
| `PUT` | `/sitemaps/{feedpath}` | Submit a sitemap |
| `DELETE` | `/sitemaps/{feedpath}` | Delete a sitemap |

### Sitemap Resource

| Field | Description |
|-------|-------------|
| `path` | URL of the sitemap |
| `lastSubmitted` | Last submission timestamp |
| `isPending` | Whether processing is incomplete |
| `isSitemapsIndex` | Whether this is a sitemap index |
| `type` | `sitemap`, `atomFeed`, `rssFeed`, `urlList`, `notSitemap` |
| `warnings` | Warning count |
| `errors` | Error count |
| `contents[]` | Array with `type` (web, image, video, news) and `submitted` count |

---

## Sites API

**Base:** `https://www.googleapis.com/webmasters/v3/sites`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sites` | List all verified properties |
| `GET` | `/sites/{siteUrl}` | Get property info |
| `PUT` | `/sites/{siteUrl}` | Add a property |
| `DELETE` | `/sites/{siteUrl}` | Remove a property |

### Property Resource

| Field | Values |
|-------|--------|
| `siteUrl` | Property URL (e.g., `sc-domain:example.com`) |
| `permissionLevel` | `siteOwner`, `siteFullUser`, `siteRestrictedUser`, `siteUnverifiedUser` |
