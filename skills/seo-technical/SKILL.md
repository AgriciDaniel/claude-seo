---
name: seo-technical
description: >
  Audit technical SEO across crawlability, indexability, security, URLs, mobile,
  Core Web Vitals, rendering, structured data, and IndexNow. Exclude content
  strategy and backlinks.
user-invocable: true
argument-hint: "[url]"
license: MIT
metadata:
  author: AgriciDaniel
  version: "2.3.1"
  category: seo
---

# Technical SEO Audit

## Categories

### 1. Crawlability
- robots.txt: exists, valid, not blocking important resources
- XML sitemap: run `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run sitemap_discovery.py <url> --json`; require a
  valid entry in `found`, and report stale or unsafe robots.txt declarations
  separately from working fallback locations
- Noindex tags: intentional vs accidental
- Crawl depth: important pages within 3 clicks of homepage
- JavaScript rendering: check if critical content requires JS execution
- Crawl budget: for large sites (>10k pages), efficiency matters
- Googlebot **fetch limits**: Googlebot fetches the first **2MB of HTML** and first **64MB of a PDF** (uncompressed; 15MB is the broader crawler-infra default). Long-standing, not a 2026 change, but inline base64 images, oversized inline CSS/JS, or bloated nav can push critical content/JSON-LD past the cap and out of the index. Keep key content + structured data within the first 2MB.
- Crawl rate **auto-adjusts** (backs off on 5xx/slow responses); there is **no manual crawl-rate control** (the legacy Search Console setting was removed Jan 2024). Influence crawling via sitemaps, server responsiveness, and robots controls.
- Google's canonical crawling/robots reference moved to **developers.google.com/crawling** (migrated 2025-11-20); IP-range files relocated to `/crawling/ipranges/` and `googlebot.json` was renamed `common-crawlers.json`.
- AMP has no separate ranking advantage. Since 2026-07-01, Google Search sends
  users directly to publisher-hosted AMP URLs, so do not recommend AMP Cache,
  AMP Viewer, or signed exchange maintenance. Audit AMP against the same content,
  action-parity, and quality requirements as other pages.

#### AI Crawler Management

As of 2025-2026, AI companies actively crawl the web to train models and power AI search. Managing these crawlers via robots.txt is a critical technical SEO consideration.

**Known AI crawlers:**

| Crawler | Company | robots.txt token | Purpose |
|---------|---------|-----------------|---------|
| GPTBot | OpenAI | `GPTBot` | Model training (NOT ChatGPT Search) |
| OAI-SearchBot | OpenAI | `OAI-SearchBot` | ChatGPT Search citability |
| ChatGPT-User | OpenAI | `ChatGPT-User` | Real-time browsing (user-triggered) |
| ClaudeBot | Anthropic | `ClaudeBot` | Model training (NOT Claude search citability) |
| Claude-SearchBot | Anthropic | `Claude-SearchBot` | Claude search-result citability |
| PerplexityBot | Perplexity | `PerplexityBot` | Search index + training |
| Bytespider | ByteDance | `Bytespider` | Model training |
| Google-Extended | Google | `Google-Extended` | Gemini training (NOT search) |
| Applebot-Extended | Apple | `Applebot-Extended` | Apple Intelligence training opt-out (NOT Siri/Spotlight/Safari) |
| CCBot | Common Crawl | `CCBot` | Open dataset |

**Key distinctions:**
- Blocking `Google-Extended` prevents Gemini training use but does NOT affect Google Search indexing or AI Overviews (those use `Googlebot`)
- Blocking `GPTBot` prevents OpenAI training but does NOT affect ChatGPT Search
  citability, which is governed by `OAI-SearchBot`, nor user-triggered browsing
  (`ChatGPT-User`). Check `OAI-SearchBot` for any citability claim; `GPTBot`
  status is evidence about training use only
- Blocking `ClaudeBot` prevents Anthropic model training but does NOT affect
  citability in Claude's own search features, which is governed by
  `Claude-SearchBot` (per Anthropic's crawler support article). Check
  `Claude-SearchBot` for any Claude-search citability claim; `ClaudeBot` status
  is evidence about training use only
- Blocking `Applebot-Extended` opts out of Apple Intelligence / generative-model
  training use but does NOT affect discoverability via Siri, Spotlight, or Safari,
  which follows `Applebot` (per Apple's support article); `Applebot-Extended` does
  not itself crawl
- ~3-5% of websites now use AI-specific robots.txt rules

**Example, selective AI crawler blocking:**
```
# Allow search indexing, block AI training crawlers
User-agent: GPTBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: Bytespider
Disallow: /

# Allow all other crawlers (including Googlebot for search)
User-agent: *
Allow: /
```

**Recommendation:** Consider your AI visibility strategy before blocking. Being cited by AI systems drives brand awareness and referral traffic. Cross-reference the `seo-geo` skill for the full AI crawler/fetcher taxonomy.

> **User-triggered fetchers ignore robots.txt by design.** Google now documents **Google-Agent** (Project Mariner, agentic browsing) plus **Google-NotebookLM** and **Google Messages** as *user-triggered* fetchers that **cannot be blocked via robots.txt**. Use server-side access controls instead. By contrast, `Google-Extended` and `Google-CloudVertexBot` obey robots.txt. Emerging: **Web Bot Auth** (RFC 9421) lets bots authenticate cryptographically via a `Signature-Agent` header + key directory at `agent.bot.goog` (used by Google-Agent); reverse-DNS verification remains the fallback.

### 2. Indexability
- Canonical tags: self-referencing, no conflicts with noindex
- Duplicate content: near-duplicates, parameter URLs, www vs non-www
- Canonicalization fixes can take time: Google may retain corrected pages in a
  duplicate cluster for **up to two weeks** while re-evaluating them. Do not
  interpret an unchanged canonical immediately after a fix as proof that the
  fix failed.
- Thin content: pages below minimum word counts per type
- Pagination: rel=next/prev or load-more pattern
- Hreflang: correct for multi-language/multi-region sites
- Index bloat: unnecessary pages consuming crawl budget

### 3. Security
- HTTPS: enforced, valid SSL certificate, no mixed content
- Security headers:
  - Content-Security-Policy (CSP)
  - Strict-Transport-Security (HSTS)
  - X-Frame-Options
  - X-Content-Type-Options
  - Referrer-Policy
- HSTS preload: check preload list inclusion for high-security sites
- **Back-button hijacking** (spam-policy violation, malicious practices): flag pages that defeat the Back button via `history.pushState`/`replaceState` (including scripts injected by third-party ad/library platforms). Added to Google's spam policies 2026-04-13; **enforcement live since 2026-06-15** (manual actions + automated demotions): treat as Critical.

### 4. URL Structure
- Clean URLs: descriptive, hyphenated, no query parameters for content
- Hierarchy: logical folder structure reflecting site architecture
- Redirects: no chains (max 1 hop), 301 for permanent moves
- URL length: flag >100 characters
- Trailing slashes: consistent usage

### 5. Mobile Optimization & Page Experience
- Responsive design: viewport meta tag, responsive CSS
- Touch targets: minimum 48x48px with 8px spacing
- Font size: minimum 16px base
- No horizontal scroll
- Mobile-first indexing: Googlebot Smartphone is the primary crawler (rollout completed 2024). A mobile version is **not strictly required** (Google says "very strongly recommended"), sites that don't work on mobile can still be indexed, but the real risk is **content/parity loss**, not hard exclusion.
- **Mobile/desktop content parity** (highest-value mobile check): equivalent primary content, matching robots meta tags, matching titles/descriptions, equivalent structured data, crawlable resources; avoid lazy-loading primary content that requires user interaction.
- **Intrusive interstitials / ad density**: flag full-page interstitials, standalone consent-redirect pages, persistent blocking dialogs, and excessive/distracting ad density (a named page-experience aspect). Acceptable: small banners, standard CMS/legal dialogs.
- **"Read more" deep links**: keep key content **immediately visible on load** (not behind tabs/accordions), don't hijack scroll on load, and preserve URL hash fragments, content hidden behind expandable sections is less likely to qualify.

> **Page experience is guidance, not a single ranking system.** Only **Core Web Vitals** feeds ranking directly; **HTTPS** is a confirmed but lightweight signal (affects <~1% of queries). Relevance can still win even when page experience is sub-par, so don't over-weight security headers. Note: the standalone **Page Experience report was removed** from Search Console (monitor via the Core Web Vitals + HTTPS reports).

### 6. Core Web Vitals
- **LCP** (Largest Contentful Paint): target <=2.5s
- **INP** (Interaction to Next Paint): target <=200ms
  - INP replaced FID on March 12, 2024. FID was removed from Chrome's field-data tools (CrUX API, PageSpeed Insights) on September 9, 2024 (Lighthouse is a lab tool that never reported FID). Do NOT reference FID anywhere.
- **CLS** (Cumulative Layout Shift): target <=0.1
- Evaluation uses 75th percentile of real user data
- Use PageSpeed Insights API or CrUX data if MCP available

### 7. Structured Data
- Detection: JSON-LD (preferred), Microdata, RDFa
- Validation against Google's supported types
- See seo-schema skill for full analysis

### 8. JavaScript Rendering
- Check if content visible in initial HTML vs requires JS
- Identify client-side rendered (CSR) vs server-side rendered (SSR)
- Flag SPA frameworks (React, Vue, Angular) that may cause indexing issues
- If dynamic rendering is detected, flag it as technical debt rather than a valid setup.
  Google documents it as "a workaround and not a recommended solution" because of the added
  complexity and resource cost.
  See https://developers.google.com/search/docs/crawling-indexing/javascript/dynamic-rendering

**Recommended rendering strategy:**

| Strategy | Use Case |
|----------|----------|
| **SSR** | Public SEO content, dynamic pages |
| **SSG** | Static content, blogs, docs |
| **CSR** | Authenticated / behind-login content only |

**Preferred frameworks:** Next.js, Astro, React Router v7 (Remix), SvelteKit

#### JavaScript SEO: Canonical & Indexing Guidance (December 2025)

Google updated its JavaScript SEO documentation in December 2025 with critical clarifications:

1. **Canonical conflicts:** If a canonical tag in raw HTML differs from one injected by JavaScript, Google may use EITHER one. Ensure canonical tags are identical between server-rendered HTML and JS-rendered output.
2. **noindex with JavaScript:** If raw HTML contains `<meta name="robots" content="noindex">` but JavaScript removes it, Google MAY still honor the noindex from raw HTML. Serve correct robots directives in the initial HTML response.
3. **Non-200 status codes:** Google does NOT render JavaScript on pages returning non-200 HTTP status codes. Any content or meta tags injected via JS on error pages will be invisible to Googlebot.
4. **Structured data in JavaScript:** Product, Article, and other structured data injected via JS may face delayed processing. For time-sensitive structured data (especially e-commerce Product markup), include it in the initial server-rendered HTML.

**Best practice:** Serve critical SEO elements (canonical, meta robots, structured data, title, meta description) in the initial server-rendered HTML rather than relying on JavaScript injection.

### 9. IndexNow Protocol
- Check if site supports IndexNow for Bing, Yandex, Naver
- Supported by search engines other than Google
- Recommend implementation for faster indexing on non-Google engines

## Agent-Friendly Pages & Agentic Browsing

Agent readiness has its own sub-skill: `/seo agentic <url>` (`seo-agentic`).
It owns the Lighthouse **Agentic Browsing** category (a fraction, X of N, not
a 0-100 score), the accessibility tree for agents, AI agent access policy,
llms.txt, Markdown delivery, ai-catalog.json, `/.well-known` discovery files,
and WebMCP. During a technical audit, record only these two signals and point
to `seo-agentic` for the rest:

- JS rendering: primary content missing from the raw HTML also hides it from
  agents that do not run JavaScript.
- A 5xx robots.txt, which compliant crawlers read as "disallow everything".

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run agent_ux_check.py https://example.com --json
```

The Agent-UX 0-100 score above is a local heuristic. Keep it distinct from the
Lighthouse fraction, and surface its findings as opportunities, not failures.

## Output

### Technical Score: XX/100

### Category Breakdown
| Category | Status | Score |
|----------|--------|-------|
| Crawlability | pass/warn/fail | XX/100 |
| Indexability | pass/warn/fail | XX/100 |
| Security | pass/warn/fail | XX/100 |
| URL Structure | pass/warn/fail | XX/100 |
| Mobile | pass/warn/fail | XX/100 |
| Core Web Vitals | pass/warn/fail | XX/100 |
| Structured Data | pass/warn/fail | XX/100 |
| JS Rendering | pass/warn/fail | XX/100 |
| IndexNow | pass/warn/fail | XX/100 |

### Critical Issues (fix immediately)
### High Priority (fix within 1 week)
### Medium Priority (fix within 1 month)
### Low Priority (backlog)

## DataForSEO Integration (Optional)

If DataForSEO MCP tools are available, use `on_page_instant_pages` for real page analysis (status codes, page timing, broken links, on-page checks), `on_page_lighthouse` for Lighthouse audits (performance, accessibility, SEO scores), and `domain_analytics_technologies_domain_technologies` for technology stack detection.

## Google API Integration (Optional)

If Google API credentials are configured, use `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run pagespeed_check.py <url> --json` for real PSI + CrUX field data (replaces lab-only CWV estimates), `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run crux_history.py <url> --json` for 25-week CWV trends, and `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run gsc_inspect.py <url> --json` for real indexation status per URL.

## Auditing a Local or Private Host

`url_safety` refuses loopback and private addresses by default, so `http://localhost:3000` and a staging host on Tailscale fail with "Blocked hostname" or "Blocked IP literal". That default is deliberate: these scripts follow URLs found on the pages they crawl.

To audit a pre-deployment host, the operator names it in `CLAUDE_SEO_LOCAL_TARGETS`, a comma-separated list of `host` or `host:port` entries:

```bash
CLAUDE_SEO_LOCAL_TARGETS="localhost:3000,127.0.0.1:8080,100.101.102.103" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run fetch_page.py http://localhost:3000/
```

What it does and does not cover:

| Behaviour | Allowlisted host |
|-----------|------------------|
| First, top-level URL over raw HTTP | Allowed |
| Redirect target reached from that URL | Refused |
| Subresource fetched by a rendered page | Refused |
| Playwright renders (`--render`, screenshots) | Refused; use the raw-HTTP path |
| A host not named in the variable | Refused |
| Cloud metadata endpoints, even when listed | Refused |

`host:port` matches that port only; a bare `host` matches any port. With the variable unset the policy is unchanged. Never suggest setting it for a host the user does not control. See SECURITY.md.

## Error Handling

| Scenario | Action |
|----------|--------|
| URL unreachable | Report connection error with status code. Suggest verifying URL, checking DNS resolution, and confirming the site is publicly accessible. |
| robots.txt not found | Note that no robots.txt was detected at the root domain. Recommend creating one with appropriate directives. Continue audit on remaining categories. |
| HTTPS not configured | Flag as a critical issue. Report whether HTTP is served without redirect, mixed content exists, or SSL certificate is missing/expired. |
| Core Web Vitals data unavailable | Note that CrUX data is not available (common for low-traffic sites). Suggest using Lighthouse lab data as a proxy and recommend increasing traffic before re-testing. |
