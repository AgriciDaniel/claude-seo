<!-- Updated: 2026-06-21 -->
# Schema.org Types: Status & Recommendations (May 2026)

**Schema.org Version:** 30.0 (2026-03-19)

## Format Preference
Always use **JSON-LD** (`<script type="application/ld+json">`).
Google's documentation explicitly recommends JSON-LD over Microdata and RDFa.

**AI Search Note:** Do not claim a confirmed schema uplift for AI-generated answers without a cited primary source.

---

## Active: Recommend freely

| Type | Use Case | Key Properties |
|------|----------|----------------|
| Organization | Company info | name, url, logo, contactPoint, sameAs |
| LocalBusiness | Physical businesses | name, address, telephone, openingHours, geo, priceRange |
| SoftwareApplication | Desktop/mobile apps | name, operatingSystem, applicationCategory, offers, aggregateRating |
| WebApplication | Browser-based SaaS | name, applicationCategory, offers, browserRequirements, featureList |
| Product | Physical/digital products | name, image, description, sku, brand, offers, review |
| Offer | Pricing | price, priceCurrency, availability, url, validFrom |
| Service | Service businesses | name, provider, areaServed, description, offers |
| Article | Blog posts, news | headline, author, datePublished, dateModified, image, publisher |
| BlogPosting | Blog content | Same as Article + blog-specific context |
| NewsArticle | News content | Same as Article + news-specific context |
| Review | Individual reviews | reviewRating, author, itemReviewed, reviewBody |
| AggregateRating | Rating summaries | ratingValue, reviewCount, bestRating, worstRating |
| BreadcrumbList | Navigation | itemListElement with position, name, item |
| WebSite | Site-level | name, url, potentialAction (SearchAction is machine-readable only; no Google sitelinks search box benefit) |
| WebPage | Page-level | name, description, datePublished, dateModified |
| Person | Author/team | name, jobTitle, url, sameAs, image, worksFor |
| ContactPage | Contact pages | name, url |
| VideoObject | Video content | name, description, thumbnailUrl, uploadDate, duration, contentUrl |
| ImageObject | Image content | contentUrl, caption, creator, copyrightHolder |
| Event | Events | name, startDate, endDate, location, organizer, offers |
| JobPosting | Job listings | title, description, datePosted, hiringOrganization, jobLocation |
| Course | Educational content | name, description, provider, hasCourseInstance |
| DiscussionForumPosting | Forum threads | headline, author, datePublished, text, url |
| ProductGroup | Variant products | name, productGroupID, variesBy, hasVariant |
| ProfilePage | Author/creator profiles | mainEntity (Person), name, url, description, sameAs |
| QAPage | Genuine user Q&A pages (one question, community answers) | mainEntity (Question), acceptedAnswer, suggestedAnswer — **fully supported** (not deprecated); expanded comment-thread properties added 2026-03-24 |
| Education Q&A (Quiz) | Educational quiz / flashcard rich result | Quiz with Question, `eduQuestionType=Flashcard`; carousel expanded to PT/ES/VI in 2026 |

---

## No Google rich results: FAQPage

| Type | SERP status | Since |
|------|------------|-------|
| FAQPage | Rich results fully retired — no SERP feature for any site | May 7, 2026 |

> Google retired FAQ rich results entirely on **May 7, 2026**. This **supersedes** the
> Aug 2023 gov/health restriction — even authoritative sites no longer get the rich result.
> FAQ docs carried a notice on **2026-05-08** and were removed on **2026-06-15**.
>
> FAQPage AI-citation benefit is unconfirmed in this pack. Do not claim it lifts
> AI-citation probability or is used for claim verification.
> - **Existing FAQPage**: Flag at Info priority, not Critical. Do **not** recommend removal solely because rich results retired.
> - **Adding new FAQPage**: No Google SERP benefit; do not recommend it for Google SERP benefit.
> - **Genuine single-question pages** where users submit answers: use **QAPage** (Google's recommended type), not FAQPage.

---

## Deprecated: Never recommend

| Type | Status | Since | Notes |
|------|--------|-------|-------|
| HowTo | Rich results fully removed | September 2023 | Google stopped showing how-to rich results |
| SpecialAnnouncement | Deprecated | July 31, 2025 | COVID-era schema, no longer processed |
| CourseInfo | Retired from rich results | June 2025 | Merged into Course |
| EstimatedSalary | Retired from rich results | June 2025 | No longer displayed |
| LearningVideo | Retired from rich results | June 2025 | Use VideoObject instead |
| ClaimReview | Retired from rich results | June 2025 | Fact-check markup no longer generates rich results |
| VehicleListing | Retired from rich results | June 2025 | Vehicle listing structured data discontinued |
| Book Actions | Deprecated | June 2025 | Deprecation banner added 2025-06-12; do not recommend unless a primary source confirms support |
| Practice Problem | Retired from rich results | Deprecation notice 2025-11-05 | Search Console / Rich Results Test support removed Jan 2026 |
| Dataset | No Google **Search** rich result | Clarified 2025-11-05 | **Not discontinued** — Dataset markup is used only by **Dataset Search** (which still exists and consumes it), not Google Search rich results. Don't tell users it was killed. |

> **Tooling-removal timeline:** for CourseInfo, EstimatedSalary, LearningVideo, SpecialAnnouncement, and VehicleListing — docs were removed 2025-09-09 and their **Search Console reporting, Rich Results Test, and appearance-filter support were removed starting January 2026**. Audits should stop telling users to validate these in the Rich Results Test / Search Console. See `skills/seo-schema/references/deprecated-types-2024-2026.md`.

---

## Recent Additions (2024-2026)

| Type/Feature | Added | Notes |
|-------------|-------|-------|
| Product Certification markup | April 2025 | Energy ratings, safety certifications. Replaced EnergyConsumptionDetails. |
| ProductGroup | 2025 | E-commerce product variants with variesBy, hasVariant properties |
| ProfilePage | 2025 | Author/creator profile pages with mainEntity Person for E-E-A-T |
| DiscussionForumPosting | 2024 | For forum/community content |
| Speakable | Updated 2024 | For voice search optimization |
| LoyaltyProgram | June 2025 | Member pricing, loyalty card structured data |
| Organization-level shipping/return policies | November 2025 | Configure via Search Console without Merchant Center |
| ConferenceEvent | December 2025 | Schema.org v29.4 addition |
| PerformingArtsEvent | December 2025 | Schema.org v29.4 addition |
| hasAdultConsideration | 2026-05-20 | Product variant / Merchant listing; **required for adult-oriented products**; Google Search supports only `https://schema.org/SexualContentConsideration` |
| QAPage / DiscussionForumPosting comment-thread props | 2026-03-24 | New supported properties for comment-thread structure |
| Education Q&A (Quiz / eduQuestionType=Flashcard) | 2026 | Active rich result; carousel expanded to more languages |

## E-commerce Requirements (Updated)

| Requirement | Status | Since |
|-------------|--------|-------|
| `returnPolicyCountry` in MerchantReturnPolicy | **Required** | March 2025 |
| Product variant structured data | Expanded | 2025, includes apparel, cosmetics, electronics |

> **Note:** Content API for Shopping sunsets August 18, 2026. Migrate to Merchant API.

---

## Validation Checklist

For any schema block, verify:

1. ✅ `@context` is `"https://schema.org"` (not http)
2. ✅ `@type` is a valid, non-deprecated type
3. ✅ All required properties are present
4. ✅ Property values match expected data types
5. ✅ No placeholder text (e.g., "[Business Name]")
6. ✅ URLs are absolute, not relative
7. ✅ Dates are in ISO 8601 format
8. ✅ Images have valid URLs

## Testing Tools

- [Google Rich Results Test](https://search.google.com/test/rich-results)
- [Schema.org Validator](https://validator.schema.org/)
