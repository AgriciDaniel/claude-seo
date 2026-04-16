# Google Indexing API v3 Reference

## Overview

The Indexing API allows you to notify Google when pages are added or removed.

**IMPORTANT:** Officially restricted to pages with **JobPosting** or **BroadcastEvent/VideoObject** structured data. Google may process other page types, but provides no guarantees. Always inform users of this limitation.

## Endpoints

### Publish Notification

**`POST https://indexing.googleapis.com/v3/urlNotifications:publish`**

```json
{
  "url": "https://example.com/jobs/software-engineer",
  "type": "URL_UPDATED"
}
```

| Field | Values |
|-------|--------|
| `url` | The fully qualified URL |
| `type` | `URL_UPDATED` (page added/changed), `URL_DELETED` (page removed) |

**Response:**
```json
{
  "urlNotificationMetadata": {
    "url": "https://example.com/jobs/software-engineer",
    "latestUpdate": {
      "url": "https://example.com/jobs/software-engineer",
      "type": "URL_UPDATED",
      "notifyTime": "2026-03-27T10:00:00Z"
    }
  }
}
```

### Get Notification Metadata

**`GET https://indexing.googleapis.com/v3/urlNotifications/metadata?url={ENCODED_URL}`**

Returns `latestUpdate` and `latestRemove` timestamps for the URL.

### Batch Requests

**`POST https://indexing.googleapis.com/batch`**

Up to **100 URLs** per batch request using `multipart/mixed` format:

```
POST /batch HTTP/1.1
Content-Type: multipart/mixed; boundary=batch_boundary

--batch_boundary
Content-Type: application/http
Content-ID: <item1>

POST /v3/urlNotifications:publish HTTP/1.1
Content-Type: application/json

{"url": "https://example.com/jobs/1", "type": "URL_UPDATED"}
--batch_boundary
Content-Type: application/http
Content-ID: <item2>

POST /v3/urlNotifications:publish HTTP/1.1
Content-Type: application/json

{"url": "https://example.com/jobs/2", "type": "URL_UPDATED"}
--batch_boundary--
```

## Authentication

- **Scope:** `https://www.googleapis.com/auth/indexing`
- **Auth type:** Service account (OAuth 2.0)
- The service account must be **Owner** in Google Search Console for the target domain

## Quotas

| Limit | Value | Scope |
|-------|-------|-------|
| Publish requests | **200/day** (default) | Per project |
| Read-only requests | 180/min | Per project |
| Total requests | 380/min | Per project |

Request a quota increase: [Indexing API Quota Increase Form](https://developers.google.com/search/apis/indexing-api/v3/quota-increase)

## Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 400 | Malformed URL or request body | Check URL format |
| 403 | Permission denied or quota exceeded | Add service account as Owner in GSC, or check quota |
| 429 | Rate limit exceeded | Back off and retry with exponential delay |
| 500/503 | Server error | Retry with exponential backoff |

## Best Practices

1. Submit only URLs with actual content changes (don't spam updates)
2. Use `URL_DELETED` only when a page is permanently removed (returns 404/410)
3. Track daily quota usage -- the 200/day limit resets at midnight Pacific Time
4. For large-scale indexing, use XML sitemaps + Search Console instead
5. Batch requests count individually against the daily quota (100 batch = 100 quota)
