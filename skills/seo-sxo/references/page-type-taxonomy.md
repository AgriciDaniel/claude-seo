# Page Type Taxonomy for SERP Classification

Classify every page -- both the target URL and each SERP result -- into exactly one
of these 8 types. When signals overlap, choose the type with the strongest primary
signal match.

---

## 1. Landing Page

**Primary signals:** hero section with single value proposition, prominent CTA
(sign up / get started / book demo), pricing section or pricing link, testimonials
or social proof badges, minimal navigation (reduced header links).

**SERP indicators (top 10):** branded queries, high ad density at top, sitelinks
pointing to /pricing or /features, title tags with "| Product Name".

**Content structure:** Hero > Social proof > Features (3-5) > How it works > Pricing > CTA repeat > FAQ.

**Required elements:** Primary CTA above fold, trust badges, at least one testimonial,
WebSite or SoftwareApplication schema.

**Common mismatches:**
- Blog Post targeting landing-page keywords (severity: CRITICAL)
- Service Page missing CTA focus (severity: HIGH)

---

## 2. Blog Post

**Primary signals:** author byline, publish date, article body > 800 words,
comment section or social share buttons, breadcrumb with /blog/ segment,
related posts section.

**SERP indicators (top 10):** featured snippets (paragraph or list), PAA boxes
with 4+ questions, diverse domains in results, dates visible in snippets,
low ad density.

**Content structure:** Title > Author + Date > Introduction > H2 sections > Images/Examples > Conclusion > Author bio.

**Required elements:** Article or BlogPosting schema, author entity, datePublished,
dateModified, at least 1 image with descriptive alt text.

**Common mismatches:**
- Product Page targeting informational keyword (severity: HIGH)
- Landing Page targeting how-to keyword (severity: CRITICAL)

---

## 3. Product Page

**Primary signals:** price displayed, add-to-cart or buy button, product images
(multiple angles), specifications/features list, customer reviews with star ratings,
SKU or product identifiers.

**SERP indicators (top 10):** shopping results / product carousel, rich snippets
with price + availability + ratings, merchant names in titles, "buy" or "shop"
in title tags.

**Content structure:** Product title > Images > Price + CTA > Description > Specs > Reviews > Related products.

**Required elements:** Product schema (name, price, availability, review),
high-quality images, clear pricing, purchase CTA.

**Common mismatches:**
- Blog Post targeting product keyword (severity: CRITICAL)
- Comparison Page when user wants to buy (severity: MEDIUM)

---

## 4. Hybrid (Service + Content)

**Primary signals:** educational content sections mixed with CTAs, feature
explanations with "learn more" and "get started" side by side, common in SaaS,
both /blog/ and /product/ internal links in navigation.

**SERP indicators (top 10):** mix of branded and informational results,
some results with FAQ schema + others with SoftwareApplication schema,
moderate ad density.

**Content structure:** Problem statement > Solution overview > How it works > Feature deep-dives > Social proof > CTA > FAQ.

**Required elements:** FAQPage or HowTo schema combined with product schema,
both educational and commercial CTAs, clear value proposition.

**Common mismatches:**
- Pure Blog Post missing product integration (severity: HIGH)
- Pure Landing Page missing educational depth (severity: MEDIUM)

---

## 5. Service Page

**Primary signals:** service descriptions with methodology/process, case studies
or portfolio, "our process" or "how we work" sections, team credentials,
contact form or consultation CTA, industry-specific terminology.

**SERP indicators (top 10):** local pack presence, "near me" related searches,
results from agency/firm domains, title tags with "[Service] | [Company]",
moderate PAA questions about process/cost.

**Content structure:** Service overview > Benefits > Process/Methodology > Case studies > Team > Pricing/Packages > Contact CTA.

**Required elements:** Service or ProfessionalService schema, clear process
description, at least one case study or testimonial, contact mechanism.

**Common mismatches:**
- Blog Post targeting service keyword (severity: HIGH)
- Product Page for custom/consultative services (severity: MEDIUM)

---

## 6. Comparison Page

**Primary signals:** "vs" or "versus" in title/URL, feature comparison matrix
or table, pros/cons lists, side-by-side layout, "best [X] for [use case]"
framing, multiple products reviewed.

**SERP indicators (top 10):** "vs" queries in related searches, multiple PAA
about alternatives, results from review sites (G2, Capterra, TrustRadius),
listicle-style titles ("10 Best..."), affiliate disclosures.

**Content structure:** Introduction > Comparison criteria > Feature matrix > Individual reviews > Verdict/Recommendation > FAQ.

**Required elements:** Comparison table with clear criteria, pros/cons for each
option, clear recommendation or "best for" segmentation, ItemList or Table schema.

**Common mismatches:**
- Single Product Page when user wants comparison (severity: HIGH)
- Blog Post without structured comparison (severity: HIGH)

---

## 7. Local Page

**Primary signals:** physical address displayed, Google Maps embed, NAP
(Name, Address, Phone) in consistent format, service area description,
directions or "visit us" section, location-specific content.

**SERP indicators (top 10):** local pack (map + 3 listings), "near me" in
related searches, Google Business Profile cards, location in title tags,
results from local directories (Yelp, BBB).

**Content structure:** Business name + location > Services at this location > Map + directions > Hours > Reviews > Local content > Contact.

**Required elements:** LocalBusiness schema (correct subtype), full NAP,
geo coordinates, openingHoursSpecification, embedded map.

**Common mismatches:**
- Generic Service Page missing local signals (severity: HIGH)
- Blog Post targeting "[service] in [city]" (severity: CRITICAL)

---

## 8. Tool / Interactive

**Primary signals:** input fields, calculator or generator interface, interactive
elements (sliders, dropdowns, toggles), results output area, utility-first
design with minimal marketing copy, "free [tool name]" in title.

**SERP indicators (top 10):** tool/calculator results in SERP, "calculator"
or "generator" or "checker" in related searches, results from tool-first sites,
minimal PAA (users want to DO, not READ).

**Content structure:** Tool interface (above fold) > Brief instructions > Tool output > Supporting content below > FAQ > Related tools.

**Required elements:** WebApplication or SoftwareApplication schema, functional
tool above fold, clear input/output flow, no login wall for basic functionality.

**Common mismatches:**
- Blog Post about topic where users want a tool (severity: CRITICAL)
- Landing Page without interactive element (severity: HIGH)

---

## Classification Priority

When a page shows signals for multiple types, use this priority:

1. If interactive tool is present and functional: **Tool**
2. If physical address + map: **Local** (unless tool is primary)
3. If comparison table + "vs" framing: **Comparison**
4. If price + buy button: **Product**
5. If CTA-heavy + minimal navigation: **Landing Page**
6. If service process + case studies: **Service Page**
7. If educational + CTA mix: **Hybrid**
8. Default: **Blog Post**
