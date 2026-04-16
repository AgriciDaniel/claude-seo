# Content Parity Audit for Multi-Language Sites

Load this reference when auditing content parity across language versions of a site.
Content parity ensures all language versions provide equivalent value and SEO signals.

Original concept: Chris Muller (Pro Hub Challenge)

## Content Parity Matrix

For each page that exists in multiple languages, check:

| Dimension | What to Compare | Acceptable Variance | Severity if Failing |
|-----------|----------------|--------------------|--------------------|
| Page existence | Does equivalent page exist in all declared languages? | 0% — all declared languages must have the page | High |
| Section structure | Same number of H2/H3 sections? | ±1 section allowed | Medium |
| FAQ items | Same number of FAQ questions? | ±2 items allowed | Medium |
| Images | Same number of images with localized alt text? | Must match exactly | Medium |
| Charts/SVGs | Charts present in all versions? | Must match exactly | Low |
| Word count | Proportional to language expansion ratio? | ±30% of expected ratio | Low |
| Schema markup | JSON-LD present and localized in all versions? | Must match type and key properties | High |
| Title tag | Localized with target keyword in local language? | Must be localized, not English | High |
| Meta description | Localized and within character limits? | Must be localized | Medium |

## Freshness Tracking

Detect stale translations by comparing:
1. **File modification timestamps**: If EN version was updated after DE version, DE may be stale
2. **Frontmatter dates**: Compare `date_modified` or `lastmod` across language versions
3. **Content hash comparison**: If the source language content hash changed since last translation

Freshness delta thresholds:
- **Fresh**: Translated within 7 days of source update → OK
- **Aging**: 8-30 days since source update → Low priority update
- **Stale**: 31-90 days since source update → Medium priority update
- **Outdated**: 90+ days since source update → High priority update

## Word Count Ratio Validation

Expected word count ratios vs English source:

| Target Language | Expected Ratio | Acceptable Range |
|----------------|---------------|-----------------|
| German (DE) | 1.25-1.35x | 1.10-1.50x |
| French (FR) | 1.15-1.25x | 1.00-1.40x |
| Spanish (ES) | 1.15-1.25x | 1.00-1.40x |
| Japanese (JA) | 0.75-0.90x | 0.60-1.00x |
| Chinese (ZH) | 0.70-0.80x | 0.55-0.95x |

A German translation that is shorter than the English original likely has missing content.
A Japanese translation that is longer than English likely has unnecessary padding.

## Cultural Adaptation Quality Gates

Beyond direct translation, check for cultural markers that indicate proper localization:

| Check | What to Look For | Severity |
|-------|-----------------|----------|
| Foreign brand references | US-specific brands on non-US pages (e.g., "Walmart" on de-DE) | Medium |
| Foreign statistics | US-only data cited on localized pages (e.g., "80% of Americans") | Medium |
| CTA aggressiveness | Aggressive CTAs on formal-culture pages (e.g., "BUY NOW!" on ja-JP) | Low |
| Legal references | Wrong jurisdiction laws cited (e.g., CCPA on de-DE instead of DSGVO) | High |
| Currency/unit mismatch | USD prices on EUR pages, imperial units on metric pages | High |
| Untranslated elements | English text remaining in navigation, buttons, alt text, schema | Medium |

## Parity Score Calculation

Score out of 100:
- Page existence parity: 30 points
- SEO element parity (title, meta, schema): 30 points
- Content structure parity (sections, images, FAQ): 25 points
- Freshness parity: 15 points

Interpretation:
- 90-100: Excellent parity across all language versions
- 70-89: Good parity with minor gaps to address
- 50-69: Significant parity issues affecting some language versions
- Below 50: Major parity failures requiring immediate attention

## Output Format

Present as a matrix table:
```
| Page | EN | DE | FR | ES | JA | Parity Score |
|------|----|----|----|----|----| -------------|
| /about | ✅ | ✅ | ✅ | ❌ | ✅ | 80/100 |
| /pricing | ✅ | ✅ | ⚠️ | ❌ | ❌ | 45/100 |
```
