---
name: seo-ecommerce
description: >
  E-commerce SEO analysis: Google Shopping visibility, Amazon marketplace
  intelligence, product schema validation, competitor pricing analysis, and
  marketplace keyword gaps. Combines on-page product SEO with marketplace data
  from DataForSEO Merchant API. Use when user says "ecommerce SEO", "product SEO",
  "Google Shopping", "marketplace SEO", "product schema", "Amazon SEO",
  "product listings", "shopping ads", or "merchant SEO".
user-invokable: true
argument-hint: "<url or keyword>"
license: MIT
compatibility: "Enhanced with DataForSEO Merchant API (optional)"
metadata:
  author: AgriciDaniel
  original_author: "Matej Marjanovic (Pro Hub Challenge)"
  version: "1.9.0"
  category: seo
---

# E-commerce SEO Analysis

Comprehensive product page optimization, marketplace intelligence, and
competitive pricing analysis. Works standalone (on-page + schema) and with
DataForSEO Merchant API for live Google Shopping and Amazon data.

## Commands

| Command | Purpose | DataForSEO? |
|---------|---------|-------------|
| `/seo ecommerce <url>` | Full e-commerce SEO analysis of a product page or store | Optional |
| `/seo ecommerce products <keyword>` | Google Shopping competitive analysis | Required |
| `/seo ecommerce gaps <domain>` | Keyword gap: organic vs Shopping visibility | Required |
| `/seo ecommerce schema <url>` | Product schema validation and enhancement | No |

---

## 1. Product Page Analysis (No DataForSEO Needed)

Fetch and parse any product page for on-page SEO quality.

### Workflow

```
1. python scripts/fetch_page.py <url>         → raw HTML
2. python scripts/parse_html.py --url <url>   → SEO elements
3. Analyze product-specific signals (below)
```

### Product SEO Checklist

#### Title Tag
- [ ] Contains primary product keyword
- [ ] Includes brand name
- [ ] Under 60 characters (no truncation in SERPs)
- [ ] Format: `[Product Name] - [Key Feature] | [Brand]`

#### Meta Description
- [ ] Contains product keyword + benefit
- [ ] Includes price or "from $XX" (triggers rich snippet interest)
- [ ] Call-to-action present (Shop now, Buy, Free shipping)
- [ ] Under 155 characters

#### Heading Structure
- [ ] Single H1 matching primary product name
- [ ] H2s for: Features, Specifications, Reviews, Related Products
- [ ] No duplicate H1 tags across product variants

#### Product Images
- [ ] Alt text includes product name + distinguishing feature
- [ ] File names are descriptive (not `IMG_001.jpg`)
- [ ] WebP format served (with JPEG fallback)
- [ ] At least 3 images per product (hero, detail, lifestyle)
- [ ] Image dimensions >= 800px for Google Shopping eligibility
- [ ] Lazy loading on below-fold images only

#### Internal Linking
- [ ] Breadcrumb navigation: Home > Category > Subcategory > Product
- [ ] Related products section (cross-sell / upsell)
- [ ] Link back to category page with keyword-rich anchor
- [ ] Reviews section links to full review page (if separate)

#### Content Quality
- [ ] Unique product description (not manufacturer copy-paste)
- [ ] Word count >= 200 for product description body
- [ ] Specs table present (not just prose)
- [ ] User reviews on-page (UGC signals)

### Scoring

| Category | Weight | Criteria |
|----------|--------|----------|
| Schema completeness | 25% | Required + recommended Product fields |
| Title & meta | 15% | Keyword placement, length, format |
| Image optimization | 20% | Alt text, format, sizing, count |
| Content quality | 20% | Unique description, specs, reviews |
| Internal linking | 10% | Breadcrumbs, related products, categories |
| Technical | 10% | Page speed, mobile rendering, canonical |

---

## 2. Google Shopping Intelligence (DataForSEO Merchant API)

Live competitive analysis from Google Shopping results.

### Cost Guardrail (MANDATORY)

Before EVERY Merchant API call:
```bash
python scripts/dataforseo_costs.py check merchant_google_products_search
```

- `"status": "approved"` -- proceed
- `"status": "needs_approval"` -- show cost, ask user
- `"status": "blocked"` -- stop, inform user

After each call:
```bash
python scripts/dataforseo_costs.py log merchant_google_products_search <cost>
```

### Workflow

```bash
# Product search: who sells what at what price
python scripts/dataforseo_merchant.py search "<keyword>" --marketplace google

# Seller analysis: merchant ratings and dominance
python scripts/dataforseo_merchant.py sellers "<keyword>"

# Normalize results for analysis
python scripts/dataforseo_normalize.py results.json --module merchant
```

### Analysis Outputs

#### Pricing Intelligence
- Price distribution: min, max, median, P25, P75
- Price outliers (> 2 standard deviations from median)
- Price-to-rating correlation
- Currency normalization to USD (or user-specified)

#### Seller Landscape
- Top 10 sellers by listing count
- Merchant rating distribution
- Free shipping prevalence
- New vs established sellers

#### Product Listing Quality
- Title keyword patterns in top listings
- Average rating and review count benchmarks
- Image count per listing
- Availability status distribution

Load `references/marketplace-endpoints.md` for full API parameter details.

---

## 3. Amazon Marketplace (DataForSEO)

Cross-marketplace intelligence comparing Google Shopping and Amazon.

### Cost Guardrail (MANDATORY)

```bash
python scripts/dataforseo_costs.py check merchant_amazon_products_search
```

Amazon endpoints are in the `warn_endpoints` set -- always requires user approval.

### Workflow

```bash
# Amazon product search
python scripts/dataforseo_merchant.py search "<keyword>" --marketplace amazon

# Cross-marketplace comparison
python scripts/dataforseo_merchant.py compare "<keyword>"
```

### Cross-Marketplace Report

| Metric | Google Shopping | Amazon |
|--------|---------------|--------|
| Avg price | $ | $ |
| Median rating | X.X | X.X |
| Avg review count | N | N |
| Top seller share | % | % |
| Free shipping % | % | % |

---

## 4. Marketplace Keyword Gaps

Identify mismatches between organic and Shopping visibility.

### Workflow

1. Fetch organic rankings via seo-dataforseo:
   `dataforseo_labs_google_ranked_keywords` for domain
2. Fetch Google Shopping presence via Merchant API:
   `merchant_google_products_search` for top organic keywords
3. Cross-reference results

### Gap Types

| Gap Type | Meaning | Action |
|----------|---------|--------|
| **Organic Only** | Ranks organically but no Shopping ads | Create Google Merchant Center feed, bid on these keywords |
| **Shopping Only** | Shopping visibility but weak/no organic | Create content (buying guides, comparison pages) for these keywords |
| **Both Present** | Visible in both channels | Optimize: ensure price consistency, enhance schema |
| **Neither** | No visibility in either | Low priority unless high volume |

### Output Format

```
## Keyword Gap Analysis: example.com

### Opportunities: Organic → Shopping (12 keywords)
| Keyword | Organic Pos | Volume | CPC | Recommended Action |
|---------|------------|--------|-----|-------------------|

### Opportunities: Shopping → Organic (8 keywords)
| Keyword | Shopping Rank | Volume | CPC | Content Type Needed |
|---------|-------------|--------|-----|-------------------|
```

---

## 5. Product Schema Enhancement

Validate and generate Product schema following Google's current requirements.

### Required Properties (Google Merchant)

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "",
  "image": [""],
  "description": "",
  "brand": { "@type": "Brand", "name": "" },
  "offers": {
    "@type": "Offer",
    "url": "",
    "priceCurrency": "USD",
    "price": "0.00",
    "availability": "https://schema.org/InStock",
    "seller": { "@type": "Organization", "name": "" }
  }
}
```

### Recommended Properties (Enhance Rich Results)

- `sku` -- product identifier
- `gtin13` / `gtin14` / `mpn` -- global trade identifiers
- `aggregateRating` -- star rating + review count
- `review` -- individual reviews (minimum 1)
- `color`, `material`, `size` -- variant attributes
- `shippingDetails` -- ShippingDetails with rate and delivery time
- `hasMerchantReturnPolicy` -- MerchantReturnPolicy with type and days

### Validation Rules

1. `price` must be a number string, not "$29.99" (no currency symbol)
2. `availability` must use full Schema.org URL enum
3. `image` should be array with >= 1 high-res image URL
4. `priceCurrency` must be ISO 4217 (USD, EUR, GBP)
5. `brand.name` must not be empty or "N/A"
6. Dates in `priceValidUntil` must be ISO 8601
7. If `aggregateRating` present: `ratingValue` and `reviewCount` required

### Schema Scoring

| Completeness | Score |
|-------------|-------|
| All required fields | 50/100 |
| + aggregateRating | 65/100 |
| + sku/gtin/mpn | 75/100 |
| + shippingDetails | 85/100 |
| + merchantReturnPolicy | 90/100 |
| + reviews (3+) | 100/100 |

---

## Cross-Skill Integration

| Skill | Integration Point |
|-------|------------------|
| **seo-schema** | Delegates Product schema generation; reuses validation logic |
| **seo-images** | Product image audit (alt text, format, dimensions) |
| **seo-content** | Product description E-E-A-T and uniqueness analysis |
| **seo-dataforseo** | Organic keyword rankings for gap analysis |
| **seo-technical** | Core Web Vitals for product pages (LCP on hero image) |
| **seo-google** | Google Merchant Center feed validation via GSC |

---

## Error Handling

| Error | Cause | Response |
|-------|-------|----------|
| No Product schema found | Page lacks JSON-LD | Analyze page content, generate recommended schema |
| DataForSEO credentials missing | Env vars not set | Run analysis without marketplace data, note limitation |
| Cost check blocked | Daily budget exceeded | Inform user, offer free-only analysis |
| Empty Shopping results | No products for keyword | Suggest broader keyword, check location settings |
| Amazon API timeout | Network/rate limit | Retry with backoff, fall back to Google-only |
| Invalid URL | Malformed input | Validate via `google_auth.validate_url()`, show error |
| Non-product page | URL is category/homepage | Detect page type, suggest `/seo ecommerce schema` instead |

---

## Output Template

```
## E-commerce SEO Report: [URL or Keyword]

### Overall Score: XX/100

### Product Page SEO
- Schema Completeness: XX/100
- Title & Meta: XX/100
- Image Optimization: XX/100
- Content Quality: XX/100
- Internal Linking: XX/100

### Marketplace Intelligence (if DataForSEO available)
- Google Shopping Listings: N products found
- Price Range: $XX - $XX (median: $XX)
- Top Seller: [name] (XX% market share)
- Amazon Comparison: [available/not checked]

### Top Recommendations
1. [Critical] ...
2. [High] ...
3. [Medium] ...

Generate a PDF report? Use `/seo google report`
```
