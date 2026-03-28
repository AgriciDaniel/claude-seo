# SEO Audit Report: AA Life Insurance
**URL:** https://www.aa.co.nz/insurance/life-insurance/
**Audit Date:** 2026-03-28
**Business Type:** Financial Services — Personal Insurance (Life Insurance hub page)
**Underwriter:** Asteron Life Limited

---

## SEO Health Score: 52 / 100

| Category | Weight | Score | Weighted |
|----------|--------|-------|---------|
| Technical SEO | 22% | 62/100 | 13.6 |
| Content Quality | 23% | 60/100 | 13.8 |
| On-Page SEO | 20% | 62/100 | 12.4 |
| Schema / Structured Data | 10% | 10/100 | 1.0 |
| Performance (CWV) | 10% | 60/100 | 6.0 |
| AI Search Readiness | 10% | 35/100 | 3.5 |
| Images | 5% | 45/100 | 2.25 |
| **TOTAL** | **100%** | | **52 / 100** |

---

## Executive Summary

AA Life Insurance is one of NZ's most recognised brands with a powerful domain (NZ rank #115, 108,246 organic keywords, ~498K estimated organic visits/mo). However, the `/insurance/life-insurance/` hub page is **not ranking on page 1** for its most valuable keyword — "life insurance nz" (5,400 searches/mo, CPC $21.61) — despite being outspent and outranked by smaller competitors including moneyhub.co.nz, southerncrosslife.co.nz and onechoice.co.nz.

The root causes are clear: **zero structured data**, **duplicate H1 tags**, **thin content depth**, **missing OG image**, and **no AI search optimisation**. These are all fixable within weeks.

### Top 5 Critical Issues
1. No schema markup anywhere on the life insurance section (no FAQPage, no BreadcrumbList, no InsuranceProduct)
2. Duplicate H1 tags — two `<h1>` elements render simultaneously
3. Missing Open Graph image — `<meta property="og:image"/>` is empty, breaking social sharing
4. Relative canonical URL — should be absolute (`https://www.aa.co.nz/insurance/life-insurance/`)
5. Not ranking page 1 for "life insurance nz" (5,400/mo) — all visible competitors are non-AA

### Top 5 Quick Wins
1. Add FAQPage schema to the 5 existing FAQs (immediate rich result eligibility for AI/LLM citations)
2. Fix canonical to absolute URL
3. Add OG image
4. Fix duplicate H1 — demote "Why consider life insurance?" to H2
5. Add BreadcrumbList schema (already has visible breadcrumb: Home > Insurance > Life Insurance)

---

## Domain Context (Semrush NZ Database)

| Metric | Value |
|--------|-------|
| NZ Organic Rank | #115 |
| Organic Keywords | 108,246 |
| Est. Organic Traffic | 498,003/mo |
| Organic Cost Value | $326,245 |
| Paid Keywords | 740 |

The domain is strong. The life insurance section is underperforming relative to the domain's authority.

---

## Keyword Landscape

| Keyword | Volume (NZ) | CPC | Competition | AA Ranking |
|---------|------------|-----|-------------|------------|
| life insurance nz | 5,400 | $21.61 | 0.89 | Not page 1 |
| aa life insurance | 1,300 | $8.11 | 0.78 | #1 (branded) |
| best life insurance nz | 880 | $19.95 | 0.86 | Not confirmed |
| funeral cover nz | 880 | $12.41 | 0.84 | Not confirmed |
| life insurance new zealand | 320 | $17.15 | 0.43 | Not confirmed |
| life cover nz | 320 | $16.63 | 0.67 | Not confirmed |
| cheap life insurance nz | 260 | $16.84 | 0.89 | Not confirmed |
| cancer insurance nz | 40 | $5.23 | 0.88 | Not confirmed |

**Page 1 for "life insurance nz" is held by:** southerncrosslife.co.nz, nzseniors.co.nz, onechoice.co.nz, momentumlife.co.nz, mas.co.nz, kiwicover.co.nz, chubb.com, moneyhub.co.nz, anz.co.nz, comparenow.co.nz.

With a CPC of $21.61, "life insurance nz" represents significant organic value. AA's domain authority is sufficient to rank — the gap is content depth and structured data.

---

## Technical SEO

### Crawlability & Indexability

| Check | Status | Notes |
|-------|--------|-------|
| robots.txt | ✅ Pass | Properly configured; disallows `/content/experience-fragments/`; sitemap declared |
| Sitemap | ✅ Present | `https://www.aa.co.nz/sitemap.xml` → redirects to `/content/nzaa/nz/en.sitemap.xml` |
| Canonical tag | ⚠️ Relative | `<link rel="canonical" href="/insurance/life-insurance/"/>` — should be absolute |
| HTTPS | ✅ Pass | Site served over HTTPS |
| Robots meta | ✅ Pass | No noindex/nofollow directives detected on page |
| Internal linking | ✅ Good | 9-item life insurance sub-nav, breadcrumb present |
| Redirects | ✅ Pass | No redirect chains detected on target URL |
| AI crawler access | ⚠️ Unknown | robots.txt disallows SemrushBot; no explicit rules for GPTBot/ClaudeBot/PerplexityBot |

### Issues Found

**[High] Relative canonical URL**
`<link rel="canonical" href="/insurance/life-insurance/"/>` should be `https://www.aa.co.nz/insurance/life-insurance/`. Relative canonicals are technically supported but absolute is best practice and prevents edge cases with proxy/CDN serving.

**[High] robots.txt blocks SemrushBot entirely**
While not a Google ranking factor, this prevents third-party SEO monitoring. Consider whether this is intentional.

**[Medium] No explicit AI crawler directives**
GPTBot, ClaudeBot, and PerplexityBot are not mentioned in robots.txt. Given the financial services content (high E-E-A-T value for AI citations), explicitly allowing these crawlers is recommended.

**[Medium] No llms.txt file**
`https://www.aa.co.nz/llms.txt` returns a 404. This emerging standard helps AI models understand site structure and content permissions.

---

## On-Page SEO

### Page Elements

| Element | Current | Assessment |
|---------|---------|------------|
| Title tag | "Trusted Life Insurance for Your Family " | Trailing space; keyword present but no brand; 50 chars |
| Meta description | "Protect your whānau with one of the most trusted life insurance brands in NZ. Get 24/7 medical support, financial security & a smoother tomorrow. Get a quote." | 161 chars — good length, includes CTA |
| H1 | "Life Insurance" | Correct — one main H1 |
| Second H1 | "Why consider life insurance?" | **Duplicate H1 — critical structural issue** |
| H2 usage | Accordion/nav items | H2s used for mobile nav — no content H2s |
| H3 usage | Section headers | Correct usage for sub-sections |
| URL | `/insurance/life-insurance/` | Clean, keyword-rich, correct |
| Breadcrumb | Home > Insurance > Life Insurance | Visible but no BreadcrumbList schema |
| OG title | "Life Insurance" | Short but acceptable |
| OG description | Present | Good |
| OG image | **Empty** | `<meta property="og:image"/>` — no image URL |
| Twitter card | Not detected | Missing |

### Issues Found

**[Critical] Duplicate H1 tags**
Both `<h1 class="h1-style">Life Insurance</h1>` and `<h1 class="cmp-title__text">Why consider life insurance?</h1>` render in the DOM. This confuses Google about the page's primary topic. Demote the second to `<h2>`.

**[High] Title tag trailing whitespace**
"Trusted Life Insurance for Your Family " has a trailing space. Fix in CMS.

**[High] Title tag could lead with primary keyword**
Current: "Trusted Life Insurance for Your Family"
Recommended: "Life Insurance NZ | AA — Trusted Cover for Your Family"
Leads with the high-value keyword, includes "NZ" geo-modifier, retains brand signal.

**[High] Missing OG image**
Social shares of this page will render with no image, significantly reducing click-through from Facebook, LinkedIn, and WhatsApp shares. Add the hero family image as the OG image (minimum 1200×630px).

**[Medium] No Twitter/X card meta tags**
Add `<meta name="twitter:card" content="summary_large_image">` and related tags.

**[Medium] H2 heading hierarchy broken**
All H2 elements in the source are navigation accordion items, not content headings. The content sections (e.g., "Why consider life insurance?", "Why choose AA Life Insurance", "AA Life Insurance Policies") use H1/H3 instead of H2. This creates a non-sequential heading outline that harms accessibility and SEO context signals.

Recommended heading outline:
```
H1: Life Insurance NZ
  H2: Why consider life insurance?
  H2: Why choose AA Life Insurance
    H3: Quick | Simple | Trusted | Supportive
  H2: AA Life Insurance Policies
    H3: Life Cover
    H3: Funeral Cover
    H3: Accidental Death
    H3: Cancer Care
  H2: Frequently Asked Questions
    H3: [FAQ items]
  H2: Our Insurance Partner
```

---

## Content Quality (E-E-A-T Assessment)

### Strengths

- **Experience:** 11-year track record explicitly mentioned; Reader's Digest Most Trusted Brand 8/11 years
- **Expertise:** Fitch A+ financial strength rating for Asteron Life; NZ-based team; Financial Advice Provider disclosure
- **Authoritativeness:** AA is a household brand in NZ; 1.3K branded searches/mo for "aa life insurance"
- **Trustworthiness:** Privacy policy and Asteron Life privacy statement linked; financial adviser disclaimer present; complaint process linked; clear T&Cs footnotes

### Content Gaps (E-E-A-T Weaknesses)

**[High] No pricing or premium range information**
Competitors like southerncrosslife.co.nz, momentumlife.co.nz, and onechoice.co.nz show pricing prominently. Google's QRG rewards pages that help users make decisions. Users searching "life insurance nz" want to understand cost before clicking "Get a quote." Even a "from $X/month" or a premium calculator would close this gap.

**[High] No customer testimonials or reviews on this page**
The Reader's Digest award is mentioned in a footnote, but no actual customer reviews, star ratings, or testimonials appear above the fold or in the main content. Competitors leverage social proof heavily.

**[High] Thin content depth (~700 words)**
The page body contains approximately 700 words of unique content (excluding nav/footer). Top-ranking competitors for "life insurance nz" typically have 1,200–2,500 words covering: what life insurance is, who needs it, how much cover, types of cover, exclusions, how to choose, and the application process. AA has a /blog and individual product pages — the hub page needs to be the definitive guide, not just a product selector.

**[Medium] No publication/review date**
Financial advice content should clearly display when it was last reviewed. Google's E-E-A-T evaluation for YMYL (Your Money or Your Life) content rewards recently reviewed/updated pages.

**[Medium] No named author or reviewer**
Even a generic "Reviewed by AA Life Insurance team" or a named financial advisor reviewer would signal expertise to Google.

**[Medium] "Connected Care" section lacks clear explanation**
The Teladoc Health partnership is a strong differentiator but is buried below the fold with a footnote disclaimer that's longer than the feature description. Elevate this as a competitive advantage with a dedicated H2 section.

---

## Schema / Structured Data

**Current implementation: NONE**

No JSON-LD, Microdata, or RDFa detected anywhere on the page.

| Schema Type | Priority | Benefit |
|-------------|----------|---------|
| BreadcrumbList | High | Rich breadcrumbs in SERPs; already has visible breadcrumb |
| FAQPage | High | AI/LLM citation eligibility; note: no Google rich result for commercial sites (Aug 2023 restriction) |
| InsuranceProduct / FinancialProduct | Medium | Emerging product markup for financial services |
| Organization | Medium | Knowledge panel, trust signals |
| WebPage + dateModified | Medium | Freshness signal for YMYL content |

### Recommended JSON-LD: BreadcrumbList

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.aa.co.nz/"},
    {"@type": "ListItem", "position": 2, "name": "Insurance", "item": "https://www.aa.co.nz/insurance/"},
    {"@type": "ListItem", "position": 3, "name": "Life Insurance", "item": "https://www.aa.co.nz/insurance/life-insurance/"}
  ]
}
```

### Recommended JSON-LD: FAQPage (5 existing FAQs)

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "How long does the application process take?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "The application takes between 15 - 30 minutes to complete online."
      }
    },
    {
      "@type": "Question",
      "name": "Can I add a beneficiary to my policy?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "You can add a beneficiary as part of the application process, or if you'd like to add one later, you can do so by completing the Beneficiary Form on our website, or getting in touch with us."
      }
    },
    {
      "@type": "Question",
      "name": "Can I apply for life insurance if I have a disease, an illness, or I am overweight?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "You may be able to, but the terms of your policy may be changed. For instance, a premium loading may apply. Any exclusions or premium loadings are made clear to you as part of the application process."
      }
    },
    {
      "@type": "Question",
      "name": "If I give up smoking, will my premium decrease?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "If you have been smoke-free for 12 months, you may be eligible for a premium decrease. Please contact us to discuss your individual situation."
      }
    },
    {
      "@type": "Question",
      "name": "Do I need to complete a medical check, or disclose further medical information?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "We'll ask you to answer the questions we need to know now. We won't need you to follow up with further medical information or complete any medical checks."
      }
    }
  ]
}
```

> **Note:** FAQPage schema on commercial insurance pages no longer triggers Google FAQ rich results (Aug 2023 restriction). However, it **does** significantly improve citability in ChatGPT, Perplexity, and Google AI Overviews — high value for a YMYL query like "life insurance nz".

---

## Performance (Core Web Vitals)

Live CWV measurement requires Lighthouse/CrUX access which is unavailable in this audit. The following is an assessment based on page structure:

| Signal | Assessment | Notes |
|--------|------------|-------|
| LCP risk | Medium | Hero image above fold; likely AEM-optimised, but large family photo |
| INP risk | Medium | Multiple accordion interactions; keyboard_arrow_down JS handlers |
| CLS risk | Low-Medium | Font loading, accordion expansion could cause layout shift |
| Third-party scripts | High risk | Google Analytics, GA4, multiple `_gl=` tracking parameters in links suggest GTM with conversion tracking |
| Page weight | Medium | Enterprise AEM CMS typically adds template overhead |

**Recommendation:** Run PageSpeed Insights (desktop + mobile) and Chrome UX Report for `aa.co.nz/insurance/life-insurance/` to get actual field data.

---

## Images

| Check | Finding |
|-------|---------|
| Hero image | Present (young family outside home) |
| Alt text (hero) | Not confirmed from markdown scrape — verify in CMS |
| OG image | **Missing** — `<meta property="og:image"/>` is empty |
| Product images | Present for Life Cover, Funeral Cover, Accidental Death, Cancer Care sections |
| Image formats | Unknown — verify WebP/AVIF serving for AEM-hosted images |
| Lazy loading | Unknown — verify `loading="lazy"` on below-fold images |
| Image file names | Appear to use CMS asset paths (`/content/dam/nzaa/...`) — not keyword-optimised |

**[High]** Add OG image immediately. This is the single highest-impact social/sharing fix on the page.

---

## AI Search Readiness (GEO)

| Signal | Status | Notes |
|--------|--------|-------|
| llms.txt | ❌ Missing | 404 — not implemented |
| GPTBot in robots.txt | ⚠️ Not specified | Not allowed or disallowed explicitly |
| ClaudeBot in robots.txt | ⚠️ Not specified | Not allowed or disallowed explicitly |
| PerplexityBot in robots.txt | ⚠️ Not specified | Not allowed or disallowed explicitly |
| FAQPage schema | ❌ Missing | Would improve AI Overview and ChatGPT citation odds |
| Passage-level citability | ⚠️ Partial | FAQs are cite-able; product comparisons are not structured for extraction |
| Brand mention signals | ✅ Strong | "Reader's Digest Most Trusted Brand" explicit claim; Fitch A+ cited |
| Definitive answer content | ⚠️ Partial | FAQs answer process questions but not "how much does life insurance cost in NZ" |

### Key AI Search Gap

When users ask ChatGPT or Perplexity "what is the best life insurance in New Zealand?", AA is unlikely to be cited because:
1. No FAQPage schema for structured extraction
2. No llms.txt to signal content permissions
3. Content doesn't directly answer comparative research questions ("how much does life insurance cost?", "what life insurance do I need?")

**Adding FAQs that answer these high-intent questions** (with FAQPage schema) is the highest-impact AI search action.

---

## Sitemap Analysis

- Sitemap declared in robots.txt: ✅ `https://www.aa.co.nz/sitemap.xml`
- Sitemap index redirects to: `https://www.aa.co.nz/content/nzaa/nz/en.sitemap.xml`
- Full sitemap content was too large to enumerate (~249K characters)
- Confirm life insurance section pages are included: `/insurance/life-insurance/`, `/insurance/life-insurance/life-cover/`, `/insurance/life-insurance/funeral-cover/`, `/insurance/life-insurance/accidental-death/`, `/insurance/life-insurance/cancer-care/`

---

## Competitor Intelligence

Page 1 for "life insurance nz" (5,400/mo) is dominated by:

| Domain | Type | Advantage vs AA |
|--------|------|-----------------|
| southerncrosslife.co.nz | Direct insurer | Deep content, pricing transparency |
| moneyhub.co.nz | Comparison/editorial | High-quality "best life insurance NZ" guide |
| onechoice.co.nz | Broker/comparison | Comparison tables, multiple product reviews |
| momentumlife.co.nz | Direct insurer | Pricing upfront, strong schema |
| anz.co.nz | Bank + insurer | Brand authority + financial trust |
| mas.co.nz | Direct insurer | Specialist market positioning |
| kiwicover.co.nz | Broker | Comparison-optimised content |

**AA's competitive advantages that are under-leveraged:**
- Reader's Digest Most Trusted Brand (8/11 years) — bury in a footnote vs. a prominent badge
- Connected Care (Teladoc Health) — unique benefit not offered by most competitors
- 108K+ organic keyword domain — internal linking power
- Physical AA Centres — trust signal not used in life insurance context
- Existing 1.3K branded searches/mo for "aa life insurance"

---

## Internal Linking Assessment

**Strengths:**
- Life insurance sub-nav (9 items) appears in header on all insurance pages
- Compare Policies page linked from main content
- Product pages linked with descriptive anchor text

**Gaps:**
- Blog (`/insurance/life-insurance/blog/`) not linked from main content area
- No internal links from other high-traffic AA pages (e.g., health insurance, car insurance) pointing to life insurance section
- "About AA Life" page exists (`/insurance/life-insurance/about-aa-life/`) but not surfaced in main content

---

## Summary Findings by Priority

### Critical (Fix Immediately)

| # | Issue | Location |
|---|-------|---------|
| C1 | Duplicate H1 tags | `<h1>Why consider life insurance?</h1>` — demote to H2 |
| C2 | Zero schema markup | Add BreadcrumbList + FAQPage JSON-LD |
| C3 | Missing OG image | Add `og:image` meta tag |

### High (Fix Within 1 Week)

| # | Issue |
|---|-------|
| H1 | Title tag: remove trailing space, lead with "Life Insurance NZ" |
| H2 | Relative canonical → absolute canonical URL |
| H3 | Add Twitter/X card meta tags |
| H4 | Fix heading hierarchy (H1→H2→H3 content outline) |
| H5 | Add pricing/premium range context (even "from $X/month" or quote range) |
| H6 | Add customer reviews or Reader's Digest badge as a prominent visual element |

### Medium (Fix Within 1 Month)

| # | Issue |
|---|-------|
| M1 | Expand page content to 1,200+ words covering: what life insurance is, who needs it, how much cover, types, exclusions, how to apply |
| M2 | Add "last reviewed" date and named reviewer byline |
| M3 | Create llms.txt at `https://www.aa.co.nz/llms.txt` |
| M4 | Explicitly allow GPTBot, ClaudeBot, PerplexityBot in robots.txt |
| M5 | Add more FAQs targeting high-intent queries: "how much life insurance do I need?", "how much does life insurance cost in NZ?", "what's the difference between life cover and income protection?" |
| M6 | Add InsuranceProduct or FinancialProduct schema for each product |
| M7 | Verify image alt text for hero and product images |
| M8 | Verify WebP format delivery for all images |
| M9 | Elevate Connected Care to a dedicated H2 section with its own content block |
| M10 | Add cross-links from car insurance, health insurance pages to life insurance |

### Low (Backlog)

| # | Issue |
|---|-------|
| L1 | Add Organization schema with sameAs social profile links |
| L2 | Implement WebPage schema with dateModified for freshness signalling |
| L3 | Keyword-optimise image file names in DAM where possible |
| L4 | Test INP on accordion interactions with Chrome DevTools |
| L5 | Explore a "life insurance calculator" tool page to capture mid-funnel "how much life insurance do I need" searches |

---

## Projected Impact of Fixes

| Fix Cluster | Estimated Outcome |
|-------------|-------------------|
| Fix C1+H4 (heading structure) | Improved relevance signals for "life insurance nz" and related queries |
| Add BreadcrumbList + FAQPage schema | Sitelinks + AI Overview citation eligibility |
| Fix title tag (H1) | Potential +10-15% CTR improvement from SERPs |
| Add OG image (C3) | Social sharing click-through rates restored |
| Content expansion to 1,200+ words (M1) | Improved topical coverage; better match for informational "life insurance nz" queries |
| Add FAQ content targeting cost/coverage questions (M5) | Capture "best life insurance nz" (880/mo) and "cheap life insurance nz" (260/mo) |
| All combined | Realistic target: top 5 for "life insurance nz" within 3-6 months |

---

*Report generated by Claude SEO Skill | aa.co.nz/insurance/life-insurance/ | 2026-03-28*
