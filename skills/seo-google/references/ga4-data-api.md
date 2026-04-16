# GA4 Data API v1beta Reference

## Overview

The Google Analytics Data API v1beta provides programmatic access to GA4 report data. For SEO, the primary use case is organic traffic analysis.

**Base URL:** `https://analyticsdata.googleapis.com/v1beta`

## Key Methods

| Method | Description |
|--------|-------------|
| `properties.runReport` | Run a standard report |
| `properties.batchRunReports` | Up to 5 reports in one call |
| `properties.runRealtimeReport` | Last 30 minutes of data |
| `properties.getMetadata` | Available dimensions and metrics |
| `properties.checkCompatibility` | Verify dimension/metric combinations |

## runReport Request

```json
{
  "property": "properties/123456789",
  "dimensions": [
    { "name": "date" },
    { "name": "landingPage" }
  ],
  "metrics": [
    { "name": "sessions" },
    { "name": "totalUsers" }
  ],
  "dateRanges": [
    { "startDate": "28daysAgo", "endDate": "yesterday" }
  ],
  "dimensionFilter": {
    "filter": {
      "fieldName": "sessionDefaultChannelGroup",
      "stringFilter": {
        "matchType": "EXACT",
        "value": "Organic Search"
      }
    }
  },
  "orderBys": [
    { "metric": { "metricName": "sessions" }, "desc": true }
  ],
  "limit": 100,
  "returnPropertyQuota": true
}
```

## SEO-Relevant Dimensions

| Dimension | Description |
|-----------|-------------|
| `date` | Date in YYYYMMDD format |
| `pagePath` | Page path (e.g., `/blog/post`) |
| `landingPage` | Entry page path |
| `landingPagePlusQueryString` | Entry page with query params |
| `fullPageUrl` | Full page URL |
| `pageTitle` | Page title |
| `sessionSource` | Traffic source (e.g., `google`) |
| `sessionMedium` | Traffic medium (e.g., `organic`) |
| `sessionDefaultChannelGroup` | Channel grouping (e.g., `Organic Search`) |
| `country` | User country |
| `deviceCategory` | `desktop`, `mobile`, `tablet` |
| `hostName` | Domain name |
| `pageReferrer` | Referrer URL |

## SEO-Relevant Metrics

| Metric | Description |
|--------|-------------|
| `sessions` | Number of sessions |
| `totalUsers` | Total unique users |
| `newUsers` | First-time users |
| `activeUsers` | Users with engagement |
| `screenPageViews` | Page views |
| `bounceRate` | Bounce rate (0-1, multiply by 100 for %) |
| `averageSessionDuration` | Avg duration in seconds |
| `engagementRate` | Engaged session rate (0-1) |
| `keyEvents` | Key events (replaced deprecated `conversions`) |
| `eventCount` | Total event count |

## Filter Expressions

### String Filter

```json
{
  "filter": {
    "fieldName": "sessionDefaultChannelGroup",
    "stringFilter": {
      "matchType": "EXACT",
      "value": "Organic Search"
    }
  }
}
```

Match types: `EXACT`, `BEGINS_WITH`, `ENDS_WITH`, `CONTAINS`, `FULL_REGEXP`, `PARTIAL_REGEXP`

### Combining Filters

```json
{
  "andGroup": {
    "expressions": [
      { "filter": { "fieldName": "country", "stringFilter": { "matchType": "EXACT", "value": "US" }}},
      { "filter": { "fieldName": "deviceCategory", "stringFilter": { "matchType": "EXACT", "value": "mobile" }}}
    ]
  }
}
```

Also supports `orGroup` and `notExpression`.

## Date Range Shortcuts

| Value | Meaning |
|-------|---------|
| `today` | Current day |
| `yesterday` | Previous day |
| `NdaysAgo` | N days ago (e.g., `28daysAgo`) |
| `YYYY-MM-DD` | Specific date |

Up to 4 date ranges per request (for period-over-period comparison).

## Token-Based Quotas

| Quota | Limit | Scope |
|-------|-------|-------|
| Daily tokens | 25,000 | Per property per project |
| Hourly tokens | 5,000 | Per property per project |
| Concurrent requests | 10 | Per property per project |
| Hourly tokens (project-wide) | 1,250 | Per project per property per hour |

Set `returnPropertyQuota: true` to monitor consumption. Simple reports cost ~1-10 tokens; complex ones up to ~100.

## Python Example

```python
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Filter, FilterExpression,
    Metric, OrderBy, RunReportRequest,
)
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
    "service_account.json",
    scopes=["https://www.googleapis.com/auth/analytics.readonly"],
)

client = BetaAnalyticsDataClient(credentials=credentials)

request = RunReportRequest(
    property="properties/123456789",
    dimensions=[Dimension(name="landingPage")],
    metrics=[Metric(name="sessions"), Metric(name="totalUsers")],
    date_ranges=[DateRange(start_date="28daysAgo", end_date="yesterday")],
    dimension_filter=FilterExpression(
        filter=Filter(
            field_name="sessionDefaultChannelGroup",
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.EXACT,
                value="Organic Search",
            ),
        )
    ),
    order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
    limit=50,
    return_property_quota=True,
)

response = client.run_report(request)
for row in response.rows:
    print(f"{row.dimension_values[0].value}: {row.metric_values[0].value} sessions")
```

## Authentication
- **Scope:** `https://www.googleapis.com/auth/analytics.readonly`
- Service account must have **Viewer** role in GA4 property
- Add via GA4 Admin > Property Access Management
