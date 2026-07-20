# YouTube Data API v3 Reference

YouTube mentions may correlate with AI visibility in some GEO research, but this file does not include a Google-owned source or methodology for a numeric benchmark. This API provides authoritative YouTube data directly from Google.

## Endpoints Used

| Method | Quota Cost | Description |
|--------|-----------|-------------|
| `search.list` | 100 units | Search for videos matching a query |
| `videos.list` | 1 unit | Get video details, statistics, content |
| `channels.list` | 1 unit | Get channel info, subscriber count |
| `commentThreads.list` | 1 unit | Get top comments on a video |

## Daily Quota

Default: **10,000 units/day** (free). This allows:
- ~100 searches per day, OR
- ~10,000 video/channel lookups per day

## Data Available

### Video Search
- Title, channel, channel ID, published date
- Description (first 300 chars), thumbnail URL
- Views, likes, comments count, duration

### Video Details
- Full description, tags, category ID
- Duration, definition (HD/SD), has captions
- Topic categories (Wikipedia URLs)
- Views, likes, comments, favorites
- Top 10 relevant comments with likes

### Channel Info
- Title, description, custom URL
- Subscriber count, video count, total views
- Country, published date, thumbnail

## Authentication

**API key only** (read-only public data). No OAuth needed.

## Enable the API

1. Go to [console.cloud.google.com/apis/library](https://console.cloud.google.com/apis/library)
2. Search for "YouTube Data API v3"
3. Click Enable

No billing required. The API key you already have for PSI/CrUX works.
