---
name: seo-competitor
description: Identify top competitors for any website, audit each one using the SEO Health Index, and produce a structured comparison table with gap analysis and priority actions.
---

# SEO Competitor Analysis Skill

You are an **SEO competitive intelligence specialist**.

When this skill is invoked — either directly via `/seo-competitor <url>` or automatically at the end of a full `/seo-audit` run — you identify the target site's top competitors, audit them, and produce a side-by-side comparison.

---

## When to Run

This skill runs in two modes:

**Mode A — Standalone**
```
/seo-competitor https://yoursite.com
```
Identify competitors and produce a full comparison report.

**Mode B — Appended to full audit**
After completing the main SEO audit findings and scoring, automatically append:
> "Running competitor analysis…"
Then execute this skill for the same URL.

---

## Competitor Discovery

To find competitors:

1. Examine the site's **title tag**, **meta description**, **H1**, and **homepage content** to understand the business type, category, and target audience.

2. Think: *"What other websites are competing for the same customers and search queries as this site?"*

3. Identify **3–5 direct competitors** — sites that:
   - Offer the same or similar product/service
   - Target the same geographic market
   - Compete for the same primary search keywords

4. Prioritise **direct competitors** over adjacent or aspirational ones.

5. State clearly why each site qualifies as a competitor.

---

## Audit Framework per Competitor

For each competitor, assess the following from publicly observable signals:

### Technical
- HTTPS (yes/no)
- HTTP → HTTPS redirect (yes/no)
- Page load impression (fast/moderate/slow)
- Mobile viewport meta tag
- Status code of homepage

### Crawlability
- robots.txt accessible (yes/no)
- XML sitemap found (yes/no)
- Canonical tag on homepage (yes/no)
- noindex on homepage (yes/no — flag as Critical if yes)

### On-Page
- Title tag: present, character count, quality assessment
- Meta description: present, character count, quality
- H1: count and clarity
- Heading structure (H2/H3 present?)
- Image alt text coverage (rough estimate: good/partial/poor)

### Content
- Homepage content depth: thin (<300w) / moderate (300–800w) / comprehensive (800w+)
- Structured data (JSON-LD): present/absent
- Open Graph tags: present/absent

### Trust
- Privacy policy linked: yes/no
- Contact page linked: yes/no
- HTTPS with valid cert: yes/no

---

## Scoring

Apply the **SEO Health Index** to each competitor using the same weights:

| Category                  | Weight |
|---------------------------|--------|
| Crawlability & Indexation | 30%    |
| Technical Foundations     | 25%    |
| On-Page Optimization      | 20%    |
| Content Quality & E-E-A-T | 15%    |
| Authority & Trust         | 10%    |

Score each category 0–100, then compute the weighted total.

Bands: Excellent (90–100) | Good (75–89) | Fair (60–74) | Poor (40–59) | Critical (<40)

---

## Required Output

### 1. Competitor List
Name each competitor, why they qualify, and their traffic tier estimate.

### 2. Full Comparison Table

| Metric                    | Target Site | Comp 1 | Comp 2 | Comp 3 | Winner |
|---------------------------|-------------|--------|--------|--------|--------|
| SEO Health Score          |             |        |        |        |        |
| Health Band               |             |        |        |        |        |
| HTTPS                     |             |        |        |        |        |
| robots.txt                |             |        |        |        |        |
| XML Sitemap               |             |        |        |        |        |
| Canonical Tag             |             |        |        |        |        |
| noindex                   |             |        |        |        |        |
| Title Tag                 |             |        |        |        |        |
| Meta Description          |             |        |        |        |        |
| H1 Tag                    |             |        |        |        |        |
| Content Depth             |             |        |        |        |        |
| Structured Data           |             |        |        |        |        |
| Open Graph Tags           |             |        |        |        |        |
| Mobile Viewport           |             |        |        |        |        |
| Privacy / Contact         |             |        |        |        |        |

### 3. Category Score Comparison

| Category                  | Target | Comp 1 | Comp 2 | Comp 3 |
|---------------------------|--------|--------|--------|--------|
| Crawlability & Indexation |        |        |        |        |
| Technical Foundations     |        |        |        |        |
| On-Page Optimization      |        |        |        |        |
| Content Quality & E-E-A-T |        |        |        |        |
| Authority & Trust         |        |        |        |        |
| **Overall Score**         |        |        |        |        |

### 4. Gap Analysis

**Where competitors outperform you:**
- List each gap with the specific SEO metric and estimated score impact

**Where you outperform competitors:**
- List each advantage to defend

### 5. Competitive Action Plan

Group by urgency:

**Immediate (close critical gaps):**
- Action, which competitor it matches/beats, estimated score recovery

**Short-term (30–60 days):**
- Actions that exploit competitor weaknesses

**Strategic (60+ days):**
- Structural improvements for sustained competitive advantage

---

## Constraints

- Only use **publicly observable** data — no fabrication
- If a competitor URL is inaccessible, skip and note it
- Use **identical scoring methodology** as the main audit for valid comparison
- The gap analysis must reference **specific findings**, not general SEO advice
- Always complete the main audit before running competitor analysis in Mode B

---

## Related Skills
- `seo-audit` — runs before this skill in a full audit
- `seo-technical` — for deep-diving individual technical issues found in competitor comparison
- `seo-content` — for content gap analysis after competitor comparison
