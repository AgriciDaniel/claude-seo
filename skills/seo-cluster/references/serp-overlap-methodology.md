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
- Keep URLs in organic ranking order and save them once per keyword.
- Do not guess URLs, fill missing results, or include ads/PAA as organic results.

Save `serp-results.json` with a `serps` list. Each entry has a `keyword`, ranked
`urls`, and an optional `error` string when collection failed. This intentionally
incomplete example demonstrates missing-data reporting:

```json
{
  "serps": [
    {"keyword": "CRM software", "urls": ["https://example.com/crm"]},
    {"keyword": "best CRM", "urls": [], "error": "Search provider unavailable"}
  ]
}
```

The script accepts up to 200 keywords and 4 MiB of UTF-8 JSON. It considers only
the first 10 supplied organic positions, never a later result to fill a gap.

URL comparison normalizes scheme/host case, IDNA host names, default ports,
unreserved percent escapes, fragments, and known attribution parameters
(`utm_*`, `gclid`, `dclid`, `fbclid`, `msclkid`, `mc_cid`, `mc_eid`, `_ga`). It
preserves the scheme, path case, trailing slash, and all other query parameters.
Do not merge those page identities without redirect or canonical evidence.

### Step 2: Pairwise Comparison

Run the saved results through the bundled script:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run serp_overlap.py serp-results.json > serp-overlap.json
```

The script normalizes and deduplicates each result set once, computes every
pairwise intersection, and reports the shared URLs. Copy its JSON output field `serp_matrix` into
`cluster-plan.json`; retain `pairs` and `coverage` as evidence.

Ten unique valid URLs and no fetch error are required for a complete SERP. If
either side is incomplete, its pair score is `null` and the relationship is
`inconclusive`. `observed_shared_count` is only the overlap in the available
data, not a complete top-ten score. Collect the missing results or leave the
relationship unresolved.

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

N keywords need N collected SERPs and N*(N-1)/2 local comparisons. For 40
keywords, collect 40 result sets and let the script compute all 780 comparisons.

### Pre-Grouping

1. Classify all keywords by intent (Informational, Commercial, Transactional)
2. Group keywords that share the same head term (e.g., "CRM software" variants)
3. Use the full computed matrix to check both within-group and boundary pairs
4. Revisit the intent grouping when the observed SERPs disagree with it

### Evidence Rules

- Intent or word similarity cannot substitute for a measured overlap score.
- A-B and B-C sharing 7 results does not prove that A-C shares 7 results. Check
  every pair before merging several keywords into one post.
- Missing, invalid, or duplicate results remain coverage gaps; do not assign a
  guessed score to make the matrix look complete.

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

The diagonal is 10 for a complete SERP and `null` for an incomplete one. Every
pair involving an incomplete SERP is also `null`, with details in `coverage`.

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

Keep `serp-results.json` for the session and reuse it for every comparison.
Re-fetch only to fill coverage gaps or deliberately refresh a keyword. Collect
all results for the same location, language, device, and time window; the script
compares supplied URLs and cannot establish those collection conditions itself.
