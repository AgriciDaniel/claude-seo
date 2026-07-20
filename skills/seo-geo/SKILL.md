---
name: seo-geo
description: >
  Optimize content for AI Overviews (formerly SGE), ChatGPT web search,
  Perplexity, and other AI-powered search experiences. Generative Engine
  Optimization (GEO) analysis including brand mention signals, AI crawler
  accessibility, llms.txt compliance, passage-level citability scoring, and
  platform-specific optimization. Use when user says "AI Overviews", "SGE",
  "GEO", "AI search", "LLM optimization", "Perplexity", "AI citations",
  "ChatGPT search", or "AI visibility".
user-invocable: true
argument-hint: "[url]"
license: MIT
metadata:
  author: AgriciDaniel
  version: "2.2.3"
  category: seo
---

# AI Search / GEO Optimization (May 2026)

## Primary Source: Google's AI Optimization Guide

Google's official position, published under Search Central docs:

> "Optimizing for generative AI search is **still SEO** from Google's
> perspective. AEO and GEO are rebranded labels for the same work."

Read `references/google-ai-optimization-guide.md` for the full synthesis,
myth-busting list (`llms.txt`, chunking, AI-rephrasing, mention-farming,
all rejected by Google as ineffective), and the Who/How/Why test for
content quality.

Audits should frame GEO findings as **SEO fundamentals applied to AI-search
surfaces**, not as a separate optimization discipline. When community
recommendations contradict Google's primary source, defer to Google and note
the contradiction in the report.

## Key Statistics

| Metric | Value | Source |
|--------|-------|--------|
| AI Overviews reach | 2.5 billion+ monthly active users, reported from Google I/O 2026 keynote coverage; not confirmed on a Google-owned source; 200+ countries | Third-party I/O reporting |
| AI Overviews query coverage | ~50% of queries (third-party measurement; varies by country) | Industry data |
| AI Mode monthly users | 1B+, reported from Google I/O 2026 keynote coverage; not confirmed on a Google-owned source | Third-party I/O reporting |
| AI Mode model | custom version of Gemini 2.5 | Google |
| AI-referred sessions growth | 527% (Jan-May 2025) | SparkToro |
| ChatGPT weekly active users | 900 million | OpenAI |
| Perplexity monthly queries | 500+ million | Perplexity |

## Critical Insight: Brand Mentions > Backlinks

**Brand mentions correlate 3x more strongly with AI visibility than backlinks.**
(Ahrefs December 2025 study of 75,000 brands)

| Signal | Correlation with AI Citations |
|--------|------------------------------|
| YouTube mentions | ~0.737 (strongest) |
| Reddit mentions | High |
| Wikipedia presence | High |
| LinkedIn presence | Moderate |
| Domain Rating (backlinks) | ~0.266 (weak) |

**Only 11% of domains** are cited by both ChatGPT and Google AI Overviews for the same query, so platform-specific optimization is essential.

---

## GEO Analysis Criteria (Updated)

### 1. Citability Score (25%)

**Optimal passage length: 134-167 words** for AI citation. And **~44% of AI
citations come from the first 30% of a page** (SE Ranking study), front-load
your most citable, self-contained answer rather than burying it below the fold.

**Strong signals:**
- Clear, quotable sentences with specific facts/statistics
- Self-contained answer blocks (can be extracted without context)
- Direct answer in first 40-60 words of section
- Claims attributed with specific sources
- Definitions following "X is..." or "X refers to..." patterns
- Unique data points not found elsewhere

**Weak signals:**
- Vague, general statements
- Opinion without evidence
- Buried conclusions
- No specific data points

### 2. Structural Readability (20%)

**92% of AI Overview citations come from top-10 ranking pages**, but 47% come from pages ranking below position 5, demonstrating different selection logic.

**Strong signals:**
- Clean H1->H2->H3 heading hierarchy
- Question-based headings (matches query patterns)
- Short paragraphs (2-4 sentences)
- Tables for comparative data
- Ordered/unordered lists for step-by-step or multi-item content
- FAQ sections with clear Q&A format

**Weak signals:**
- Wall of text with no structure
- Inconsistent heading hierarchy
- No lists or tables
- Information buried in paragraphs

### 3. Multi-Modal Content (15%)

Content with multi-modal elements sees **156% higher selection rates**.

**Check for:**
- Text + relevant images
- Video content (embedded or linked)
- Infographics and charts
- Interactive elements (calculators, tools)
- Structured data supporting media

### 4. Authority & Brand Signals (20%)

**Strong signals:**
- Author byline with credentials
- Publication date and last-updated date
- **Recency**, content under 3 months old is ~3x more likely to be cited in AI answers; pages left stale 6+ months lose citation eligibility (SE Ranking, 1.3M-citation study). A scheduled refresh program is one of the highest-leverage GEO plays.
- Citations to primary sources (studies, official docs, data)
- Organization credentials and affiliations
- Expert quotes with attribution
- Entity presence in Wikipedia, Wikidata
- Mentions on Reddit, YouTube, LinkedIn

**Weak signals:**
- Anonymous authorship
- No dates
- No sources cited
- No brand presence across platforms

### 5. Technical Accessibility (20%)

**AI crawlers do NOT execute JavaScript.** Server-side rendering is critical.

**Check for:**
- Server-side rendering (SSR) vs client-only content
- AI crawler access in robots.txt
- llms.txt file presence and configuration
- RSL 1.0 licensing terms

---

## AI Crawler Detection

Check `robots.txt` for these AI crawlers:

| Crawler | Owner | Purpose | Obeys robots.txt? |
|---------|-------|---------|---|
| GPTBot | OpenAI | ChatGPT web search | yes |
| OAI-SearchBot | OpenAI | OpenAI search features | yes |
| ChatGPT-User | OpenAI | ChatGPT browsing (user-triggered) | no (user-triggered) |
| ClaudeBot | Anthropic | Claude web features | yes |
| PerplexityBot | Perplexity | Perplexity AI search | yes |
| CCBot | Common Crawl | Training data (often blocked) | yes |
| anthropic-ai | Anthropic | Claude training | yes |
| Bytespider | ByteDance | TikTok/Douyin AI | yes |
| cohere-ai | Cohere | Cohere models | yes |
| Google-Extended | Google | Gemini/Vertex training & grounding opt-out | yes |
| Google-CloudVertexBot | Google | Site-owner-requested Vertex AI Agent crawls | yes |
| Google-Agent | Google | Agentic browsing (Project Mariner), acts for a user | **no (user-triggered)** |
| Google-NotebookLM | Google | Fetches individual user-added source URLs | **no (user-triggered)** |
| Google Messages | Google | User-triggered fetch | **no (user-triggered)** |

**Recommendation:** Allow GPTBot, OAI-SearchBot, ClaudeBot, PerplexityBot for AI search visibility. Block CCBot and training crawlers if desired.

> **User-triggered fetchers ignore robots.txt by design** (Google-Agent, Google-NotebookLM, Google Messages, ChatGPT-User). robots.txt cannot block them, use server-side access controls. Google's canonical crawling/robots reference moved to **developers.google.com/crawling** (migrated 2025-11-20); IP-range files now live at `/crawling/ipranges/` and `googlebot.json` was renamed `common-crawlers.json`. Emerging: **Web Bot Auth** (RFC 9421) lets bots authenticate via a `Signature-Agent` header + key directory (used by Google-Agent); reverse-DNS verification remains the fallback.

---

## llms.txt Standard

Read `references/llmstxt-evidence.md` for the primary-source evidence (Mueller, Illyes, SE Ranking 300k-domain study, OtterlyAI server-log audit) on why `/llms.txt` is not currently a citation lever for major AI search systems. claude-seo reports presence but assigns no citation-ranking weight.

> **Google now states this explicitly.** Google's AI optimization guide (updated 2026-06-29) says you do **not** need `llms.txt` / AI-text files for Google Search, including its generative AI features, and that doing so "won't harm (nor help) your visibility or rankings in Google Search, as Google Search ignores them." Mueller separately called the llms.txt discovery use case "a dead end." It's fine to keep for **non-Google** AI services; never recommend it as a Google ranking/citation lever. Source: developers.google.com/search/docs/fundamentals/ai-optimization-guide

The emerging **llms.txt** standard provides AI crawlers with structured content guidance.

**Location:** `/llms.txt` (root of domain)

**Format:**
```
# Title of site
> Brief description

## Main sections
- [Page title](url): Description
- [Another page](url): Description

## Optional: Key facts
- Fact 1
- Fact 2
```

**Check for:**
- Presence of `/llms.txt`
- Structured content guidance
- Key page highlights
- Contact/authority information

---

## RSL 1.0 (Really Simple Licensing)

New standard (December 2025) for machine-readable AI licensing terms.

**Backed by:** Reddit, Yahoo, Medium, Quora, Cloudflare, Akamai, Creative Commons

**Check for:** RSL implementation and appropriate licensing terms.

---

## Platform-Specific Optimization

| Platform | Key Citation Sources | Optimization Focus |
|----------|---------------------|-------------------|
| **Google AI Overviews** | Strongly ranking-correlated, cites pages that already rank well | Traditional SEO + passage optimization |
| **Google AI Mode** (custom version of Gemini 2.5) | Weakly ranking-correlated; broader pool (~9 domains cited/query, Ahrefs) | Distinct surface: freshness, entity authority, citable passages beyond position 5 |
| **ChatGPT** | Wikipedia (47.9%), Reddit (11.3%) | Entity presence, authoritative sources |
| **Perplexity** | Reddit (46.7%), Wikipedia | Community validation, discussions |
| **Bing Copilot** | Bing index, authoritative sites | Bing SEO, IndexNow |

> **Two Google citation engines, not one.** AI Mode and AI Overviews reach the
> same conclusion ~86% of the time but cite the same URLs only **13.7%** of the
> time (Ahrefs study, 540K query pairs). Treat them as separate surfaces: ranking
> well in classic Search feeds AI Overviews, but AI Mode draws from a broader pool
> where freshness and entity authority outweigh raw position. Score both.
>
> **UX is now unified, surfaces still distinct.** At Google I/O 2026 (2026-05-19)
> Google merged AI Overviews and AI Mode into "one seamless AI Search experience"
> (question → AI Overview → follow-up in AI Mode) with a new intelligent Search
> box. The *experience* is one flow, but the two citation engines remain
> technically distinct (different models/link sets), keep scoring both.

### Citation surfaces & controls in AI Search (2026)

Google added many AI citation/source surfaces across AI Overviews **and** AI Mode (May 2026):

- **Preferred Sources**, users pick sites that get a "preferred" badge in AI answers; all-languages since 2026-04-30 (>345K sources selected); Google is working toward using it as a ranking signal. *Quick win:* encourage your audience to add the brand as a Preferred Source.
- **"Highly Cited" badges**, earned via original primary reporting that other articles cite.
- **Community Perspectives**, elevates Reddit/forum/firsthand content.
- Inline links, desktop hover **Link Previews**, and prominent link carousels.

**Controlling AI-feature appearance:** there is **no AI-specific opt-out file**. Appearance in AI Overviews and AI Mode is governed by standard preview/index directives, `nosnippet`, `data-nosnippet`, `max-snippet`, `noindex` (distinct from the third-party AI-crawler robots controls above). Source: developers.google.com/search/docs/appearance/ai-features

**Search agents (live, not just WebMCP):** Google's "Information Agents" run in the background to monitor topics, plus agentic booking/calling for select categories (rolling out to US users, summer 2026), so agent-friendly-page optimization (real interactive elements, accessibility tree, layout stability) now matters for actions, not only citations.

---

## Output

Generate `GEO-ANALYSIS.md` with:

1. **GEO Readiness Score: XX/100**
2. **Platform breakdown** (Google AIO, ChatGPT, Perplexity scores)
3. **AI Crawler Access Status** (which crawlers allowed/blocked)
4. **llms.txt Status** (present, missing, recommendations)
5. **Brand Mention Analysis** (presence on Wikipedia, Reddit, YouTube, LinkedIn)
6. **Passage-Level Citability** (optimal 134-167 word blocks identified)
7. **Server-Side Rendering Check** (JavaScript dependency analysis)
8. **Top 5 Highest-Impact Changes**
9. **Schema Recommendations** (for AI discoverability)
10. **Content Reformatting Suggestions** (specific passages to rewrite)

---

## Quick Wins

1. Add "What is [topic]?" definition in first 60 words
2. Create 134-167 word self-contained answer blocks
3. Add question-based H2/H3 headings
4. Include specific statistics with sources
5. Add publication/update dates
6. Implement Person schema for authors
7. Allow key AI crawlers in robots.txt

## Medium Effort

1. Create `/llms.txt` file (optional: ignored by Google Search; may help other AI crawlers)
2. Add author bio with credentials + Wikipedia/LinkedIn links
3. Ensure server-side rendering for key content
4. Build entity presence on Reddit, YouTube
5. Add comparison tables with data
6. Implement FAQ sections (structured, not schema for commercial sites)

## High Impact

1. Create original research/surveys (unique citability)
2. Build Wikipedia presence for brand/key people
3. Establish YouTube channel with content mentions
4. Implement comprehensive entity linking (sameAs across platforms)
5. Develop unique tools or calculators

## DataForSEO Integration (Optional)

If DataForSEO MCP tools are available, use `ai_optimization_chat_gpt_scraper` to check what ChatGPT web search returns for target queries (real GEO visibility check) and `ai_opt_llm_ment_search` with `ai_opt_llm_ment_top_domains` for LLM mention tracking across AI platforms.

## Error Handling

| Scenario | Action |
|----------|--------|
| URL unreachable (DNS failure, connection refused) | Report the error clearly. Do not guess site content. Suggest the user verify the URL and try again. |
| AI crawlers blocked by robots.txt | Report exactly which crawlers are blocked and which are allowed. Provide specific robots.txt directives to add for enabling AI search visibility. |
| No llms.txt found | Note the absence (optional file; Google Search ignores it) and provide a ready-to-use llms.txt template for non-Google AI crawlers. |
| No structured data detected | Report the gap and provide specific schema recommendations (Article, Organization, Person) for improving AI discoverability. |

## FLOW Framework Integration

For prompt-guided AI content optimization, use `/seo flow optimize <url>`, FLOW's 21 optimize-stage prompts complement GEO's citability and structure analysis with evidence-led AI prompts.
