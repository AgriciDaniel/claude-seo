# DMA + Consent Mode v2 — click-through impact diagnostic

EU traffic flowing through Google Search has been subject to the
**Digital Markets Act** since 2024-03-07. The DMA limits how Google
can use behavioural data and forces consent-mode v2 compliance for
GA4 + Ads in EU. The operational effect for SEO audits:

- EU click-through-rate (CTR) data from Search Console may be noisier
  after the DMA enforcement date (an inference: Google publishes no
  measurement of this). Treat year-over-year CTR comparisons across that
  boundary with care.
- GA4 organic-traffic reports for EU users show systematic
  under-reporting when consent-mode v2 is configured as "denied for
  ad_storage" (a common EEA setup defaults every consent type to denied
  until the user consents).
  Conversion modelling fills the gap, but the raw counts are lower
  than pre-2024.

## What the seo-google skill should do

1. **When pulling GSC search analytics for an EU-targeted property**,
   note: "EU CTR comparisons before/after 2024-03-07 are not
   apples-to-apples (DMA + consent-mode v2 took effect)."
2. **When pulling GA4 organic traffic**, surface the consent-mode
   configuration if it is visible. If default consent denies
   ad_storage or analytics_storage for EEA users, note "EU traffic
   counts are conservative; conversion-modelled uplift may apply."
3. **Do not lecture the user on cookie consent UX** — that's a legal
   team / engineering concern outside SEO scope. Just attach the
   diagnostic note.

## Required GA4 / Consent Mode setup the audit should check for

- Consent Mode v2 wired up (`gtag('consent', 'default', {...})`
  including `ad_user_data` and `ad_personalization`, set before any tags
  fire; https://developers.google.com/tag-platform/security/guides/consent).
- `ads_data_redaction` flag set on EU traffic.
- Server-side tagging at consent transitions (recommended pattern;
  not legally required).

## Softening cookieless-attribution warnings

Google **abandoned** third-party cookie deprecation in July 2024 and
confirmed in April 2025 that Chrome will not ship a standalone cookie
prompt. The "cookieless future" framing is no longer urgent.

For audits as of September 2026:

- Do NOT recommend "switch to cookieless attribution" as a priority.
- DO recommend "implement consent-mode v2 + server-side tagging" for
  EU compliance + signal-loss recovery.
- Most Privacy Sandbox APIs (Topics, Protected Audience, Attribution
  Reporting, Shared Storage and Private Aggregation, Related Website
  Sets, IP Protection) were retired per Google's October 17, 2025
  announcement. Do not recommend them. CHIPS, FedCM and Private State
  Tokens remain.

## Primary sources

- DMA enforcement: https://digital-markets-act.ec.europa.eu/
- Google's third-party cookie reversal: https://privacysandbox.google.com/blog/privacy-sandbox-next-steps
- Privacy Sandbox API retirements (2025-10-17): https://privacysandbox.google.com/blog/update-on-plans-for-privacy-sandbox-technologies
- Consent Mode v2, EEA consent updates: https://support.google.com/google-ads/answer/13695607

Last verified: 2026-09-23.
