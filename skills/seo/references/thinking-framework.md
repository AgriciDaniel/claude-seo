# The 10-Principle Audit Synthesis Framework

This is the canonical methodology claude-seo uses to assemble raw findings
into strategically coherent recommendations. Every full-site audit and
deep-page analysis walks through these ten principles before producing the
final action plan.

The principles group into four phases:

| Phase | Principles |
|---|---|
| **PERCEIVE** | OBSERVE (external) · OBSERVE (internal) · LISTEN |
| **ANALYZE** | THINK · CONNECT (lateral) · CONNECT (system) |
| **VALIDATE** | FEEL · ACCEPT |
| **ACT** | CREATE · GROW |

A recommendation that has not passed through all four phases is a finding,
not a recommendation.

---

## PERCEIVE

### 1. OBSERVE — the external input

Collect signals without interpreting them. For a website audit this means:

- Raw HTML + rendered HTML (via `claude-seo run render_page.py`)
- Schema.org markup actually present (via `seo-schema`)
- SERP visibility for the site's published topics (via `seo-dataforseo` /
  Google APIs when available)
- Backlink + brand-mention landscape (via `seo-backlinks`)
- Core Web Vitals field data from CrUX (via `claude-seo run pagespeed_check.py`)
- AI-search citation patterns (via `seo-geo`)
- Competitor pages on the target's primary keywords

**Discipline:** do not score yet. Do not classify yet. Just collect.

### 2. OBSERVE — internal metacognition

Audit your own assumptions about the site before assembling
recommendations. Common assumption traps in SEO:

- Assuming the homepage represents the site (often it doesn't —
  programmatic pages or category pages drive traffic)
- Assuming "low traffic" means "low value" (intent-matched low-volume can
  outconvert high-volume informational queries)
- Assuming the brand wants what the analyst thinks is "best practice"
  (their constraint might be brand voice, legal, or trade-offs you don't
  see)
- Assuming a CMS limitation is unfixable (often it isn't)
- Assuming a 1.x finding still applies in 2.x (Google updates change the
  ground)

**Discipline:** for each major recommendation, ask "what assumption is
this resting on?" If the answer surprises you, surface the assumption in
the report so the user can reject it explicitly.

### 3. LISTEN — active receptivity

Read what the site, user intent, and platform signals are actually saying
— not what you expect them to say.

- Read the page's existing copy before recommending a rewrite. The brand
  voice is data.
- Read the SERP for target keywords before deciding what page type to
  build. The SERP is Google's revealed preference for that intent.
- Read user reviews / community discussions / Reddit threads for what
  customers actually ask about (versus what the marketing team thinks
  they ask about).
- Read the user's prior conversations + memory if available — they may
  have ruled out approaches already.

**Discipline:** if a recommendation contradicts the SERP for the same
intent, the SERP wins unless you can explain why this site is the
exception.

---

## ANALYZE

### 4. THINK — critical processing

Reduce the findings to first principles:

- What is the **page type** (informational, transactional, navigational,
  local, commercial-investigation) and does the current layout serve
  that intent?
- What is the **eligibility floor** for AI features (indexed + can be
  shown with a snippet)? If the page is not indexed, no AI work
  matters yet.
- What is the **highest-leverage constraint** binding the site right
  now? (Often: a single technical defect — non-indexable, slow LCP,
  missing canonical — that gates everything else.)
- What does **Google's primary-source guidance** say about the
  recommendation? When community claims and Google contradict, defer
  to Google (see `skills/seo-geo/references/google-ai-optimization-guide.md`).

**Discipline:** the highest-leverage constraint goes first in the action
plan, even if it's less interesting than the "growth" recommendations.

### 5. CONNECT — lateral / associative

Combine findings from sub-skills that the user wouldn't naturally pair.
Examples that frequently produce the highest-value recommendations:

- `seo-content` thin-content finding × `seo-cluster` SERP-overlap data →
  consolidate three weak pages into one cluster hub.
- `seo-schema` missing Product schema × `seo-ecommerce` UCP-not-declared
  → both close the same agent-era buying gap; bundle as one
  recommendation.
- `seo-geo` low AI-citation rate × `seo-backlinks` brand-mention
  underweight → mentions matter 3× more than backlinks for AI
  citations; reframe link-building budget into PR / Reddit / YouTube.
- `seo-technical` SPA detection × `seo-content` missing main-content
  → JS-blocked content is the upstream cause of the content finding.

**Discipline:** any single sub-skill finding that survives connection
unchanged should be skeptical — it might be a symptom, not a cause.

### 6. CONNECT — system orchestration

Wire the validated recommendations into an executable sequence:

- Which recommendation **unblocks** the most others? Do that first.
- Which recommendations **depend** on each other? Sequence them.
- Which recommendations can be **parallelized**? Surface that to the
  user so they can dispatch them.
- Which recommendations need a **tool that's not yet installed** (e.g.
  Firecrawl for site crawl, DataForSEO for SERP data)? Flag the gap.

**Discipline:** the action plan is a dependency graph, not a list. If
two recommendations cannot be done in either order, say so.

---

## VALIDATE

### 7. FEEL — emotional intelligence + intuition

Pure-logic recommendations break on contact with the actual reader /
business / stakeholder. Pressure-test against:

- **User experience.** Would the recommendation make the page worse for
  a human reader? (Common failure: stuffing FAQ schema for a site Google
  doesn't even show rich results for.)
- **Brand voice.** Would the recommendation conflict with the site's
  existing tone? (Common failure: recommending "answer-first" rewrites
  on a luxury brand that uses suspense as a UX device.)
- **Operator capacity.** Is this realistic for the team that has to ship
  it? (Common failure: recommending 30 new location pages to a 2-person
  agency.)
- **Hard-earned intuition.** When the data is ambiguous, trust pattern
  recognition from past sites in the same vertical.

**Discipline:** if you can't articulate the human cost of a
recommendation, you haven't fully validated it.

### 8. ACCEPT — intellectual humility

Each recommendation should carry the falsifiability that comes with
honesty:

- If the hypothesis behind the recommendation is wrong, what would
  prove it? (Set a measurable check.)
- If the user has tried this and it didn't work before, surface that.
  Don't re-recommend the same thing.
- If a constraint cannot be removed (legal, brand, technical), the
  recommendation has to pivot — not double down.
- If a v1 recommendation is now stale because Google's guidance shifted,
  retract it explicitly.

**Discipline:** every recommendation gets a "how would we know this
failed?" line. No invisible bets.

---

## ACT

### 9. CREATE — generative output

Stop strategizing. Produce the artifact:

- A markdown report with prioritized actions, dependencies, and
  measurable outcomes.
- Generated schema JSON-LD ready to paste into the site.
- A content brief with target keywords, outline, and internal links.
- A PDF via `claude-seo run google_report.py` when the user asks for one.
- The smallest implementation of the highest-leverage recommendation,
  not the full plan.

**Discipline:** ship the artifact. Analysis paralysis is the enemy.

### 10. GROW — iterative loop

The audit is a snapshot, not a verdict. Build the feedback loop:

- Capture a baseline via `/seo drift baseline <url>` so subsequent
  audits can prove what changed.
- Define one or two leading indicators the user should monitor (CrUX
  trend, GSC impressions for a target cluster, brand-mention growth on
  Reddit / YouTube).
- Schedule a re-audit cadence appropriate to the site's velocity
  (weekly for a high-churn ecommerce; quarterly for a B2B SaaS).
- Surface what claude-seo itself **could not measure** (offline
  conversion, brand lift, customer interviews) so the human closes
  those loops.

**Discipline:** the last paragraph of every audit names what the next
audit should look for.

---

## How to invoke the framework

Every full-site audit (`/seo audit`) and deep-page audit (`/seo page`)
walks through PERCEIVE → ANALYZE → VALIDATE → ACT before emitting the
action plan. The Critical / High / Medium / Low priority bucketing
happens **after** the validation phase, not instead of it.

Single-purpose commands (`/seo schema`, `/seo images`, `/seo technical`,
etc.) can skip the full loop when the user is asking a narrow question
— but their recommendations should still pass at least THINK + ACCEPT
before being emitted (does this rest on a sound first principle, and is
the falsifiability surfaced?).

## When to escalate to the user

These principles are claude-seo's; they are not the user's. Surface them
for the user when:

- A recommendation requires accepting an assumption you'd rather not own
  (CONNECT-lateral often produces these — surface the link and let the
  user confirm).
- The validation phase flagged a brand-voice / operator-capacity / hard
  constraint you can see but cannot resolve.
- The audit found no upstream constraint and is recommending an
  optimization that may be premature.
