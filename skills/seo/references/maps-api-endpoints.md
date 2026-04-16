<!-- Updated: 2026-03-23 -->
# DataForSEO Maps & Business Data API Endpoints

## Source Key

- **Docs**: docs.dataforseo.com (official API documentation)
- **Pricing**: dataforseo.com/pricing (official pricing pages)

---

## Authentication & Limits

- HTTP Basic Auth (login:password)
- Rate limit: **2,000 API calls/minute** across all endpoints
- Each POST supports up to **100 tasks** in a single request
- Minimum deposit: $50. $1 free trial credit. Credits never expire.

---

## Google Maps SERP API (Geo-Grid Backbone)

**Endpoint:** `POST https://api.dataforseo.com/v3/serp/google/maps/live/advanced`
**Pricing source:** https://dataforseo.com/pricing/serp-api

### Request Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `keyword` | Yes | Search query (e.g., "dentist") |
| `location_name` | No | Named location (e.g., "Austin,Texas,United States") |
| `location_code` | No | DataForSEO location code (e.g., 1026339 for Austin) |
| `location_coordinate` | No | `"latitude,longitude,zoom"` (max 7 decimals, zoom 3z-21z) |
| `language_code` | No | Default: "en" |
| `device` | No | "desktop" or "mobile" |
| `depth` | No | Number of results to return |

**Critical for geo-grid:** Use `location_coordinate` to simulate searches from specific GPS points. Format: `"40.7128,-74.0060,15z"`.

### Response Fields (per business item)

`cid`, `place_id`, `feature_id`, `title`, `domain`, `url`, `category`, `additional_categories`, `address`, `phone` (via `contact_info` array), `rating.value`, `rating.votes_count`, `rating.rating_distribution` (1-5 star breakdown), `price_level`, `attributes` (grouped: accessibility, payments, children), `work_time` (per-day timetable + `current_status`), `popular_times` (hourly by day), `latitude`, `longitude`, `local_business_links` (booking, menu, order URLs)

### Pricing

| Method | Cost per task | Turnaround |
|--------|--------------|------------|
| Standard | $0.0006 (100 desktop / 20 mobile results) | Up to 5 min |
| Priority | $0.0012 | Up to 1 min |
| **Live** | **$0.002** | Up to 6 sec |

Search operators in keyword multiply cost by 5x.

---

## Google My Business Info API (Single Business Deep-Dive)

**Endpoint:** `POST https://api.dataforseo.com/v3/business_data/google/my_business_info/live`
**Pricing source:** https://dataforseo.com/pricing/business-data

### Input Options

- `keyword`: Business name + location (e.g., "Starbucks Austin TX")
- `"cid:XXXX"`: Direct CID lookup
- `"place_id:XXXX"`: Direct Place ID lookup

### Response Fields

Full profile: `title`, `description`, `category`, `additional_categories`, `category_ids`, `attributes` (available + unavailable, grouped by type), `contact_info` (phone array), `domain`, `url`, `work_hours` (per-day with open/close times), `popular_times`, `cid`, `place_id`, `rating` (with distribution), `address_info` (full breakdown), `latitude`/`longitude`, `photos_count`, `main_image`

**Cost:** $0.0015 per profile (standard queue)

**Use case:** Deep-dive on the TARGET business. Maps SERP for competitor discovery.

---

## Google Reviews API (Sentiment & Velocity)

**Endpoint:** `POST https://api.dataforseo.com/v3/business_data/google/reviews/task_post`
**Pricing source:** https://dataforseo.com/pricing/business-data

### Parameters

| Parameter | Description |
|-----------|-------------|
| `keyword` | Business name + location (or CID/place_id) |
| `depth` | Number of reviews to retrieve |
| `sort_by` | `"highest_rating"`, `"lowest_rating"`, `"most_relevant"`, `"newest"` |

### Response Fields (per review)

`review_text`, `original_review_text`, `time_ago`, `timestamp`, `rating.value`, `review_id`, `profile_name`, `profile_url`, `profile_image_url`, `owner_answer` (text + timestamp), `review_images`

### Pricing

| Method | Input Type | Cost |
|--------|-----------|------|
| Standard (per 10 reviews) | keyword | $0.003 |
| Extended (per 20 reviews) | keyword | $0.003 |
| Extended (per 20 reviews) | place_id/CID | **$0.00075** |

**Optimization:** Always use `place_id` or `cid` input (4x cheaper than keyword).

---

## Google Q&A API

**Endpoint:** `POST https://api.dataforseo.com/v3/business_data/google/questions_and_answers/live`

Returns questions, answers, upvotes, dates, answer sources. Live and standard methods available.

**Use case:** Identify unanswered questions, FAQ gap analysis.

**Note:** Google deprecated GBP Q&A in Dec 2025 (replaced by Ask Maps Gemini AI). This endpoint returns historical data.

---

## Business Listings Search (Pre-Indexed Database)

**Endpoint:** `POST https://api.dataforseo.com/v3/business_data/business_listings/search/live`

Queries DataForSEO's pre-indexed database (not live Google). Faster for bulk category-based queries. Up to 700+ results per query.

**Categories Aggregation:** `/v3/business_data/business_listings/categories_aggregation/live` provides category taxonomy.

**MCP tool name:** `business_data_business_listings_search`

---

## Cross-Platform Review APIs

### Tripadvisor

- Search: `/v3/business_data/tripadvisor/search/task_post`
- Reviews: `/v3/business_data/tripadvisor/reviews/task_post`
- Billed per 30 reviews. Standard method only.

### Trustpilot

- Search: `/v3/business_data/trustpilot/search/task_post`
- Reviews: `/v3/business_data/trustpilot/reviews/task_post`
- ~$0.00075/task. Standard method only.

---

## Cost Estimation Table

| Operation | API Calls | Est. Cost (Live) |
|-----------|-----------|-----------------|
| 7x7 geo-grid, 1 keyword | 49 | $0.098 |
| 7x7 geo-grid, 3 keywords | 147 | $0.294 |
| 3x3 geo-grid, 1 keyword | 9 | $0.018 |
| Target business profile | 1 | $0.0015 |
| 100 reviews (via place_id) | 5 | $0.00375 |
| 20 competitor profiles | 20 | $0.03 |
| GBP posts audit | 1 | ~$0.002 |
| Q&A retrieval | 1 | ~$0.002 |
| **Full audit (1-keyword grid)** | **~73** | **~$0.13** |
| **Full audit (3-keyword grid)** | **~171** | **~$0.33** |

**Formula:** `grid_size^2 x keywords x $0.002` (live) or `x $0.0006` (standard)
