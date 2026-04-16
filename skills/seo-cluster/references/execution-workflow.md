# Execution Workflow

## Overview

The execution phase transforms a `cluster-plan.json` into actual content. It handles
priority ordering, context injection for the blog writer, backward link updates,
resume capability, and post-execution quality scoring.

## Priority Algorithm

Content is created in this strict order:

1. **Pillar page first** -- The hub must exist before any spokes can link to it
2. **Spokes by search volume (descending)** -- Highest-volume spokes first for
   maximum early impact
3. **Within same volume, by cluster index** -- Process Cluster 0 before Cluster 1
4. **Within same cluster, by post index** -- Process Post 0 before Post 1

Rationale: The pillar establishes the topical authority foundation. High-volume
spokes generate the most organic traffic, so they should be published earliest
for faster compounding returns.

## Cluster Context Injection

When invoking `blog-write` for each post, pass a structured context block:

```json
{
  "cluster_context": {
    "role": "pillar|spoke",
    "pillar_title": "The Complete Guide to ...",
    "pillar_url": "/guide/...",
    "cluster_name": "Cluster Name",
    "cluster_index": 0,
    "post_index": 0,
    "primary_keyword": "target keyword",
    "secondary_keywords": ["variant 1", "variant 2"],
    "template": "how-to",
    "word_count_target": 1500,
    "outgoing_links": [
      { "url": "/pillar-url", "anchor": "main topic guide", "type": "mandatory" },
      { "url": "/sibling-post", "anchor": "related subtopic", "type": "recommended" }
    ],
    "incoming_link_placeholder": "<!-- cluster-link:cluster-0-post-1 -->",
    "differentiation_note": "This post should focus on X, while sibling post covers Y"
  }
}
```

### Context Fields Explained

| Field | Purpose |
|-------|---------|
| `role` | Whether this is the pillar or a spoke (affects depth and breadth) |
| `pillar_title` / `pillar_url` | So spokes can link back to the pillar |
| `cluster_name` / `cluster_index` | For organizing and labeling |
| `post_index` | Position within the cluster |
| `primary_keyword` | The main target keyword for this post |
| `secondary_keywords` | Additional keywords to naturally incorporate |
| `template` | Content template to follow (how-to, listicle, comparison, etc.) |
| `word_count_target` | Target word count (not a hard limit, a guideline) |
| `outgoing_links` | Links this post MUST include, with suggested anchor text |
| `incoming_link_placeholder` | HTML comment marker for future backward link injection |
| `differentiation_note` | How this post differs from siblings targeting similar topics |

## Backward Link Injection

After each new post is written, update previously written posts to link to it:

### Process

1. Read the link matrix from `cluster-plan.json`
2. Identify all posts that should link TO the newly written post
3. For each of those posts (that is already written):
   a. Open the post file
   b. Search for the placeholder comment: `<!-- cluster-link:POST_ID -->`
   c. Replace the placeholder with an actual contextual link
   d. If no placeholder found, append a contextual link in the most relevant section
4. Log all backward links added

### Placeholder Format

```html
<!-- cluster-link:cluster-0-post-1 -->
```

This is inserted during content creation at a contextually appropriate location.
When the target post is later written, the placeholder is replaced with:

```html
For a deeper dive, see our guide on <a href="/target-url">anchor text</a>.
```

## Resume Capability

Execution can be interrupted and resumed. The resume algorithm:

### Detection

1. Read `cluster-plan.json` from the current directory
2. Scan the output directory for existing post files
3. Match found files against the plan using:
   - Filename patterns (slug derived from title or keyword)
   - Content inspection (check for `primary_keyword` in frontmatter or first H1)
4. Mark matched posts as `"status": "written"` in the plan

### Resume Logic

1. Load the plan with updated statuses
2. Filter to `"status": "planned"` posts only
3. Apply the priority algorithm to the remaining posts
4. Continue execution from the next unwritten post
5. Run backward link injection for any links between newly written and
   previously written posts

### Edge Cases

- If the pillar is missing but spokes exist, write the pillar first and then
  inject backward links into existing spokes
- If a spoke file exists but is incomplete (under 50% of target word count),
  treat it as unwritten and recreate
- If `cluster-plan.json` has been modified since last execution, re-validate
  the plan before resuming

## Scorecard Metrics

After execution completes (or on demand), generate `cluster-scorecard.md`:

### Metric Definitions

| Metric | Formula | Target |
|--------|---------|--------|
| Coverage | `written_posts / planned_posts * 100` | 100% |
| Link Density | `total_internal_links / total_posts` | >= 3.0 per post |
| Orphan Pages | Count of posts with 0 incoming internal links | 0 |
| Pillar Connectivity | `spokes_linking_to_pillar / total_spokes * 100` | 100% |
| Reverse Pillar Links | `spokes_linked_from_pillar / total_spokes * 100` | 100% |
| Cross-Links | `implemented_cross_links / recommended_cross_links * 100` | >= 80% |
| Cannibalization | Count of posts sharing a primary keyword | 0 |
| Image Count | Posts with at least one image / total posts | >= 90% |
| Content Gaps | Planned posts not yet written | 0 |
| Avg Word Count | Mean word count across all written posts | Within 10% of targets |

### Scorecard Output Format

```markdown
# Cluster Scorecard: [Seed Keyword]

## Summary
- Posts: X/Y written (Z%)
- Total words: N (estimated: M)
- Internal links: L (density: L/Y per post)

## Metrics
| Metric | Score | Status |
|--------|-------|--------|
| Coverage | 100% | PASS |
| Link Density | 3.2/post | PASS |
| ...

## Issues Found
- [List any FAIL or WARN metrics with remediation steps]

## Next Steps
- [Actionable items to reach 100% on all metrics]
```

## Quality Gates

Before marking execution as complete, verify:

1. Every spoke links to the pillar (mandatory)
2. The pillar links to every spoke (mandatory)
3. No post has fewer than 3 incoming internal links
4. No two posts share the same primary keyword
5. No orphan pages exist
6. All posts meet minimum word count (80% of target)

If any gate fails, flag it in the scorecard and provide specific remediation
instructions. Do NOT silently pass a failing cluster.
