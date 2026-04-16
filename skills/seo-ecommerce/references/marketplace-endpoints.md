# DataForSEO Merchant API Reference

Endpoint details for Google Shopping and Amazon marketplace data.

## Endpoints

### Google Shopping Products

| Field | Value |
|-------|-------|
| Endpoint | `merchant_google_products_search` |
| Method | POST (task) / GET (results) |
| Cost | $0.02 per call |
| Queue | Standard (60-80% savings vs live) |

**Parameters:**
- `keyword` (required) -- search query
- `location_code` (default: 2840 = US) -- DataForSEO location ID
- `language_code` (default: "en") -- language
- `price_min` / `price_max` (optional) -- filter by price range
- `sort_by` (optional) -- "relevance", "price_low_to_high", "price_high_to_low", "rating"
- `depth` (optional, default: 100) -- number of results

**Response fields:**
- `title` -- product listing title
- `price` -- numeric price value
- `currency` -- currency code (USD, EUR, etc.)
- `seller` -- merchant name
- `rating` -- product rating (float, 0-5)
- `reviews_count` -- number of reviews
- `url` -- product listing URL
- `image_url` -- product image URL
- `availability` -- "in_stock", "out_of_stock", "preorder"
- `delivery_info` -- shipping details text
- `product_id` -- Google Shopping product ID

### Google Shopping Sellers

| Field | Value |
|-------|-------|
| Endpoint | `merchant_google_sellers_search` |
| Method | POST (task) / GET (results) |
| Cost | $0.02 per call |

**Parameters:** Same as products search.

**Response fields:**
- `seller_name` -- merchant name
- `seller_rating` -- merchant rating (float)
- `seller_reviews_count` -- merchant review count
- `price` -- price offered by this seller
- `delivery_info` -- shipping and delivery text
- `url` -- seller listing URL

### Amazon Products

| Field | Value |
|-------|-------|
| Endpoint | `merchant_amazon_products_search` |
| Method | POST (task) / GET (results) |
| Cost | $0.02 per call |
| Note | In `warn_endpoints` -- always requires user approval |

**Parameters:**
- `keyword` (required) -- search query
- `location_code` (default: 2840 = US)
- `language_code` (default: "en")
- `depth` (optional, default: 100)
- `sort_by` (optional) -- "relevance", "price_low_to_high", "price_high_to_low", "avg_customer_review"

**Response fields:**
- `title` -- product title
- `price` -- numeric price
- `currency` -- currency code
- `seller` -- seller/brand name
- `rating` -- star rating (float, 0-5)
- `reviews_count` -- review count
- `url` -- Amazon product URL
- `image_url` -- product image
- `availability` -- stock status
- `asin` -- Amazon Standard Identification Number
- `is_prime` -- Prime eligibility (boolean)
- `is_best_seller` -- Best Seller badge (boolean)

## Task/Poll Pattern

All Merchant endpoints use the standard DataForSEO queue pattern:

1. **POST** task with parameters to create endpoint
2. **Poll** for results with exponential backoff (2s, 4s, 8s, max 60s)
3. **GET** completed results by task ID

This saves 60-80% compared to live endpoints.

## Rate Limits

- Max 2000 tasks per minute (across all endpoints)
- Max 30,000 tasks per day on standard plans
- Backoff on HTTP 429: wait 60 seconds, then retry

## Data Normalization

When consuming responses, normalize:

| Field | Raw | Normalized |
|-------|-----|-----------|
| Price | String "$29.99" or float | Float `29.99` |
| Currency | Mixed formats | ISO 4217 code (USD, EUR, GBP) |
| Availability | Various strings | Enum: `in_stock`, `out_of_stock`, `preorder`, `unknown` |
| Rating | Integer or float | Float rounded to 1 decimal |
| Reviews | String or int | Integer |

Use `scripts/dataforseo_normalize.py --module merchant` for automatic normalization.

## Cost Reference

See `skills/seo-dataforseo/references/cost-tiers.md` for the full pricing table,
budget presets, and cost reduction tips. All Merchant endpoints are $0.02/call
on standard queue.
