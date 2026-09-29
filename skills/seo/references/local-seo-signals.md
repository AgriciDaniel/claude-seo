<!-- Updated: 2026-09-23 -->
# Local SEO Ranking Signals & Benchmarks (September 2026)

## Source Key

- **Confirmed**: Google official documentation or employee statements
- **Study**: Data-driven industry research from recognized firms
- **Consensus**: Practitioner agreement without controlled testing
- **Caution**: Single-source or unverified claims

---

## Whitespark 2026 Local Search Ranking Factors

Published November 6, 2025. 47 experts surveyed across 187 factors. (Study)

### Local Pack/Maps Factor Groups

| Factor Group | Weight | Trend |
|---|---|---|
| GBP Signals | **32%** | Stable (top group) |
| Review Signals | **~20%** | Up from ~16% in 2023 |
| On-Page Signals | ~15-19% | Slight decline |
| Link Signals | Declining | Continued multi-year drop |
| Behavioral/Engagement | Rising | Clicks, calls, direction requests |
| Citation Signals | Lower for Pack | But 3 of top 5 AI visibility factors are citation-related |
| Social Signals | New entry | First time measured |
| AI Search Signals | New category | Added for the first time |

### Top 15 Individual Local Pack Factors

1. Primary GBP category (score: 193)
2. Keywords in GBP business title (score: 181)
3. Proximity of address to search point (score: 176)
4. Verified GBP
5. Business open at time of search (Sterling Sky controlled study)
6. High numerical Google ratings
7. Quantity of native Google reviews
8. Additional GBP categories
9. Review recency/velocity
10. Dedicated service pages
11. Domain authority
12. NAP consistency
13. Spam listing removal
14. Quality backlinks
15. Review sentiment

### Top Negative Factors

1. Incorrect primary category (score: 176) -- single worst mistake
2. Duplicate profiles at same address (score: 142)

---

## Search Atlas ML Study (August 2025)

XGBoost regression model, explains 92-93% of variance. (Study)

| Factor | Variance Explained |
|--------|-------------------|
| Proximity | **55.2%** |
| Review Count | **19.2%** |
| Domain Power | 5.9% |
| Semantic Relevance in Reviews | 5.3% |
| All others | <5% each |

---

## Review Benchmarks

### Sterling Sky Findings (2025, Study)

- **Magic 10 threshold**: Significant ranking boost at 10 reviews. 9-to-10 = noticeable increase. 10-to-11 = no similar bump.
- **18-Day Rule**: Rankings "fall off a cliff" if no new reviews for 3 weeks. Velocity > volume.

### BrightLocal LCRS 2026 (February 2026, Study)

| Metric | Value |
|--------|-------|
| Only care about reviews in last 3 months | 74% |
| "Always" read reviews | 41% (up from 29% in 2025) |
| Only use 4.5+ stars | 31% (up from 17% in 2025) |
| Only use 4+ stars | 68% (up from 55% in 2025) |
| Consumers use average review sites | 6 platforms |

### Review Platform Usage (BrightLocal 2026)

| Platform | Usage | Trend |
|----------|-------|-------|
| Google | 71% | Down from 83% in 2025 |
| Instagram | 37% | Rising |
| TikTok | 29% | Rising |
| Apple Maps | 27% | Up from 14% in 2025 |

### Enforcement

- Google blocked/removed **240M+ policy-violating reviews** in 2024 (Confirmed, 40% increase over 2023)
- Review deletion rates up **600%+** Jan-Jul 2025; 38% of deleted were 5-star (Study, GMBapi.com)
- FTC Consumer Review Rule effective Oct 21, 2024: penalties up to **$53,088/violation** (Confirmed, US law; unchanged for 2026 because the 2026 inflation adjustment was cancelled, Federal Register 2026-09-15)
- **Review gating prohibited** by both Google (fake engagement policy) and FTC (Confirmed)

---

## Citation Source Tiers

### Tier 1 (Universal, All Industries)

| Source | Why It Matters |
|--------|---------------|
| Google Business Profile | Primary local signal source |
| Apple Business (formerly Apple Business Connect) | TechRadar/secondary reporting described a new all-in-one platform launched 2026-04-14, 200+ countries (replaces Business Connect / Manager / Essentials), and Apple Maps Ads beginning summer 2026; unverified against Apple primary. ~14% to 27% usage (BrightLocal 2026, secondary). 1B+ iPhone users |
| Bing Places | Overhauled Oct 2025. Powers ChatGPT, Copilot, Alexa. 900M queries/day |
| Facebook | Social + citation signal |
| Yelp | Still ranks on page 1 for many local queries |

### Tier 2 (Broad Directories)

BBB, YellowPages, Manta, Superpages, Foursquare, Nextdoor

### Tier 3 (Data Aggregators)

| Aggregator | Partnerships |
|-----------|-------------|
| Data Axle (formerly Infogroup) | Google, Bing, Apple |
| Foursquare | Merged with Factual. Powers Uber, Nextdoor, Yahoo, ChatGPT. 500M+ devices |
| Neustar/TransUnion Digital | 80+ platform partnerships including Bing, Apple |

### Industry-specific directories: see `local-schema-types.md`

---

## GBP Feature Status (March 2026)

### Deprecated/Removed

| Feature | Date | Replacement |
|---------|------|------------|
| GBP Messaging/Chat | Jul 31, 2024 | None |
| Call History/Tracking | Jul 31, 2024 | None |
| GBP-hosted websites | Historically reported; unverified in this run | Recheck live primary source before advising redirects |
| School reviews/ratings | Apr 30, 2025 | None |
| Q&A (API; public Q&A being phased out) | API discontinued Nov 3, 2025 | Put FAQs on the website; answer questions in reviews and the description |

### Active Features

Posts (with scheduling), Services menu, Attributes (including identity: Women-led, Eco-friendly), Photos/Video, Local Lists (Local Gems, Trending, Top List), AI-generated "Suggest Description", Google Verified badge (replaced Guaranteed/Screened Oct 2025)

### Key GBP Insights

- **Posts**: No direct ranking impact (WebFX empirical testing). Can trigger Post Justifications. (Study)
- **Photos**: "Likely a ranking benefit adding some vs none, but not continued benefit adding more" (WebFX). Geotagging has NO impact. 45% more direction requests with photos. (Study/Confirmed mix)
- **Attributes**: Identity attributes have minor, targeted impact for attribute-specific searches only (WebFX/Sterling Sky). General attributes are filter/informational, NOT direct ranking factors. (Study)

---

## Algorithm Updates Affecting Local (2025-2026)

| Update | Date | Impact | Source |
|--------|------|--------|--------|
| March 2025 Core | Mar 13-27 | Third-party reports: E-E-A-T emphasis, thin/AI content losses | Dates confirmed |
| June 2025 Core | Jun 30-Jul 17 | General quality focus (third-party reading) | Dates confirmed |
| August 2025 Spam | Aug 26-Sep 22 | Google named no target; third-party reports cite keyword stuffing, fake reviews, PBNs, with the Local Pack often stable | Dates confirmed |
| December 2025 Core | Dec 11-29 | Broad core update (rollout confirmed; "impact" is third-party interpretation; Google gave only generic guidance) | Dates confirmed |
| February 2026 Discover Update | Feb 5-27 | Discover-only; favored original/in-depth/local content, reduced clickbait | Dates confirmed |
| March 2026 Spam | Mar 24 (~19.5h) | Fast spam refresh; no local-specific guidance | Dates confirmed |
| March 2026 Core | Mar 27-Apr 8 | First core update of 2026 | Dates confirmed |
| May 2026 Core | May 21-Jun 2 | Second core update of 2026 | Dates confirmed |
| June 2026 Spam | Jun 24-26 | Normal spam update, all languages | Dates confirmed |
| August 2026 Spam | Aug 18-21 | Normal spam update | Dates confirmed |
| September 2026 Spam | Sep 24, active on Sep 28 (up to two weeks) | Normal spam update; Google named no target | Dates confirmed |
| "Diversity Update" | 2025 | Harder to rank in both map pack AND organic simultaneously | Study (Sterling Sky) |

> **Note:** core-update *rollout dates* are Google-confirmed (Search Status Dashboard); the **"Impact" descriptions are third-party interpretation**; Google's only on-record statement for broad core updates is generic ("better surface relevant, satisfying content from all types of sites"). Do not present impact framing as Google fact.

---

Voice search, AI search impact on local, Local Pack structure and proximity: `local-search-behavior.md`.
