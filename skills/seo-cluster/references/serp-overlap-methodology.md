# SERP Overlap Methodology

## Core Principle

Two keywords that return the same Google results should be targeted by the same page.
Two keywords that return completely different results need separate pages. This is the
foundation of SERP-based clustering -- using Google's own ranking decisions to determine
content architecture rather than relying on keyword text similarity or stemming.

## Scoring Algorithm

### Step 1: Collect SERP Data

For each keyword in the candidate set, retrieve the top 10 organic results:
- Use WebSearch or DataForSEO `serp_organic_live_advanced`
- Extract only organic result URLs (ignore ads, featured snippets, PAA, knowledge panels)
- Normalize URLs: strip protocol, trailing slash, and query parameters (except meaningful ones)
- Store as a set of 10 URLs per keyword

### Step 2: Pairwise Comparison

For each pair of keywords (A, B):
1. Retrieve the URL sets: `urls_A` and `urls_B`
2. Compute overlap: `shared = urls_A intersection urls_B`
3. Score: `overlap_score = len(shared)`

### Step 3: Apply Thresholds

| Overlap Score | Relationship | Action |
|--------------|-------------|--------|
| 7-10 | **Same post** | Merge keywords into one target page. Use higher-volume keyword as primary. |
| 4-6 | **Same cluster** | Place in same spoke cluster. May be separate posts or same post depending on volume difference. |
| 2-3 | **Interlink** | Place in adjacent clusters. Create cross-cluster internal links. |
| 0-1 | **Separate** | Different clusters entirely or exclude from current pillar topic. |

### Step 4: Handle Ambiguous Scores (3-4 Range)

Scores in the 3-4 range require tiebreaking:
1. Check domain overlap (same domains but different pages = closer relationship)
2. Check intent alignment (same intent category = lean toward same cluster)
3. Check volume ratio (if one keyword has 10x+ more volume, it likely deserves its own post)
4. When in doubt, keep in same cluster with separate posts (err toward cohesion)

## Optimization Strategy

Full pairwise comparison of N keywords requires N*(N-1)/2 SERP fetches. For 40
keywords, that is 780 comparisons. Optimize by reducing unnecessary checks:

### Pre-Grouping

1. Classify all keywords by intent (Informational, Commercial, Transactional)
2. Group keywords that share the same head term (e.g., "CRM software" variants)
3. Only run pairwise SERP comparison within pre-groups
4. Cross-check boundary keywords (highest volume in each group) across groups

### Skip Rules

- If keywords A and B are both long-tail variants of the same head term AND share
  the same intent, assume overlap 4-6 (same cluster) without checking SERP
- If keywords are in different intent categories, assume overlap 0-2 unless they
  share a head term
- Verify assumptions with spot-check SERP comparisons (sample 20% of skipped pairs)

## Scoring Matrix Format

Store the overlap data as a symmetric matrix in `cluster-plan.json`:

```json
{
  "serp_matrix": {
    "keywords": ["keyword-a", "keyword-b", "keyword-c"],
    "scores": [
      [10, 5, 1],
      [5, 10, 3],
      [1, 3, 10]
    ]
  }
}
```

Diagonal is always 10 (a keyword overlaps perfectly with itself).

## Anti-Patterns

1. **Never cluster by text similarity alone.** "Dog training tips" and "dog training
   classes" may have completely different SERPs despite similar text.
2. **Never use stemming-only grouping.** "Run" and "running" may target different
   intents entirely.
3. **Never assume related searches belong in the same cluster.** Verify with SERP data.
4. **Never ignore SERP feature differences.** If keyword A triggers a local pack and
   keyword B triggers a featured snippet, they likely need different content types
   even with moderate URL overlap.
5. **Never treat all domains equally.** Wikipedia and Reddit appear in many SERPs.
   Consider filtering out ubiquitous domains (top 5 most common) before scoring, or
   weighting domain-specific results higher.

## Data Source Priority

1. **DataForSEO** (if available): Most reliable, consistent SERP data. Use
   `serp_organic_live_advanced` with `location_code: 2840` (US) and `language_code: "en"`.
2. **WebSearch** (fallback): Adequate for clustering but results may vary by session.
   Run multiple searches for the same keyword and use the most common result set.

## Caching

Within a single clustering session, cache all SERP results. If keyword A's results
are fetched for the A-B comparison, reuse them for the A-C comparison. This halves
the number of actual SERP fetches needed.
