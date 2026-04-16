# Core Web Vitals Audit

**URL/Origin:** {target}
**Strategy:** {strategy}

## CrUX Field Data (28-day rolling average)

Real Chrome user experience data from the Chrome UX Report.

| Metric | p75 Value | Rating | Good Threshold | Distribution |
|--------|-----------|--------|----------------|-------------|
| LCP | {lcp_value} | {lcp_rating} | ≤ 2,500ms | Good: {lcp_good}% / NI: {lcp_ni}% / Poor: {lcp_poor}% |
| INP | {inp_value} | {inp_rating} | ≤ 200ms | Good: {inp_good}% / NI: {inp_ni}% / Poor: {inp_poor}% |
| CLS | {cls_value} | {cls_rating} | ≤ 0.1 | Good: {cls_good}% / NI: {cls_ni}% / Poor: {cls_poor}% |
| FCP | {fcp_value} | {fcp_rating} | ≤ 1,800ms | Good: {fcp_good}% / NI: {fcp_ni}% / Poor: {fcp_poor}% |
| TTFB | {ttfb_value} | {ttfb_rating} | ≤ 800ms | Good: {ttfb_good}% / NI: {ttfb_ni}% / Poor: {ttfb_poor}% |

**Collection Period:** {collection_start} to {collection_end}

## Lighthouse Lab Scores

| Category | Score |
|----------|-------|
| Performance | {perf_score}/100 |
| Accessibility | {a11y_score}/100 |
| Best Practices | {bp_score}/100 |
| SEO | {seo_score}/100 |

## CrUX History Trends (25-week)

| Metric | Direction | Change | Earliest → Latest |
|--------|-----------|--------|-------------------|
{trends_table}

## Top Opportunities

| Opportunity | Estimated Savings |
|-------------|-------------------|
{opportunities_table}

## Recommendations

{recommendations}

---
*CrUX data updated daily ~04:00 UTC. 28-day rolling average.*
*INP replaced FID as the responsiveness Core Web Vital on March 12, 2024.*
*Generated {timestamp}.*
