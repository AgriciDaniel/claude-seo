# Action Plan: AA Life Insurance SEO
**URL:** https://www.aa.co.nz/insurance/life-insurance/
**Date:** 2026-03-28

---

## CRITICAL — Fix Immediately

### C1: Fix Duplicate H1 Tags
**Impact:** High | **Effort:** Low
- `<h1 class="cmp-title__text">Why consider life insurance?</h1>` must be changed to `<h2>`
- Only one H1 per page — currently "Life Insurance" is the correct primary H1

### C2: Add Schema Markup (BreadcrumbList + FAQPage)
**Impact:** High | **Effort:** Low-Medium
- Add BreadcrumbList JSON-LD (see FULL-AUDIT-REPORT.md for code)
- Add FAQPage JSON-LD for all 5 existing FAQs (see FULL-AUDIT-REPORT.md for code)
- Deploy in `<head>` via AEM component or GTM

### C3: Add Open Graph Image
**Impact:** High | **Effort:** Low
- `<meta property="og:image"/>` is currently empty
- Add the hero family image URL (full absolute URL, min 1200×630px)
- Also add `<meta name="twitter:card" content="summary_large_image">`

---

## HIGH — Fix Within 1 Week

### H1: Improve Title Tag
- Remove trailing whitespace
- Change to: `Life Insurance NZ | AA — Trusted Cover for Your Family`
- Leads with primary keyword, includes NZ geo-modifier

### H2: Fix Canonical URL
- Change: `<link rel="canonical" href="/insurance/life-insurance/"/>`
- To: `<link rel="canonical" href="https://www.aa.co.nz/insurance/life-insurance/"/>`

### H3: Fix Heading Hierarchy
Follow this content outline:
```
H1: Life Insurance NZ (keep existing)
  H2: Why consider life insurance? (currently H1 — demote)
  H2: Why choose AA Life Insurance (currently H3)
  H2: AA Life Insurance Policies (currently H3)
  H2: Frequently Asked Questions (currently H3)
  H2: Our Insurance Partner (currently H3)
```

### H4: Add Premium Range / Pricing Context
- Add a line like "Cover from as little as $X/month — get a quote in under 2 minutes"
- Or add a "How much does life insurance cost?" FAQ entry
- This alone addresses the #1 reason users leave without converting

### H5: Make Trust Badge Visual
- Reader's Digest Most Trusted Brand (8/11 years) is in a footnote
- Move it to a prominent visual badge near the hero or above the fold

---

## MEDIUM — Fix Within 1 Month

### M1: Expand Page Content
- Target 1,200–1,500 words of body content (currently ~700)
- Add sections:
  - "How much life insurance do I need?" (targets 880/mo keyword cluster)
  - "What does life insurance cover in NZ?" (explainer, reduces bounce)
  - "How to apply for life insurance with AA" (reduces friction)

### M2: Add FAQ Content for High-Intent Queries
Add these FAQ questions (also add to FAQPage schema):
- "How much does life insurance cost in NZ?"
- "How much life insurance cover do I need?"
- "What's the difference between life cover and income protection?"
- "Can I get life insurance with a pre-existing condition in NZ?"
- "Is AA life insurance underwritten by Asteron Life?"

### M3: Create llms.txt
Create `https://www.aa.co.nz/llms.txt` with:
```
# AA New Zealand — AI Crawler Access
# https://www.aa.co.nz

## Life Insurance
- https://www.aa.co.nz/insurance/life-insurance/
- https://www.aa.co.nz/insurance/life-insurance/life-cover/
- https://www.aa.co.nz/insurance/life-insurance/funeral-cover/
- https://www.aa.co.nz/insurance/life-insurance/accidental-death/
- https://www.aa.co.nz/insurance/life-insurance/cancer-care/
- https://www.aa.co.nz/insurance/life-insurance/compare-policies/
```

### M4: Allow AI Crawlers in robots.txt
Add to robots.txt:
```
User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /
```

### M5: Add Content Freshness Signals
- Add "Last reviewed: [date]" near page header
- Add WebPage schema with `dateModified`

### M6: Internal Linking Improvements
- Add life insurance link from health insurance page
- Add life insurance link from car insurance page
- Link to blog from main content area (not just nav)
- Link to Connected Care page prominently

### M7: Connected Care — Dedicated Section
- Move Connected Care from its current position to a dedicated H2 section
- Shorten the Teladoc disclaimer to a linked footnote
- Highlight the key benefit: free GP/specialist/mental health access

### M8: Image Optimisation
- Verify alt text on all images (hero, product images)
- Confirm WebP format served via AEM
- Add `loading="lazy"` to below-fold images

---

## LOW — Backlog

### L1: Organization Schema
Add Organization JSON-LD with name, URL, logo, sameAs (Facebook, Instagram)

### L2: InsuranceProduct Schema
Mark up each product (Life Cover, Funeral Cover, etc.) with FinancialProduct schema

### L3: Life Insurance Calculator
Create a separate page: `/insurance/life-insurance/calculator/`
- Targets: "how much life insurance do I need calculator nz"
- High conversion tool that captures mid-funnel traffic
- Competitors like moneyhub.co.nz use these effectively

### L4: Performance Audit
- Run PageSpeed Insights on the page (desktop + mobile)
- Check INP on accordion interactions
- Confirm CLS is within 0.1 threshold

### L5: Investigate Sitemap Coverage
- Confirm all life insurance sub-pages are in the sitemap
- Check lastmod dates are accurate in the sitemap XML

---

## Keyword Targets After Fixes

| Keyword | Volume | Target Position | Timeframe |
|---------|--------|----------------|-----------|
| life insurance nz | 5,400 | Top 5 | 3-6 months |
| aa life insurance | 1,300 | #1 (already branded) | Maintain |
| best life insurance nz | 880 | Top 5 | 3-6 months |
| funeral cover nz | 880 | Top 5 | 2-4 months |
| how much life insurance do i need nz | Est. 200+ | Top 3 | 2-4 months |
| cheap life insurance nz | 260 | Top 10 | 4-6 months |
| life cover nz | 320 | Top 5 | 3-5 months |

---

*Action Plan generated by Claude SEO Skill | 2026-03-28*
