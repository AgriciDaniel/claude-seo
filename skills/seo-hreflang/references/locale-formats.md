# Locale Format Reference for International SEO

Load this reference when validating content parity or generating localized content.
Mismatched formats (e.g., US date format on a German page) signal poor localization
and reduce user trust.

Original concept: Chris Muller (Pro Hub Challenge)

## Number Formats

| Locale | Thousands | Decimal | Example |
|--------|-----------|---------|---------|
| en-US | , | . | 1,234.56 |
| en-GB | , | . | 1,234.56 |
| de-DE | . | , | 1.234,56 |
| de-AT | . | , | 1.234,56 |
| de-CH | ' | . | 1'234.56 |
| fr-FR | (space) | , | 1 234,56 |
| fr-CA | (space) | , | 1 234,56 |
| es-ES | . | , | 1.234,56 |
| es-MX | , | . | 1,234.56 |
| ja-JP | , | . | 1,234 |
| pt-BR | . | , | 1.234,56 |
| it-IT | . | , | 1.234,56 |
| nl-NL | . | , | 1.234,56 |
| ko-KR | , | . | 1,234 |
| zh-CN | , | . | 1,234.56 |

## Date Formats

| Locale | Format | Example |
|--------|--------|---------|
| en-US | MM/DD/YYYY | 04/14/2026 |
| en-GB | DD/MM/YYYY | 14/04/2026 |
| de-DE | DD.MM.YYYY | 14.04.2026 |
| fr-FR | DD/MM/YYYY | 14/04/2026 |
| es-ES | DD/MM/YYYY | 14/04/2026 |
| ja-JP | YYYY/MM/DD or YYYY年MM月DD日 | 2026/04/14 |
| pt-BR | DD/MM/YYYY | 14/04/2026 |
| ko-KR | YYYY.MM.DD | 2026.04.14 |
| zh-CN | YYYY年MM月DD日 | 2026年04月14日 |

## Currency Formats

| Locale | Symbol | Placement | Example |
|--------|--------|-----------|---------|
| en-US | $ | Before | $1,234.56 |
| en-GB | £ | Before | £1,234.56 |
| de-DE | € | After (space) | 1.234,56 € |
| fr-FR | € | After (space) | 1 234,56 € |
| es-ES | € | After (space) | 1.234,56 € |
| ja-JP | ¥ | Before | ¥1,234 |
| pt-BR | R$ | Before | R$ 1.234,56 |
| ko-KR | ₩ | Before | ₩1,234 |
| zh-CN | ¥ | Before | ¥1,234.56 |
| de-CH | CHF | Before | CHF 1'234.56 |

## Address Formats

| Region | Order | Example |
|--------|-------|---------|
| US/CA | Street, City, State ZIP | 123 Main St, Austin, TX 78701 |
| UK | Street, City, Postcode | 10 Downing St, London, SW1A 2AA |
| DE/AT | Street Nr, PLZ City | Hauptstr. 1, 10115 Berlin |
| FR | Street, Code Postal City | 1 Rue de Rivoli, 75001 Paris |
| JP | Postal City District Street | 〒100-0001 東京都千代田区千代田1-1 |

## Phone Formats

| Region | Format | Example |
|--------|--------|---------|
| US | +1 (XXX) XXX-XXXX | +1 (512) 555-0123 |
| UK | +44 XXXX XXXXXX | +44 2071 234567 |
| DE | +49 XXX XXXXXXX | +49 30 12345678 |
| FR | +33 X XX XX XX XX | +33 1 23 45 67 89 |
| JP | +81 X-XXXX-XXXX | +81 3-1234-5678 |

## Text Expansion Ratios (vs English)

| Language | Expansion | Impact |
|----------|-----------|--------|
| German | +25-35% | Longer headlines, buttons, navigation labels |
| French | +15-25% | Moderate expansion |
| Spanish | +15-25% | Moderate expansion |
| Italian | +15-25% | Moderate expansion |
| Portuguese | +15-25% | Moderate expansion |
| Dutch | +10-20% | Slight expansion |
| Japanese | -10-25% | Contraction (more compact) |
| Korean | -10-20% | Contraction |
| Chinese | -20-30% | Significant contraction |

## Validation Rules

When checking locale format consistency:
1. Scan for number patterns on the page (prices, statistics, measurements)
2. Compare against the expected format for the page's declared language
3. Flag US-format numbers on non-US pages (e.g., "$1,234.56" on a de-DE page)
4. Check date formats in blog posts, copyright notices, update timestamps
5. Verify currency symbols match the target market
6. Check that phone numbers use international format with correct country code
