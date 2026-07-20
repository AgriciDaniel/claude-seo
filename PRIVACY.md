# Privacy

## Data Handling

Claude SEO is a Claude Code skill that runs on your local machine. The core skill makes no third-party API calls by default (audits still fetch the target URLs you point them at), and does not collect, store, or transmit any personal data to a vendor.

## What Stays Local

- All SEO analysis runs in your Claude Code session
- HTML parsing, content analysis, and report generation happen locally
- Generated reports (PDF, HTML, Excel) are saved to your local filesystem
- No telemetry, analytics, or usage tracking

## Extension APIs

Optional extensions make API calls to third-party services when you invoke their commands:

| Extension | Service | Data Sent | Privacy Policy |
|-----------|---------|-----------|---------------|
| **DataForSEO** | api.dataforseo.com | URLs and domains you analyze | [DataForSEO Privacy](https://dataforseo.com/privacy-policy) |
| **Firecrawl** | api.firecrawl.dev | URLs you crawl or scrape | [Firecrawl Privacy](https://www.firecrawl.dev/privacy) |
| **Banana (Gemini)** | generativelanguage.googleapis.com | Image generation prompts | [Google AI Privacy](https://ai.google.dev/terms) |
| **Ahrefs** | Official `@ahrefs/mcp` server (Ahrefs API) | Domains and URLs you analyze | [Ahrefs Privacy](https://ahrefs.com/privacy) |
| **SE Ranking** | seranking.com/api | Domains and keywords you analyze | [SE Ranking Privacy](https://seranking.com/privacy-policy) |
| **Profound** | Profound API (tryprofound.com) | Brands and domains you track | [Profound Privacy](https://tryprofound.com/privacy) |
| **Bing Webmaster / IndexNow** | Bing Webmaster Tools API and IndexNow endpoints | Domains, submitted URLs, and key-verification URL data | [Microsoft Privacy](https://privacy.microsoft.com/) |
| **Unlighthouse** | Local only — no third-party vendor | Runs Lighthouse locally against the target URL; only the target site is contacted (to crawl it). Nothing is sent to a third-party vendor. | N/A (runs locally) |

## Backlink APIs

When configured with backlink API credentials, these scripts transmit data to third-party services:

| Script | Service | Data Sent | Privacy Policy |
|--------|---------|-----------|---------------|
| `moz_api.py` | Moz Link Explorer API | Domains you analyze | [Moz Privacy](https://moz.com/privacy-policy) |
| `bing_webmaster.py` | Bing Webmaster Tools API | Domains you analyze | [Microsoft Privacy](https://privacy.microsoft.com/) |
| `indexnow_submit.py` | IndexNow endpoints (Bing / Yandex / Seznam / Naver) | URLs submitted and key-verification URL data | Endpoint provider policies |
| `commoncrawl_graph.py` | Common Crawl | Domains (public dataset query) | [Common Crawl Terms](https://commoncrawl.org/terms-of-use) |
| `verify_backlinks.py` | Target URLs directly | URLs to verify backlink existence | N/A (direct HTTP requests) |

## Google SEO APIs

When configured with Google API credentials, these scripts transmit data to Google:

| Script | Google API | Data Sent |
|--------|-----------|-----------|
| `pagespeed_check.py` | PageSpeed Insights | URL to analyze |
| `gsc_query.py` | Search Console | Authenticated query for your verified properties |
| `gsc_inspect.py` | URL Inspection | URLs to inspect |
| `indexing_notify.py` | Indexing API | URLs to submit for indexing |
| `ga4_report.py` | Analytics Data | Authenticated query for your GA4 properties |
| `crux_history.py` | CrUX History | URL or origin to query |
| `nlp_analyze.py` | Cloud Natural Language | Text content for entity / sentiment / category analysis |
| `keyword_planner.py` | Google Ads (Keyword Planner) | Seed keywords for volume, CPC, and competition lookups |
| `youtube_search.py` | YouTube Data API v3 | Search queries for YouTube SEO research |

Google API usage is governed by [Google's Privacy Policy](https://policies.google.com/privacy) and the [Google API Terms of Service](https://developers.google.com/terms).

## Credentials

- API keys and OAuth tokens are stored locally in `~/.config/claude-seo/` or environment variables
- Credentials are never committed to the repository (blocked by `.gitignore`)
- OAuth tokens use refresh tokens and never store client secrets in token files
