# Audit Synthesis Framework: VALIDATE and ACT

> Phases 3 and 4 of the 10-principle framework in `thinking-framework.md`. Read that file first for the phase overview, PERCEIVE and ANALYZE.

## VALIDATE

### 7. FEEL: emotional intelligence + intuition

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

### 8. ACCEPT: intellectual humility

Each recommendation should carry the falsifiability that comes with
honesty:

- If the hypothesis behind the recommendation is wrong, what would
  prove it? (Set a measurable check.)
- If the user has tried this and it didn't work before, surface that.
  Don't re-recommend the same thing.
- If a constraint cannot be removed (legal, brand, technical), the
  recommendation has to pivot, not double down.
- If a v1 recommendation is now stale because Google's guidance shifted,
  retract it explicitly.

**Discipline:** every recommendation gets a "how would we know this
failed?" line. No invisible bets.

---

## ACT

### 9. CREATE: generative output

Stop strategizing. Produce the artifact:

- A markdown report with prioritized actions, dependencies, and
  measurable outcomes.
- Generated schema JSON-LD ready to paste into the site.
- A content brief with target keywords, outline, and internal links.
- A PDF via `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run google_report.py` when the user asks for one.
- The smallest implementation of the highest-leverage recommendation,
  not the full plan.

**Discipline:** ship the artifact. Analysis paralysis is the enemy.

### 10. GROW: iterative loop

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
