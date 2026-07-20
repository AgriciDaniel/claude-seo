---
name: seo-content
description: >
  Content quality and E-E-A-T analysis with AI citation readiness assessment.
  Use when user says "content quality", "E-E-A-T", "content analysis",
  "readability check", "thin content", or "content audit".
user-invocable: true
argument-hint: "[url]"
license: MIT
metadata:
  author: AgriciDaniel
  version: "2.2.3"
  category: seo
---

# Content Quality & E-E-A-T Analysis

## Google's "Who / How / Why" Test (canonical heuristic)

Before scoring E-E-A-T sub-factors, every page audit should pass Google's
own three-question heuristic from the helpful-content guide:

| Question | What to look for |
|---|---|
| **Who** created it? | Visible byline, author bio page, professional credentials. Required where readers expect it; non-negotiable for YMYL. |
| **How** was it created? | Process disclosure where readers would reasonably ask, especially for AI-assisted content. Original research / first-hand evidence / lived experience. |
| **Why** does it exist? | "To help people" rather than "to attract search clicks." Watch for niche entry without expertise, content churn for freshness signals, content written to a word-count target. |

Primary source:
https://developers.google.com/search/docs/fundamentals/creating-helpful-content

When all three answers are weak, the page is at risk under the core ranking
system's helpfulness signals (formerly the standalone Helpful Content System,
merged into core during the March 2024 update).

## E-E-A-T Framework (updated Sept 2025 QRG)

Read `skills/seo/references/eeat-framework.md` for full criteria.

### Experience (first-hand signals)
- Original research, case studies, before/after results
- Personal anecdotes, process documentation
- Unique data, proprietary insights
- Photos/videos from direct experience

### Expertise
- Author credentials, certifications, bio
- Professional background relevant to topic
- Technical depth appropriate for audience
- Accurate, well-sourced claims

### Authoritativeness
- External citations, backlinks from authoritative sources
- Brand mentions, industry recognition
- Published in recognized outlets
- Cited by other experts

### Trustworthiness
- Contact information, physical address
- Privacy policy, terms of service
- Customer testimonials, reviews
- Date stamps, transparent corrections
- Secure site (HTTPS)

## Content Metrics

### Word Count Analysis
Compare against page type minimums:
| Page Type | Minimum |
|-----------|---------|
| Homepage | 500 |
| Service page | 800 |
| Blog post | 1,500 |
| Product page | 300+ (400+ for complex products) |
| Location page | 500-600 |

> **Important:** These are **topical coverage floors**, not targets. Google has confirmed word count is NOT a direct ranking factor. The goal is comprehensive topical coverage; a 500-word page that thoroughly answers the query will outrank a 2,000-word page that doesn't. Use these as guidelines for adequate coverage depth, not rigid requirements.

### Readability
- Flesch Reading Ease: target 60-70 for general audience

> **Note:** Flesch Reading Ease is a useful proxy for content accessibility but is NOT a direct Google ranking factor. John Mueller has confirmed Google does not use basic readability scores for ranking. Yoast deprioritized Flesch scores in v19.3. Use readability analysis as a content quality indicator, not as an SEO metric to optimize directly.
- Grade level: match target audience
- Sentence length: average 15-20 words
- Paragraph length: 2-4 sentences

### Keyword Optimization
- Primary keyword in title, H1, first 100 words
- Natural density (1-3%)
- Semantic variations present
- No keyword stuffing

### Content Structure
- Logical heading hierarchy (H1 -> H2 -> H3)
- Scannable sections with descriptive headings
- Bullet/numbered lists where appropriate
- Table of contents for long-form content

### Multimedia
- Relevant images with proper alt text
- Videos where appropriate
- Infographics for complex data
- Charts/graphs for statistics

### Internal Linking
- 3-5 relevant internal links per 1000 words
- Descriptive anchor text
- Links to related content
- No orphan pages

### External Linking
- Cite authoritative sources
- Open in new tab for user experience
- Reasonable count (not excessive)

## AI Content Assessment (Sept 2025 QRG addition)

Google's raters assess low-quality, scaled, copied, or AI-generated main content patterns rather than AI authorship as a standalone issue.

### Acceptable AI Content
- Demonstrates genuine E-E-A-T
- Provides unique value
- Has human oversight and editing
- Contains original insights

### Low-Quality AI Content Markers
- Generic phrasing, lack of specificity
- No original insight
- Repetitive structure across pages
- No author attribution
- Factual inaccuracies

> **Helpful Content System (March 2024):** The Helpful Content System was merged into Google's core ranking algorithm during the March 2024 core update. It no longer operates as a standalone classifier. Helpfulness signals are now weighted within every core update. The same principles apply (people-first content, demonstrating E-E-A-T, satisfying user intent), but enforcement is continuous rather than through separate HCU updates. Google now also documents **continuous, smaller unannounced core updates** between major ones (changelog 2025-12-09).

> **Gen-AI optimization is SEO (Google docs, 2026-06-29):** the official "optimizing for generative AI features" guide states you do **not** need new AI files, markup, Markdown, content chunking, or AI-specific rewrites; chasing inauthentic "mentions" is unhelpful. AEO/GEO is rebranded SEO rooted in core ranking/quality.

> **Honest scoping (Google docs, 2026-06-05):** per "Using third-party SEO tools, services, and advice," no tool guarantees rankings and third-party tools have no access to Google's internal ranking data. claude-seo's scores are **heuristics**, not Google-internal signals, so say so in reports, and validate GEO/AEO findings against Google's official guidance (Search Console is the first-party source).

## AI Citation Readiness (GEO signals)

Optimize for AI search engines (ChatGPT, Perplexity, Google AI Overviews):

- Clear, quotable statements with statistics/facts
- Structured data (especially for data points)
- Strong heading hierarchy (H1->H2->H3 flow)
- Answer-first formatting for key questions
- Tables and lists for comparative data
- Clear attribution and source citations

### AI Search Visibility & GEO (2025-2026)

**Google AI Mode** is Google's conversational AI search surface. Google's last official model naming for AI Mode / AI Overviews is a custom version of **Gemini 2.5**. Treat third-party AI Mode usage, citation, and link-share figures as methodology-dependent unless primary-sourced, and optimize for both AI Mode and AI Overviews (see the `seo-geo` skill).

**Key optimization strategies for AI citation:**
- **Structured answers:** Clear question-answer formats, definition patterns, and step-by-step instructions that AI systems can extract and cite
- **First-party data:** Original research, statistics, case studies, and unique datasets are highly cited by AI systems
- **Schema markup:** Article and other relevant structured content. FAQPage no longer produces Google FAQ rich results; use QAPage only for genuine user Q&A where appropriate
- **Topical authority:** AI systems preferentially cite sources that demonstrate deep expertise. Build content clusters, not isolated pages
- **Entity clarity:** Ensure brand, authors, and key concepts are clearly defined with structured data (Organization, Person schema)
- **Multi-platform tracking:** Monitor visibility across Google AI Overviews, AI Mode, ChatGPT, Perplexity, and Bing Copilot, not just traditional rankings. Treat AI citation as a standalone KPI alongside organic rankings and traffic.

**Generative Engine Optimization (GEO):**
Per Google's AI optimization guide, "AEO" and "GEO" are rebranded labels for SEO: AI Overviews and AI Mode are grounded in the same ranking and quality systems as classic Search. The optimization signals that matter (quotability, attribution, heading hierarchy, freshness) are SEO fundamentals applied to AI-search surfaces, not a separate discipline. Cross-reference the `seo-geo` skill for detailed workflows; both surfaces share the primary-source synthesis in `skills/seo-geo/references/google-ai-optimization-guide.md`.

## Content Freshness

- Publication date visible
- Last updated date if content has been revised
- Flag content older than 12 months without update for fast-changing topics

## Output

### Content Quality Score: XX/100

### E-E-A-T Breakdown
| Factor | Score | Key Signals |
|--------|-------|-------------|
| Experience | XX/20 | ... |
| Expertise | XX/25 | ... |
| Authoritativeness | XX/25 | ... |
| Trustworthiness | XX/30 | ... |

> Weights are **this skill's own scoring model**, ordered to reflect Google's
> stated hierarchy: **Trust is most important** (30), then Expertise/
> Authoritativeness (25 each), then Experience (20); maxima sum to 100. Google
> publishes no numeric E-E-A-T weights (only that trust is most important), so
> treat the split as our internal model. Do not use an equal 25/25/25/25 split
> (it contradicts Google's "trust is most important").

### AI Citation Readiness: XX/100

### Issues Found
### Recommendations

## DataForSEO Integration (Optional)

If DataForSEO MCP tools are available, use `kw_data_google_ads_search_volume` for real keyword volume data, `dataforseo_labs_bulk_keyword_difficulty` for difficulty scores, `dataforseo_labs_search_intent` for intent classification, and `content_analysis_summary` for content quality analysis.

## Error Handling

| Scenario | Action |
|----------|--------|
| URL unreachable (DNS failure, connection refused) | Report the error clearly. Do not guess page content. Suggest the user verify the URL and try again. |
| Content behind paywall (402/403, login wall) | Report that the content is not publicly accessible. Analyze only the visible portion (meta tags, headers) and note the limitation. |
| Thin content (fewer than 100 words retrievable) | Report the findings as-is rather than guessing. Flag the page as potentially JavaScript-rendered or gated, and suggest the user provide the full text directly. |

## FLOW Framework Integration

For prompt-guided content optimization, use `/seo flow optimize <url>` and `/seo flow win <url>`: FLOW's optimize and win prompts provide structured E-E-A-T improvement and BOFU conversion workflows.
