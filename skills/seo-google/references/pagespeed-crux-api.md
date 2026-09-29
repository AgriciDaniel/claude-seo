# PageSpeed Insights v5 + CrUX API Reference

## Table of Contents
1. [PageSpeed Insights v5](#pagespeed-insights-v5)
2. [CrUX API (Daily)](#crux-api-daily)
3. [CrUX History API (Weekly)](crux-history-api.md#crux-history-api-weekly)
4. [Core Web Vitals Thresholds](crux-history-api.md#core-web-vitals-thresholds)

---

## PageSpeed Insights v5

**Endpoint:** `GET https://www.googleapis.com/pagespeedonline/v5/runPagespeed`

### Parameters

| Param | Type | Description |
|-------|------|-------------|
| `url` | string | Required. URL to analyze. |
| `category` | string | `ACCESSIBILITY`, `BEST_PRACTICES`, `PERFORMANCE`, `SEO`. Can specify multiple. |
| `strategy` | string | `DESKTOP` or `MOBILE` (default). |
| `locale` | string | Locale for text (e.g., `en`). |
| `key` | string | API key. Optional but recommended for quota. |

### Response Structure

```
{
  "id": "https://example.com/",
  "loadingExperience": { ... },        // URL-level CrUX data
  "originLoadingExperience": { ... },  // Origin-level CrUX data
  "lighthouseResult": {
    "categories": {
      "performance": { "score": 0.85 },
      "accessibility": { "score": 0.92 },
      "best-practices": { "score": 0.88 },
      "seo": { "score": 0.95 }
    },
    "audits": { ... }                  // Individual audit results
  },
  "analysisUTCTimestamp": "2026-03-27T..."
}
```

### Field Data Metrics (in loadingExperience)

| PSI Key | CrUX Metric | Unit |
|---------|-------------|------|
| `LARGEST_CONTENTFUL_PAINT_MS` | LCP | ms |
| `INTERACTION_TO_NEXT_PAINT` | INP | ms |
| `CUMULATIVE_LAYOUT_SHIFT_SCORE` | CLS | unitless |
| `FIRST_CONTENTFUL_PAINT_MS` | FCP | ms |
| `EXPERIMENTAL_TIME_TO_FIRST_BYTE` | TTFB | ms |

Each metric contains: `percentile` (p75), `distributions[]` ({min, max, proportion}), `category` (FAST/AVERAGE/SLOW/NONE).

### Key Lighthouse Audit IDs

`first-contentful-paint`, `largest-contentful-paint`, `total-blocking-time`, `cumulative-layout-shift`, `speed-index`, `interactive`

### Rate Limits
- 25,000 QPD with API key
- 240 QPM
- Free, no billing required

### Note on Field Data Migration
Google is migrating CrUX field data out of PSI. For field data, prefer the CrUX API directly. Use PSI primarily for Lighthouse lab data.

---

## CrUX API (Daily)

**Endpoint:** `POST https://chromeuxreport.googleapis.com/v1/records:queryRecord`

Send the API key in the `X-Goog-Api-Key` header, not in the URL.

### Request

```json
{
  "origin": "https://example.com",
  "formFactor": "PHONE",
  "metrics": ["largest_contentful_paint", "interaction_to_next_paint", "cumulative_layout_shift"]
}
```

| Field | Description |
|-------|-------------|
| `origin` | Origin URL (mutually exclusive with `url`) |
| `url` | Specific page URL (mutually exclusive with `origin`) |
| `formFactor` | `DESKTOP`, `PHONE`, `TABLET` (optional, omit for all) |
| `metrics` | Array of metric names (optional, omit for all) |

### Available Metrics

| Metric | Type | Notes |
|--------|------|-------|
| `largest_contentful_paint` | int (ms) | Core Web Vital |
| `largest_contentful_paint_resource_type` | fractions | LCP resource type, added January 2025 |
| `largest_contentful_paint_image_time_to_first_byte` | int (ms) | LCP image subpart, added January 2025 |
| `largest_contentful_paint_image_resource_load_delay` | int (ms) | LCP image subpart, added January 2025 |
| `largest_contentful_paint_image_resource_load_duration` | int (ms) | LCP image subpart, added January 2025 |
| `largest_contentful_paint_image_element_render_delay` | int (ms) | LCP image subpart, added January 2025 |
| `interaction_to_next_paint` | int (ms) | Core Web Vital (replaced FID) |
| `cumulative_layout_shift` | **string** | Core Web Vital. **String-encoded!** Parse carefully. |
| `first_contentful_paint` | int (ms) | |
| `experimental_time_to_first_byte` | int (ms) | |
| `round_trip_time` | int (ms) | Replaced effectiveConnectionType (Feb 2025) |
| `navigation_types` | fractions | navigate, navigate_cache, reload, etc. |
| `form_factors` | fractions | desktop/phone/tablet distribution |

### Response

```json
{
  "record": {
    "key": { "origin": "https://example.com" },
    "metrics": {
      "largest_contentful_paint": {
        "histogram": [
          { "start": 0, "end": 2500, "density": 0.72 },
          { "start": 2500, "end": 4000, "density": 0.18 },
          { "start": 4000, "density": 0.10 }
        ],
        "percentiles": { "p75": 2100 }
      },
      "cumulative_layout_shift": {
        "percentiles": { "p75": "0.05" }
      }
    },
    "collectionPeriod": {
      "firstDate": { "year": 2026, "month": 2, "day": 27 },
      "lastDate": { "year": 2026, "month": 3, "day": 26 }
    }
  }
}
```

### Important
- **CLS p75 is a string** (e.g., `"0.05"` not `0.05`). Always parse as float from string.
- Last histogram bin has **no `end`** (extends to infinity).
- Densities sum to approximately 1.0.
- **404** = no data (insufficient Chrome traffic). Not an auth error.
- Updated daily ~04:00 UTC with ~2 day lag.

### Rate Limits
- 150 QPM shared between CrUX and CrUX History APIs
- Free, no paid increase available

---

CrUX History API (weekly) and Core Web Vitals thresholds: `crux-history-api.md`.
