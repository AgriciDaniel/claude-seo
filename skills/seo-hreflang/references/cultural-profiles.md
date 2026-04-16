# Cultural Adaptation Profiles for International SEO

Load this reference when analyzing multi-language sites or generating hreflang
implementations. Profiles guide cultural assessment beyond technical validation.

Original concept: Chris Muller (Pro Hub Challenge)

## DACH Region (DE, AT, CH)

| Dimension | Guideline |
|-----------|-----------|
| Formality | High. Use "Sie" (formal you). Professional tone expected. |
| Humor | Conservative. Avoid sarcasm and wordplay in CTAs. |
| CTA Style | Indirect preferred. "Jetzt entdecken" over "Jetzt kaufen". |
| Trust Signals | Certifications (TUV, ISO), "Datenschutz" (privacy), Impressum required by law. |
| Legal | Impressum page mandatory. DSGVO (GDPR). Widerrufsrecht (right of withdrawal). |
| Number Format | 1.000,00 (dot for thousands, comma for decimal) |
| Date Format | DD.MM.YYYY |
| Currency | EUR (DE/AT), CHF (CH) |
| Color Symbolism | Blue = trust, Green = eco/nature, Red = caution (not urgency) |
| Brand Substitution | Walmart → MediaMarkt, Home Depot → Hornbach, Amazon → Otto/Zalando |
| Word Expansion | +25-35% vs English (plan for longer headlines and button text) |

## Francophone (FR, BE, CA-FR, CH-FR)

| Dimension | Guideline |
|-----------|-----------|
| Formality | Medium-high. "Vous" default. "Tu" only for youth/casual brands. |
| Humor | Appreciated when sophisticated. Avoid blunt/direct humor. |
| CTA Style | Elegant phrasing. "Decouvrir nos solutions" over "Achetez maintenant". |
| Trust Signals | "Fabrique en France" (made in France), professional certifications, press mentions. |
| Legal | Mentions legales required. CNIL (data protection). CGV (terms). |
| Number Format | 1 000,00 (space for thousands, comma for decimal) |
| Date Format | DD/MM/YYYY |
| Currency | EUR (FR/BE), CAD (CA-FR), CHF (CH-FR) |
| Color Symbolism | Blue = stability, White = purity/luxury, Red = passion |
| Brand Substitution | Walmart → Carrefour, Amazon → Fnac/Cdiscount, Target → Leclerc |
| Word Expansion | +15-25% vs English |

## Hispanic (ES, LATAM)

| Dimension | Guideline |
|-----------|-----------|
| Formality | Varies by country. Spain: "Usted" formal. LATAM: mixed. |
| Humor | Warm and relational. Self-deprecating humor accepted. |
| CTA Style | Warm, personal. "Empieza tu viaje" over "Comprar ahora". |
| Trust Signals | Community proof, family/relationship themes, celebrity endorsements popular. |
| Legal | LOPD (Spain data protection). Each LATAM country has own regulations. |
| Number Format | Spain: 1.000,00 / LATAM: varies by country |
| Date Format | DD/MM/YYYY (most), DD-MM-YYYY (some LATAM) |
| Currency | EUR (ES), regional currencies (MXN, ARS, COP, CLP, PEN) |
| Color Symbolism | Red = energy/passion, Yellow = warmth, Blue = trust |
| Brand Substitution | Walmart → Mercadona (ES) / Coppel (MX), Amazon → MercadoLibre |
| Word Expansion | +15-25% vs English |

## Japanese (JA)

| Dimension | Guideline |
|-----------|-----------|
| Formality | Very high. Keigo (honorific language) expected in business. |
| Humor | Subtle. Avoid direct humor in B2B. Kawaii (cute) elements acceptable in B2C. |
| CTA Style | Subtle and polite. "Otoiawase" (inquire) over direct "buy now". |
| Trust Signals | Company longevity, ISO certifications, endorsements from recognized institutions. |
| Legal | APPI (Act on Protection of Personal Information). Tokutei Shotorihiki law. |
| Number Format | 1,000 (comma for thousands, no decimal in most contexts) |
| Date Format | YYYY/MM/DD or YYYY年MM月DD日 |
| Currency | JPY (no decimals) |
| Color Symbolism | White = purity, Red = vitality/celebration, Black = formality |
| Brand Substitution | Amazon → Rakuten, Google Shopping → Yahoo! Shopping Japan |
| Word Contraction | -10-25% vs English (Japanese is more compact) |

## Default Profile (Unlisted Languages)

When analyzing a locale without a pre-built profile above:

1. **Research formality norms**: Check if the language has formal/informal registers (e.g., Korean has 7 speech levels)
2. **Check text direction**: LTR vs RTL (Arabic, Hebrew, Farsi, Urdu)
3. **Verify number/date formats**: Use CLDR (Unicode Common Locale Data Repository)
4. **Research legal requirements**: Privacy law, business registration, consumer protection
5. **Check word expansion ratio**: Germanic/Slavic languages expand, CJK languages contract
6. **Verify currency and payment preferences**: Local payment methods may need mention
7. **Research color meanings**: Colors have different cultural associations globally

## How to Use in Analysis

When running `/seo hreflang` on a multi-language site:
1. Identify all language versions and their target markets
2. Load the relevant cultural profile(s)
3. Check that CTAs, trust signals, and legal pages match the cultural expectations
4. Flag mismatches as "Cultural Adaptation" findings (Medium severity)
5. Check number/date/currency formatting consistency within each locale version
