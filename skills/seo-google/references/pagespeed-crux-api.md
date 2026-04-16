# PageSpeed Insights v5 + CrUX API Reference

## Table of Contents
1. [PageSpeed Insights v5](#pagespeed-insights-v5)
2. [CrUX API (Daily)](#crux-api-daily)
3. [CrUX History API (Weekly)](#crux-history-api-weekly)
4. [Core Web Vitals Thresholds](#core-web-vitals-thresholds)

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

**Endpoint:** `POST https://chromeuxreport.googleapis.com/v1/records:queryRecord?key={API_KEY}`

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

## CrUX History API (Weekly)

**Endpoint:** `POST https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord?key={API_KEY}`

Same request format as CrUX API. Returns up to **25 weekly collection periods**.

### Response Differences from CrUX API

Instead of single values, returns timeseries:

```json
{
  "record": {
    "metrics": {
      "largest_contentful_paint": {
        "histogramTimeseries": [
          { "start": 0, "end": 2500, "densities": [0.70, 0.71, 0.72, ...] },
          { "start": 2500, "end": 4000, "densities": [0.19, 0.18, 0.18, ...] },
          { "start": 4000, "densities": [0.11, 0.11, 0.10, ...] }
        ],
        "percentilesTimeseries": {
          "p75s": [2200, 2150, 2100, ...]
        }
      }
    },
    "collectionPeriods": [
      {
        "firstDate": { "year": 2025, "month": 9, "day": 29 },
        "lastDate": { "year": 2025, "month": 10, "day": 26 }
      },
      ...
    ]
  }
}
```

### NaN Handling
- `"NaN"` string for densities in ineligible periods
- `null` for percentile values in ineligible periods
- Always check for these before numeric operations

### Update Schedule
- Updated **Mondays** ~04:00 UTC
- Each period = 28-day rolling average ending on a Sunday

---

## Core Web Vitals Thresholds

Current as of March 2026. INP replaced FID on March 12, 2024.

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| **LCP** | ≤ 2,500ms | 2,500–4,000ms | > 4,000ms |
| **INP** | ≤ 200ms | 200–500ms | > 500ms |
| **CLS** | ≤ 0.1 | 0.1–0.25 | > 0.25 |
| **FCP** | ≤ 1,800ms | 1,800–3,000ms | > 3,000ms |
| **TTFB** | ≤ 800ms | 800–1,800ms | > 1,800ms |

FID was fully removed from Chrome tools (CrUX, PSI, Lighthouse) on September 9, 2024. Never reference FID in outputs.
