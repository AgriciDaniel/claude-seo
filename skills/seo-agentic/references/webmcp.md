# WebMCP: status, API, consumers and safety

WebMCP lets a page register tools (name, description, JSON Schema input,
handler) that an in-browser agent can call instead of driving the UI. Treat it
as a **progressive enhancement**: useful for sites with forms or
transactions, never a replacement for a sound accessibility tree. Facts
checked 2026-09-23.

## Standards status

| Item | Status |
|---|---|
| Spec | W3C Web Machine Learning Community Group draft ("not a W3C Standard nor on the Standards Track"); last spec commit 2026-09-17. Editors from Microsoft and Google. |
| Chrome | Origin trial M149 to M156 (chromestatus 5117755740913664); dev flag `chrome://flags/#enable-webmcp-testing`. M157 is a target, not a commitment. |
| Edge | Testing in Canary/Dev; origin trial; MicrosoftEdge/webmcp-labs samples and WebMCP Explorer. No evidence Copilot consumes tools. |
| WebKit | Position `oppose` (standards-positions #670): prefers the accessibility tree over a parallel tool layer. Exact dates and quotes come from secondary trackers. |
| Mozilla | Position `neutral` (#1412): interest in the imperative API, not the declarative one. |

## Who calls WebMCP tools today

| Consumer | Imperative | Declarative | Notes |
|---|---|---|---|
| ChatGPT desktop built-in browser ("site tools") | yes | **no** | On by default; top-level document only (no iframes); not in Enterprise/Edu; confirmation policies still apply. Docs: learn.chatgpt.com/docs/webmcp |
| Chrome / Edge (origin trial or flag) | yes | yes | What Lighthouse and PSI see |
| Brave Leo | experimental | ? | Nightly behind a flag |
| Gemini in Chrome, Claude for Chrome, Perplexity Comet | no public signal | no | Rely on page text, DOM, screenshots and the accessibility tree |

## API surface (spec draft)

- Entry point: **`document.modelContext`** (secure contexts). Older engines and
  some tools used `navigator.modelContext`; feature-detect both, preferring
  `document`. Lighthouse detects either.
- `registerTool(tool, { exposedTo, signal })` returns a Promise. There is no
  `unregisterTool`: pass an `AbortSignal` and abort it.
- Also `getTools()`, `executeTool()`, and the events `toolchange`,
  `toolactivated`, `toolcancel`.
- Tool fields: `name` (required), `title`, `description` (required),
  `inputSchema`, `execute(input, { signal })` (required), `annotations`.
- Annotations: `readOnlyHint`, `untrustedContentHint`, `consequentialHint`,
  `debugging` (all default false).
- Permissions policy feature `tools` (default `'self'`): a cross-origin iframe
  needs `allow="tools"`; `Permissions-Policy: tools=()` disables it.

Declarative (explainer; the spec section is still TODO, Chrome only):
`toolname`, `tooldescription` and `toolautosubmit` on `<form>`,
`toolparamdescription` on controls; parameter names come from each control's
`name`. `SubmitEvent.agentInvoked` (boolean) and `respondWith(Promise)` let the
page tell agent submissions apart. CSS: `:tool-form-active`,
`:tool-submit-active`.

## Imperative pattern that works in Chrome and ChatGPT desktop

```html
<meta http-equiv="origin-trial" content="YOUR_CHROME_OT_TOKEN">
<script type="module">
const mc = document.modelContext ?? navigator.modelContext; // navigator: legacy
if (mc?.registerTool) {
  const controller = new AbortController();
  await mc.registerTool({
    name: "search_articles",
    description: "Search published articles by keyword. Returns titles and URLs.",
    inputSchema: {
      type: "object",
      properties: { query: { type: "string", description: "Keywords to search" } },
      required: ["query"]
    },
    annotations: { readOnlyHint: true },
    async execute({ query }) {
      const r = await fetch(`/api/search?q=${encodeURIComponent(query)}`); // same endpoint as the UI
      return { content: [{ type: "text", text: JSON.stringify(await r.json()) }] };
    }
  }, { signal: controller.signal });
}
</script>
```

The origin-trial `<meta>` token enables the API for ordinary Chrome visitors
during the trial; ChatGPT desktop and PSI do not need it. The return shape
above follows the MCP content convention used in current samples; confirm it against the Chrome WebMCP docs before shipping.
`agentic_fix.py webmcp <url>` drafts one tool per real form, bound to the
form's own submit handler.

## Safety rules for exposed tools

1. Bind every tool to the same code path as the UI action (same endpoint,
   same validation, same authorization). Never add a privileged back door.
2. Mark purchases, sends and deletes `consequentialHint: true` **and** keep a
   human confirmation step. The hint does not replace it.
3. Mark tools that return user- or third-party-supplied text
   `untrustedContentHint: true`. Hidden instructions to agents are Mozilla's
   core concern.
4. Keep consequential tools out of cross-origin iframes; never wildcard
   `exposedTo`.
5. Log `SubmitEvent.agentInvoked` and tool calls server-side; rate-limit them.
6. Session-bound tools run with the user's real privileges (OpenAI's cloud
   browser can keep a signed-in session). Scope them accordingly.
7. For API or MCP access use OAuth (RFC 9728 metadata), not session scraping.

## Audit posture

- Absence of WebMCP is an opportunity, not a defect.
- Recommend imperative tools only where a form or transaction exists (P2, or
  P1 for transactional sites); declarative attributes are P3 (Chrome only).
- Label every WebMCP item "W3C CG draft" with the check date.
- Never cite "token efficiency" percentages for WebMCP: the widely repeated
  figures trace to marketing posts, not benchmarks.

## Verification tools

- `lighthouse_agentic.py` (PSI) lists registered tools and schema issues.
- Vercel `agent-browser webmcp list` / `webmcp invoke` (WebMCP on by default).
- GoogleChromeLabs/webmcp-tools and the Model Context Tool Inspector;
  MicrosoftEdge/webmcp-labs WebMCP Explorer.
- Lightpanda still exposes only `navigator.modelContext`, so spec-following
  pages are invisible to it.
