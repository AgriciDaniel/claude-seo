# Hub-and-Spoke Content Architecture

## Structure Overview

A hub-and-spoke cluster consists of one pillar page (the hub) connected to multiple
spoke clusters, each containing 2-4 individual posts. The pillar provides broad
coverage; spokes provide deep dives into subtopics.

```
                    [Spoke 1a] --- [Spoke 1b]
                         \       /
                      [Cluster 1]
                           |
[Spoke 2a] -- [Cluster 2] -- [PILLAR] -- [Cluster 3] -- [Spoke 3a]
[Spoke 2b] /                                        \ [Spoke 3b]
                           |
                      [Cluster 4]
                         /       \
                    [Spoke 4a] --- [Spoke 4b]
```

## Pillar Page Specifications

| Attribute | Requirement |
|-----------|-------------|
| Word count | 2,500-4,000 words |
| Keyword | Broadest, highest-volume keyword in the set |
| Content type | Comprehensive overview covering all cluster subtopics |
| Template | `ultimate-guide` (default) |
| Internal links | Link to EVERY spoke post in every cluster (mandatory) |
| Structure | Table of contents, section per cluster, summary per subtopic |
| Schema | Article + BreadcrumbList + ItemList (listing all cluster pages) |
| Update frequency | Refresh quarterly or when new spokes are added |

## Spoke Page Specifications

| Attribute | Requirement |
|-----------|-------------|
| Word count | 1,200-1,800 words |
| Keyword | Specific subtopic keyword (unique per post) |
| Content type | Deep-dive into a single subtopic |
| Template | Selected by intent (see template mapping below) |
| Internal links | Link to pillar (mandatory) + 2-3 sibling spokes |
| Schema | Article + BreadcrumbList |
| Depth | More detailed than the pillar's coverage of the same subtopic |

## Cluster Constraints

| Constraint | Value |
|-----------|-------|
| Clusters per pillar | 2-5 |
| Posts per cluster | 2-4 |
| Total posts (including pillar) | 5-21 |
| Max total estimated words | ~50,000 (pillar + 20 spokes at max) |

## Template Auto-Selection by Intent

| Intent Pattern | Template | Description |
|---------------|----------|-------------|
| Informational (broad) | `ultimate-guide` | Comprehensive topic overview |
| Informational (how) | `how-to` | Step-by-step instructions |
| Informational (list) | `listicle` | Numbered list of items/tips |
| Informational (concept) | `explainer` | Deep explanation of a concept |
| Commercial (compare) | `comparison` | Side-by-side product/service comparison |
| Commercial (evaluate) | `review` | In-depth review of a single product/service |
| Commercial (rank) | `best-of` | Ranked list of top options |
| Transactional | `landing-page` | Conversion-focused page |

**Selection logic:**
1. Match the keyword's classified intent to the table above
2. If multiple templates match, prefer the one whose SERP results show the most
   similar content format (e.g., if top results are all listicles, use `listicle`)
3. Avoid duplicate templates within the same cluster unless justified by intent

## Internal Link Rules

### Mandatory Links
- Every spoke MUST link to the pillar (at least once in body content)
- The pillar MUST link to every spoke (in its relevant section)
- These are non-negotiable -- a cluster without these links is structurally broken

### Recommended Links
- Spoke-to-spoke within the same cluster: 2-3 links per post
- Use contextual anchor text (target keyword or close variant)
- Place links within body paragraphs, not just in "related posts" sections

### Optional Links
- Cross-cluster spoke-to-spoke: 0-1 links per post
- Only when there is a genuine topical bridge between clusters
- Avoid forcing cross-links that do not add reader value

### Minimum Link Requirements
- Every post must have at least 3 incoming internal links
- No orphan pages (every page reachable from pillar within 2 clicks)
- Anchor text diversity: no single anchor text used for more than 40% of links to a page

## Cannibalization Prevention

1. **No two posts share the same primary keyword.** Period.
2. If SERP overlap between two keywords is 7+, merge into a single post
3. After clustering, verify uniqueness: list all primary keywords and check for
   near-duplicates (e.g., "best CRM" and "top CRM software")
4. If near-duplicates found, either merge the posts or differentiate by intent
   (e.g., one as "best-of" list, another as "comparison")

## JSON-LD Schema Templates

### Pillar Page
```json
[
  { "@type": "Article", "headline": "...", "author": {...}, "datePublished": "..." },
  { "@type": "BreadcrumbList", "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "..." },
    { "@type": "ListItem", "position": 2, "name": "Pillar Title", "item": "..." }
  ]},
  { "@type": "ItemList", "name": "Topic Cluster", "itemListElement": [
    { "@type": "ListItem", "position": 1, "url": "spoke-1-url" }
  ]}
]
```

### Spoke Page
```json
[
  { "@type": "Article", "headline": "...", "author": {...}, "isPartOf": { "@id": "pillar-url" } },
  { "@type": "BreadcrumbList", "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "..." },
    { "@type": "ListItem", "position": 2, "name": "Pillar Title", "item": "pillar-url" },
    { "@type": "ListItem", "position": 3, "name": "Spoke Title", "item": "..." }
  ]}
]
```

## cluster-plan.json Schema

```json
{
  "version": "1.9.0",
  "seed_keyword": "string",
  "created_at": "ISO-8601",
  "pillar": {
    "title": "string",
    "keyword": "string",
    "volume": 0,
    "template": "ultimate-guide",
    "wordCount": 4000,
    "url": "string",
    "status": "planned|written"
  },
  "clusters": [
    {
      "name": "Cluster Name",
      "posts": [
        {
          "title": "string",
          "keyword": "string",
          "volume": 0,
          "template": "string",
          "wordCount": 1500,
          "url": "string",
          "status": "planned|written"
        }
      ]
    }
  ],
  "links": [
    { "from": "pillar", "to": "cluster-0-post-0", "type": "mandatory", "anchor": "keyword" }
  ],
  "serp_matrix": {
    "keywords": ["string"],
    "scores": [[0]]
  },
  "scorecard": {
    "coverage": 0.0,
    "linkDensity": 0.0,
    "orphanPages": 0,
    "cannibalization": 0,
    "contentGaps": 0
  }
}
```
