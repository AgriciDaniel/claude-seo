# Lighthouse Agentic Browsing category (source-verified, Lighthouse 13.5.0)

Verified 2026-09-23 against the Lighthouse 13.5.0 npm package
(`core/config/default-config.js`, `core/audits/agentic/*`,
`core/audits/webmcp-*`, `core/gather/gatherers/agentic/*`,
`report/renderer/report-utils.js`) and live PSI v5 runs. The category is
labelled "still under development and subject to change", so re-read the
source when the Lighthouse version moves.

## Where it runs

| Path | Notes |
|---|---|
| PSI API v5 | `category=AGENTIC_BROWSING` (enum in the v5 discovery doc; `agentic-browsing` also works). PSI ran Lighthouse 13.5.0 on HeadlessChrome 153 on 2026-09-23 and exposed WebMCP tools. |
| Lighthouse CLI | `npx lighthouse@latest <url> --only-categories=agentic-browsing --output=json` (Node 22.19+). |
| DevTools | Lighthouse panel, Chrome 150+. WebMCP audits need a browser with WebMCP enabled (origin trial or flag). |

CrUX never provides these audits: they are lab-only.

## Category definition

Category id `agentic-browsing`, `categoryScoreDisplayMode: "fraction"`,
supported modes navigation and snapshot. Seven audit refs, all weight 1:

| Audit id | Group | Scoring |
|---|---|---|
| `agent-accessibility-tree` | agent-accessibility | Binary. Passes only if none of 33 axe rules fail (below). |
| `webmcp-form-coverage` | webmcp | Informative while any form lacks both `toolname` and `tooldescription`; **binary pass** once every form has one; N/A with no forms or no WebMCP support. Never fails. |
| `webmcp-registered-tools` | webmcp | Always informative; N/A without WebMCP support. Lists imperative and declarative tools. |
| `webmcp-schema-validity` | webmcp | 0 on errors, 0.5 on warnings (both count as failures), 1 when clean; N/A without WebMCP or when there are no tools and no issues. |
| `cumulative-layout-shift` | (none, CLS) | Numeric lab CLS; passes at score 0.9 or higher. |
| `llms-txt` | agent-discoverability | Fetches `/llms.txt`. 4xx: N/A. 5xx or fetch error: 0. Otherwise needs an H1 (`^\s*#\s+.+`), one Markdown link (`[..](..)`) and 50+ characters. |
| `ard-schema` | agent-discoverability | Validates `ai-catalog.json`. N/A unless a catalog is signalled or `/.well-known/ai-catalog.json` returns 200. Errors: 0; warnings only: 0.9 (still passes). |

`webmcp-schema-validity` errors: missing tool name, missing tool
description, a required parameter without a name. Warnings: a parameter with
no title or description, an optional parameter without a name. They surface
as Chrome DevTools issues (`FormModelContext*`).

### The 33 axe rules behind `agent-accessibility-tree`

`button-name`, `input-button-name`, `input-image-alt`, `label`, `link-name`,
`select-name`, `document-title`, `aria-allowed-attr`, `aria-allowed-role`,
`aria-command-name`, `aria-conditional-attr`, `aria-dialog-name`,
`aria-hidden-body`, `aria-hidden-focus`, `aria-input-field-name`,
`aria-prohibited-attr`, `aria-required-attr`, `aria-required-children`,
`aria-required-parent`, `aria-roles`, `aria-text`, `aria-toggle-field-name`,
`aria-tooltip-name`, `aria-treeitem-name`, `aria-valid-attr`,
`aria-valid-attr-value`, `duplicate-id-aria`, `definition-list`,
`table-duplicate-name`, `tabindex`, `autocomplete-valid`,
`presentation-role-conflict`, `svg-img-alt`.

Colour contrast, heading order and landmarks are **not** in the set, so a page
can fail the Accessibility category and still pass this audit.

### ARD catalog discovery order (gatherer `agentic/ard.js`)

1. robots.txt `Agentmap: <url>` (first match, case-insensitive)
2. `<link rel="ai-catalog" href="...">` in the DOM
3. HTTP `Link: <...>; rel="ai-catalog"` on the main document
4. `/.well-known/ai-catalog.json`

The ARD checks (specVersion `1.0`, `entries` array, `urn:air:` identifiers,
`displayName`, `type`, exactly one of `url`/`data`, 2 to 5
`representativeQueries`, `trustManifest.identity`, no top-level
`collections`) are ported in `agentic_check.py` (`validate_ai_catalog`).
Spec: agenticresourcediscovery.org/spec; upstream repo ards-project/ard-spec.

## How the fraction is computed

From `ReportUtils.calculateCategoryFraction`:

- Skip audits in the `hidden` group and audits whose mode is `manual` or
  `notApplicable`.
- Informative audits are never counted in N (they only raise a separate
  informative count).
- Every other audit adds 1 to N and passes when `score >= 0.9`. An `error`
  audit counts in N and fails.

The JSON field `categories["agentic-browsing"].score` is a weighted mean, not
the fraction. Report "X/N", never a percentage.

### Maximum N and what moves it

`webmcp-registered-tools` never counts, so N is at most 6. Typical values:

| Site state | Counted audits |
|---|---|
| No WebMCP, no llms.txt, no catalog | tree + CLS = **2** |
| + valid llms.txt | **3** |
| + imperative WebMCP tools | + schema validity = **4** |
| + every form annotated (`toolname`/`tooldescription`) | + form coverage = **5** (see note) |
| + valid `ai-catalog.json` | **6** |

Note: annotated forms register declarative tools. On a page with no
imperative tools, that also turns `webmcp-schema-validity` from N/A into a
counted audit, which scores 0.5 (a failure) if any parameter lacks a
description. Annotate fully or not at all.

Worked example, claude-seo.md on 2026-09-23 (PSI, mobile and desktop): 4
imperative tools registered, one form without annotations, no catalog. Result
**4/4** with 2 informative audits. When a run shows 5/5, form coverage was
counted, meaning every form on that page carried an annotation (or the
annotated form was the only one). Read `lighthouse_agentic.py` output rather
than guessing: it lists each audit's status and the "paths" that add a
counted audit.

## Reading results responsibly

- A higher N is not a better site. Adding a catalog or annotating forms only
  adds audits; do it when the resource or form is real and safe for agents.
- WebMCP audits depend on the testing browser. PSI supports WebMCP today; a
  local Chrome without the origin trial or flag marks them N/A.
- Imperative tool registration timing can vary between runs. Run twice
  before reporting a WebMCP regression.
- `llms-txt` passing says nothing about Google Search: Google ignores
  llms.txt (see `seo-geo`).

## Recheck triggers

- A new Lighthouse minor version (compare the category `auditRefs`).
- WebMCP leaving origin trial (the trial runs M149 to M156; no ship
  milestone is announced).
- Changes to the ARD schema pin (`third-party/ard/README.md` in Lighthouse).
