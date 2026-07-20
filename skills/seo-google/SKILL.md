---
name: seo-google
description: >
  Google SEO APIs: Search Console (Search Analytics, URL Inspection, Sitemaps),
  PageSpeed Insights v5, CrUX field data with 25-week history, Indexing API v3,
  and GA4 organic traffic. Provides real Google field data for Core Web Vitals,
  indexation status, search performance, and organic traffic trends. Use when
  user says "search console", "GSC", "PageSpeed", "CrUX", "field data",
  "indexing API", "GA4 organic", "URL inspection", or "real CWV data".
user-invocable: true
argument-hint: "[command] [url|property]"
license: MIT
metadata:
  author: AgriciDaniel
  version: "2.2.3"
  category: seo
---

# Google SEO APIs

Direct access to Google's own SEO data. Bridges the gap between crawl-based
analysis (existing claude-seo skills) and Google's real-time field data: actual
Chrome user metrics, real indexation status, search performance, and organic traffic.

All APIs are free. Setup requires a Google Cloud project with API key and/or
service account -- run `/seo google setup` for step-by-step instructions.

## Prerequisites

Before executing any command, check credentials:
```bash
python3 scripts/google_auth.py --check --json
```

Config file: `~/.config/claude-seo/google-api.json`
```json
{
  "service_account_path": "/path/to/service_account.json",
  "api_key": "<GOOGLE_API_KEY>",
  "default_property": "sc-domain:example.com",
  "ga4_property_id": "properties/123456789"
}
```

If missing, read `references/auth-setup.md` and walk the user through setup.

### Credential Tiers

| Tier | Detection | Available Commands |
|------|-----------|-------------------|
| **0** (API Key) | `api_key` present | `pagespeed`, `crux`, `crux-history`, `youtube`, `nlp` |
| **1** (OAuth/SA) | + OAuth token or service account | Tier 0 + `gsc`, `inspect`, `sitemaps`, `index` |
| **2** (Full) | + `ga4_property_id` configured | Tier 1 + `ga4`, `ga4-pages` |
| **3** (Ads) | + `ads_developer_token` + `ads_customer_id` | Tier 2 + `keywords`, `volume` |

Always communicate the detected tier before running commands.

## Quick Reference

| Command | What it does | Tier |
|---------|-------------|------|
| `/seo google setup` | Check/configure API credentials | -- |
| `/seo google pagespeed <url>` | PSI Lighthouse + CrUX field data | 0 |
| `/seo google crux <url>` | CrUX field data only (p75 metrics) | 0 |
| `/seo google crux-history <url>` | 25-week CWV trend analysis | 0 |
| `/seo google gsc <property>` | Search Console: clicks, impressions, CTR, position | 1 |
| `/seo google inspect <url>` | URL Inspection: index status, canonical, crawl info | 1 |
| `/seo google inspect-batch <file>` | Batch URL Inspection from file | 1 |
| `/seo google sitemaps <property>` | GSC sitemap status | 1 |
| `/seo google index <url>` | Submit URL to Indexing API | 1 |
| `/seo google index-batch <file>` | Batch submit up to 200 URLs | 1 |
| `/seo google ga4 [property-id]` | GA4 organic traffic report | 2 |
| `/seo google ga4-pages [property-id]` | Top organic landing pages | 2 |
| `/seo google youtube <query>` | YouTube video search (views, likes, duration) | 0 |
| `/seo google youtube-video <id>` | YouTube video details + top comments | 0 |
| `/seo google nlp <url-or-text>` | NLP entity extraction + sentiment + classification | 0 |
| `/seo google entities <url-or-text>` | Entity analysis only (for E-E-A-T) | 0 |
| `/seo google keywords <seed>` | Keyword ideas from Google Ads Keyword Planner | 3 |
| `/seo google volume <keywords>` | Search volume lookup from Keyword Planner | 3 |
| `/seo google entity <query>` | Knowledge Graph entity check | 0 |
| `/seo google safety <url>` | Web Risk URL safety check | 0 |
| `/seo google quotas` | Show rate limits for all APIs | -- |

---

## PageSpeed + CrUX

### `/seo google pagespeed <url>`

Combined Lighthouse lab data + CrUX field data.

**Script:** `python3 scripts/pagespeed_check.py <url> --json`
**Reference:** `references/pagespeed-crux-api.md`
**Default:** Both mobile + desktop strategies, all Lighthouse categories.

Output merges lab scores (point-in-time Lighthouse) with field data (28-day
Chrome user metrics). CrUX tries URL-level first, falls back to origin-level.

### `/seo google crux <url>`

CrUX field data only (no Lighthouse run). Faster.

**Script:** `python3 scripts/pagespeed_check.py <url> --crux-only --json`

### `/seo google crux-history <url>`

25-week CrUX History trends. Shows whether CWV metrics are improving, stable, or degrading.

**Script:** `python3 scripts/crux_history.py <url> --json`
**Reference:** `references/pagespeed-crux-api.md`

Output includes per-metric trend direction, percentage change, and weekly p75 values.

---

## Search Console

### `/seo google gsc <property>`

Search Analytics: clicks, impressions, CTR, position for last 28 days.

**Script:** `python3 scripts/gsc_query.py --property <property> --json`
**Reference:** `references/search-console-api.md`
**Default:** 28 days, dimensions=query,page, type=web, limit=1000.

Includes quick-win detection: queries at position 4-10 with high impressions.

> **AI surfaces in GSC (2026):**
> - **Generative AI performance report** (launched 2026-06-03), a dedicated view of **AI Overviews + AI Mode** visibility. **Impressions only** (no clicks/CTR/position/query); dimensions Pages/Countries/Devices/Dates (Pacific Time); 1,000-row limit; newest data preliminary; a separate Discover gen-AI report also exists. Rolling out to a subset of properties.
> - **AI Mode already rolls into standard Performance totals** (Web search type), clicks (external-link clicks in AI Mode) and impressions are counted in the normal report, so you **cannot** cleanly split "classic" vs "AI" traffic from totals. Use the Generative AI report for impressions-only AI visibility.
> - **Data-reliability caveat:** a GSC logging error made **impressions, CTR, and average position unreliable from 2025-05-13 to 2026-04-27** (clicks unaffected; fixed forward-only, **no backfill**). Treat impression/CTR/position trends spanning that window with caution; expect an apparent impressions drop after the fix.

### `/seo google inspect <url>`

URL Inspection: real indexation status from Google.

**Script:** `python3 scripts/gsc_inspect.py <url> --json`

Returns: verdict (PASS/FAIL), coverage state, robots.txt status, indexing state,
page fetch state, canonical selection, mobile usability, rich results.

### `/seo google inspect-batch <file>`

Batch inspection from a file (one URL per line). Rate limited to 2,000/day per site.

**Script:** `python3 scripts/gsc_inspect.py --batch <file> --json`

### `/seo google sitemaps <property>`

List submitted sitemaps with status, errors, warnings. Sitemap contents report
submitted counts only; URL Inspection API is the indexation truth for whether
specific URLs are indexed.

**Script:** `python3 scripts/gsc_query.py sitemaps --property <property> --json`

---

## Indexing API

### `/seo google index <url>`

Notify Google of a URL update.

**Script:** `python3 scripts/indexing_notify.py <url> --json`
**Reference:** `references/indexing-api.md`

The Indexing API is officially for JobPosting and BroadcastEvent/VideoObject pages.
Always inform the user of this restriction. Daily quota: 200 publish requests.

### `/seo google index-batch <file>`

Batch submit URLs from a file. Tracks quota usage.

**Script:** `python3 scripts/indexing_notify.py --batch <file> --json`

---

## GA4 Traffic

### `/seo google ga4 [property-id]`

Organic traffic report: daily sessions, users, pageviews, bounce rate, engagement.

**Script:** `python3 scripts/ga4_report.py --property <id> --json`
**Reference:** `references/ga4-data-api.md`
**Default:** 28 days, filtered to Organic Search channel group.

> **GA4 "AI Assistants" channel (live ~2026-05-13):** GA4 added a native *AI Assistants* Default Channel Group. Sessions referred by a recognized AI assistant get `medium=ai-assistant`. Google's recognized sources are **ChatGPT, Gemini, Claude, Deepseek, Copilot, Grok** and the channel **excludes** Google AI Overviews / AI Mode. **Verify Perplexity separately if needed**; unsupported sources may stay in Referral, and most AI sessions arrive referrer-less and fall into **Direct**, so this channel undercounts AI traffic. Forward-only, no backfill.

### `/seo google ga4-pages [property-id]`

Top organic landing pages ranked by sessions.

**Script:** `python3 scripts/ga4_report.py --property <id> --report top-pages --json`

---

## YouTube (Video SEO)

Some third-party studies report a 0.737 correlation between YouTube mentions and AI visibility. Treat it as a methodology-dependent signal. Free, API key only.

### `/seo google youtube <query>`

Search YouTube for videos. Returns title, channel, views, likes, duration.

**Script:** `python3 scripts/youtube_search.py search "<query>" --json`
**Reference:** `references/youtube-api.md`
**Quota:** 100 units per search (10,000 units/day free).

### `/seo google youtube-video <video_id>`

Detailed video info + tags + top 10 comments.

**Script:** `python3 scripts/youtube_search.py video <video_id> --json`
**Quota:** 2 units (video details + comments).

---

## NLP Content Analysis

Google NLP entity/sentiment output for internal content-quality checks. Do not treat it as Google E-E-A-T scoring.

### `/seo google nlp <url-or-text>`

Full NLP analysis: entities, sentiment, content classification.

**Script:** `python3 scripts/nlp_analyze.py --url <url> --json` or `--text "..."`
**Reference:** `references/nlp-api.md`
**Free tier:** 5,000 units/month. Requires billing enabled on GCP project.

### `/seo google entities <url-or-text>`

Entity extraction only (faster, less quota).

**Script:** `python3 scripts/nlp_analyze.py --url <url> --features entities --json`

---

## Keyword Research (Google Ads)

Gold-standard keyword volume data. Requires Google Ads account.

### `/seo google keywords <seed>`

Generate keyword ideas from seed terms.

**Script:** `python3 scripts/keyword_planner.py ideas "<seed>" --json`
**Reference:** `references/keyword-planner-api.md`
**Requires:** Ads developer token + customer ID in config (Tier 3).

### `/seo google volume <keywords>`

Search volume for specific keywords (comma-separated).

**Script:** `python3 scripts/keyword_planner.py volume "<kw1>,<kw2>" --json`

---

## Supplementary

### `/seo google entity <query>`

Knowledge Graph entity check. Verifies brand presence.

**Reference:** `references/supplementary-apis.md`
Uses Knowledge Graph Search API with API key.

### `/seo google safety <url>`

Web Risk API check for malware/social engineering flags.

**Reference:** `references/supplementary-apis.md`

### `/seo google quotas`

Display rate limits table. Read `references/rate-limits-quotas.md`.

---

## Reports

After any analysis command, offer to generate a PDF/HTML report.

### `/seo google report <type>`

Generate a professional PDF report with charts and analytics.

**Script:** `python3 scripts/google_report.py --type <type> --data <json> --domain <domain> --format pdf`

| Type | Input | Output |
|------|-------|--------|
| `cwv-audit` | PSI + CrUX + CrUX History data | Core Web Vitals audit with gauges, timelines, distributions |
| `gsc-performance` | GSC query data | Search Console report with query tables, quick wins |
| `indexation` | Batch inspection data | Indexation status with coverage donut chart |
| `full` | All data combined | Comprehensive Google SEO report (all sections) |

**Workflow:**
1. Run data collection commands (pagespeed, gsc, inspect-batch, etc.)
2. Save JSON output to file: `python3 scripts/pagespeed_check.py <url> --json > data.json`
3. Generate report: `python3 scripts/google_report.py --type cwv-audit --data data.json --domain <domain>`

**Convention:** After completing analysis, suggest: "Generate a report? Use `/seo google report <type>`"

---

## Rate Limits

| API | Per-Minute | Per-Day | Auth |
|-----|-----------|---------|------|
| PSI v5 | 240 QPM | 25,000 QPD | API Key |
| CrUX + History | 150 QPM (shared) | Unlimited | API Key |
| GSC Search Analytics | 1,200 QPM/site | 30M QPD | Service Account |
| GSC URL Inspection | 600 QPM | 2,000 QPD/site | Service Account |
| Indexing API | 380 RPM | 200 publish/day | Service Account |
| GA4 Data API | 10 concurrent | ~25K tokens/day | Service Account |

## Cross-Skill Integration

- **seo-audit**: Spawns `seo-google` agent for live CWV + indexation data (conditional)
- **seo-technical**: Uses pagespeed_check.py for real CWV field data
- **seo-performance**: CrUX field data supplements Lighthouse lab data
- **seo-sitemap**: GSC sitemap status shows submitted counts, errors, and warnings; use URL Inspection for indexation truth
- **seo-content**: GSC query data informs keyword targeting
- **seo-geo**: Use GSC Generative AI performance reports and AI Overviews/AI Mode/Discover gen-AI include/exclude controls where available

## Output Format

- CWV metrics: traffic-light rating (Good / Needs Improvement / Poor)
- Performance reports: tables with sortable columns
- Always include data freshness note
- Save reports as `GOOGLE-API-REPORT-{domain}.md`
- Markdown/LLM templates in `assets/templates/`: `cwv-audit-report.md`, `gsc-performance-report.md`, `indexation-status-report.md`; distinct from `google_report.py`'s PDF pipeline

## Technical Notes

- INP replaced FID on March 12, 2024. Never reference FID.
- CLS values from CrUX are string-encoded (e.g., "0.05"). Scripts handle parsing.
- CrUX 404 = insufficient traffic, not an auth error.
- Search Analytics data has 2-3 day lag.
- `round_trip_time` replaced `effectiveConnectionType` in CrUX (Feb 2025).
- Custom Search JSON API is closed to new customers (2025).

## Error Handling

| Scenario | Action |
|----------|--------|
| No credentials configured | Run `/seo google setup`. List Tier 0 commands that work with just an API key. |
| Service account lacks GSC access | Report error. Instruct: add `client_email` to GSC > Settings > Users > Add. |
| CrUX data unavailable (404) | Report insufficient Chrome traffic. Suggest PSI lab data as fallback. |
| GA4 property not found | Report error. Show how to find property ID in GA4 Admin > Property Details. |
| Indexing API quota exceeded | Report 200/day limit. Suggest prioritizing most important URLs. |
| Rate limit (429) | Wait and retry with exponential backoff. Report which API hit the limit. |
