# Persona-Based Scoring Methodology

Score the target page from the perspective of each derived persona. This reveals
which audience segments the page serves well and which it fails.

---

## Persona Derivation

Derive 4-7 personas from SERP intent signals. Do not invent personas without
evidence -- every persona must trace back to a signal cluster.

### Sources for Persona Derivation

| Source | What It Reveals | Example Persona |
|--------|----------------|-----------------|
| PAA question cluster | Knowledge gaps by audience | Beginner, Technical Evaluator |
| Ad copy segments | Commercial audience targets | Budget Buyer, Enterprise Buyer |
| Related search themes | Journey stage groups | Researcher, Comparison Shopper |
| SERP result types | Content consumption preferences | Visual Learner, Data-Driven Analyst |
| Featured snippet format | Expected answer style | Quick-Answer Seeker |

### Persona Card Format

For each persona, document:

```
**[Persona Name]** -- [one-line description]
- Role: [job title or situation]
- Goal: [what they want to accomplish]
- Emotional state: [from user-story-framework.md]
- Journey stage: Awareness | Consideration | Decision
- Key questions: [2-3 questions this persona needs answered]
- SERP evidence: [specific signals that generated this persona]
```

---

## 4-Dimension Scoring Rubric

Score each persona on 4 dimensions. Maximum 25 points each, 100 total per persona.

### Dimension 1: Relevance (0-25)

Does the page address this persona's specific need?

| Score | Criteria |
|-------|----------|
| 21-25 | Page directly addresses the persona's primary goal with specific content |
| 16-20 | Page covers the topic but lacks persona-specific depth or framing |
| 11-15 | Page is tangentially relevant -- persona must extrapolate to find value |
| 6-10 | Page mentions the topic but serves a different audience |
| 0-5 | Page is irrelevant to this persona's need |

**Scoring signals:** keyword alignment with persona goal, presence of persona-relevant
sections (e.g., "for small businesses" section for SMB persona), depth of coverage
for persona-specific use cases.

### Dimension 2: Clarity (0-25)

Can this persona find their answer within 10 seconds?

| Score | Criteria |
|-------|----------|
| 21-25 | Answer is visible above fold or within first scroll for this persona |
| 16-20 | Answer is on the page but requires scrolling or navigation |
| 11-15 | Answer exists but is buried in dense text or unclear structure |
| 6-10 | Persona must piece together the answer from multiple sections |
| 0-5 | Answer is not clearly present -- persona would bounce |

**Scoring signals:** heading clarity for persona's question, scan-ability (bullets,
tables, bold key terms), table of contents or jump links, information hierarchy
matching persona priority.

### Dimension 3: Trust (0-25)

Does the page provide adequate trust signals for this persona?

| Score | Criteria |
|-------|----------|
| 21-25 | Multiple trust signals directly relevant to this persona's concerns |
| 16-20 | General trust signals present but not persona-specific |
| 11-15 | Some trust signals but gaps in what this persona needs |
| 6-10 | Minimal trust signals -- persona would feel uncertain |
| 0-5 | No trust signals or signals that actively undermine trust for this persona |

**Scoring signals:** testimonials from similar users/companies, relevant credentials
or certifications, security badges (for risk-averse personas), case studies matching
persona's industry or size, author expertise signals.

### Dimension 4: Action (0-25)

Is there a clear next step for this persona?

| Score | Criteria |
|-------|----------|
| 21-25 | Clear, persona-appropriate CTA with low friction |
| 16-20 | CTA exists but is generic (not tailored to persona's stage) |
| 11-15 | Next step is available but not prominent or requires searching |
| 6-10 | Only one CTA that doesn't match persona's journey stage |
| 0-5 | No clear next step -- persona reaches a dead end |

**Scoring signals:** CTA relevance to journey stage (awareness = "learn more",
decision = "buy now"), friction level (free trial vs sales call), CTA placement
relative to persona-relevant content, alternative paths for different readiness levels.

---

## Score Interpretation

| Range | Rating | Implication |
|-------|--------|-------------|
| 80-100 | Excellent | Page serves this persona well -- minor optimizations only |
| 60-79 | Good | Page is relevant but has notable gaps for this persona |
| 40-59 | Needs Work | Page partially serves this persona -- significant improvements needed |
| 0-39 | Critical Mismatch | Page fails this persona -- major restructuring or new page needed |

---

## Aggregation and Prioritization

### Weighted Average

Not all personas are equally important. Weight by estimated search volume share:

- If SERP shows 70% informational intent, weight informational personas higher
- If ads dominate, weight commercial personas higher
- If local pack present, weight local personas higher

### Priority Ranking

Sort improvement recommendations by:

1. **Weakest persona with highest search volume weight** = biggest opportunity
2. **Lowest-scoring dimension across all personas** = systemic issue
3. **Critical mismatch personas** = fundamental page-type problem

### Output Format

```
## Persona Scores for [URL]

| Persona | Relevance | Clarity | Trust | Action | Total | Rating |
|---------|-----------|---------|-------|--------|-------|--------|
| [Name] | XX/25 | XX/25 | XX/25 | XX/25 | XX/100 | [Rating] |
| ... | ... | ... | ... | ... | ... | ... |

### Weakest Persona: [Name] (XX/100)
**Top issue:** [specific problem]
**Recommended fix:** [concrete action with page-level detail]

### Systemic Issues
- [dimension]: [pattern across all personas]

### Priority Actions
1. [Action targeting weakest persona]
2. [Action targeting systemic issue]
3. [Action targeting next weakest persona]
```

---

## Validation Rules

- [ ] Every persona traces to specific SERP signals (no invented personas)
- [ ] Scores include specific evidence from the page (not just numbers)
- [ ] Recommendations are concrete (section names, CTA text, placement)
- [ ] At least 4 personas scored, no more than 7
- [ ] Weakest persona is addressed first in recommendations
- [ ] Score interpretation uses the standard ranges above
