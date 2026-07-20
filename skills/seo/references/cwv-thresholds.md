<!-- Updated: 2026-06-21 -->
# Core Web Vitals Thresholds (June 2026)

## Current Metrics

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| LCP (Largest Contentful Paint) | ≤2.5s | 2.5s–4.0s | >4.0s |
| INP (Interaction to Next Paint) | ≤200ms | 200ms–500ms | >500ms |
| CLS (Cumulative Layout Shift) | ≤0.1 | 0.1–0.25 | >0.25 |

## Key Facts
- INP replaced FID (First Input Delay) on **March 12, 2024**. FID was removed from Chrome's field-data tools (CrUX API, PageSpeed Insights) on **September 9, 2024** (Lighthouse is a lab tool that never reported FID). INP is the sole interactivity metric.
- Evaluation uses the **75th percentile** of real user data (field data from CrUX).
- Google assesses at the **page level** and the **origin level**.
- Core Web Vitals are a **tiebreaker** ranking signal: they matter most when content quality is similar between competitors.
- **Thresholds unchanged since original definitions**: ignore claims of "tightened thresholds" from SEO blogs.
- **Anti-hallucination guard**: There is **no "Visual Stability Index" (VSI)**, **no "Core Web Vitals 2.0"**, no "Engagement Reliability" metric, and no LCP-lowered-to-2.0s change. These appear only in third-party SEO blogs and are directly contradicted by web.dev/articles/vitals and the CrUX release notes. The three stable metrics (LCP, INP, CLS) are the entire CWV set as of 2026. Do **not** ingest VSI/CWV-2.0 as real.
- As of the **May 2026 CrUX dataset** (~18.4M origins, published 2026-06-09): **55.9%** of origins pass all three CWV (down ~0.8% MoM); ~68.6% good LCP, ~87% good INP. Google reports **origin-level** pass rates (not a desktop/mobile split). This number moves monthly — re-check the CrUX release notes.

## LCP Subparts (February 2025 CrUX Addition)

LCP can now be broken into diagnostic subparts:

| Subpart | What It Measures | Target |
|---------|------------------|--------|
| **TTFB** | Time to First Byte (server response) | <800ms |
| **Resource Load Delay** | Time from TTFB to resource request start | Minimize |
| **Resource Load Time** | Time to download the LCP resource | Depends on size |
| **Element Render Delay** | Time from resource loaded to rendered | Minimize |

**Total LCP = TTFB + Resource Load Delay + Resource Load Time + Element Render Delay**

Use this breakdown to identify which phase is causing LCP issues.

## Soft Navigations API (Experimental)

**Final origin trial Chrome 147-149 (2026), targeting an unflagged ship around Chrome 151**: measures CWV attribution for SPA soft navigations.

- Addresses the long-standing SPA measurement blind spot
- Currently experimental, **no ranking impact yet**
- Detects "soft navigations" (URL changes without full page load)
- May affect future SPA CWV measurement

**Detection:** Check for SPA frameworks (React, Vue, Angular, Svelte) and warn about current CWV measurement limitations.

## Measurement Sources

### Field Data (Real Users)
- Chrome User Experience Report (CrUX)
- PageSpeed Insights (uses CrUX data)
- Search Console Core Web Vitals report

### Lab Data (Simulated)
- Lighthouse
- WebPageTest
- Chrome DevTools

> Field data is what Google uses for ranking. Lab data is useful for debugging.

## Common Bottlenecks

### LCP (Largest Contentful Paint)
- Unoptimized hero images (compress, use WebP/AVIF, add preload)
- Render-blocking CSS/JS (defer, async, critical CSS inlining)
- Slow server response (TTFB >200ms: use edge CDN, caching)
- Third-party script blocking (defer analytics, chat widgets)
- Web font loading delay (use font-display: swap + preload)

### INP (Interaction to Next Paint)
- Long JavaScript tasks on main thread (break into smaller tasks <50ms)
- Heavy event handlers (debounce, use requestAnimationFrame)
- Excessive DOM size (>1,500 elements is concerning)
- Third-party scripts hijacking main thread
- Synchronous XHR or localStorage operations
- Layout thrashing (multiple forced reflows)

### CLS (Cumulative Layout Shift)
- Images/iframes without width/height dimensions
- Dynamically injected content above existing content
- Web fonts causing layout shift (use font-display: swap + preload)
- Ads/embeds without reserved space
- Late-loading content pushing down the page

## Optimization Priority

1. **LCP**: Most impactful for perceived performance
2. **CLS**: Most common issue affecting user experience
3. **INP**: Matters most for interactive applications

## Tools

```bash
# PageSpeed Insights API
curl -H "X-Goog-Api-Key: $GOOGLE_API_KEY" \
  "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=URL"

# Lighthouse CLI
npx lighthouse URL --output json --output-path report.json
```

## Performance Tooling Updates (2025-2026)

- **Lighthouse 13.4.0** (June 2026, latest stable): Lighthouse 13.0 (Oct 2025) migrated performance audits to **insight-based audits** aligned with the DevTools Performance panel and removed legacy audits (first-meaningful-paint, font-size, third-party-facades) — the performance *score* is metric-based and was **not** re-weighted. 13.2.0–13.3.0 added and default-enabled a new **Agentic Browsing** category (Chrome 150+; fractional pass-ratio — see `agent-friendly-pages.md`); 13.4.0 disabled it in the PSI REST API. Lighthouse is a lab tool (simulated conditions): always cross-reference with CrUX field data.
- **PSI / PSI API v5** run Lighthouse 13.x (updated 2025-10-20). The **PWA category was removed in Lighthouse 12** — do not parse a `pwa` category. Mobile lab **CPU throttling was increased on 2024-12-05** (higher mobile lab TBT since then; field/desktop unaffected — do not compare mobile lab TBT across that boundary).
- **CrUX Vis** replaced the CrUX Dashboard (Looker Studio), which was **shut down at end of November 2025** (October 2025 was its final dataset; the CrUX Connector is no longer updated). Use [CrUX Vis](https://cruxvis.withgoogle.com) or the CrUX API directly.
- **LCP subparts** added to CrUX (February 2025): Time to First Byte (TTFB), resource load delay, resource load time, and element render delay are now available as sub-components of LCP in CrUX data.
- **Google Search Console (2025-2026)**: hourly data in the Search Analytics API (HOUR dimension / HOURLY_ALL) shipped **April 2025**; the **branded vs. non-branded** query filter launched **Nov 2025** (expanded to all eligible sites ~Mar 2026, AI-classified — no manual regex); the AI-powered natural-language configuration tool was announced Dec 2025 and rolled out globally **Feb 2026**. The standalone **Page Experience report was removed** from Search Console — monitor via the Core Web Vitals report and the HTTPS report only.

> **Mobile-first indexing** is the default for the indexed web and Googlebot Smartphone is the primary crawler (rollout completed 2024). A mobile version is **not strictly required** (Google says it is "very strongly recommended"); sites that don't work well on mobile can still be indexed, but the real risk is content/parity loss. Ensure the mobile version contains equivalent primary content, structured data, and meta tags.
