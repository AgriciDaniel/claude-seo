# Google Ads API - Keyword Planner Reference

Gold-standard source for keyword search volume. DataForSEO gets its volume data from Google Ads -- this cuts out the middleman.

## Prerequisites (More Complex Than Other Google APIs)

1. **Google Ads Manager Account** -- create at ads.google.com (free to create)
2. **Developer Token** -- apply at Google Ads API Center (requires Basic access approval)
3. **OAuth 2.0 credentials** -- reuse existing OAuth client from seo-google config
4. **For exact volumes**: Run a minimal campaign (~$5-10/day). Without spend, volumes are bucketed ranges ("1K-10K")

## Key Methods

### GenerateKeywordIdeas
Generate keyword suggestions from seed terms.

**Returns per keyword:**
- `text`: Keyword string
- `avg_monthly_searches`: Average monthly volume (exact if spending, bucketed if not)
- `competition`: LOW / MEDIUM / HIGH (for ads, not organic)
- `competition_index`: 0-100 competition score
- `low_top_of_page_bid_micros`: ~20th percentile CPC in micros
- `high_top_of_page_bid_micros`: ~80th percentile CPC in micros
- `monthly_search_volumes[]`: Per-month volume for last 12 months

### GenerateKeywordHistoricalMetrics
Get volume data for specific keywords.

Same return fields as above but for exact keyword list instead of suggestions.

### GenerateKeywordForecastMetrics
Predict clicks, impressions, and cost for keywords.

## Configuration

Add to `~/.config/claude-seo/google-api.json`:

```json
{
  "ads_developer_token": "YOUR_DEV_TOKEN",
  "ads_customer_id": "123-456-7890",
  "ads_login_customer_id": "123-456-7890"
}
```

## Rate Limits

- Keyword Planning requests are more strictly rate-limited than other Ads API services
- Exact QPM/QPS not publicly documented
- Google recommends caching results

## Python Library

```bash
pip install google-ads
```

Uses `google-ads` library (separate from `google-api-python-client`).

## Important Notes

- **Volume accuracy**: Without active ad spend, Google returns bucketed ranges ("1K-10K", "10K-100K") instead of exact numbers like "14,800"
- **Competition score**: Measures advertiser competition for ads, NOT organic ranking difficulty
- **CPC bids**: Reflect what advertisers pay, useful for estimating keyword commercial value
- **Location targeting**: Use location IDs (2840 = United States, 2826 = United Kingdom)
- **Language targeting**: Use language IDs (1000 = English, 1003 = Spanish)
