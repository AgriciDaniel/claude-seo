# Agent vendor matrix (dated, source-graded)

Fast-moving facts live here and nowhere else in this skill. Each row carries a
source grade: **P** = primary (vendor docs, spec, source code), **S** =
secondary only, **C** = conflicting sources. Last full check: **2026-09-23**.
Refresh before quoting any row older than 60 days (see "Refresh procedure").

## What each agent reads and whether it calls WebMCP

| Vendor / product | Reads | WebMCP | Identity | Grade |
|---|---|---|---|---|
| OpenAI: ChatGPT desktop built-in browser ("site tools") | ARIA / accessibility tree (publisher FAQ) | **Yes, imperative only**, top-level document, on by default, not Enterprise/Edu | ChatGPT-User; signs agent and cloud-browser traffic with Web Bot Auth | P |
| OpenAI: cloud browser (ChatGPT Work), Codex | as above | not documented | Web Bot Auth | S |
| Google: Gemini in Chrome, Chrome auto browse | page elements and screen positions | no public evidence of consumption; Google co-edits the spec | Google-Agent (user-triggered, generally ignores robots.txt); experimenting with Web Bot Auth as `https://agent.bot.goog` | P (identity), S (reading) |
| Microsoft: Edge, Copilot Mode | not documented | Edge supports WebMCP for testing; no evidence Copilot consumes tools | not researched | P (Edge), S (Copilot) |
| Anthropic: Claude in Chrome (Claude Code, Cowork, Desktop), computer use | page text, DOM, console and network, screenshots | none (public issue reports discovery missing) | ClaudeBot, Claude-SearchBot, Claude-User; all honour robots.txt; IPs at claude.com/crawling/bots.json | P (bots), S (reading) |
| Perplexity: Comet | accessibility tree and screenshots | no public signal | PerplexityBot honours robots.txt; Perplexity-User generally does not | P (bots), S (reading) |
| Brave: Leo | not documented | experimental, Nightly behind `brave://flags/#enable-webmcp-testing` | not verified | S |
| Opera Neon, Dia, Sigma, Fellou | not documented | no public signal | not verified | S |
| Apple: Safari / WebKit | n/a | **opposes** (agents are closer to assistive tech; sites should not detect them) | n/a | P (label), S (quotes) |
| Mozilla: Firefox | n/a | neutral; not implementing | n/a | P |

Two gaps to state plainly in reports: no primary source shows any consumer
agent sending `Accept: text/markdown`, and robots.txt behaviour for Dia,
Opera and Comet agent actions is unverified.

## Product status notes

| Item | Status | Grade |
|---|---|---|
| ChatGPT Atlas browser | reported stopped 2026-08-09; ChatGPT agent removed early Aug 2026 | S |
| ChatGPT Instant Checkout | reported moved to Apps in 2026-03 | S |
| Project Mariner | reported shut down 2026-05-04 | S |
| Chrome WebMCP origin trial | M149 to M156; M157 targeted, not committed | P (range), S (end date 2026-11-17) |
| Lighthouse | 13.5.0 (npm latest, 2026-09-18); PSI runs 13.5.0 | P |
| Web Bot Auth | `draft-ietf-webbotauth-httpsig-protocol-00` (2026-09-01); `Signature-Agent` dictionary form | P |
| Content-Signal | Cloudflare CC0 policy; IETF individual draft expired 2026-04-04; Google does not act on it | P |
| MCP Server Card | SEP-2127 open and unmerged (updated 2026-09-12) | P |

## Evidence of impact (flag vendor numbers)

- Cloudflare's token-reduction figures for Markdown are vendor-sourced.
- "Token efficiency" percentages for WebMCP come from marketing posts with no
  traceable benchmark. Do not cite them.
- Agent benchmarks such as WebArena measure models, not site quality.
- No controlled public study links accessibility-tree quality or WebMCP to
  agent task success. Treat such claims as hypotheses.

## Contested or unverified (do not quote without rechecking)

- Exact WebKit and Mozilla position dates and the WebKit quotes (secondary
  trackers, one written by an automated agent). Check the GitHub timeline.
- A WebKit suggestion of a new working group or TPAC workshop (vendor tracker
  paraphrase only).
- Anthropic and Perplexity Web Bot Auth signing (secondary only).
- Cloudflare verification of the dictionary-form `Signature-Agent` (reported
  mismatch, not tested).
- Whether Content-Signal is scoped per robots.txt group (no normative text).
- ChatGPT site-tools model requirements (vendor pages disagreed).

## Refresh procedure

1. PSI: run `lighthouse_agentic.py https://claude-seo.md/ --json`. If
   `lighthouse_version` changed, diff the category `auditRefs` against
   `references/lighthouse-agentic-category.md`.
2. Lighthouse source: `npm view lighthouse version`, then read
   `core/config/default-config.js` and `core/audits/agentic/` for the new tag.
3. WebMCP: the spec's last commit (webmachinelearning/webmcp), chromestatus
   feature 5117755740913664, learn.chatgpt.com/docs/webmcp.
4. Bots: developers.openai.com/api/docs/bots, support.claude.com crawler
   article, docs.perplexity.ai/guides/bots, Google's user-triggered fetchers
   page.
5. Drafts: datatracker.ietf.org for webbotauth and aipref.
6. Update the dates here and the `CHECKED_ON` constant in
   `agentic_check.py` in the same change.
