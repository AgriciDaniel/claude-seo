![Claude SEO cover: a Claude Code command palette with /seo audit, schema, geo, content, and backlinks commands over a dark CRT panel](assets/cover.svg)

# Claude SEO: SEO Skill for Claude Code

**Claude SEO is an open-source SEO analysis plugin for [Claude Code](https://claude.ai/claude-code).** It runs 25 sub-skills and 18 specialist agents in parallel across technical SEO, content quality (E-E-A-T), Schema.org markup, AI search optimization (GEO), local SEO, e-commerce, and international SEO. Every audit produces a prioritized action plan with testable recommendations grounded in primary-source guidance from Google.

[![CI](https://github.com/AgriciDaniel/claude-seo/actions/workflows/ci.yml/badge.svg)](https://github.com/AgriciDaniel/claude-seo/actions/workflows/ci.yml)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-blue)](https://claude.ai/claude-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/github/v/release/AgriciDaniel/claude-seo)](https://github.com/AgriciDaniel/claude-seo/releases)
[![Tests](https://img.shields.io/badge/tests-326%20passing-brightgreen)](tests/)
[![Community](https://img.shields.io/badge/AI%20Marketing%20Hub-Pro%20community-purple)](https://www.skool.com/ai-marketing-hub-pro)

> **Two versions of this skill.**
> - 🌐 **Public open-source** → [`AgriciDaniel/claude-seo`](https://github.com/AgriciDaniel/claude-seo): MIT, public releases, no membership. Use this if you want stable + downloadable.
> - 🔒 **Community private mirror** → [`AI-Marketing-Hub/claude-seo`](https://github.com/AI-Marketing-Hub/claude-seo): early access to upcoming features and direct collaboration with the [AI Marketing Hub Pro](https://www.skool.com/ai-marketing-hub-pro) community. Requires membership.

### Why Claude SEO

- **AI-search first.** Aligned with [Google's AI Optimization Guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide). Question-based citability scoring, primary-source evidence on llms.txt, IPTC `TrainedAlgorithmicMedia` for AI-generated product images, agent-friendly page checks per [web.dev](https://web.dev/).
- **Parallel execution.** Full site audits spawn up to 15 specialist agents simultaneously. Site-level audits complete in minutes rather than hours.
- **Falsifiable, not promotional.** Every recommendation carries the first-principle observation it rests on, its dependency relationships, an explicit "how would we know this failed?" check, and a leading indicator. See [Methodology](#methodology).

### Real results

![Google Search Console clicks and impressions for a three-month-old site climbing from launch to steady organic growth between 23 March and 12 June 2026](assets/growth-3-months.png)

Google Search Console for a site started 23 March 2026 and run on this workflow: total clicks and impressions across its first three months, through 12 June 2026.

> Using Codex instead of Claude Code? Use [Codex SEO](https://github.com/AgriciDaniel/codex-seo), the Codex-first port with TOML agents, plugin packaging, deterministic runners, and the same SEO workflow surface.

## Who this is for

- **SEO agencies running 5+ client sites.** Replace quarterly deep audits with weekly automated runs. Same team capacity, 4× audit cadence, every recommendation comes with a falsifiability check the client can verify.
- **In-house SEO leads at SaaS / publisher / e-commerce companies.** Second-pair-of-eyes before executive reviews. Catches what GSC and Lighthouse hide: schema deprecation, AI-citability gaps, expired-domain heritage risk, parasite-SEO exposure, machine-translation drift.
- **Freelance SEO consultants.** Anchor day-one client scope with a 15-minute audit and a real 0-100 score. Win the engagement with concrete proof of value before you spend an hour writing the proposal.

![Claude SEO /seo command demo in Claude Code terminal](screenshots/seo-command-demo.gif)

Run a full audit and watch parallel agents fan out across the site:

![Claude SEO /seo audit demo: parallel subagents producing a prioritized action plan](screenshots/seo-audit-demo.gif)

[Watch the full demo on YouTube](https://www.youtube.com/watch?v=COMnNlUakQk)

## Table of Contents

- [Who this is for](#who-this-is-for)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Commands](#commands)
- [Features](#features)
- [Compared to manual / agency / commercial tools](#compared-to-manual--agency--commercial-tools)
- [Use cases](#use-cases)
- [Sample Output](#sample-output)
- [Architecture](#architecture)
- [Methodology](#methodology)
- [What's New in v2](#whats-new-in-v2)
- [Limitations](#limitations)
- [Requirements](#requirements)
- [Uninstall](#uninstall)
- [Extensions](#extensions)
- [Ecosystem](#ecosystem)
- [Documentation](#documentation)
- [FAQ](#faq)
- [Community Contributors](#community-contributors)
- [License](#license)
- [Contributing](#contributing)
- [Author](#author)

## Installation

> ℹ️ **Which version are you installing?**
>
> - **Public open-source (default).** The commands below install from [`AgriciDaniel/claude-seo`](https://github.com/AgriciDaniel/claude-seo) — MIT, public releases, no membership required.
> - **AI Marketing Hub Pro member?** Install the community version with early access instead: swap `AgriciDaniel/claude-seo` for `AI-Marketing-Hub/claude-seo` and the plugin slug `claude-seo@agricidaniel-claude-seo` for `claude-seo@ai-marketing-hub-claude-seo`. Requires `gh auth login` (or PAT) with access to the `AI-Marketing-Hub` org. If `/plugin marketplace add` 404s, DM in the [Skool community](https://www.skool.com/ai-marketing-hub-pro) to get added.

### Plugin Install (Claude Code 1.0.33+)

The fastest path. One-time marketplace add, then plugin install:

```bash
/plugin marketplace add AgriciDaniel/claude-seo
/plugin install claude-seo@agricidaniel-claude-seo
```

### Manual Install (Unix / macOS / Linux)

```bash
git clone --depth 1 https://github.com/AgriciDaniel/claude-seo.git
bash claude-seo/install.sh
```

<details>
<summary>One-liner (curl, review then run)</summary>

```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh > install.sh
cat install.sh        # review before running
bash install.sh
rm install.sh
```

</details>

### Windows (PowerShell)

```powershell
git clone --depth 1 https://github.com/AgriciDaniel/claude-seo.git
powershell -ExecutionPolicy Bypass -File claude-seo\install.ps1
```

> **Why `git clone` instead of `irm | iex`?** Claude Code's own security guardrails flag `irm ... | iex` as a supply chain risk: downloading and executing remote code without verification. The `git clone` approach lets you inspect `claude-seo\install.ps1` before running it.

## Quick Start

```bash
# Start Claude Code
claude

# Full site audit: parallel sub-agents produce a prioritized action plan
/seo audit https://example.com

# Deep single-page analysis: on-page elements, content quality, schema
/seo page https://example.com/about

# Schema markup audit: detect, validate, generate
/seo schema https://example.com

# AI search optimization: passage citability + primary-source-aligned recommendations
/seo geo https://example.com

# Generate a sitemap with industry templates
/seo sitemap generate
```

## Commands

![Claude SEO sub-skill ecosystem: 25 modules grouped into 8 categories (audit, content, schema, technical, AI search, local + maps, commerce + intl, extensions) around the central orchestrator](assets/sub-skills.svg)

25 user-invocable `/seo` commands across the orchestrator and its sub-skills. Full reference in [docs/COMMANDS.md](docs/COMMANDS.md).

| Command | Description |
|---------|-------------|
| `/seo audit <url>` | Full website audit with parallel sub-agent delegation |
| `/seo page <url>` | Deep single-page analysis |
| `/seo technical <url>` | Technical SEO audit across 9 categories |
| `/seo content <url>` | E-E-A-T and content quality analysis |
| `/seo content-brief <topic>` | Detailed content brief: target keywords, outline, internal links |
| `/seo schema <url>` | Detect, validate, and generate Schema.org markup |
| `/seo geo <url>` | AI Overviews / Generative Engine Optimization |
| `/seo sitemap <url \| generate>` | Analyze or generate XML sitemaps |
| `/seo images <url>` | Image optimization analysis |
| `/seo plan <type>` | Strategic SEO planning (saas, local, ecommerce, publisher, agency) |
| `/seo programmatic <url>` | Programmatic SEO analysis and planning |
| `/seo competitor-pages <url>` | Competitor comparison page generation |
| `/seo local <url>` | Local SEO analysis (GBP, citations, reviews, map pack) |
| `/seo maps [command]` | Maps intelligence (geo-grid, GBP audit, reviews, competitors) |
| `/seo hreflang <url>` | Hreflang / i18n SEO audit and generation |
| `/seo google [command]` | Google SEO APIs (GSC, PageSpeed, CrUX, Indexing, GA4, PDF reports) |
| `/seo backlinks <url>` | Backlink profile analysis (Moz, Bing, Common Crawl) |
| `/seo cluster <keyword>` | SERP-based semantic clustering |
| `/seo sxo <url>` | Search Experience Optimization (page-type, user stories, personas) |
| `/seo drift baseline \| compare \| history <url>` | SEO drift monitoring with SQLite snapshots |
| `/seo ecommerce <url>` | E-commerce SEO and marketplace intelligence |
| `/seo flow [stage]` | FLOW framework prompts (CC BY 4.0, evidence-led) |
| `/seo firecrawl [command] <url>` | Full-site crawling (extension) |
| `/seo dataforseo [command]` | Live SEO data (extension) |
| `/seo image-gen [use-case]` | AI image generation for SEO assets (extension) |

## Features

### What Core Web Vitals does Claude SEO check?

Claude SEO measures the current three Core Web Vitals: **LCP** (Largest Contentful Paint, target under 2.5s), **INP** (Interaction to Next Paint, target under 200ms), and **CLS** (Cumulative Layout Shift, target under 0.1). [INP replaced FID](https://web.dev/articles/inp) on March 12, 2024; FID was removed from all Chrome tools (CrUX API, PageSpeed Insights, Lighthouse) on September 9, 2024, and Claude SEO never references FID. Field data comes from the Chrome User Experience Report (CrUX) when available; lab data falls back to Lighthouse via PageSpeed Insights. LCP can be decomposed into subparts (TTFB, load delay, load duration, render delay) via the `/seo google` CrUX integration to localize bottlenecks. Mobile and desktop are measured separately. CrUX History (25-week trend) is included in the Tier 0 free credential set.

### How does Claude SEO assess E-E-A-T?

E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) is evaluated against the Search Quality Rater Guidelines, last updated September 2025 with YMYL expanded to include political and social topics. Experience signals: original research, case studies, first-hand photos. Expertise: author credentials and topical depth. Authoritativeness: external citations and brand mentions. Trustworthiness, the most heavily weighted of the four: contact info, secure HTTPS, transparent corrections, date stamps. Before scoring sub-factors, Claude SEO applies Google's own Who / How / Why heuristic from the [helpful-content guide](https://developers.google.com/search/docs/fundamentals/creating-helpful-content). Generative AI content is fine if it meets Search Essentials; it crosses into spam when used to scale low-value pages, which `seo-content humanize` and `seo-content verify` are designed to detect.

### What Schema.org types does Claude SEO support?

JSON-LD is the preferred format (Google's stated preference). Active types Claude SEO detects, validates, and generates: Organization, LocalBusiness, Article, BlogPosting, NewsArticle, Product, ProductGroup, Offer, Review, AggregateRating, BreadcrumbList, WebSite, WebPage, Person, ProfilePage, ContactPage, VideoObject, ImageObject, Event, JobPosting, Course, DiscussionForumPosting, Reservation, OrderAction, plus video and specialized types (BroadcastEvent, Clip, SeekToAction, SoftwareSourceCode). FAQPage: Google stopped showing FAQ rich results for all sites on May 7, 2026; still useful as a supporting AI/entity signal, not for rich results. Deprecated and never recommended: HowTo (rich results removed September 2023), SpecialAnnouncement (July 2025), ClaimReview, VehicleListing, EstimatedSalary, LearningVideo, CourseInfo carousel (all retired June 2025). Replacement guidance: [skills/seo-schema/references/deprecated-types-2024-2026.md](skills/seo-schema/references/deprecated-types-2024-2026.md).

### How does Claude SEO optimize for AI search?

Aligned with [Google's AI Optimization Guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide), which states that "AEO" and "GEO" are rebranded labels for SEO. AI Overviews and AI Mode are grounded in the same ranking systems as classic Search; pages must be indexed and eligible for snippet display to appear in any AI feature. Claude SEO scores passage citability (optimal 134-167 word self-contained answer blocks), question-based heading hierarchy, attribution density, structured data coverage, and entity presence across Wikipedia, Reddit, YouTube, and LinkedIn. The `seo-geo` skill includes evidence-based reframes of three popular myths: llms.txt is not currently a citation lever ([primary-source evidence](skills/seo-geo/references/llmstxt-evidence.md)), content chunking is not required, and AI-specific keyword rewriting is unnecessary because synonym understanding is sufficient.

### Which Google SEO APIs does Claude SEO integrate with?

A 4-tier credential system lets you start with zero keys and add data as needed. Every tier delivers real value at its level:

| Tier | Credentials | APIs Unlocked |
|------|------|------|
| 0 | API key | PageSpeed Insights, CrUX, CrUX History (25-week trends) |
| 1 | + OAuth or Service Account | + Search Console (queries, URL Inspection, sitemap status), Indexing API |
| 2 | + GA4 property config | + GA4 organic traffic, top landing pages, device / country breakdown |
| 3 | + Ads developer token | + Keyword Planner search volume and competition data |

PDF reports are generated via [WeasyPrint](https://weasyprint.org/) (A4 layout) with matplotlib charts at 200 DPI. Run `/seo google setup` for the credential wizard. All credentials live under `~/.config/claude-seo/` with `0o600` permissions; nothing is checked into the repo.

### How does Claude SEO handle local SEO?

Three layers. **Google Business Profile signals**: categories, hours, photos, posts, products, attributes. **NAP consistency** across citations: name, address, phone matched against major directories with deviation flagging. **Review intelligence**: rating trends, sentiment, response coverage. For multi-location businesses, Claude SEO enforces a 30-page warning threshold and a 50-page hard stop to prevent doorway-page violations (configurable). The `/seo maps` workflow adds geo-grid rank tracking, GBP profile auditing, and competitor radius mapping. Local schema generation covers `LocalBusiness` with all required and recommended properties (geo coordinates, opening hours, areaServed). Phase F (v2) added a GBP deprecation linter that detects retired chat-field references and `.business.site` URLs.

## Bring your own knowledge (optional)

Teams that maintain their own cited SEO knowledge (house playbooks, or API cost and rate-limit facts that move faster than a plugin release) can feed it to the orchestrator without forking the plugin.

Set `CLAUDE_SEO_KNOWLEDGE_DIR` to a directory, or use the zero-config default `~/.claude/skill-knowledge/seo/wiki/`. The orchestrator reads its `index.md` and `hot.md`, reasons over the relevant notes alongside the built-in references, and (during `/seo audit`) passes the relevant facts into each subagent's Task prompt. It is opt-in and a no-op when the directory is absent.

Guardrails: the read is read-only, nothing from the directory is executed, external notes are treated as operator-supplied context rather than authority over Google or primary-source facts, and notes are expected to carry a dated `## Sources` block.

## Compared to manual / agency / commercial tools

| | Manual audit | Agency engagement | Commercial SEO audit tool | **Claude SEO** |
|---|---|---|---|---|
| **Time per audit** | 4-8 hrs senior SEO time | 1-3 weeks turnaround | 10-45 min crawl + report | **10-15 min** |
| **Cost** | High (billable hours) | $2k-$15k+ project | $99-$999/mo subscription | **Free skill + Claude Code subscription** |
| **Repeatable** | Inconsistent across analysts | Inconsistent across engagements | Yes | **Yes, deterministic + scriptable** |
| **Output format** | Wall-of-findings PDF | Branded slide deck | Web dashboard, CSV exports | **Markdown + PDF + JSON, local files** |
| **Custom benchmarks** | Manual per analyst | Agency-specific frameworks | Vendor-fixed | **Edit local SKILL.md** |
| **Data leaves machine?** | No (your spreadsheet) | Yes (sent to agency) | Yes (uploaded to vendor) | **No, fully local by default** |
| **Lock-in** | None | High | High (data-exit friction) | **None. MIT, your files.** |
| **AI search awareness** | Depends on analyst | Depends on agency seniority | Lagging (typically 6-12 mo behind) | **Google AI Optimization Guide (May 2026), Sept 2025 QRG, INP-not-FID, GEO/AEO=SEO reframe, llms.txt evidence-based posture** |
| **Falsifiability per finding** | No | No | No | **Yes. Every recommendation carries a "how would we know this failed?" check + leading indicator** |

> Cost benchmarks: manual audit assumes a senior SEO consultant at typical agency billable rates; agency engagement based on common discovery/audit deliverable scopes; commercial-tool subscriptions reflect published mid-tier pricing across the SEO audit category (Ahrefs, Semrush, Sitebulb, Screaming Frog). Your numbers may differ.

## Use cases

**SEO agency lead running 10 client sites.** Replaces the quarterly "deep audit" ritual with a weekly Monday-morning `/seo audit` run per site. Time to deliver a client health-score email drops from 4 hours to 12 minutes; coverage goes from quarterly to weekly without billing more hours. The drift baseline catches regressions between audits so the client conversation moves from "look at this snapshot" to "here is what changed this week."

**In-house SEO lead at a 50-person SaaS company.** Runs `/seo audit` 24 hours before each quarterly business review. Catches the items the platform UI buries (broken canonical chains on programmatic pages, schema deprecation after Google's June 2025 retirement wave, AI-citability gaps that erode SERP-to-AI-Overview pickup, expired-domain heritage on acquired blog assets) before the CMO asks why organic traffic is down in front of the board.

**Freelance SEO consultant onboarding a new client.** Runs `/seo audit` on the discovery call. Anchors the engagement scope with a real 0-100 score, 3 prioritized critical findings, and a falsifiability check on each recommendation, instead of a vague "I'll take a look and get back to you." Closes more retainers because the proof of value happens during the call, not after the proposal.

## Sample Output

Claude SEO writes real markdown reports as its primary deliverable. Below is the first ~50 lines of a `/seo schema https://rankenstein.pro/about` audit verbatim. The actual structure, headers, and grading format the plugin produces follows.

<details>
<summary><code>SCHEMA-REPORT.md</code>: first 50 lines of a real audit</summary>

```markdown
# Schema Markup Report: rankenstein.pro/about

**URL:** https://rankenstein.pro/about
**Date:** 2026-02-09
**Format Detected:** JSON-LD (3 blocks) | No Microdata | No RDFa

---

## Summary

| Metric | Value |
|--------|-------|
| **JSON-LD Blocks** | 3 |
| **Schema Types** | Organization, WebSite, SoftwareApplication |
| **Critical Issues** | 2 |
| **Warnings** | 5 |
| **Passed Checks** | 18 |
| **Overall Grade** | B+ (solid foundation, actionable gaps) |

---

## Existing Schema Validation

### 1. Organization (`@id: #organization`)

| Property | Value | Status | Notes |
|----------|-------|--------|-------|
| `@context` | https://schema.org | Valid | |
| `@type` | Organization | Valid | Active type |
| `@id` | https://rankenstein.pro#organization | Good | Enables cross-referencing |
| `name` | Rankenstein | Valid | |
| `description` | Present, 200+ chars | Good | Descriptive and keyword-rich |
| `url` | https://rankenstein.pro | Valid | Absolute URL |
| `logo` | ImageObject with @id, url, width, height, caption | Excellent | Well-structured |
| `foundingDate` | "2024" | Imprecise | Year-only accepted but ISO 8601 preferred |
| `areaServed` | "Worldwide" | Text | Works but `GeoShape` is more semantic |
| `contactPoint` | email + contactType | Valid | Consider adding `telephone` |
| `founder` | 1 Person (Daniel Agrici) | Incomplete | Page describes two co-founders; second missing |
| `sameAs` | 5 social profiles | Good | GitHub, X, LinkedIn, YouTube, Reddit |
| `knowsAbout` | 6 topics | Good | Relevant topical signals |

**Critical Issue:** The `founder` property only includes Daniel Agrici. Benjamin Samar (Co-Founder & Technical Director) is displayed on the page but absent from the schema. This creates a content-schema mismatch that can confuse search engines.
```

</details>

Other audit outputs follow the same shape: `FULL-AUDIT-REPORT.md` (umbrella audit), `GEO-ANALYSIS.md` (AI-search readiness), `LOCAL-SEO-ANALYSIS.md` (GBP and citations), and a production PDF via WeasyPrint + matplotlib (cover, TOC, executive summary, data sections, recommendations, methodology, roughly 32 A4 pages for a full site audit).

## Architecture

![Claude SEO audit signal flow: /seo audit enters the orchestrator, fans out to 25 sub-skills and 6 parallel audit agents, and converges through the scoring engine into a prioritized report](assets/signal-flow.svg)

The plugin follows the [Agent Skills standard](https://docs.claude.com/en/docs/claude-code/skills) with a 3-layer architecture (directive, orchestration, execution). Skills and agents are auto-discovered from `skills/seo-*/` and `agents/seo-*.md`. The orchestrator (`skills/seo/SKILL.md`) handles industry detection (SaaS, local, ecommerce, publisher, agency), parallel sub-agent dispatch up to 15 simultaneously, and synthesis through the [10-principle framework](#methodology) before emitting the action plan. Full architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Methodology

![Claude SEO 10-principle methodology: PERCEIVE, ANALYZE, VALIDATE, and ACT phases with 10 principles arranged by quadrant](assets/framework.svg)

Every audit walks 10 principles grouped into four phases. Each emitted recommendation carries four fields: the first-principle observation it rests on, its dependency relationship to other recommendations, a "how would we know this failed?" check, and a leading indicator to monitor.

| Phase | Principles | What it does |
|---|---|---|
| **PERCEIVE** | OBSERVE (external) · OBSERVE (internal) · LISTEN | Collect raw signals; audit your own assumptions; read what the SERP, the brand voice, and the community actually say |
| **ANALYZE** | THINK · CONNECT (lateral) · CONNECT (system) | Reduce to first principles; find non-obvious cross-skill links; sequence into a dependency graph |
| **VALIDATE** | FEEL · ACCEPT | Pressure-test against UX, brand voice, operator capacity; surface falsifiability |
| **ACT** | CREATE · GROW | Ship the artifact; set the feedback loop for the next audit |

Full methodology: [skills/seo/references/thinking-framework.md](skills/seo/references/thinking-framework.md).

## What's New in v2

v2.0.0 is the largest release in the plugin's history. Six build phases, all shipped:

- **Phase A: Headless rendering everywhere.** Shared `scripts/render_page.py` with Playwright Chromium plus [trafilatura](https://github.com/adbar/trafilatura) and [htmldate](https://github.com/adbar/htmldate). Every audit subagent gets SPA-aware fetching via `--render auto` (auto-detected on Next.js, React, Vue, Nuxt, Astro islands). Closes the SPA limitation that capped v1.x.
- **Phase B: QRG-aligned content quality gates.** Filler detector and AI-pattern humanizer keyed to QRG §4.6.5 and §4.6.6, claim-verification scanner, expired-domain heritage check via WHOIS, primary-source Google updates changelog.
- **Phase C: Technical and CWV depth.** LCP subparts via CrUX (TTFB, load delay, load duration, render delay), Speculation Rules and bfcache detection, IndexNow submitter for Bing / Yandex / Seznam / Naver, Unlighthouse multi-page Lighthouse wrapper.
- **Phase D: Schema completeness.** Four explicit generators (Reservation, OrderAction, DiscussionForumPosting, ProfilePage), e-commerce schema validator (`hasMerchantReturnPolicy`, `shippingDetails`, `MemberProgram`, EU `energyEfficiencyClass`, ProductGroup variants), dual validator (Rich Results Test plus Schema Markup Validator).
- **Phase E: AI search reframing and 5 new MCP extensions.** Ahrefs, SE Ranking (AI Share-of-Voice), Profound (LLM citation tracker), Bing Webmaster plus IndexNow, Unlighthouse. Plus the parasite-SEO risk scanner per Google's November 2024 [site reputation abuse policy](https://developers.google.com/search/blog/2024/11/site-reputation-abuse-update).
- **Phase F: Local, international, and privacy polish.** Google Business Profile deprecation linter (chat field, `.business.site` URLs, Q&A), DMA consent-mode-v2 click-through diagnostic, machine-translation QA flag per January 2025 QRG.

Test coverage: 248 → 271 (a 5.4× increase over the v1.9.9 baseline). 83 SSRF and DNS-rebinding bypass tests close the full obfuscated-IPv4, FQDN-trailing-dot, and redirect-rebinding bypass classes. Full migration notes and breaking changes: [docs/MIGRATION-v1-to-v2.md](docs/MIGRATION-v1-to-v2.md).

## Limitations

Two real boundaries worth being upfront about.

**Heavy client-side hydration timing.** Phase A's headless renderer handles most SPAs out of the box (`--render auto` detects empty `<div id="root">` shells and switches to Playwright). Edge cases that still produce noisy findings: pages with hydration tied to scroll position past the fold, pages that fetch critical content after user interaction (modal opens, tab clicks), pages with race-condition-prone third-party widget mounts. For these, manually triggering the `seo-visual` subagent and comparing its Playwright snapshot to the raw-HTML subagents' findings is the recommended workflow.

**Local-only without enrichment.** The free tier does not call any external API and produces zero-network output. Adding Google API credentials (Tier 0 through 3) unlocks real field data and live indexation status; without them, Core Web Vitals are lab estimates only and indexation is inferred from page-level signals. Adding MCP extensions (Ahrefs, DataForSEO, SE Ranking, Profound) similarly unlocks competitive and AI-citation data but requires their respective accounts.

## Requirements

- Python 3.10+
- Claude Code CLI
- Optional: Playwright Chromium (auto-installed by `install.sh`) for SPA rendering and screenshots
- Optional: Google API credentials for enriched CWV / GSC / GA4 data (see `/seo google setup`)

## Uninstall

```bash
git clone --depth 1 https://github.com/AgriciDaniel/claude-seo.git
bash claude-seo/uninstall.sh
```

<details>
<summary>One-liner (curl)</summary>

```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/uninstall.sh | bash
```

</details>

## Extensions

Optional MCP servers add live data to the audit pipeline. Claude SEO ships extensions for 8 servers; the plugin core works without any of them.

### DataForSEO

Live SERP data, keyword research, backlinks, on-page analysis, content analysis, business listings, AI visibility checks, and LLM mention tracking. 22 commands across 9 API modules.

```bash
./extensions/dataforseo/install.sh   # requires DataForSEO account
/seo dataforseo serp best coffee shops
/seo dataforseo ai-mentions your brand
```

Full DataForSEO docs: [extensions/dataforseo/README.md](extensions/dataforseo/README.md).

### Firecrawl

Full-site crawling and URL discovery via the [Firecrawl](https://www.firecrawl.dev/) MCP server.

```bash
./extensions/firecrawl/install.sh
/seo firecrawl crawl https://example.com
```

Full Firecrawl docs: [extensions/firecrawl/README.md](extensions/firecrawl/README.md).

### Banana: AI image generation

SEO image generation (OG previews, blog heroes, product photos, infographics) via the [Claude Banana](https://github.com/AgriciDaniel/banana-claude) Creative Director pipeline.

```bash
./extensions/banana/install.sh
/seo image-gen og "Professional SaaS dashboard"
```

Full Banana docs: [extensions/banana/README.md](extensions/banana/README.md).

### Ahrefs, SE Ranking, Profound, Bing Webmaster, Unlighthouse (new in v2)

Five extensions added in Phase E:

- **Ahrefs:** official `@ahrefs/mcp` server with backlink and organic data
- **SE Ranking:** AI Share-of-Voice across ChatGPT, Gemini, Perplexity, AI Overviews, AI Mode
- **Profound:** LLM citation tracker with time-series data
- **Bing Webmaster:** Bing Webmaster Tools plus IndexNow unified
- **Unlighthouse:** MIT-licensed multi-page Lighthouse runner

Setup walkthroughs: [docs/MCP-INTEGRATION.md](docs/MCP-INTEGRATION.md).

## Ecosystem

Claude SEO is part of a family of Claude Code skills that interoperate cleanly:

| Skill | What it does | How it connects |
|-------|-------------|-----------------|
| [Claude SEO](https://github.com/AgriciDaniel/claude-seo) | SEO analysis, audits, schema, GEO | Core. Analyzes sites and generates action plans. |
| [Claude Blog](https://github.com/AgriciDaniel/claude-blog) | Blog writing, optimization, scoring | Companion. Writes content optimized by SEO findings. |
| [Claude Banana](https://github.com/AgriciDaniel/banana-claude) | AI image generation via Gemini | Shared. Generates images for SEO assets and blog posts. |
| [Codex SEO](https://github.com/AgriciDaniel/codex-seo) | Codex-first SEO skill suite | Port. Same SEO system adapted for Codex skills, TOML agents, deterministic runners. |
| [AI Marketing Claude](https://github.com/zubair-trabzada/ai-marketing-claude) | Copywriting, emails, social, ads, funnels, CRO | Community. Post-audit marketing action from SEO findings. |
| [FLOW](https://github.com/AgriciDaniel/flow) | Evidence-led SEO framework (41 AI prompts, CC BY 4.0) | Knowledge base. Powers `seo-flow` prompts. |

**Workflow example:**

1. `/seo audit https://example.com`: identify content gaps and technical issues
2. `/seo backlinks https://example.com`: analyze link profile and competitor gaps
3. `/seo geo https://example.com/blog/post`: score AI-citation readiness
4. `/blog write "target keyword"`: create SEO-optimized blog post (Claude Blog)
5. `/seo image-gen hero "blog topic"`: generate hero image (Banana extension)

## Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Commands Reference](docs/COMMANDS.md): every `/seo` command in depth
- [Architecture](docs/ARCHITECTURE.md): 3-layer design, auto-discovery, parallel dispatch
- [Migration v1 → v2](docs/MIGRATION-v1-to-v2.md): breaking changes, six phases of work
- [MCP Integration](docs/MCP-INTEGRATION.md): extension setup for all 8 servers
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Contributors](CONTRIBUTORS.md): community credits

## FAQ

### What is Claude SEO?

Claude SEO is an open-source SEO analysis plugin for Claude Code. It runs 25 sub-skills and 18 specialist agents in parallel across technical SEO, content quality, Schema.org markup, AI search optimization, local SEO, e-commerce, and international SEO. Audits produce a prioritized action plan where each recommendation carries the first-principle observation it rests on, its dependency relationship to other recommendations, a "how would we know this failed?" check, and a leading indicator. The plugin is MIT-licensed, ships zero proprietary tracking, and works fully offline if you skip the optional Google API and MCP-extension enrichments. Aligned with [Google's AI Optimization Guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide) and the September 2025 Quality Rater Guidelines.

### How is Claude SEO different from Screaming Frog or Ahrefs Site Audit?

Different surface area, different tradeoffs. **Screaming Frog** crawls deeper and faster at the link-graph level; it is purpose-built as a crawler and Claude SEO does not attempt to replace it. **Ahrefs Site Audit** brings a proprietary backlink index and link intelligence; Claude SEO integrates with Ahrefs via its MCP extension rather than competing. Where Claude SEO leads: conversational LLM-native workflow, recommendation falsifiability (every finding carries an explicit failure-mode check), open-source MIT licensing with zero per-domain pricing, AI search optimization aligned with Google's primary-source guidance, and primary-source schema-deprecation tracking. Use Screaming Frog or Ahrefs for what they are best at; use Claude SEO when you want LLM-driven synthesis, conversational iteration, and AI-search-first audits in the same environment as your other Claude Code workflows.

### Does Claude SEO work on single-page applications (Next.js, React, Vue)?

Yes. Phase A of v2 shipped a shared headless renderer (`scripts/render_page.py`) backed by Playwright Chromium. Every fetching subagent supports `--render auto` (the default), which auto-detects SPA hallmarks (empty `<div id="root">` shells, single bundle script, hydration markers) and switches to a rendered fetch. Set `--render always` to force rendering, or `--render never` for raw HTML only. Content extraction uses [trafilatura](https://github.com/adbar/trafilatura) for boilerplate removal. Publication dates come from [htmldate](https://github.com/adbar/htmldate). Known nuance: pages with scroll-bound hydration or post-interaction content fetches still produce noisy findings; see the [Limitations](#limitations) section for the recommended `seo-visual` cross-check workflow on those edge cases.

### What Google APIs does Claude SEO use, and are they required?

None are required. Claude SEO is fully functional with zero API keys. A 4-tier credential system lets you upgrade gradually: Tier 0 (API key only) unlocks PageSpeed Insights, CrUX, and CrUX History (25-week trend data). Tier 1 (+ OAuth or service account) adds Search Console with queries, URL Inspection, sitemap status, and the Indexing API. Tier 2 (+ GA4 property config) adds organic traffic, top landing pages, and device / country breakdowns. Tier 3 (+ Ads developer token) adds Keyword Planner search volume and competition data. The credential setup wizard runs via `/seo google setup`. All credentials live under `~/.config/claude-seo/` with `0o600` file permissions; nothing is checked into the repo and nothing is transmitted beyond Google's own endpoints.

### Is Claude SEO free?

Yes. MIT licensed, fully open source, no per-domain pricing, no telemetry, no API quotas imposed by the plugin itself. The core plugin and all 25 sub-skills work without any paid service. Some optional MCP extensions wrap paid services (DataForSEO, Ahrefs, Profound, SE Ranking) where you bring your own account credentials; their use is opt-in and the plugin works fully without them. Google APIs (PageSpeed Insights, Search Console, Indexing, GA4) are free from Google with normal account quota limits and require your own credentials. If you want commercial support or enterprise features beyond the open-source plugin, that is not part of this project.

### How is Claude SEO different from regular SEO tools when it comes to AI search?

Most SEO tools treat AI search as a separate optimization discipline. Claude SEO follows [Google's own position](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide) that AEO and GEO are rebranded labels for SEO. AI Overviews and AI Mode are grounded in the same ranking systems as classic Search; the eligibility floor is normal indexation. Claude SEO scores passage citability (134-167 word self-contained answer blocks), question-based heading hierarchy, attribution density, and entity presence across Wikipedia, Reddit, YouTube, and LinkedIn. It explicitly rejects three influencer myths: llms.txt as a citation lever, content chunking for AI, and AI-specific keyword rewriting. For commerce sites, Claude SEO audits the IPTC `TrainedAlgorithmicMedia` requirement on AI-generated product images per Google Merchant Center policy.

## Community Contributors

v1.9.0 includes contributions from the [AI Marketing Hub](https://www.skool.com/ai-marketing-hub) Pro Hub Challenge:

| Contributor | Contribution |
|------------|-------------|
| **Lutfiya Miller** (Winner) | Semantic Cluster Engine → `seo-cluster` |
| **Florian Schmitz** | SXO Skill → `seo-sxo` |
| **Dan Colta** | SEO Drift Monitor → `seo-drift` |
| **Chris Muller** | Multi-lingual SEO → `seo-hreflang` enhancements |
| **Matej Marjanovic** | E-commerce + DataForSEO Cost Config → `seo-ecommerce` + cost guardrails |

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for full details and original repo links.

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting PRs. The project enforces a per-PR audit gate covering manifest consistency (14 assertions), the test suite (326 passing), and an 8-dimension security review before any merge to `main`.

---

## Author

Built by **[Agrici Daniel](https://agricidaniel.com/about)**, AI Workflow Architect. Single maintainer, open to community contributions via the [Pro Skool community](https://www.skool.com/ai-marketing-hub-pro). Background in marketing automation, AI-assisted content workflows, and open-source tooling for Claude Code.

- [Blog](https://agricidaniel.com/blog): deep dives on AI marketing automation
- [AI Marketing Hub (free)](https://www.skool.com/ai-marketing-hub): open community
- [AI Marketing Hub Pro](https://www.skool.com/ai-marketing-hub-pro): Pro community, early access to this skill
- [YouTube](https://www.youtube.com/@AgriciDaniel): tutorials and demos
- [GitHub](https://github.com/AgriciDaniel): all open-source tools
