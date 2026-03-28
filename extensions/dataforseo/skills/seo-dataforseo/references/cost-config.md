# DataForSEO Cost Configuration

> Load this reference when DataForSEO tools are about to be used.
> It defines the approval mode, pricing lookup table, and conservative defaults.

## Configuration File

Stored at `~/.claude-seo/dataforseo-cost-config.json`. Created automatically
with conservative defaults on first use (via `scripts/dataforseo_costs.py init`).

### Schema

```json
{
  "version": 1,
  "approval_mode": "threshold",
  "threshold_usd": 0.50,
  "prefer_standard_queue": true,
  "default_limits": {
    "serp_depth": 10,
    "keyword_limit": 20,
    "backlink_limit": 50,
    "review_depth": 20,
    "content_limit": 10,
    "grid_size": 5
  },
  "session_budget_usd": null,
  "warn_modules": ["BACKLINKS", "AI_OPTIMIZATION"]
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `approval_mode` | string | `"always"`, `"threshold"`, or `"none"` |
| `threshold_usd` | number | Dollar threshold that triggers approval when mode is `"threshold"` |
| `prefer_standard_queue` | bool | Use standard queue (cheapest) instead of live when possible |
| `default_limits` | object | Conservative defaults for list endpoints |
| `session_budget_usd` | number\|null | Optional per-session spending cap (null = no cap) |
| `warn_modules` | array | Modules that always require confirmation regardless of mode |

### Approval Modes

| Mode | Behavior |
|------|----------|
| `always` | Every DataForSEO API call shows a cost estimate and waits for user approval |
| `threshold` | Calls below `threshold_usd` proceed automatically; calls at or above ask for approval |
| `none` | All calls proceed without approval (not recommended) |

**Default:** `threshold` at `$0.50`. This allows cheap lookups (single SERP, keyword
volume) to proceed automatically while flagging expensive operations (geo-grids,
full backlink profiles, AI optimization batches).

---

## Pricing Lookup Table (March 2026)

### SERP API

| Operation | Mode | Base Cost |
|-----------|------|-----------|
| Google/Bing/Yahoo organic | Standard | $0.0006/SERP |
| Google/Bing/Yahoo organic | Priority | $0.0012/SERP |
| Google/Bing/Yahoo organic | Live | $0.0020/SERP |
| YouTube search | Live | $0.0020/SERP |
| YouTube video info | Live | $0.0060/video |
| YouTube subtitles | Live | $0.0060/video |
| Google Maps SERP | Standard | $0.0006/task |
| Google Maps SERP | Live | $0.0020/task |
| SERP screenshot | Any | $0.0040/image |
| Google Autocomplete | Live | $0.0020/task |

**Modifier:** Search operators in keyword multiply base cost by 5x.

### Keywords Data

| Operation | Mode | Cost |
|-----------|------|------|
| Google Ads search volume | Standard | $0.05/task (up to 1k keywords) |
| Google Ads search volume | Live | $0.001/request + $0.0001/keyword |
| Similar keywords | Live | $0.01/request + $0.0001/keyword |
| Keyword suggestions (basic) | Live | $0.075/request |
| Google Trends explore | Live | mirrors base SERP pricing |

### DataForSEO Labs

| Operation | Cost |
|-----------|------|
| Keyword ideas | $0.075/request |
| Keyword suggestions | $0.01 + $0.0001/keyword |
| Related keywords | $0.01 + $0.0001/keyword |
| Bulk keyword difficulty | $0.001 + $0.0001/keyword |
| Search intent | $0.001 + $0.0001/keyword |
| Ranked keywords | $0.01 + $0.0001/target |
| Competitors domain | $0.01 + $0.0001/target |
| Domain rank overview | $0.01 + $0.0001/target |
| Domain intersection | $0.01 + $0.0001/target |
| Bulk traffic estimation | $0.002/domain |
| Subdomains | $0.01 + $0.0001/target |
| Top searches | $0.01 + $0.0001/target |
| Relevant pages | $0.01 + $0.0001/target |

### Backlinks API

**Requires $100/month minimum commitment (funds usable on any module).**

| Operation | Cost |
|-----------|------|
| Summary | $0.02/task + $0.00003/row |
| Backlinks list | $0.02/task + $0.00003/row |
| Anchors | $0.02/task + $0.00003/row |
| Referring domains | $0.02/task + $0.00003/row |
| Bulk spam score | $0.02/task + $0.00003/target |
| Timeseries summary | $0.02/task + $0.00003/row |
| Domain intersection | $0.02/task + $0.00003/row |

### On-Page API

| Operation | Cost |
|-----------|------|
| Instant pages (basic) | $0.000125/page |
| Instant pages (JS rendering) | $0.00125/page |
| Instant pages (browser) | $0.00425/page |
| Content parsing | $0.000125/page |
| Lighthouse | $0.00425/page |
| Page screenshot | $0.0040/page |

### Domain Analytics

| Operation | Cost |
|-----------|------|
| Technologies detection | $0.10/task + $0.001/domain |
| WHOIS overview | $0.10/task + $0.001/domain |

### Business Data

| Operation | Mode | Cost |
|-----------|------|------|
| My Business Info | Standard | $0.0015/profile |
| My Business Info | Live | $0.0054/profile |
| Reviews (via place_id) | Standard | $0.00075/20 reviews |
| Reviews (via keyword) | Standard | $0.003/10 reviews |
| Business Listings search | Live | $0.01/task + $0.0003/item |
| Tripadvisor reviews | Standard | $0.00075/task |
| Trustpilot reviews | Standard | $0.00075/task |

### Content Analysis

All endpoints: $0.02/request + $0.00003/row (search, summary, phrase trends).

### AI Optimization (requires separate module activation)

| Operation | Cost |
|-----------|------|
| LLM mentions (search/domains/pages/aggregate) | $0.10/task + $0.001/row |
| ChatGPT scraper | $0.004 live, $0.0012 standard |
| AI keyword data | $0.01/task + $0.0001/keyword |

---

## Command Cost Estimates

Use `scripts/dataforseo_costs.py estimate --command <CMD>` for live calculations.
Key reference points (live mode):

| Command | Est. Cost | Command | Est. Cost |
|---------|-----------|---------|-----------|
| `serp` | $0.002 | `backlinks` | ~$0.15 |
| `keywords` | $0.225 | `ai-mentions` | ~$0.44 |
| `volume` (20kw) | ~$0.003 | `content` | ~$0.065 |
| `onpage` | ~$0.009 | `tech` / `whois` | ~$0.101 |
| `ai-scrape` | $0.004 | `listings` | ~$0.013 |

Composite: Full audit $0.50–$1.50 | Geo-grid 7×7 live $0.098 | 5×5 standard $0.015

## Conservative Defaults

| Setting | Aggressive | Conservative (default) |
|---------|-----------|----------------------|
| Queue preference | Live | Standard when available |
| SERP depth | 100 | 10 |
| Keyword limit | 50–100 | 20 |
| Backlink rows | 100 | 50 |
| Grid size | 7×7 | 5×5 |

Conservative defaults reduce costs by ~60–80% for most operations.

---

## Agent Integration Rules

1. **Before any DataForSEO call:** estimate cost using `scripts/dataforseo_costs.py estimate`
2. **Check approval mode:** read config, compare estimated cost to threshold
3. **If approval needed:** display cost breakdown and wait for user confirmation
4. **After calls complete:** log actual costs with `scripts/dataforseo_costs.py log`
5. **Warn on expensive modules:** always flag BACKLINKS and AI_OPTIMIZATION regardless of mode
