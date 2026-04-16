<!-- Updated: 2026-02-07 -->
# Google SEO Quick Reference (February 2026)

Concise reference guide for subagents. Summarizes key Google Search concepts,
requirements, and best practices. Not a reproduction of Google's documentation;
see Official Documentation Links at the bottom for full details.

---

## How Google Search Works

Google Search operates in three stages: **Crawling** (Googlebot discovers pages by following links and reading sitemaps), **Indexing** (Google processes and stores page content, metadata, and signals in its search index), and **Serving** (when a user searches, Google's algorithms rank indexed pages by relevance, quality, and usability to return the most useful results). Pages must be crawlable and indexable to appear in search results.

---

## Google Search Essentials

Formerly known as "Webmaster Guidelines." Key requirements:

### Technical Requirements
- Pages must be accessible to Googlebot (not blocked by robots.txt or noindex)
- Pages must return HTTP 200 status for indexable content
- Content must be in a format Google can process (HTML preferred, JS-rendered content supported but slower)
- Pages must be served over HTTPS

### Spam Policies
- No cloaking (showing different content to Googlebot vs users)
- No doorway pages (pages created solely to rank for specific queries)
- No hidden text or links
- No keyword stuffing
- No link spam (buying links, excessive link exchanges)
- No scraped or auto-generated content without added value
- No sneaky redirects
- No thin affiliate pages

### Key Best Practices
- Create content for users, not search engines
- Make your site easy to navigate with a clear hierarchy
- Use descriptive, unique titles and meta descriptions per page
- Use heading tags (H1-H6) to structure content logically
- Optimize images with alt text and appropriate file sizes
- Ensure mobile-friendly responsive design
- Improve page load speed (Core Web Vitals)
- Submit an XML sitemap to Google Search Console
- Use structured data (JSON-LD) to help Google understand content

---

## Content Quality Signals

Google evaluates content quality through the E-E-A-T framework:

- **Experience**: Does the content creator have first-hand experience with the topic? (Original photos, personal stories, demonstrated use)
- **Expertise**: Does the creator have relevant knowledge or credentials? (Professional background, technical depth, accurate sourcing)
- **Authoritativeness**: Is the creator or site recognized as a go-to source? (Industry citations, brand mentions, expert recognition)
- **Trustworthiness**: Is the content and site reliable and transparent? (Contact info, secure site, editorial standards, accurate claims)

> **YMYL Note**: "Your Money or Your Life" topics (health, finance, safety, legal) are held to the highest E-E-A-T standards. Inaccurate YMYL content can cause real-world harm, so Google applies stricter quality thresholds.

> **December 2025 Update**: E-E-A-T evaluation now extends to ALL competitive queries, not just YMYL topics. Every page competing for ranking is assessed on these signals.

---

## Core Web Vitals

Measured at the 75th percentile of real user data (field data).

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| **LCP** (Largest Contentful Paint) | ≤ 2.5s | 2.5s – 4.0s | > 4.0s |
| **INP** (Interaction to Next Paint) | ≤ 200ms | 200ms – 500ms | > 500ms |
| **CLS** (Cumulative Layout Shift) | ≤ 0.1 | 0.1 – 0.25 | > 0.25 |

**Key facts:**
- INP replaced FID (First Input Delay) on March 12, 2024. FID was fully removed from all Chrome tools (CrUX API, PageSpeed Insights, Lighthouse) on September 9, 2024. Do NOT reference FID.
- Core Web Vitals are a confirmed ranking signal (since June 2021)
- Field data (CrUX) is preferred over lab data (Lighthouse) for assessment
- Passing all three metrics at "Good" is the target

**Measurement tools:**
- Google PageSpeed Insights (field + lab data)
- Chrome User Experience Report (CrUX): field data
- Lighthouse (lab data only)
- Google Search Console Core Web Vitals report

---

## Structured Data Best Practices

- **JSON-LD is Google's preferred format** (over Microdata and RDFa)
- Place JSON-LD in `<script type="application/ld+json">` tags in the `<head>` or `<body>`
- Always include `@context` and `@type` properties
- **Required properties** must be present for rich result eligibility
- **Recommended properties** improve rich result quality but aren't mandatory
- Only mark up content that is visible on the page
- Use Google's Rich Results Test to validate before deployment
- Do not mark up content that is misleading or hidden from users
- Keep schema current: update when page content changes

### Deprecated/Restricted Types (as of Feb 2026)
- **HowTo**: Rich results removed (September 2023)
- **FAQ**: Restricted to government and healthcare authority sites (August 2023)
- **SpecialAnnouncement**: Deprecated (July 31, 2025)
- **CourseInfo, EstimatedSalary, LearningVideo**: Retired (June 2025)
- **ClaimReview**: Retired (June 2025)
- **VehicleListing**: Retired (June 2025)

---

## Common Penalties & How to Avoid Them

### Manual Actions
Google Search Console notifications for violations. Common causes:
- **Unnatural links** (buying/selling links): Disavow bad links, request reconsideration
- **Thin content**: Add substantial unique value to affected pages
- **Cloaking/sneaky redirects**: Remove deceptive serving, request reconsideration
- **User-generated spam**: Moderate comments/forums, add nofollow to user links
- **Structured data issues**: Fix misleading or spam markup

### Algorithmic Demotions
No manual notification, detected through ranking drops. Common causes:
- **Helpful Content System**: Merged into Google's core ranking in March 2024: no longer a standalone system. Helpfulness signals are now evaluated within every core update. Low-value, AI-generated, or unhelpful content at scale still triggers demotions via core updates.
- **Core Updates**: Broad quality reassessment across all signals
- **Spam Updates**: Automated detection of spam patterns
- **Link Spam Updates**: Devaluation of manipulative link patterns

### Recovery Steps
1. Identify the issue (Search Console, ranking timeline analysis)
2. Fix the root cause (remove spam, improve content, clean links)
3. For manual actions: submit reconsideration request via Search Console
4. For algorithmic: improve quality, wait for next core update reassessment
5. Monitor recovery in Search Console performance reports

---

## Official Documentation Links

- [Google Search Essentials](https://developers.google.com/search/docs/essentials)
- [How Google Search Works](https://developers.google.com/search/docs/fundamentals/how-search-works)
- [Structured Data Overview](https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data)
- [Rich Results Test](https://search.google.com/test/rich-results)
- [Core Web Vitals Report](https://support.google.com/webmasters/answer/9205520)
- [PageSpeed Insights](https://pagespeed.web.dev/)
- [Search Console Help](https://support.google.com/webmasters)
- [Manual Actions Report](https://support.google.com/webmasters/answer/9044175)
- [Google Search Status Dashboard](https://status.search.google.com/)
- [Google Search Central Blog](https://developers.google.com/search/blog)
- [Spam Policies](https://developers.google.com/search/docs/essentials/spam-policies)
- [E-E-A-T and Quality Rater Guidelines](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)

> **Mobile-first indexing** is 100% complete as of July 5, 2024. Google now crawls and indexes ALL websites exclusively with the mobile Googlebot user-agent.
