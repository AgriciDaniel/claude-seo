# User Story Framework: SERP Signals to User Intent

Derive user stories from observable SERP signals. Every story must cite the
specific signal that generated it -- no guessing.

---

## Signal Sources

### 1. People Also Ask (PAA)

PAA questions reveal **knowledge gaps and concerns** the searcher has.

- Cluster PAA by theme: definitional ("what is"), procedural ("how to"),
  evaluative ("is X worth it"), comparative ("X vs Y"), risk ("is X safe")
- Each cluster maps to a distinct persona or journey stage
- Definitional PAA = awareness stage, evaluative PAA = consideration,
  comparative PAA = decision stage

### 2. Ad Copy

Ads reveal **commercial triggers and objection handling** that convert.

- Extract recurring themes across all visible ads (top + bottom)
- Common patterns: free trial emphasis (barrier: commitment), trusted-by counts
  (barrier: trust), price anchoring (barrier: cost), speed claims (barrier: time)
- If no ads appear, the keyword is likely informational -- commercial intent is low

### 3. Related Searches

Related searches reveal the **search journey** -- what comes before and after.

- Searches with added qualifiers (+ "for beginners", + "pricing") = narrowing
- Searches with removed qualifiers = broadening / pivoting
- "[keyword] alternatives" = dissatisfaction signal
- "[keyword] vs [competitor]" = active comparison stage
- "[keyword] reviews" = trust-seeking before purchase

### 4. Featured Snippets

The snippet format reveals the **expected answer structure**.

- Paragraph snippet = user wants a concise definition or explanation
- List snippet = user wants steps or ranked items
- Table snippet = user wants structured comparison data
- Video snippet = user wants visual demonstration
- No snippet = Google uncertain about best format (opportunity)

### 5. AI Overview

AI Overview reveals what Google considers the **authoritative synthesis**.

- Sources cited = authority signals Google trusts for this topic
- Answer structure = the format Google believes best serves the query
- If target page is not cited = content does not match Google's synthesis model

---

## User Story Format

```
As a [persona],
I want to [goal],
because [emotional driver],
but I'm blocked by [barrier].
```

### Persona Derivation

Derive from signal clusters, not assumptions:
- PAA cluster about cost/pricing = **Budget-Conscious Buyer**
- PAA cluster about setup/implementation = **Technical Evaluator**
- Ads emphasizing trust/security = **Risk-Averse Decision Maker**
- Related searches with "for small business" = **SMB Owner**
- Related searches with "enterprise" = **Enterprise Buyer**

### Emotional States

Map SERP signals to emotional states:

| Signal Pattern | Emotional State |
|---------------|----------------|
| "Is X safe / legitimate / scam" in PAA | Skeptical |
| Many comparison queries in related | Overwhelmed by choices |
| "How to [basic task]" dominating PAA | Confused / frustrated |
| High ad density + shopping results | Ready to buy |
| "Best [X] for [use case]" results | Evaluating carefully |
| "[X] not working / problems" in PAA | Frustrated with current solution |

### Barrier Types

| Barrier | SERP Signal | Page Must Address |
|---------|------------|-------------------|
| Information gap | PAA questions unanswered by snippet | Clear, complete answer in first scroll |
| Trust gap | Ads emphasize trust badges / reviews | Social proof, credentials, guarantees |
| Comparison fatigue | Many "vs" and "best" related searches | Clear differentiation or recommendation |
| Price sensitivity | PAA about cost, free alternatives | Transparent pricing, value justification |
| Technical confusion | "How to" PAA, setup-related queries | Step-by-step guide, demo, or tool |
| Time pressure | Ads with "instant" / "today" / "fast" | Quick-win content, speed of resolution |

---

## Example Derivation

**Keyword**: "project management software"

**Observed signals:**
- PAA: "Is Monday.com better than Asana?", "What is the cheapest project management tool?", "Do I need project management software for a small team?"
- Ads: "Free forever plan", "Trusted by 150,000 teams", "Set up in 5 minutes"
- Related: "project management software for small business", "free project management tools", "Asana vs Monday vs ClickUp"
- Featured snippet: list of tools with brief descriptions

**Derived user stories:**

1. As a **small business owner**, I want to find affordable PM software, because
   I need to organize my growing team, but I'm blocked by **price sensitivity**
   and fear of paying for features I won't use.
   *(Source: PAA "cheapest", related "small business", ads "free forever")*

2. As a **team lead evaluating tools**, I want to compare the top 3 options side
   by side, because my boss asked for a recommendation, but I'm blocked by
   **comparison fatigue** from too many similar-looking options.
   *(Source: related "Asana vs Monday vs ClickUp", PAA "is Monday better than Asana")*

3. As a **non-technical manager**, I want software that works immediately without
   training, because I can't afford downtime during migration, but I'm blocked by
   **technical confusion** about setup complexity.
   *(Source: ads "set up in 5 minutes", PAA "do I need PM software for small team")*

---

## Story Quality Checklist

- [ ] Every story cites at least one specific SERP signal
- [ ] Persona name reflects the signal source, not assumptions
- [ ] Emotional driver is grounded in observable SERP tone
- [ ] Barrier is specific enough to suggest a page-level fix
- [ ] 3-5 stories cover the primary intent angles (no duplicates)
- [ ] Stories span at least 2 journey stages (awareness, consideration, decision)
