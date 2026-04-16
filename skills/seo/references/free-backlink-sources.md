# Free Backlink Data Sources

Reference for the seo-backlinks skill. Loaded on demand when analyzing backlinks
with free sources.

## Source Comparison

| Source | Auth | Any Domain? | Data Quality | Coverage vs Commercial | Rate Limit |
|--------|------|-------------|-------------|----------------------|------------|
| **Moz API** | API key (free signup) | Yes | ★★★★☆ | ~70% for DA/PA | 1 req/10s, 2,500 rows/mo |
| **Bing Webmaster** | API key (free) | Verified sites only | ★★★☆☆ | ~15% (Bing index) | Generous |
| **Common Crawl** | None (public) | Yes | ★★★☆☆ | ~25-40% domains | N/A |
| **Verification Crawler** | None | Yes | ★★★★★ (binary) | N/A (checks known links) | 1 req/s per domain |
| **DataForSEO** (paid) | API key | Yes | ★★★★★ | ~90%+ | Per plan |

## Confidence Weighting

When merging data from multiple sources, apply confidence weights to each metric:

| Source | Weight | Rationale |
|--------|--------|-----------|
| DataForSEO | 1.00 | Commercial-grade, real-time, comprehensive |
| Verification Crawler | 0.95 | Direct observation (binary: link exists or not) |
| Moz API | 0.85 | Large index (45.5T links), established metrics, 3-day update lag |
| Bing Webmaster | 0.70 | Smaller index (~15% of web), but authoritative for Bing-indexed pages |
| Common Crawl | 0.50 | Domain-level only, quarterly updates, no anchor text |

**Composite formula:**
```
weighted_score = Σ(source_score × confidence × factor_weight) / Σ(confidence × factor_weight)
```

When only Common Crawl is available, cap the maximum health score at 70/100 and note
"limited to domain-level metrics" in the report.

## Source Details

### Moz API (Tier 1)
- **Endpoint:** `https://api.moz.com/jsonrpc` (JSON-RPC 2.0)
- **Free tier:** 2,500 rows/month, 1 request per 10 seconds (verify current limits at https://moz.com/products/api — free tier limits may change)
- **Signup:** https://moz.com/products/api (credit card required, not charged)
- **Data:** Domain Authority (0-100), Page Authority, Spam Score (1-17%), link counts,
  referring domains, anchor text distribution
- **Script:** `scripts/moz_api.py`
- **Commands:** `metrics`, `domains`, `anchors`, `pages`
- **Blind spots:** No link velocity, no toxic link patterns beyond Spam Score,
  3-day update lag, smaller index than Ahrefs/Semrush

### Bing Webmaster Tools (Tier 2)
- **Endpoint:** `https://ssl.bing.com/webmaster/api.svc/json/`
- **Free tier:** Unlimited for verified sites
- **Signup:** https://www.bing.com/webmasters (Microsoft account)
- **Unique feature:** Competitor backlink comparison (no other free tool offers this)
- **Data:** Inbound links with anchor text, source URL, discovery date
- **Script:** `scripts/bing_webmaster.py`
- **Commands:** `links`, `counts`, `compare`
- **Blind spots:** Only Bing-indexed pages (~15% of web), verified sites only,
  no authority metrics, no spam scoring

### Common Crawl Web Graph (Always Available)
- **Data source:** `s3://commoncrawl/projects/hyperlinkgraph/`
- **Releases:** Quarterly (e.g., cc-main-2025-18)
- **No auth needed:** Public data, free to download
- **Data:** Domain-level in-degree, PageRank, harmonic centrality, referring domains
- **Script:** `scripts/commoncrawl_graph.py`
- **Cache:** `~/.cache/claude-seo/commoncrawl/` (90-day TTL)
- **Blind spots:** No anchor text, no page-level data, monthly/quarterly freshness,
  domain-level only (e.g., "nytimes.com links to example.com" but not which page)

### Verification Crawler (Always Available)
- **No auth needed:** Uses existing fetch_page.py + parse_html.py
- **Data:** Binary verification (link exists/lost/moved), anchor text, rel attributes
- **Script:** `scripts/verify_backlinks.py`
- **Input:** JSON file with `[{"source_url": "..."}]` entries
- **Polite crawling:** 1-second delay between requests to same domain
- **Best for:** Checking if known backlinks still exist, monitoring link health

## When to Recommend DataForSEO Upgrade

Suggest the paid DataForSEO extension when:
- User needs **toxic link detection** beyond Moz's basic Spam Score
- User needs **competitor gap analysis** at scale (Bing only compares verified sites)
- User needs **link velocity trends** (new/lost links over time)
- User needs **real-time data** (free sources update monthly at best)
- User manages **multiple client sites** (free tier limits are per-account)
- User needs **disavow file generation** with confidence scoring

## Data Quality Reality Check

- Commercial tools index **35-45 trillion links** across 500M+ referring domains
- Free sources combined capture **20-40% of raw backlink data**
- But **60-70% of actionable intelligence** since highest-authority links appear in free samples
- For sites with <500 backlinks, free sources can capture **50%+ of the meaningful profile**
- **Referring domain count matters more than raw backlink count** for SEO
- Top 50-100 referring domains capture the majority of link authority

## Five Systematic Biases in Free Data

1. **Popularity bias:** Free tools crawl popular sites more, underrepresenting niche sites
2. **Truncation bias:** All free tools cap at 100-1,000 links, hiding the long tail
3. **Own-site restriction:** GSC and Ahrefs Webmaster Tools only work for verified properties
4. **Missing quality metrics:** Raw CC data lacks authority/toxicity scores
5. **Freshness lag:** Free sources update monthly at best vs. minutes for commercial
