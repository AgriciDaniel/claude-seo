# Topical Authority Reference

Based on Koray Tuğberk GÜBÜR's Holistic SEO methodology.

---

## The Topical Authority Formula

**Topical Authority = Topical Coverage + Historical Data + Cost of Retrieval**

- **Topical Coverage**: A website comprehensively covers all semantic variations, subtopics, and related questions within a niche. No significant gaps exist in the semantic field.
- **Historical Data**: A reliable content history builds trust signals — publishing cadence, consistency, and longevity of relevant content.
- **Cost of Retrieval**: The efficiency with which search engines can crawl, parse, and understand the semantic network — affected by technical SEO, internal linking structure, and schema clarity.

---

## Topical Maps

A **topical map** is a structured hierarchy of all topics, subtopics, and semantic relationships within a niche. Each node represents a single page with one macro context.

### How to create a topical map:
1. **Identify the root topic** (the niche or domain of authority to build)
2. **Enumerate all subtopics** at each level of specificity — every angle, question, attribute, and variant users might search for
3. **Map semantic relationships** — which subtopics are adjacent, which are parent/child, which require bridging pages
4. **Assign one page per node** — each unique subtopic gets its own URL with a single macro context
5. **Identify gaps** — nodes in the map without corresponding published pages are topical gaps that weaken authority

### Topical Map Signals to Audit:
- Does every key subtopic in the niche have a dedicated page?
- Are there cluster pages that mix multiple macro contexts (dilution)?
- Are the topical levels properly nested (root → pillar → cluster → detail)?
- Does the content calendar fill gaps in topical order, not just chronologically?

---

## Entity-Attribute-Value (EAV) Coverage

Search engines and LLMs parse content through entities, their attributes, and the values of those attributes.

### Framework:
| Layer | Definition | Example |
|-------|-----------|---------|
| **Entity** | A named concept, person, place, product, or idea | "espresso machine" |
| **Attribute** | A property or characteristic of the entity | "pressure", "material", "price range" |
| **Value** | The specific data or description for that attribute | "15 bar", "stainless steel", "$200-$500" |

### Auditing EAV Coverage:
- Identify the **primary entity** the page is about
- List all **expected attributes** for that entity type (based on user intent and competitor coverage)
- Check whether **values** are present, specific, and accurate for each attribute
- Flag missing attributes as **topical gaps** — an incomplete entity representation weakens the page's semantic signal
- Check that entities are **named explicitly** — avoid pronoun ambiguity ("it", "they") that NLP systems cannot resolve

---

## Semantic Content Networks

A **semantic content network** is an interconnected set of pages where every internal link reflects a meaningful topical or entity relationship.

### Principles:
- **Semantic relevance over quantity**: Link from page A to page B only when there is a genuine entity/topic overlap. Anchor text must describe the semantic relationship.
- **Hub-and-spoke topology**:
  - **Hub (pillar)** pages: broad topic overview, link out to all cluster/spoke pages
  - **Spoke (cluster)** pages: deep subtopic, link back to hub and sideways to adjacent spokes
- **Contextual bridges**: Pages on adjacent topics that lack a direct relationship should be connected through a "bridge" page that addresses both
- **No orphan pages**: Every page must be reachable through contextually relevant anchor text from at least one related page
- **Anchor text signals**: Anchor text communicates the semantic content of the linked page to search engines — use descriptive, entity-rich anchors, not generic text ("click here", "read more")

### Network Quality Checks:
- Is the hub/spoke topology clearly defined?
- Do all spoke pages link back to their hub?
- Are adjacent-topic pages connected through semantically appropriate anchors?
- Are anchor texts descriptive and entity-rich?
- Are there orphan pages (no inbound internal links from topically related pages)?
- Are there "over-linked" hub pages where internal links dilute PageRank without semantic value?

---

## Entity Identity Management

For a brand, website, or author to be recognized as an authoritative entity in Google's Knowledge Graph, the entity must be clearly defined and consistently represented across the web.

### Core entity identity elements:
- **Organization schema** with `name`, `url`, `logo`, `sameAs` (Wikipedia, Wikidata, Crunchbase, LinkedIn, social profiles)
- **Person schema** for key authors/founders with `name`, `jobTitle`, `worksFor`, `sameAs` links
- **Knowledge Panel signals**: consistent Name-Address-Phone (NAP for local), consistent brand name across all mentions
- **Wikipedia / Wikidata presence** (if brand meets notability threshold)
- **Structured data completeness**: all entity attributes that Google supports for the entity type should be present

### Audit checklist:
| Signal | Status | Notes |
|--------|--------|-------|
| Organization schema with sameAs links | ✅/⚠️/❌ | ... |
| Consistent brand name across the web | ✅/⚠️/❌ | ... |
| Author Person schema on key content | ✅/⚠️/❌ | ... |
| Wikidata entity exists (if applicable) | ✅/⚠️/❌ | ... |
| Google Knowledge Panel present | ✅/⚠️/❌ | ... |
| AboutPage / ProfilePage schema | ✅/⚠️/❌ | ... |

---

## Content Structure for NLP Alignment

Koray's "41 content rules" are built on aligning content structure with how NLP algorithms process text.

### Key structural principles:

1. **One macro context per page**: Each page addresses exactly one primary topic or question. Pages that mix multiple unrelated intents confuse NLP classifiers and dilute authority.

2. **H2 headings as user questions**: Frame H2s as the actual questions users ask, creating passage-level topical signals that match query intent patterns.

3. **40-word extractive answers**: After each H2 question, provide a ~40-word, self-contained answer that can be directly extracted and cited by search engines (Featured Snippets, AI Overviews, Perplexity).

4. **Full EAV coverage**: Include all relevant Entity-Attribute-Value data for the page's primary entity — don't assume search engines infer what's missing.

5. **Semantic field completeness**: Use synonyms, related terms, and semantically adjacent concepts naturally. NLP systems expect a rich semantic field — sparse content with only one keyword repeated scores poorly for topical depth.

6. **Explicit entity naming**: Name entities directly and clearly. Avoid vague pronouns or ambiguous references that NLP cannot resolve to a specific entity.

---

## Topical Authority Assessment Scoring

When evaluating a page or site for topical authority, score across these dimensions:

| Dimension | Weight | What to Measure |
|-----------|--------|-----------------|
| Topical Map Coverage | 30% | % of niche subtopics covered vs estimated full map |
| EAV Completeness | 25% | % of entity attributes/values present vs expected |
| Semantic Network Quality | 20% | Internal link semantic relevance; hub/spoke topology correctness |
| Entity Identity Clarity | 15% | Organization/Person schema, sameAs links, Knowledge Graph signals |
| NLP Structure Compliance | 10% | Macro context focus, H2 framing, extractive passages |

**Score interpretation:**
- 80-100: Strong topical authority signals; competitive for high-volume queries in the niche
- 60-79: Moderate; topical gaps exist that competitors can exploit
- 40-59: Weak; significant content gaps and/or poor entity definition
- 0-39: Thin topical coverage; authority signals are insufficient for competitive queries

---

## Holistic SEO vs Traditional SEO

| Dimension | Traditional SEO | Holistic SEO (Koray's methodology) |
|-----------|----------------|-----------------------------------|
| Primary ranking driver | Backlinks + keyword targeting | Topical authority (coverage + entity clarity) |
| Content strategy | Individual pages per keyword | Topical maps → semantic content networks |
| Internal linking | Quantity metric (X links/page) | Semantic relevance of each link |
| Keyword focus | Keyword density % | Semantic field / EAV coverage |
| Authority metric | Domain Authority (DA/DR) | Topical Coverage Score |
| Scaling approach | More backlinks | Fill topical map systematically |
| Entity treatment | Keywords mentioning brands | Named entities with schema + Knowledge Graph |
