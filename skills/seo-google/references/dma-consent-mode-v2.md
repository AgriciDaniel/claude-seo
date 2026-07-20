# DMA + Consent Mode v2 — click-through impact diagnostic

EU traffic flowing through Google Search has been subject to the
**Digital Markets Act** since 2024-03-07. The DMA limits how Google
can use behavioural data and forces consent-mode v2 compliance for
GA4 + Ads in EU. The operational effect for SEO audits:

- EU click-through-rate (CTR) data from Search Console is materially
  noisier after the DMA enforcement date. Year-over-year CTR
  comparisons across that boundary are not apples-to-apples.
- GA4 organic-traffic reports for EU users show systematic
  under-reporting when consent-mode v2 is configured as "denied for
  ad_storage, granted for analytics_storage" (the typical EU default).
  Conversion modelling fills the gap, but the raw counts are lower
  than pre-2024.

## What the seo-google skill should do

1. **When pulling GSC search analytics for an EU-targeted property**,
   note: "EU CTR comparisons before/after 2024-03-07 are not
   apples-to-apples (DMA + consent-mode v2 took effect)."
2. **When pulling GA4 organic traffic**, surface the consent-mode
   configuration if the GA4 admin API exposes it. If the property
   has `eu_data_collection_disabled` or denies ad_storage by default,
   note "EU traffic counts are conservative; conversion-modelled
   uplift may apply."
3. **Do not lecture the user on cookie consent UX** — that's a legal
   team / engineering concern outside SEO scope. Just attach the
   diagnostic note.

## Required GA4 / Consent Mode setup the audit should check for

- GA4 4.x consent-mode v2 wired up (`gtag('consent', 'default', ...)`
  before any pageview).
- `ads_data_redaction` flag set on EU traffic.
- Server-side tagging at consent transitions (recommended pattern;
  not legally required).

## Softening cookieless-attribution warnings

Google **abandoned** third-party cookie deprecation in July 2024 and
confirmed in April 2025 that Chrome will not ship a standalone cookie
prompt. The "cookieless future" framing is no longer urgent.

For audits as of May 2026:

- Do NOT recommend "switch to cookieless attribution" as a priority.
- DO recommend "implement consent-mode v2 + server-side tagging" for
  EU compliance + signal-loss recovery.
- Privacy Sandbox APIs are still available, but optional. Mention
  only if the audit subject is consumer-facing and has heavy
  retargeting dependence.

## Primary sources

- DMA enforcement: https://digital-markets-act.ec.europa.eu/
- Google's third-party cookie reversal: https://privacysandbox.com/news/privacy-sandbox-update/
- Consent Mode v2, EEA consent updates: https://support.google.com/google-ads/answer/13695607

Last verified: 2026-05-17.
