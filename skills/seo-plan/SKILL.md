---
name: seo-plan
description: >
  Strategic SEO planning for new or existing websites. Industry-specific
  templates, competitive analysis, content strategy, and implementation
  roadmap. Use when user says "SEO plan", "SEO strategy", "content strategy",
  "site architecture", or "SEO roadmap".
---

# Strategic SEO Planning

## Process

### 1. Discovery
- Business type, target audience, competitors, goals
- Current site assessment (if exists)
- Budget and timeline constraints
- Key performance indicators (KPIs)

### 2. Competitive Analysis
- Identify top 5 competitors
- Analyze their content strategy, schema usage, technical setup
- Identify keyword gaps and content opportunities
- Assess their E-E-A-T signals
- Estimate their domain authority

### 3. Architecture Design
- Load industry template from `assets/` directory
- Design URL hierarchy and content pillars
- **Topical Map**: Create a hierarchical map of all topics, subtopics, and semantic relationships in the niche. Each node in the map = one page with a single macro context. The map defines complete topical coverage — no gaps.
- **Semantic Content Network**: Design how pages link to each other based on entity/topical adjacency (not just navigation). Every internal link should reflect a meaningful semantic relationship.
- Plan internal linking strategy (hub/spoke topology: pillar pages → cluster/subtopic pages)
- Sitemap structure with quality gates applied
- Information architecture for user journeys
- **Entity identity**: Define the core entities of the brand (Organization, People, Products, Services) and how they will be represented in structured data and Knowledge Graph signals.

### 4. Content Strategy

> **Koray's Holistic SEO principle:** Build Topical Authority through comprehensive topical coverage, not by accumulating backlinks or targeting individual keywords in isolation.

- **Topical Authority roadmap**: Prioritize content to fill the topical map systematically — cover all subtopics within a niche cluster before moving to adjacent clusters.
- Content gaps vs competitors (semantic angle analysis, not just keyword gap)
- Page types and estimated counts
- **One macro context per page**: Each planned page addresses exactly one primary topic/question. Flag any brief/category pages that mix multiple intents.
- **EAV planning**: For key pages, pre-define the Entities, Attributes, and Values to cover so writers know the semantic scope.
- Blog/resource topics and publishing cadence (topically ordered, not chronological)
- E-E-A-T building plan (author bios, credentials, experience signals)
- Content calendar with priorities

### 5. Technical Foundation
- Hosting and performance requirements
- Schema markup plan per page type
- Core Web Vitals baseline targets
- AI search readiness requirements
- Mobile-first considerations

### 6. Implementation Roadmap (4 phases)

#### Phase 1 — Foundation (weeks 1-4)
- Technical setup and infrastructure
- Core pages (home, about, contact, main services)
- Essential schema implementation
- Analytics and tracking setup

#### Phase 2 — Expansion (weeks 5-12)
- Content creation for primary pages
- Blog launch with initial posts
- Internal linking structure
- Local SEO setup (if applicable)

#### Phase 3 — Scale (weeks 13-24)
- Advanced content development
- Link building and outreach
- GEO optimization
- Performance optimization

#### Phase 4 — Authority (months 7-12)
- Thought leadership content
- PR and media mentions
- Advanced schema implementation
- Continuous optimization

## Industry Templates

Load from `assets/` directory:
- `saas.md` — SaaS/software companies
- `local-service.md` — Local service businesses
- `ecommerce.md` — E-commerce stores
- `publisher.md` — Content publishers/media
- `agency.md` — Agencies and consultancies
- `generic.md` — General business template

## Output

### Deliverables
- `SEO-STRATEGY.md` — Complete strategic plan
- `TOPICAL-MAP.md` — Full topic hierarchy with macro context per node, semantic relationships, and coverage gaps
- `SEMANTIC-CONTENT-NETWORK.md` — Internal linking plan based on entity/topical adjacency
- `COMPETITOR-ANALYSIS.md` — Competitive insights (topical coverage gaps, entity signals)
- `CONTENT-CALENDAR.md` — Content roadmap (topically ordered)
- `IMPLEMENTATION-ROADMAP.md` — Phased action plan
- `SITE-STRUCTURE.md` — URL hierarchy and architecture
- `ENTITY-IDENTITY.md` — Brand entity definitions, Knowledge Graph signals, schema plan

### KPI Targets
| Metric | Baseline | 3 Month | 6 Month | 12 Month |
|--------|----------|---------|---------|----------|
| Organic Traffic | ... | ... | ... | ... |
| Keyword Rankings (target cluster) | ... | ... | ... | ... |
| Topical Map Coverage (% of nodes published) | ... | ... | ... | ... |
| Indexed Pages | ... | ... | ... | ... |
| Core Web Vitals | ... | ... | ... | ... |
| Knowledge Panel / Entity recognition | ... | ... | ... | ... |

> **Note on Domain Authority:** Domain Authority (DA/DR) is a third-party proxy metric, not a Google signal. Per Koray's holistic SEO methodology, prioritize **topical coverage completeness** as the primary growth lever — comprehensive topical authority achieves rankings independently of link acquisition. Track link metrics as supplementary signals, not primary KPIs.

### Success Criteria
- Clear, measurable goals per phase
- Resource requirements defined
- Dependencies identified
- Risk mitigation strategies
