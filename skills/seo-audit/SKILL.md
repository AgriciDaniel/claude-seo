---
name: seo-audit
description: "Run a full-site SEO audit and return a scored, prioritized report. Use only for site-wide checks; use seo-page for one URL or seo-technical for a technical-only review."
user-invocable: true
argument-hint: "[url]"
license: MIT
metadata:
  author: AgriciDaniel
  version: "2.4.0"
  category: seo
---

# Full Website SEO Audit

## Process

1. **Render homepage**: use `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run render_page.py <url> --mode auto --json` to capture raw HTML, rendered HTML, extracted text, SPA status, and accessibility data when needed
2. **Detect business type**: analyze homepage signals per seo orchestrator
3. **Crawl site**: follow internal links up to 500 pages, respect robots.txt
4. **Delegate to subagents** (if available, otherwise run inline sequentially):
   - `seo-technical` -- robots.txt, sitemaps, canonicals, Core Web Vitals, security headers
   - `seo-content` -- E-E-A-T, readability, thin content, AI citation readiness
   - `seo-schema` -- detection, validation, generation recommendations
   - `seo-sitemap` -- structure analysis, quality gates, missing pages
   - `seo-performance` -- LCP, INP, CLS measurements
   - `seo-visual` -- screenshots, mobile testing, above-fold analysis
   - `seo-geo` -- AI crawler access, llms.txt, citability, brand mention signals
   - `seo-agentic` -- Lighthouse Agentic Browsing fraction (X/N), accessibility tree for agents, AI agent access policy, Markdown and discovery files, WebMCP (always include in full audits; its findings feed AI Search Readiness)
   - `seo-local` -- GBP signals, NAP consistency, reviews, local schema, industry-specific local factors (spawn when Local Service industry detected: brick-and-mortar, SAB, or hybrid business type)
   - `seo-maps` -- Geo-grid rank tracking, GBP audit, review intelligence, competitor radius mapping (spawn when Local Service detected AND DataForSEO MCP available)
   - `seo-google` -- CWV field data (CrUX), URL indexation (GSC), organic traffic (GA4) (spawn when Google API credentials detected via `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run google_auth.py --check`)
   - `seo-matomo` -- Matomo Reporting API: organic traffic, landing pages, device / country splits, referrer analysis (spawn when Matomo credentials detected via `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_auth.py --check`; runs alongside `seo-google` when both are configured, or as a GA4 alternative when GA4 is not)
   - `seo-backlinks` -- Backlink profile data: DA/PA, referring domains, anchor text, toxic links (spawn when Moz or Bing API credentials detected via `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run backlinks_auth.py --check`, or always include Common Crawl domain-level metrics)
   - `seo-cluster` -- Semantic clustering analysis (spawn when content strategy signals detected: blog, pillar pages, topic clusters)
   - `seo-sxo` -- Search experience analysis: page-type mismatch, user stories, persona scoring (always include in full audits)
   - `seo-drift` -- Drift analysis: compare against stored baseline (spawn when drift baseline exists for the URL via `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run drift_history.py <url>`)
   - `seo-ecommerce` -- Product schema, marketplace intelligence (spawn when E-commerce industry detected)
5. **Verify** -- re-check every Critical and High finding yourself before it reaches the report (see "Verification Pass" below). Subagent findings are claims, not facts.
6. **Score** -- `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run audit_score.py {domain}-audit/audit-data.json --write --strict`. Scores only measured categories and withholds the composite when coverage is below 70% (see "Scoring Weights"). Never hand-compute or estimate a health score.
7. **Persist audit artifacts** -- write all outputs under `{domain}-audit/`
8. **Report** -- generate prioritized action plan and optional PDF/HTML report

## Crawl Configuration

```
Max pages: 500
Respect robots.txt: Yes
Follow redirects: Yes (max 3 hops)
Timeout per page: 30 seconds
Concurrent requests: 5
Delay between requests: 1 second
```

## Output Files

- `{domain}-audit/FULL-AUDIT-REPORT.md`: Comprehensive findings
- `{domain}-audit/ACTION-PLAN.md`: Prioritized recommendations (Critical > High > Medium > Low)
- `{domain}-audit/audit-data.json`: Structured audit envelope for report generation
- `{domain}-audit/findings/*.md`: Per-category specialist findings (`technical.md`, `content.md`, `schema.md`, `performance.md`, `visual.md`, etc.)
- `{domain}-audit/screenshots/`: Desktop + mobile captures (if Playwright available)
- **PDF Report** (recommended): Generate a professional A4 PDF using `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run google_report.py --type full --data {domain}-audit/audit-data.json --domain <domain> --output-dir {domain}-audit/`. This produces a white-cover enterprise report with TOC, executive summary, charts (Lighthouse gauges, query bars, index donut), metric cards, threshold tables, prioritized recommendations with effort estimates, and implementation roadmap. Always offer PDF generation after completing an audit.

## Structured Audit Data Envelope

Write `{domain}-audit/audit-data.json` with this shape so `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run google_report.py --type full --data {domain}-audit/audit-data.json --domain <domain> --output-dir {domain}-audit/` can generate a report even when Google API data is unavailable:

```json
{
  "summary": {
    "health_score": 0,
    "business_type": "detected type",
    "top_findings": [],
    "quick_wins": []
  },
  "categories": [
    {
      "name": "Technical SEO",
      "score": 0,
      "measured": true,
      "what_works": [],
      "findings": [
        {
          "title": "Finding title",
          "severity": "Critical|High|Medium|Low|Info",
          "description": "Evidence-backed detail",
          "recommendation": "Specific fix",
          "source": "seo-technical",
          "verification": {
            "status": "verified|unverified|disproved",
            "method": "How the orchestrator re-checked it",
            "evidence": "What the re-check observed (counts, URLs, status codes)"
          }
        }
      ]
    }
  ],
  "corrections": [],
  "action_plan": {
    "phases": [
      {"name": "Phase 1: Critical Fixes", "timeframe": "Week 1", "items": []},
      {"name": "Phase 2: High-Impact Improvements", "timeframe": "Weeks 2-3", "items": []},
      {"name": "Phase 3: Content & Authority", "timeframe": "Month 2", "items": []},
      {"name": "Phase 4: Monitoring & Iteration", "timeframe": "Ongoing", "items": []}
    ]
  },
  "artifacts": {
    "findings_dir": "findings/",
    "screenshots_dir": "screenshots/"
  }
}
```

## Scoring Weights

| Category | Weight |
|----------|--------|
| Technical SEO | 22% |
| Content Quality | 23% |
| On-Page SEO | 20% |
| Schema / Structured Data | 10% |
| Performance (CWV) | 10% |
| AI Search Readiness | 10% |
| Images | 5% |

Name categories after the rows above, or set `"scoring_category"` to one of
them; `audit_score.py` reports how it mapped any other name. A category that
was not measured (its agent failed, timed out, or lacked the data) gets
`"score": null, "measured": false`, never `0` and never an estimate. A score
drawn from a narrow slice of the category (one template, one signal) also
counts as not measured: record the slice as findings, not as the score.
`audit_score.py` renormalises the weights over measured categories and writes
`summary.score_coverage` and `summary.unmeasured_categories`. When measured
categories cover less than 70% of the weight it removes `summary.health_score`
and writes `summary.health_score_withheld` with the reason; the report then
states which categories are missing instead of showing a number. Always quote
the coverage next to the score ("68/100, 77% of categories measured").

## Verification Pass

Subagents misread pages, count wrong, and generalise from one sample. Before
scoring, the orchestrator re-checks every Critical and High finding with its
own tool calls; Medium findings are spot-checked when they drive a
recommendation.

1. **Re-derive, don't re-read.** Fetch the evidence directly (`fetch_page.py`,
   `render_page.py`, `parse_html.py`, curl for status codes) rather than
   rereading the agent's summary. Check the rendered DOM as well as raw HTML
   before calling anything "missing".
2. **Recount every number.** Counts, percentages and "N of M" claims are
   recomputed from the raw data. A number that cannot be reproduced is not
   reported.
3. **Try to disprove it.** Ask what would make the finding false and check
   that: a "missing" element may exist under another type or template; a
   "broken" link may redirect to a live page; a "slow" asset may load after
   LCP. A finding survives only if the disproof attempt fails.
4. **Check the scope.** A finding observed on one page is reported for one
   page. Claim a template-wide or site-wide issue only after sampling at least
   one page per affected template.
5. **Record the outcome** in each finding's `verification` object:
   - `verified`: the re-check reproduced it; `evidence` says what was observed.
   - `disproved`: the re-check contradicted it; `evidence` says why.
     `audit_score.py --write` moves it to top-level `corrections`, so it never
     reaches the client report.
   - `unverified`: could not be checked (blocked, needs credentials). Downgrade
     it to Medium, or keep the severity and label it unverified in the report.
6. `audit_score.py --strict` exits 2 while any Critical or High finding is
   still unverified. Resolve each one before generating the report.

`FULL-AUDIT-REPORT.md` ends with a **Corrections** section listing every
disproved claim, its source agent and the disproof, so later runs do not
regress to it.

## Shell Pitfalls

- **Parallel writes to one file lose lines.** `xargs -P` or `&` jobs sharing a
  single `>` redirect silently drop output. Have each job append (`>>`) to its
  own file, then concatenate, and check that the collected line count equals
  the input count before using the result.
- **macOS lacks GNU tools.** No `timeout` or `shuf` by default: use `gtimeout`
  (coreutils) or Python's `subprocess` timeout, and `sort -R` or Python
  `random.sample` for sampling. `sed -i` needs `''` on BSD sed.
- **Persist raw evidence** (sitemap, status scans, fetched HTML) under
  `{domain}-audit/evidence/` so a re-run or verification pass starts warm
  instead of re-crawling.

## Report Structure

### Executive Summary
- Overall SEO Health Score (0-100) with its coverage, or the reason it was withheld
- Business type detected
- Top 5 critical issues
- Top 5 quick wins

### Technical SEO
- Crawlability issues
- Indexability problems
- Security concerns
- Core Web Vitals status

### Content Quality
- E-E-A-T assessment
- Thin content pages
- Duplicate content issues
- Readability scores

### On-Page SEO
- Title tag issues
- Meta description problems
- Heading structure
- Internal linking gaps

### Schema & Structured Data
- Current implementation
- Validation errors
- Missing opportunities

### Performance
- LCP, INP, CLS scores
- Resource optimization needs
- Third-party script impact

### Images
- Missing alt text
- Oversized images
- Format recommendations

### AI Search Readiness
- Citability score
- Structural improvements
- Authority signals

## Priority Definitions

- **Critical**: Blocks indexing or causes penalties (fix immediately)
- **High**: Significantly impacts rankings (fix within 1 week)
- **Medium**: Optimization opportunity (fix within 1 month)
- **Low**: Nice to have (backlog)

## DataForSEO Integration (Optional)

If DataForSEO MCP tools are available, spawn the `seo-dataforseo` agent alongside existing subagents to enrich the audit with live data: real SERP positions, backlink profiles with spam scores, on-page analysis (Lighthouse), business listings, and AI visibility checks (ChatGPT scraper, LLM mentions).

## Google API Integration (Optional)

If Google API credentials are configured (`"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run google_auth.py --check`), spawn the `seo-google` agent to enrich the audit with real Google field data: CrUX Core Web Vitals (replaces lab-only estimates), GSC URL indexation status, search performance (clicks, impressions, CTR), and GA4 organic traffic trends. The Performance (CWV) category score benefits most from field data.

## Matomo Integration (Optional)

If Matomo credentials are configured (`"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_auth.py --check`), spawn the `seo-matomo` agent to enrich the audit with self-hosted analytics: organic visits trend, top landing pages, device and country breakdowns, channel / search-engine split, and organic keywords. Works as a GA4 alternative (when only Matomo is configured) or as a complement (when both GA4 and Matomo are present). Matomo numbers will not match GA4 exactly because of segmentation differences (`referrerType==search` vs `sessionDefaultChannelGroup == "Organic Search"`) and attribution-window rules.

## Google Update Correlation

Before attributing a traffic or ranking change to anything, list the confirmed
Google updates in that window from the primary-source ledger:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run seo_updates.py --since <yyyy-mm> --json
```

Every entry cites a Google-owned URL. If `freshness.stale` is true, say the
ledger may miss recent updates and check status.search.google.com before
drawing conclusions. A date overlap is a hypothesis, never proof of cause.

## Error Handling

| Scenario | Action |
|----------|--------|
| URL unreachable (DNS failure, connection refused) | Report the error clearly. Do not guess site content. Suggest the user verify the URL and try again. |
| robots.txt blocks crawling | Report which paths are blocked. Analyze only accessible pages and note the limitation in the report. |
| Rate limiting (429 responses) | Back off and reduce concurrent requests. Report partial results with a note on which sections could not be completed. |
| Timeout on large sites (500+ pages) | Cap the crawl at the timeout limit. Report findings for pages crawled and estimate total site scope. |
| Subagent hits its `maxTurns` budget on a large site | Findings are not lost: every audit subagent writes a partial `output_dir/findings/*.md` after its first analysis pass and overwrites it with the complete findings before finishing. Read whatever findings file exists and merge it into the report, noting it may be partial. |
| Subagent returns nothing and no findings file exists | Mark its categories `"score": null, "measured": false`. Do not fill the gap with estimates; `audit_score.py` accounts for it in coverage. |
