---
name: seo-sxo
description: >
  Search Experience Optimization: reads Google SERPs backwards to detect page-type
  mismatches, derives user stories from search intent signals, and scores pages
  from multiple persona perspectives. Identifies why well-optimized pages fail
  to rank by analyzing what Google rewards for each keyword. Use when user says
  "SXO", "search experience", "page type mismatch", "SERP analysis", "user story",
  "persona scoring", "why isn't my page ranking", "intent mismatch", or "wireframe".
user-invokable: true
argument-hint: "<url> [keyword]"
license: MIT
metadata:
  author: AgriciDaniel
  original_author: "Florian Schmitz (Pro Hub Challenge)"
  version: "1.9.0"
  category: seo
---

# Search Experience Optimization (SXO)

SXO bridges the gap between SEO (what Google rewards) and UX (what users need).
Traditional SEO audits check technical health. SXO asks: "Does this page deserve
to rank for this keyword based on what Google is actually rewarding in the SERP?"

## Core Insight

A page can score 95/100 on technical SEO and still fail to rank because it is the
**wrong page type** for the keyword. If Google shows 8 product pages and 2 comparison
pages for your keyword, your blog post will never break through -- no matter how
well-optimized it is.

## Commands

| Command | Purpose |
|---------|---------|
| `/seo sxo <url>` | Full SXO analysis (auto-detect keyword from page) |
| `/seo sxo <url> <keyword>` | Full SXO analysis for a specific keyword |
| `/seo sxo wireframe <url>` | Generate IST/SOLL wireframe with concrete placeholders |
| `/seo sxo personas <url>` | Persona-only scoring (skip SERP analysis) |

## Execution Pipeline

### Step 1: Target Acquisition

1. Fetch the target URL via `scripts/fetch_page.py` (SSRF-safe)
2. Parse with `scripts/parse_html.py` to extract: title, H1, meta description,
   headings hierarchy, word count, schema markup, CTAs, media elements
3. If no keyword provided, extract primary keyword from title tag + H1 overlap
4. Validate keyword is non-empty before proceeding

### Step 2: SERP Backwards Analysis

Read `references/page-type-taxonomy.md` for classification rules.

1. Search Google for the target keyword (WebSearch)
2. For each of the top 10 organic results, record:
   - URL and domain authority tier (brand / niche authority / unknown)
   - Page type (classify using taxonomy)
   - Content format (long-form, listicle, how-to, comparison, tool, video)
   - Word count estimate (from snippet length and page structure)
   - Schema types present (from SERP features: ratings, FAQ, HowTo)
   - Media signals (video carousel, image pack, thumbnail presence)
3. Record SERP features present:
   - Featured snippet (paragraph / list / table / video)
   - People Also Ask (extract all visible questions)
   - Ads (top and bottom -- count and analyze ad copy themes)
   - Related searches (extract all)
   - Knowledge panel / local pack / shopping results
   - AI Overview presence and source types
4. Calculate SERP consensus:
   - Dominant page type (>60% = strong consensus, 40-60% = mixed, <40% = fragmented)
   - Content depth expectations (average word count tier)
   - Schema expectation (most common structured data types)
   - Media expectations (video required? images critical?)

### Step 3: Page-Type Mismatch Detection

This is the core SXO insight. Compare target page type against SERP consensus.

**Mismatch severity levels:**

| Target Type | SERP Expects | Severity | Recommendation |
|-------------|-------------|----------|----------------|
| Blog Post | Product Pages | CRITICAL | Create dedicated product page |
| Blog Post | Comparison | HIGH | Restructure as comparison with matrix |
| Product | Informational | HIGH | Add educational content layer |
| Landing Page | Tool/Calculator | HIGH | Build interactive tool component |
| Service Page | Local Results | MEDIUM | Add location signals + local schema |
| Any type match | - | ALIGNED | Focus on content depth and UX |

**Classification rules:**
- Classify target page using `references/page-type-taxonomy.md`
- Classify each SERP result using the same taxonomy
- Flag mismatch if target type differs from SERP dominant type
- If SERP is fragmented (no dominant type), note opportunity for differentiation

### Step 4: User Story Derivation

Read `references/user-story-framework.md` for the full framework.

From SERP signals, derive user stories:

1. **PAA questions** reveal knowledge gaps and concerns
2. **Ad copy themes** reveal commercial triggers and value propositions
3. **Related searches** reveal the search journey (what comes before/after)
4. **Featured snippet format** reveals the expected answer structure
5. **AI Overview** reveals what Google considers the definitive answer

For each signal cluster, generate a user story:
```
As a [persona derived from signal],
I want to [goal derived from query intent],
because [emotional driver from ad copy / PAA tone],
but I'm blocked by [barrier derived from PAA questions / related searches].
```

Generate 3-5 user stories covering the primary intent angles.

### Step 5: Gap Analysis

Compare the target page against SERP expectations across 7 dimensions:

| Dimension | What to Compare | Score |
|-----------|----------------|-------|
| Page Type | Target type vs SERP dominant type | 0-15 |
| Content Depth | Word count, heading depth, topic coverage | 0-15 |
| UX Signals | CTA clarity, above-fold content, mobile layout | 0-15 |
| Schema Markup | Present vs expected structured data types | 0-15 |
| Media Richness | Images, video, interactive elements vs SERP norm | 0-15 |
| Authority Signals | E-E-A-T markers, social proof, credentials | 0-15 |
| Freshness | Last updated, date signals, content recency | 0-10 |

**Total: 0-100 SXO Gap Score** (lower = larger gap, higher = better alignment)

### Step 6: Persona-Based Scoring

Read `references/persona-scoring.md` for methodology.

1. Derive 4-7 personas from SERP intent signals:
   - Cluster PAA questions by theme
   - Segment ad copy by target audience
   - Map related searches to journey stages
2. For each persona, score the target page on 4 dimensions (25 pts each):
   - **Relevance**: Does the page address this persona's need?
   - **Clarity**: Can this persona find their answer within 10 seconds?
   - **Trust**: Are there adequate trust signals for this persona?
   - **Action**: Is there a clear next step for this persona?
3. Output persona cards with scores and specific improvement recommendations
4. Sort recommendations by weakest persona first (biggest opportunity)

### Step 7: Wireframe Generation (Optional)

Only execute when `/seo sxo wireframe` is invoked.

Read `references/wireframe-templates.md` for templates.

1. Generate IST (current state) wireframe from parsed page structure
2. Generate SOLL (target state) wireframe based on:
   - SERP consensus page type
   - Gap analysis findings
   - Persona scoring weaknesses
3. Use ultra-concrete placeholders:
   - NOT: "Add a CTA here"
   - YES: "Add pricing CTA with annual savings badge below hero, linking to /pricing#enterprise"
4. Output as semantic HTML section outline with annotations

## DataForSEO Integration

If DataForSEO MCP tools are available:

1. **Before any API call**, run cost estimate and confirm with user
2. Use `google_organic_serp` for precise SERP data (positions, features, snippets)
3. Use `keyword_data` for search volume and competition metrics
4. Fall back to WebSearch if DataForSEO unavailable -- note reduced precision in output

## SXO Score vs SEO Health Score

The SXO score is **separate** from the main SEO Health Score.

- SEO Health Score = technical compliance (crawlability, speed, schema, etc.)
- SXO Gap Score = alignment between page and SERP expectations
- A page can score 95 SEO + 30 SXO = technically perfect but strategically misaligned
- Both scores should be reported together when both are available

## Cross-Skill References

| Finding | Hand Off To |
|---------|-------------|
| E-E-A-T gaps in persona scoring | `/seo content` for deep E-E-A-T audit |
| Missing schema types | `/seo schema` for generation |
| Local intent detected in SERP | `/seo local` for GBP analysis |
| Content depth gaps | `/seo page` for deep page analysis |
| Technical issues found during fetch | `/seo technical` for full audit |
| Image/media gaps | `/seo images` for optimization |

## Output Format

### Full SXO Analysis

```
## SXO Analysis: [URL]
### Target Keyword: [keyword]

### 1. SERP Landscape
- Dominant page type: [type] ([confidence]% consensus)
- SERP features: [list]
- Content depth norm: [word count range]
- Schema expectation: [types]

### 2. Page-Type Alignment
- Your page type: [type]
- SERP expects: [type]
- Verdict: [ALIGNED | MISMATCH (severity)]
- Impact: [explanation]

### 3. User Stories (derived from SERP signals)
[3-5 user stories with source signals]

### 4. Gap Analysis (SXO Score: XX/100)
[7-dimension breakdown table]

### 5. Persona Scores
[4-7 persona cards with 4-dimension scores]

### 6. Priority Actions
[Ranked list: fix mismatch first, then weakest persona gaps]

### 7. Limitations
[What could not be assessed, data source notes]
```

## Error Handling

| Error | Action |
|-------|--------|
| URL fetch fails | Report error, suggest checking URL accessibility |
| No keyword provided or detected | Ask user to provide target keyword |
| WebSearch returns <5 results | Proceed with available data, note limited sample |
| SERP has no organic results (all ads) | Note highly commercial SERP, analyze ad copy only |
| Target page is JavaScript-rendered | Note limitation, use available HTML content |
| DataForSEO cost exceeds threshold | Fall back to WebSearch, notify user |

## Quality Checklist

Before delivering results, verify:
- [ ] Target URL was fetched via `scripts/fetch_page.py` (not raw curl/fetch)
- [ ] Page type classification uses taxonomy from references
- [ ] At least 5 SERP results were analyzed
- [ ] User stories cite specific SERP signals as evidence
- [ ] Persona scores include concrete improvement suggestions
- [ ] SXO score is clearly labeled as separate from SEO Health Score
- [ ] Limitations section is present and honest
- [ ] Cross-skill recommendations are included where relevant
