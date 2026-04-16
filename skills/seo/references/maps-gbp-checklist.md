<!-- Updated: 2026-03-23 -->
# GBP Profile Completeness Checklist (Via API)

This checklist scores a Google Business Profile using data retrieved from
the DataForSEO My Business Info API. It measures profile completeness on
the maps PLATFORM, not on-page signals (seo-local handles on-page).

## Sources

- Google official: https://support.google.com/business/answer/7091
- Whitespark 2026 Local Search Ranking Factors (Study)
- BrightLocal LCRS 2026 (Study)

---

## Scoring System

Each field: **Present + Optimized = 2pts**, **Present = 1pt**, **Missing = 0pts**

Total possible: 50 points. Normalize to 0-100 scale: `(score / 50) * 100`

---

## Critical Fields (Direct Ranking Impact)

| # | Field | Points | Optimized Criteria |
|---|-------|--------|-------------------|
| 1 | **Primary category** | 2 | Most specific subtype for industry (e.g., "Cosmetic Dentist" not "Dentist") |
| 2 | **Additional categories** | 2 | 3-5 relevant categories (optimal: 4 additional per BrightLocal) |
| 3 | **Business name** | 2 | Matches real-world name exactly (no keyword stuffing) |
| 4 | **Physical address** | 2 | Complete, matches website NAP |
| 5 | **Phone number** | 2 | Local number (not toll-free), matches website |
| 6 | **Website URL** | 2 | Points to correct page (not strongest page -- Diversity Update risk) |
| 7 | **Business hours** | 2 | Complete with special/holiday hours. Open-at-search-time = factor #5 |
| 8 | **Verified status** | 2 | Google Verified badge active |

**Subtotal: 16 points (8 fields)**

---

## Important Fields (Significant Influence)

| # | Field | Points | Optimized Criteria |
|---|-------|--------|-------------------|
| 9 | **Business description** | 2 | 250-750 chars, includes primary service + location keywords naturally |
| 10 | **Services list** | 2 | All core services listed with descriptions |
| 11 | **Products** | 2 | Key products/services with prices (if applicable) |
| 12 | **Photos** | 2 | 10+ photos across types: logo, cover, interior, exterior, team, products |
| 13 | **Photo recency** | 2 | Photos uploaded within last 30 days |
| 14 | **Attributes** | 2 | Relevant attributes set (accessibility, payments, amenities, identity) |
| 15 | **Service areas** | 2 | Defined for SABs, up to 20 areas (cities or zip codes) |
| 16 | **Menu/services link** | 2 | Menu URL (restaurants) or services URL (others) |

**Subtotal: 16 points (8 fields)**

---

## Supplementary Fields (Supporting Signals)

| # | Field | Points | Optimized Criteria |
|---|-------|--------|-------------------|
| 17 | **Google Posts** | 2 | Active posting (1+/week). Types: update, offer, event, product |
| 18 | **Post recency** | 2 | Post within last 7 days |
| 19 | **Booking link** | 2 | Appointment/reservation URL configured |
| 20 | **Social profiles** | 2 | Linked via `sameAs` or GBP social links |
| 21 | **Logo** | 2 | High-quality square logo uploaded |
| 22 | **Cover photo** | 2 | On-brand, high-resolution cover image |
| 23 | **Videos** | 2 | At least 1 video uploaded |
| 24 | **Owner responses** | 2 | Responding to reviews (target: 80%+ response rate) |
| 25 | **Q&A engagement** | 2 | FAQ content on website (GBP Q&A deprecated Dec 2025) |

**Subtotal: 18 points (9 fields)**

---

## Industry-Specific Weight Adjustments

When scoring, apply multipliers to fields that matter more for specific industries:

### Restaurant
- Menu/services link: **x2** (critical for food-related searches)
- Photos: **x1.5** (food photos drive engagement)
- Booking link: **x1.5** (reservation systems expected)
- Attributes: **x1.5** (dietary, dine-in/takeout/delivery critical)

### Healthcare
- Business hours: **x1.5** (patients need accurate hours)
- Attributes: **x1.5** (insurance, accessibility, telehealth)
- Services list: **x2** (insurance and procedure matching)

### Legal
- Business description: **x1.5** (practice area clarity)
- Services list: **x2** (practice area matching drives visibility)
- Photos: **x0.5** (less impactful for legal)

### Home Services
- Service areas: **x2** (SAB model depends on this)
- Business hours: **x1.5** (emergency availability)
- Photos: **x1.5** (before/after project photos)

### Real Estate
- Photos: **x2** (property photos critical)
- Social profiles: **x1.5** (agent branding)
- Posts: **x1.5** (listing updates)

### Automotive
- Products: **x2** (vehicle inventory)
- Photos: **x2** (vehicle photos)
- Services list: **x1.5** (sales + service departments)

### Re-normalization After Multipliers

After applying industry multipliers, re-normalize so the total remains 0-100:
```
final_score = (weighted_raw_score / max_possible_weighted_score) * 100
```
This ensures consistent scoring regardless of which industry multipliers are active.

---

## Score Interpretation

| Score | Rating | Action |
|-------|--------|--------|
| 90-100 | Excellent | Maintain posting cadence and photo freshness |
| 75-89 | Good | Fill remaining gaps in supplementary fields |
| 50-74 | Needs Work | Missing important fields, address Critical + Important gaps |
| 25-49 | Poor | Major profile gaps hurting visibility. Prioritize Critical fields |
| 0-24 | Critical | Profile barely exists or unclaimed. Start with verification + Critical fields |

---

## Data Mapping (DataForSEO → Checklist)

| Checklist Field | DataForSEO My Business Info Field |
|----------------|----------------------------------|
| Primary category | `category` |
| Additional categories | `additional_categories` |
| Business name | `title` |
| Address | `address_info` |
| Phone | `contact_info` (type: phone) |
| Website | `domain`, `url` |
| Hours | `work_hours` |
| Description | `description` |
| Services | (separate API or attributes) |
| Photos | `photos_count`, `main_image` |
| Attributes | `attributes` (grouped by type) |
| Popular times | `popular_times` |
| Posts | My Business Updates API |
| Verified status | Not directly exposed — infer from profile completeness + Maps SERP presence, or flag as "Unknown (manual check required)" |
