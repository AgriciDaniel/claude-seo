# CrUX History API and Core Web Vitals Thresholds

> Split from `pagespeed-crux-api.md`, which covers PageSpeed Insights v5 and the daily CrUX API.

## CrUX History API (Weekly)

**Endpoint:** `POST https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord`

Send the API key in the `X-Goog-Api-Key` header, not in the URL.

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

Current as of 2026-07-09; no threshold changes were announced. INP replaced FID on March 12, 2024.

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| **LCP** | ≤ 2,500ms | 2,500–4,000ms | > 4,000ms |
| **INP** | ≤ 200ms | 200–500ms | > 500ms |
| **CLS** | ≤ 0.1 | 0.1–0.25 | > 0.25 |
| **FCP** | ≤ 1,800ms | 1,800–3,000ms | > 3,000ms |
| **TTFB** | ≤ 800ms | 800–1,800ms | > 1,800ms |

FID was removed from Chrome's field-data tools (CrUX, PSI) on September 9, 2024. Never reference FID in outputs.
