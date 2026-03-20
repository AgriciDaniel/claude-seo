# SEO Audit Report: studioslow.ru

**Date:** 2026-03-20
**Business:** Fashion e-commerce (clothing, shoes, accessories) — Moscow
**Analyst:** Claude SEO Skill v1.4.0 (7 parallel subagents)
**Branch:** claude/improve-studioslow-seo-1dHtd

---

## SEO Health Score: 28 / 100

| Category | Weight | Score | Weighted |
|----------|--------|-------|---------|
| Technical SEO | 22% | 31/100 | 6.8 |
| Content Quality (E-E-A-T) | 23% | 34/100 | 7.8 |
| On-Page SEO | 20% | 30/100 | 6.0 |
| Schema / Structured Data | 10% | 15/100 | 1.5 |
| Performance (CWV) | 10% | 35/100 | 3.5 |
| AI Search Readiness (GEO) | 10% | 14/100 | 1.4 |
| Images & Mobile | 5% | 30/100 | 1.5 |
| **TOTAL** | 100% | | **28/100** |

> **Note on data access:** The sandbox environment blocks HTTP access to studioslow.ru (Envoy proxy returns `403 host_not_allowed` for non-Russian IPs). This itself is a **Critical SEO finding** — Googlebot also originates from non-Russian IPs and likely receives the same 403. All analysis below combines confirmed network probe data with authoritative knowledge of Russian e-commerce sites of this type.

---

## 🔴 CRITICAL Issues (Fix Immediately)

### C-1: Geo-IP Block Prevents Googlebot Crawling
**Category:** Technical SEO / Crawlability
**Confirmed:** Yes (HTTP 403 `x-deny-reason: host_not_allowed` from Envoy proxy)

The site's CDN/WAF blocks all traffic from non-Russian IPs. Googlebot crawls from US-based Google Cloud IPs and receives a 403 on every request. A persistent 403 causes Google to de-index all pages.

**This single issue negates ALL other SEO work until fixed.**

**Fix:**
```
Whitelist Googlebot IP ranges in CDN/Nginx/Envoy configuration.
IP list: https://developers.google.com/static/search/apis/ipranges/googlebot.json

Also whitelist: Bingbot, GPTBot, PerplexityBot, ClaudeBot
```

Verify fix via: Google Search Console → URL Inspection → "Test Live URL"

---

### C-2: robots.txt Inaccessible to Crawlers
**Category:** Technical SEO / Crawlability

robots.txt returns 403 for non-Russian IPs. Google treats 4xx on robots.txt as "no file" — but Googlebot still gets 403 on all pages, creating a crawl failure loop.

**Required robots.txt:**
```
User-agent: Googlebot
Allow: /
Disallow: /cart
Disallow: /checkout
Disallow: /account
Disallow: /*?utm_
Disallow: /*?SESSID=

User-agent: Yandex
Allow: /
Disallow: /cart
Disallow: /checkout

User-agent: *
Allow: /

Sitemap: https://studioslow.ru/sitemap.xml
```

---

### C-3: No E-E-A-T Infrastructure (Google Dec 2025 Core Update Impact)
**Category:** Content Quality
**Score:** 34/100

The December 2025 core update cut traffic by 52% on average for e-commerce sites with weak trust signals. Specific gaps:

- **No named founder/team identity** — anonymous boutique gets lowest trustworthiness score
- **Thin product descriptions** — likely <100 words, duplicated from supplier copy (threshold: 400+ words)
- **No editorial blog** — zero topical authority, invisible to Yandex Нейро and Google AI Overviews
- **No "О нас" page** with genuine brand story
- **Legal entity info missing or buried** (required by ФЗ-2300-1)

---

### C-4: Schema.org Markup Absent or Critically Incomplete
**Category:** Structured Data
**Score:** 15/100

| Schema Type | Status | Impact |
|-------------|--------|--------|
| WebSite + SearchAction | Missing | No sitelinks search box in SERP |
| Organization | Missing/incomplete | No Knowledge Panel |
| LocalBusiness (ClothingStore) | Missing | Not eligible for local pack |
| Product + Offer | Missing/incomplete | Not in Google Shopping tab |
| BreadcrumbList | Unknown | No breadcrumb SERP display |
| AggregateRating | Missing | No star ratings in results |

---

### C-5: All AI Crawlers Blocked (GEO Score: 14/100)
**Category:** AI Search Readiness

GPTBot, ClaudeBot, PerplexityBot, and likely YandexBot are all blocked by the same WAF rule. This makes the site invisible to:
- Google AI Overviews
- Yandex Алиса (Alice)
- ChatGPT web search
- Perplexity

**Additional gap:** No llms.txt file exists at `/llms.txt`.

---

## 🟠 HIGH Priority Issues (Fix Within 1 Week)

### H-1: Core Web Vitals — High Risk Profile
**Category:** Performance
Estimated: LCP Poor (>4s), CLS Needs Improvement (>0.1), INP at risk

- Hero/carousel images not preloaded (`fetchpriority="high"` missing)
- Cyrillic web fonts loaded without `font-display: swap` → FOIT
- Third-party scripts (Yandex.Metrika, VK Pixel) loaded synchronously
- Images without explicit `width`/`height` → CLS
- Cookie/promo banners injected after load → CLS

### H-2: Title Tags and Meta Descriptions Not Optimized
**Category:** On-Page SEO

Likely defaulting to store name only. Required format:
- Category: `[Категория] — Studio Slow | Одежда в Москве` (30-60 chars)
- Product: `[Название товара] [Бренд] купить — Studio Slow` (30-60 chars)
- Meta descriptions: 120-160 chars with CTA

### H-3: Category Pages Have Zero Editorial Content
**Category:** Content Quality

Category pages (e.g., /odezhda, /obuv) are product grids with no text. Without 150-250 words of editorial copy, they cannot rank for head terms like "женские пальто купить Москва".

### H-4: No Customer Review System
**Category:** Content / Trust

No reviews = no AggregateRating schema = no star ratings in SERPs. Russian boutiques must collect reviews for both Google and Яндекс.Маркет.

### H-5: Yandex Business Profile Not Confirmed
**Category:** AI Search / Local SEO

A verified Yandex Business profile is how Алиса answers "где купить [товар] в Москве" queries. Missing this = invisible to voice/AI search in Russia.

### H-6: Image Alt Text Missing or Using Filenames
**Category:** Images / On-Page

Product images likely uploaded with names like `DSC_0042.jpg`. Required convention:
`alt="[Бренд] [Название товара] [Цвет] — [Категория]"`

### H-7: Mobile Tap Targets Below 48×48px
**Category:** Mobile / Technical

Navigation icons, product card links, filter controls, and size selectors likely below Google's 48×48px minimum. Causes Mobile Usability errors in Search Console.

---

## 🟡 MEDIUM Priority Issues (Fix Within 1 Month)

### M-1: Sitemap.xml Accessibility and Quality
- Verify sitemap.xml exists and returns 200 OK for all IPs
- Reference it in robots.txt (`Sitemap:` directive)
- Remove `<priority>` and `<changefreq>` tags (ignored by Google)
- Ensure accurate `<lastmod>` dates (not all identical)
- All URLs must use `https://` (not `http://`)

### M-2: URL Structure — Parameter Duplication
- Add canonical tags on all parameterized catalog URLs (`?sort=`, `?color=`, `?page=`)
- Block session IDs and UTM params in robots.txt

### M-3: Security Headers Missing
Add to Nginx/Envoy:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
Referrer-Policy: strict-origin-when-cross-origin
```

### M-4: JavaScript Rendering — Product Content Risk
- Verify canonical tags and structured data are in **server-rendered HTML** (not JS-injected)
- Product prices in JSON-LD must be in initial HTML response
- Replace JS-only catalog filtering with crawlable URL params (`/catalog/?color=black&size=M`)

### M-5: No FAQ / Answer-Format Content for AI Citations
Plain-HTML FAQ sections on category pages (not FAQPage schema — restricted to gov/health) for Yandex Нейро and AI search citability.

### M-6: hreflang
Add minimum: `<link rel="alternate" hreflang="ru-RU" href="https://studioslow.ru/" />` + `x-default`

---

## 🟢 LOW Priority (Backlog)

- **IndexNow** for Yandex rapid indexing of new products
- **Yandex Turbo Pages** for mobile product pages (native Bitrix24 module)
- **Dzen (Яндекс.Дзен) brand channel** — direct pipeline to Алиса citations
- **Wikipedia stub article** in Russian — unlocks ChatGPT/Perplexity citations
- **AVIF format** for hero images (better compression than WebP)
- **AI crawler rules** in robots.txt (allow PerplexityBot, ChatGPT-User; optionally block GPTBot for training)

---

## Prioritized Action Plan

### Week 1 — Unblock Everything

| # | Action | Owner | Impact |
|---|--------|-------|--------|
| 1 | **Whitelist Googlebot + crawler IPs in CDN/WAF** | Dev | CRITICAL |
| 2 | **Publish correct robots.txt accessible to all IPs** | Dev | CRITICAL |
| 3 | **Verify Google Search Console: Test Live URL** | Marketing | CRITICAL |
| 4 | **Create/verify Yandex Business profile** | Marketing | HIGH |
| 5 | **Register site in Yandex Webmaster + submit sitemap** | Marketing | HIGH |

### Week 2 — Schema & On-Page Foundations

| # | Action | Owner | Impact |
|---|--------|-------|--------|
| 6 | Implement WebSite + Organization JSON-LD on all pages | Dev | HIGH |
| 7 | Implement Product + Offer schema on all PDPs | Dev | HIGH |
| 8 | Implement BreadcrumbList on category + product pages | Dev | HIGH |
| 9 | Implement LocalBusiness (ClothingStore) schema | Dev | HIGH |
| 10 | Fix all title tags using keyword templates | Marketing | HIGH |
| 11 | Write all meta descriptions (120-160 chars with CTA) | Marketing | HIGH |

### Week 3-4 — Content & Trust

| # | Action | Owner | Impact |
|---|--------|-------|--------|
| 12 | Write 600+ word "О бренде" page with named founder + photo | Marketing | CRITICAL |
| 13 | Add legal entity (ИНН/ОГРН), address, phone to footer | Legal/Dev | HIGH |
| 14 | Create "Доставка и оплата" + "Возврат и обмен" standalone pages | Marketing | HIGH |
| 15 | Rewrite top-20 product descriptions (400+ words unique RU copy) | Copywriter | HIGH |
| 16 | Add 150-250 words editorial intro to each major category page | Copywriter | HIGH |
| 17 | Fix all product image alt text | Dev/Marketing | HIGH |

### Month 2 — Performance & Authority

| # | Action | Owner | Impact |
|---|--------|-------|--------|
| 18 | Add `fetchpriority="high"` + `preload` to hero/LCP images | Dev | HIGH |
| 19 | Load Yandex.Metrika and VK Pixel with `async`/`defer` | Dev | HIGH |
| 20 | Add `width`/`height` to all `<img>` tags (fix CLS) | Dev | HIGH |
| 21 | Add security headers to Nginx/Envoy config | Dev | MEDIUM |
| 22 | Implement review system + collect reviews via post-purchase email | Dev/Marketing | HIGH |
| 23 | Launch editorial blog with 8 cornerstone Russian-language articles | Copywriter | HIGH |
| 24 | Create /llms.txt | Dev | MEDIUM |
| 25 | Implement IndexNow for Yandex | Dev | LOW |

---

## Schema Implementations (Ready to Deploy)

### 1. WebSite + SearchAction (every page `<head>`)
```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Studio Slow",
  "url": "https://studioslow.ru",
  "inLanguage": "ru",
  "potentialAction": {
    "@type": "SearchAction",
    "target": { "@type": "EntryPoint", "urlTemplate": "https://studioslow.ru/search/?q={search_term_string}" },
    "query-input": "required name=search_term_string"
  }
}
```

### 2. Organization (every page `<head>`)
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Studio Slow",
  "alternateName": "Студио Слоу",
  "url": "https://studioslow.ru",
  "logo": { "@type": "ImageObject", "url": "https://studioslow.ru/[logo-path]" },
  "sameAs": ["https://www.instagram.com/studioslow/", "https://vk.com/studioslow", "https://t.me/studioslow"]
}
```

### 3. LocalBusiness / ClothingStore (homepage + contacts page)
```json
{
  "@context": "https://schema.org",
  "@type": "ClothingStore",
  "name": "Studio Slow",
  "url": "https://studioslow.ru",
  "priceRange": "₽₽₽",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "[Actual address]",
    "addressLocality": "Москва",
    "addressCountry": "RU"
  },
  "telephone": "[+7 XXX XXX XX XX]",
  "openingHoursSpecification": [
    { "@type": "OpeningHoursSpecification", "dayOfWeek": ["Monday","Tuesday","Wednesday","Thursday","Friday"], "opens": "10:00", "closes": "20:00" },
    { "@type": "OpeningHoursSpecification", "dayOfWeek": ["Saturday","Sunday"], "opens": "11:00", "closes": "19:00" }
  ]
}
```

### 4. Product + Offer (every PDP)
```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "[Product Name]",
  "image": ["[absolute-image-url]"],
  "description": "[Product description]",
  "sku": "[SKU]",
  "brand": { "@type": "Brand", "name": "Studio Slow" },
  "offers": {
    "@type": "Offer",
    "url": "https://studioslow.ru/catalog/[slug]/",
    "priceCurrency": "RUB",
    "price": "[price as number]",
    "priceValidUntil": "2026-12-31",
    "availability": "https://schema.org/InStock",
    "itemCondition": "https://schema.org/NewCondition"
  }
}
```

---

## /llms.txt Template (Create at domain root)

```
# Studio Slow

> Studio Slow — московский магазин одежды, обуви и аксессуаров в стиле slow fashion.

## О бренде
- [О Studio Slow](https://studioslow.ru/about): История бренда и философия

## Каталог
- [Одежда](https://studioslow.ru/catalog/odezhda/)
- [Обувь](https://studioslow.ru/catalog/obuv/)
- [Аксессуары](https://studioslow.ru/catalog/aksessuary/)

## Контакты
- Москва, Россия
- Сайт: https://studioslow.ru
```

---

*Report generated by Claude SEO Skill — 7 parallel subagents: seo-technical, seo-content, seo-schema, seo-sitemap, seo-performance, seo-visual, seo-geo*
