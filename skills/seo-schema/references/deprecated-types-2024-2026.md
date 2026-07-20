# Deprecated Schema.org rich result types (2024–2026)

Authoritative reference for every rich result Google retired during the
2024–2025 cleanup. Whenever a user asks for one of these, the
`seo-schema` skill must explain that the type is deprecated and either
redirect to an active alternative or note that no replacement exists.

## Retired June 12, 2025

Announced at
[Simplifying our Search rich results](https://developers.google.com/search/blog/2025/06/simplifying-search-results)
(developers.google.com/search/blog).

| Type | Retired | Notes |
|---|---|---|
| **Vehicle Listing** (`@type: VehicleListing` / `Vehicle`) | June 2025 | No replacement. Google no longer renders dealer inventory rich cards. Use regular `Product` schema if the listing is sold online. |
| **Claim Review** (`@type: ClaimReview`) | June 2025 | No replacement. The fact-check rich result was the main consumer of ClaimReview; without it, the markup has no SERP effect. ClaimReview *the vocabulary* is still in schema.org, but Google ignores it. |
| **Estimated Salary** (`@type: EstimatedSalary` / `OccupationalAggregateRating`) | June 2025 | No replacement. `JobPosting` remains live for individual jobs. |
| **Learning Video** | June 2025 | No replacement. The generic `VideoObject` rich result still renders. |
| **Course Info carousel** | June 2025 | The carousel variant retired. The single-result `Course` rich card is still live. When asked for "Course Info", verify whether the user wants the carousel (dead) or the live single-result variant. |

## Retired July 31, 2025

| Type | Retired | Notes |
|---|---|---|
| **Special Announcement** (`@type: SpecialAnnouncement`) | July 2025 | The COVID-era emergency-info card was deprecated. No replacement. |

## Earlier (pre-v2 baseline) retirements

These are listed for completeness so the LLM doesn't suggest them.

| Type | Retired | Notes |
|---|---|---|
| **HowTo** (`@type: HowTo`) | September 2023 | Rich result removed from desktop and mobile. The vocabulary remains but produces no Google rich-result effect. Do not recommend HowTo for SERP benefit; any AI citation rationale is unconfirmed. |
| **FAQ** (`@type: FAQPage`) | Aug 2023 (restricted); **May 7, 2026 (fully retired)** | Rich results fully retired for **all** sites on May 7, 2026, superseding the 2023 gov/health restriction. FAQ docs were removed 2026-06-15; Search Console API timing needs recheck. Flag existing FAQPage as Info (not Critical); any AI/LLM citation benefit is unconfirmed. Do **not** recommend removal or new FAQPage for SERP benefit. For genuine single-question pages, use `QAPage`. |

## Tooling-removal timeline (don't send users to dead validators)

For **CourseInfo, EstimatedSalary, LearningVideo, SpecialAnnouncement, VehicleListing**:
documentation was removed in **2025** (the type docs went away **2025-09-09**) and these
types no longer produce rich results. Don't validate them in the Rich Results Test or
expect Search Console reporting — those surfaces no longer cover them. **Practice
Problem** is the type Google explicitly ties to the January-2026 sunset: it got a
deprecation notice **2025-11-05**, with Rich Results Test, Search Console rich-result
reporting, and appearance-filter support removed starting **January 2026**.

**Dataset** is a separate case: **not discontinued** — Dataset markup is consumed only
by **Dataset Search** (still live), not by Google Search rich results (clarified
2025-11-05). Don't advise removal as if it were killed.

## Replacement decision table

When generating schema, prefer these alternatives:

| Asked for | Replacement |
|---|---|
| `ClaimReview` | None — explain rich result is dead; suggest `Article` with `dateline` if news context. |
| `EstimatedSalary` | `JobPosting` with `baseSalary` for specific roles. |
| `LearningVideo` | `VideoObject` (still live). |
| `Course Info` carousel | Single `Course` rich card (still live). |
| `SpecialAnnouncement` | `Event` if time-bounded; otherwise `Article` or `WebPage`. |
| `VehicleListing` | `Product` with vehicle-specific properties. |
| `HowTo` (for SERP) | None — explain the rich result is dead. Suggest article structure with clear `<h2>` step headings if the goal is comprehension; ranking benefit is no longer schema-driven. |
| `FAQPage` (for SERP) | None, rich results retired May 2026. Keep only if accurate for non-SERP consumers; use `QAPage` for genuine user-submitted Q&A pages. |

## Primary sources

- Google retirement announcement (June 2025): https://developers.google.com/search/blog/2025/06/simplifying-search-results
- Special Announcement deprecation (July 2025): https://developers.google.com/search/blog
- HowTo retirement (September 2023): https://developers.google.com/search/blog/2023/08/howto-faq-changes
- FAQ restriction (August 2023): https://developers.google.com/search/blog/2023/08/howto-faq-changes
- FAQ rich result retirement (May 7, 2026): https://developers.google.com/search/docs/appearance/structured-data/faqpage

Last verified against developers.google.com: 2026-05-25.
