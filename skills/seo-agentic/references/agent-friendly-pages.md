# Agent-friendly pages: page-level audit reference

Agents act for people: they search, compare, fill forms and buy. They read a
page through three channels, and most combine all three:

1. **Screenshots and a vision model**: visual hierarchy, button prominence,
   layout. Slow and token-expensive.
2. **Raw HTML and the DOM**: nesting, IDs, classes, data attributes.
3. **The accessibility tree**: the browser's semantic summary (roles, names,
   states). The cleanest signal of the three, and the one vendors agree on.
   OpenAI's publisher guidance says its browser "uses ARIA tags ... to interpret
   page structure and interactive elements"; the Lighthouse Agentic Browsing
   docs call the accessibility tree the agents' primary data model; WebKit's
   objection to WebMCP argues for using the accessibility tree instead of a
   parallel tool layer.

Prefer native elements over ARIA (the W3C first rule of ARIA). ARIA repairs
custom widgets; it does not replace a real `<button>`.

**Primary sources:** Google AI optimization guide
(developers.google.com/search/docs/fundamentals/ai-optimization-guide), the
web.dev agent-friendly article it links, and Chrome's Lighthouse Agentic
Browsing docs (developer.chrome.com/docs/lighthouse/agentic-browsing).

## Audit checklist

### 1. Use real interactive elements

| Pass | Fail |
|---|---|
| `<button>` for actions | `<div onclick="...">` |
| `<a href="...">` for navigation | `<div onclick="window.location...">` |
| `<input>` / `<select>` / `<textarea>` | Custom `contenteditable` widgets |

If a real element is impossible, supply `role`, `tabindex="0"`, an accessible
name, and key handlers for Enter and Space. Custom div widgets often reach the
accessibility tree with no role, and agents skip them.

### 2. Accessible names and labels

Every input needs a `<label for>`, `aria-label`, or `aria-labelledby`. Every
icon-only button needs an accessible name. These map to the axe rules
`label`, `button-name`, `link-name`, `select-name` and `input-button-name`
inside Lighthouse's `agent-accessibility-tree` audit (full list in
`references/lighthouse-agentic-category.md`).

### 3. Interactive target size

Visual pipelines drop interactive elements with very small unobscured area.
WCAG 2.2 AA asks for 24 x 24 CSS pixels (Apple HIG 44 x 44); meeting those
also clears the agent threshold. Treat anything smaller as a candidate for
agent invisibility.

### 4. No transparent overlays on interactive nodes

Vision models discard covered nodes. Common offenders:

- Full-card click handlers laid over every child link.
- Cookie-consent layers that persist after consent.
- Modal portals left with `pointer-events: auto` after dismissal.
- Tracking layers with `position: absolute; inset: 0`.

### 5. Layout stability

Keep CLS at or under 0.1 (Lighthouse counts it in the Agentic Browsing
fraction), and keep functionally identical actions in the same place across
templates. An "Add to cart" button that moves between `/shoes` and `/bags`
forces screenshot agents to relearn each page.

### 6. `cursor: pointer` as a signal

Vision models read `cursor: pointer` as "actionable". Keep it on real
controls and never add it to non-interactive elements.

### 7. Stable, meaningful selectors

DOM-parsing agents rely on landmarks (`<nav>`, `<main>`, `<article>`,
`<aside>`), stable `id`s on layout containers, and `data-*` attributes that
describe purpose. Hashed class names alone tell an agent nothing.

### 8. Failure patterns to flag (practitioner consensus, not vendor-measured)

- Hover-only menus, and infinite scroll with no paginated links.
- Custom selects and date pickers without the ARIA pattern for their role.
- Closed shadow DOM and canvas-only interfaces.
- Consent banners or modals that trap focus or cover controls.
- CAPTCHAs or bot challenges on content and informational pages.
- Client-only rendering of primary content (check with
  `agentic_check.py`, `server-rendered`).
- Confirmation states that only flash briefly or live in a toast.

No controlled public study links accessibility-tree quality to agent task
success. Present these as reasoned practice, not measured uplift.

## Tools

```bash
# Local 0-100 Agent-UX heuristic (HTML semantics + Chromium accessibility tree)
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run agent_ux_check.py <URL> --json

# Raw accessibility tree without scoring
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run render_page.py <URL> --mode auto --a11y-tree --json

# Google's own pass/fail view (the X/N fraction)
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run lighthouse_agentic.py <URL> --json
```

The Agent-UX score is a local heuristic. Never present it as the Lighthouse
Agentic Browsing result, which is a fraction (X of N), not a 0-100 score.

## Quick manual check

In DevTools, open the Accessibility pane or the full-page accessibility tree
and look for:

- Interactive elements exposed as `generic` (broken semantics).
- Inputs or buttons with no accessible name.
- A `<div>` with a click handler and no role or tabindex.

## Last verified

2026-09-23 against Lighthouse 13.5.0 source and Chrome's Agentic Browsing
docs. Recheck when web.dev revises its agent-friendly criteria or Lighthouse
changes the `agent-accessibility-tree` rule set.
