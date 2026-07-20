# Agent-friendly pages — audit reference (June 2026)

The next wave of AI search is not summarization — it's **agents** acting on the
user's behalf (search, compare, buy, book). Google's AI optimization guide and
the linked web.dev article describe three channels through which agents
interpret your site:

1. **Screenshots + vision model** — interprets visual hierarchy, button
   prominence, layout. Slow and token-expensive.
2. **Raw HTML / DOM** — nesting, IDs, classes, data attributes.
3. **The accessibility tree** — the browser-native semantic distillation
   (roles, names, states). The cleanest signal of the three.

Modern agents combine all three. Optimizing for the **accessibility tree** is
the single highest-leverage move; if your accessibility tree is broken, no
amount of visual polish saves you.

**Primary sources:**
- Google AI optimization guide:
  https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- web.dev (referenced from the guide above): article on building
  agent-friendly websites

## Audit checklist

### 1. Use real interactive elements

| Pass | Fail |
|---|---|
| `<button>` for actions | `<div onclick="...">` |
| `<a href="...">` for navigation | `<div onclick="window.location...">` |
| `<input>` / `<select>` / `<textarea>` | Custom `contenteditable` widgets |

If you cannot use a real interactive tag, supply ARIA: `role="button"`,
`role="link"`, `tabindex="0"`, plus key handlers for `Enter` and `Space`.

**Why it matters:** the accessibility tree exposes real interactive elements
with their roles. Custom div widgets often appear in the tree with no role at
all — agents skip them.

### 2. Label associations

Every form input must have an associated label:

```html
<label for="email">Email</label>
<input id="email" type="email" name="email">
```

Or use `aria-label` / `aria-labelledby` where a visible label isn't possible.
Agents that read the accessibility tree get the field purpose directly from
the associated label — without it, the input is a void.

### 3. Interactive target size

Visual-analysis pipelines filter out interactive elements smaller than **~8
square pixels** of unobscured area. Tap-target accessibility minimums (24×24
WCAG AA, 44×44 Apple HIG) are stricter and pass the agent gate by default.

Audit: any clickable element below 24×24px is a candidate for agent
invisibility, in addition to the WCAG failure.

### 4. Don't cover interactive nodes with transparent overlays

Vision models discard covered nodes when computing what's "interactive at this
position". Common offenders:

- Full-card click handlers that overlay every child link.
- Transparent cookie-consent layers persisting beyond consent.
- Modal portals with `pointer-events: auto` left on after dismiss.
- "Ghost" tracking pixels with `position: absolute; inset: 0`.

### 5. Layout stability

If "Add to cart" lives in different positions on `/category/shoes` vs
`/category/bags`, screenshot-based agents have to relearn the page each
visit. Keep functionally identical actions in the same screen quadrant across
templates.

Cross-reference: this overlaps with **CLS** (Cumulative Layout Shift) in Core
Web Vitals, but the agent-UX concern is broader — it covers page-to-page
stability, not just within-page shift.

### 6. `cursor: pointer` as a legitimate signal

Vision models read `cursor: pointer` (set by default on `<a>` / `<button>`) as
a hint that an element is actionable. Do not override it to `cursor: default`
on truly interactive elements just for visual minimalism.

Inverse: do not apply `cursor: pointer` to non-interactive elements — that
makes agents click things that do nothing.

### 7. Stable, meaningful selectors

Agents that fall back to DOM parsing rely on:

- Real semantic tags (`<nav>`, `<main>`, `<article>`, `<section>`, `<aside>`)
- Stable `id` attributes on top-level layout containers
- `data-*` attributes that describe purpose, not implementation

Avoid auto-generated class names like `__sc_a4b7d9e2` as the only handle on a
critical interactive element — agents can target them but cannot tell what
they mean.

## Lighthouse Agentic Browsing category (shipped)

Google now ships a dedicated **Agentic Browsing** Lighthouse category — created
in Lighthouse **13.2.0 (2026-05-01)** and **on by default since 13.3.0
(2026-05-07)** in DevTools and the CLI (Chrome 150+). Category id:
`agentic-browsing`. Unlike other categories it reports a **fractional
pass-ratio** (X of N checks passed), **not** a 0–100 weighted score — so do not
compute or report a weighted agentic "score". It groups deterministic audits
into three buckets:

- **Agent-centric accessibility** — reuses three a11y audits: *Names and labels*
  (every interactive element has a programmatic name), *Tree integrity* (valid
  roles + parent-child relationships), *Visibility* (interactive content not
  hidden from the accessibility tree). These map directly onto checklist items
  1–2 above and the `agent_ux_check.py` heuristics.
- **Stability & discoverability** — *CLS* (visual stability for element
  positioning; see checklist item 5) + an *llms.txt* presence-at-domain-root
  check (13.4.0 relaxed it to allow leading whitespace).
- **WebMCP integration** — three audits, see below.

**Run paths:** DevTools Lighthouse panel (Chrome 150+, default-on, no toggle);
CLI `npx lighthouse@latest <url> --only-categories=agentic-browsing` (per-audit
JSON for CI); PageSpeed Insights **web UI**. **The PSI REST API does NOT return
this category** — `scripts/pagespeed_check.py` will not contain agentic results
(disabled in Lighthouse 13.4.0); CrUX never provides these lab audits.

## WebMCP (proposed standard; status needs recheck)

**WebMCP** lets a site declare structured tools/actions for agents rather than
agents inferring intent from the DOM. It is **no longer "years away"**: a
flag-gated Early Preview (Chrome 146 Canary) opened 2026-02-10, and Chrome 149
origin-trial/sign-up status needs verification from a Google-owned source
(local dev flag: `chrome://flags/#enable-webmcp-testing`). It remains a
*proposed* standard from the Web Machine Learning community group
(github.com/webmachinelearning/webmcp), not W3C-finalized.

Lighthouse 13.2+ ships **three WebMCP audits** under the Agentic Browsing
category (require Chrome 150+ and origin-trial registration). Shipped audit ids
in the 13.2.0 release notes:

- `webmcp-form-coverage`: informational; flags `<form>` elements lacking
  `toolname` / `tooldescription`.
- `webmcp-registered-tools`: informational; lists tools registered via the
  declarative (HTML) and imperative (JS) APIs.
- `webmcp-schema-validity`: validates WebMCP form schemas.

(Code parsing Lighthouse JSON should expect the release-note ids above.)

**Audit posture:** WebMCP is an active opportunity, not a finding to hard-fail —
absence is not a defect. Surface it as an opportunity for sites that want
first-class agent actions, and note origin-trial enrollment is required for the
audits to fire.

## Quick-audit one-liner

For a fast smoke check, capture the accessibility tree via Lighthouse or
Chrome DevTools and look for:

- Any interactive element with `role="generic"` → broken semantics.
- Any input without an `accessible name` → missing label.
- Any `<div>` with `onclick` and no `role` / `tabindex` → custom widget that
  agents won't see.

`scripts/render_page.py --mode auto` already loads pages headlessly; extending
it with an accessibility-tree dump (`page.accessibility.snapshot()` in
Playwright) is the natural place to land an automated agent-UX check in a
future iteration.

## Last verified

2026-06-21. (Google has now published an agent-UX scoring framework — the
Lighthouse Agentic Browsing category — and WebMCP has reached a public Chrome
149 origin trial; both are reflected above.) Update when:

- WebMCP graduates from origin trial to a stable/shipped API (or W3C status changes).
- Google adds or renames audits in the `agentic-browsing` category.
- web.dev publishes a follow-up article with revised criteria.
