# Core Web Vitals Thresholds (February 2026)

## Current Metrics

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| LCP (Largest Contentful Paint) | ≤2.5s | 2.5s–4.0s | >4.0s |
| INP (Interaction to Next Paint) | ≤200ms | 200ms–500ms | >500ms |
| CLS (Cumulative Layout Shift) | ≤0.1 | 0.1–0.25 | >0.25 |

## Key Facts
- INP replaced FID (First Input Delay) on **March 12, 2024**. FID is fully deprecated.
- Evaluation uses the **75th percentile** of real user data (field data from CrUX).
- Google assesses at the **page level** and the **origin level**.
- Core Web Vitals are a **tiebreaker** ranking signal — they matter most when content quality is similar between competitors.

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
- Slow server response (TTFB >200ms — use edge CDN, caching)
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

1. **LCP** — Most impactful for perceived performance
2. **CLS** — Most common issue affecting user experience
3. **INP** — Matters most for interactive applications

## Tools

```bash
# PageSpeed Insights API
curl "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=URL&key=API_KEY"

# Lighthouse CLI
npx lighthouse URL --output json --output-path report.json
```
