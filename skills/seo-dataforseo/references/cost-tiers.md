# DataForSEO API Cost Reference

## Pricing Tiers (USD per call, standard queue)

| Category | Endpoint | Cost/Call | Notes |
|----------|----------|-----------|-------|
| **SERP** | `serp_*_live_advanced` | $0.002 | Per 100 results |
| **SERP** | `serp_*_live_regular` | $0.001 | Lightweight |
| **SERP Images** | `serp_google_images_live_*` | $0.002 | 5x with site:/filetype: operators |
| **Keywords** | `kw_data_google_ads_search_volume` | $0.05 | Per batch of keywords |
| **Keywords** | `kw_data_google_trends_explore` | $0.01 | Per query |
| **Labs** | `dataforseo_labs_*_keyword_*` | $0.05 | Ideas, suggestions, related |
| **Labs** | `dataforseo_labs_bulk_*` | $0.01 | Difficulty, traffic |
| **Labs** | `dataforseo_labs_*_domain_*` | $0.05 | Competitors, intersection |
| **On-Page** | `on_page_instant_pages` | $0.01 | Quick analysis |
| **On-Page** | `on_page_lighthouse` | $0.02 | Full Lighthouse |
| **Backlinks** | `backlinks_*` | $0.02 | Per sub-call |
| **Content** | `content_analysis_*` | $0.02 | Search, summary, trends |
| **Business** | `business_data_*` | $0.05 | Listings search |
| **AI/GEO** | `ai_optimization_*` | $0.05 | ChatGPT scraper, LLM mentions |
| **Merchant** | `merchant_*` | $0.02 | Google Shopping, Amazon |
| **Domain** | `domain_analytics_whois_*` | $0.005 | WHOIS data |
| **Domain** | `domain_analytics_technologies_*` | $0.01 | Tech stack |

## Budget Presets

| Preset | Daily Limit | Threshold | Mode | Best For |
|--------|------------|-----------|------|----------|
| **Conservative** | $2.00 | $0.10 | threshold | Learning, testing |
| **Standard** | $10.00 | $0.50 | threshold | Regular audits |
| **Aggressive** | $50.00 | $2.00 | threshold | Agency bulk work |
| **Unlimited** | $999.00 | -- | none | Trusted pipelines |

Configure with: `python scripts/dataforseo_costs.py config --mode threshold --threshold 0.50 --daily-limit 10.00`

## Cost Reduction Tips

- Use `live_regular` instead of `live_advanced` when full SERP features aren't needed (50% savings)
- Batch keywords into single `search_volume` calls instead of individual SERP lookups
- Use `standard` task queue instead of `live` for non-urgent analysis (60-80% savings)
- Avoid `site:` and `filetype:` operators in image SERP queries (5x cost multiplier)
- Cache session results — don't re-fetch the same keyword/domain within a session

## Approval Flow

Before any DataForSEO MCP call:
1. Run `python scripts/dataforseo_costs.py check <endpoint> [--count N]`
2. If `status: "approved"` → proceed
3. If `status: "needs_approval"` → show cost to user, ask to confirm
4. If `status: "blocked"` → inform user daily limit would be exceeded
5. After call completes, log: `python scripts/dataforseo_costs.py log <endpoint> <cost>`

## Warn Endpoints

These endpoints always require user confirmation regardless of approval mode:
- `backlinks_backlinks` (can generate large result sets)
- `backlinks_domain_intersection` (expensive multi-domain comparison)
- `ai_optimization_chat_gpt_scraper` (ChatGPT web scraping)
- `ai_opt_llm_ment_search` (LLM mention tracking)
- `merchant_amazon_products_search` (Amazon product data)
