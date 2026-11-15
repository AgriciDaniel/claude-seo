# DataForSEO API Cost Reference

## Pricing (USD, live mode unless noted)

Source: the per-API pages under https://dataforseo.com/pricing, read 2026-11-15.
The cost script `dataforseo_costs.py` holds the same figures, keyed on the v3 path. The
2.8.10 tool names in the third column are accepted as aliases.

| Category | v3 path | 2.8.10 tool name | Price | Notes |
|----------|---------|------------------|-------|-------|
| **SERP** | `/v3/serp/google/organic/live/advanced`, `.../regular` | `serp_organic_live_*` | $0.002 per 10 results | `depth` rounded up to the next ten: depth 100 = $0.02 |
| **SERP Images** | `/v3/serp/google/images/live/advanced` | (no tool on 2.8.10) | $0.002 per 100 results | No `live/regular` endpoint in v3 |
| **YouTube** | `/v3/serp/youtube/organic/live/advanced`, `.../video_comments/...` | `serp_youtube_*` | $0.002 per 20 results | `video_info`, `video_subtitles`: $0.006 per task |
| **Keywords** | `/v3/keywords_data/google_ads/search_volume/live` | `kw_data_google_ads_search_volume` | $0.09 per task | Up to 1,000 keywords per task |
| **Keywords** | `/v3/keywords_data/google_trends/explore/live` | `kw_data_google_trends_explore` | $0.011 per task | Up to 5 keywords |
| **Labs** | `/v3/dataforseo_labs/google/*/live` | `dataforseo_labs_*` | $0.012 + $0.00012 per item | Grows with `limit`: 1,000 items = $0.132 |
| **On-Page** | `/v3/on_page/instant_pages`, `/v3/on_page/content_parsing/live` | `on_page_instant_pages`, `on_page_content_parsing` | $0.00015 per page | JavaScript/browser rendering cost extra |
| **On-Page** | `/v3/on_page/lighthouse/live/json` | `on_page_lighthouse` | $0.005 per task | |
| **Backlinks** | `/v3/backlinks/*/live` | `backlinks_*` | $0.024 + $0.000036 per row | |
| **Content** | `/v3/content_analysis/*/live` | `content_analysis_*` | $0.024 + $0.000036 per row | |
| **Business** | `/v3/business_data/business_listings/search/live` | `business_data_business_listings_search` | $0.012 + $0.00036 per item | |
| **AI/GEO** | `/v3/ai_optimization/llm_mentions/*/live` | `ai_opt_llm_ment_*` | $0.1 + $0.001 per row | 100 rows = $0.20 |
| **AI/GEO** | `/v3/ai_optimization/chat_gpt/llm_scraper/live/advanced` | `ai_optimization_chat_gpt_scraper` | $0.004 per result page | |
| **Merchant** | `/v3/merchant/google/products/task_post` | `merchant_google_products_search` | $0.001 per 40 products | Standard queue |
| **Merchant** | `/v3/merchant/google/sellers/task_post` | `merchant_google_sellers_search` | $0.001 per 10 sellers | Standard queue |
| **Merchant** | `/v3/merchant/amazon/products/task_post` | `merchant_amazon_products_search` | $0.0015 per 100 results | Standard queue |
| **Domain** | `/v3/domain_analytics/whois/overview/live` | `domain_analytics_whois_overview` | $0.12 + $0.0012 per item | |
| **Domain** | `/v3/domain_analytics/technologies/domain_technologies/live` | `domain_analytics_technologies_domain_technologies` | $0.012 per task | |

Not modelled by the cost script: search operators (5x) and pixel rankings or AI
Overview (+1 base) on SERP, `include_clickstream_data` (2x) on Labs. The billed
amount is the `cost` field of the real response; the `.ai` response format that
dataforseo-mcp-server 3.x uses by default omits it, `noAiMode: true` returns it.

## Budget Presets

| Preset | Daily Limit | Threshold | Mode | Best For |
|--------|------------|-----------|------|----------|
| **Conservative** | $2.00 | $0.10 | threshold | Learning, testing |
| **Standard** | $10.00 | $0.50 | threshold | Regular audits |
| **Aggressive** | $50.00 | $2.00 | threshold | Agency bulk work |
| **Unlimited** | $999.00 | -- | none | Trusted pipelines |

Configure with: `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run dataforseo_costs.py config --mode threshold --threshold 0.50 --daily-limit 10.00`

## Cost Reduction Tips

- Set `depth` on SERP calls to what you need: each further 10 results costs another base price
- Set `limit` on Labs, Backlinks and LLM Mentions calls: these bill per returned item or row
- Batch keywords into single `search_volume` calls (up to 1,000 per task) instead of individual SERP lookups
- Use the standard task queue instead of live for non-urgent analysis (SERP: $0.0006 instead of $0.002 per 10 results)
- Avoid search operators such as `site:` and `filetype:` in SERP queries (5x cost multiplier)
- Cache session results: don't re-fetch the same keyword/domain within a session

## Approval Flow

Before any DataForSEO MCP call:
1. Run `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run dataforseo_costs.py check <endpoint> [--count N] [--items N]`
   (`<endpoint>` is the v3 path or the 2.8.10 tool name; `--items` is the request's `limit` or `depth`)
2. If `status: "approved"` → proceed
3. If `status: "needs_approval"` → show cost to user, ask to confirm
4. If `status: "blocked"` → inform user daily limit would be exceeded
5. After call completes, log: `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run dataforseo_costs.py log <endpoint> <cost>`

## Warn Endpoints

These endpoints always require user confirmation regardless of approval mode:
- `/v3/backlinks/backlinks/live` (`backlinks_backlinks`; can generate large result sets)
- `/v3/backlinks/domain_intersection/live` (`backlinks_domain_intersection`; multi-domain comparison)
- `/v3/ai_optimization/chat_gpt/llm_scraper/live/advanced` (`ai_optimization_chat_gpt_scraper`; ChatGPT web scraping)
- `/v3/ai_optimization/llm_mentions/search/live` (`ai_opt_llm_ment_search`; LLM mention tracking)
- `/v3/merchant/amazon/products/task_post` (`merchant_amazon_products_search`; Amazon product data)
