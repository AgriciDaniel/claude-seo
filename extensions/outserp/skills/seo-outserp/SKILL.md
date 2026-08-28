---
name: seo-outserp
description: >
  Outserp AI answer-engine visibility analyst + content engine (extension).
  Audits how a domain actually appears in ChatGPT and Perplexity answers,
  tracks citations/mentions over time, scans template defects and SEO drift,
  and can generate, optimize, and publish articles through the Outserp
  platform. Pairs with seo-profound and seo-seranking for triangulated
  AI visibility coverage.
user-invocable: true
argument-hint: "[command] <domain|brand>"
license: MIT
compatibility: "Requires the Outserp MCP server (https://mcp.outserp.ai/mcp, OAuth) or an OUTSERP_API_KEY for the REST fallback."
metadata:
  version: "2.2.5"
  category: seo
  original_author: Meddicle (Outserp — https://outserp.ai; vendor-contributed, disclosed)
---

# seo-outserp

Outserp measures what AI answer engines actually say — it queries live
ChatGPT / Perplexity answers for buyer-intent prompts, counts brand vs.
competitor appearances head-to-head, and tracks the deltas over time.
It also carries a production path (generate → optimize → publish) so a
gap found in an audit can be closed from the same session.

This is the piece claude-seo's local analysis deliberately delegates to
vendors: `seo-geo` scores *citability* of your pages; Outserp reports
*actual citations and answers* from the engines, as a time-series, like
the Profound and SE Ranking extensions do — plus the write path.

Disclosure: this extension is contributed by the Outserp team. Outserp is
a commercial platform; audits and generation spend account credits.

## Prerequisites

- Run `extensions/outserp/install.sh` (or `install.ps1`).
- An Outserp account (https://outserp.ai). The MCP server authenticates
  via OAuth: after install, run `/mcp` in Claude Code and complete the
  browser flow for `outserp`.
- **Check availability:** before any call, verify an Outserp MCP tool
  (e.g. `whoami`) is available. If not, tell the user the extension is
  not installed / not authenticated and point to
  `extensions/outserp/docs/OUTSERP-SETUP.md`.
- REST fallback: if the MCP server is unreachable but
  `~/.claude/settings.json` has `env.OUTSERP_API_KEY`, call the REST API
  (docs: https://outserp.ai/api-docs) with base URL
  `https://outserp.ai/api/v1`. Tool paths are relative to that base —
  never duplicate `/api/v1` in the path (`/api/v1/audit`, not
  `/api/v1/api/v1/audit`).

## Routing

| Command | Purpose |
|---|---|
| `/seo outserp whoami` | Account, plan, credit balance, projects |
| `/seo outserp audit <domain>` | AI-search visibility audit: real ChatGPT/Perplexity answers, head-to-head competitor counts, gaps, content briefs |
| `/seo outserp visibility <brand>` | Visibility summary: mention rate per engine + trend |
| `/seo outserp citations <brand>` | URLs the engines actually cite for the brand's prompt set |
| `/seo outserp mentions <brand>` | Raw brand/competitor mentions across tracked prompts |
| `/seo outserp defects <domain>` | Template-defect scanner + SEO drift findings |
| `/seo outserp context [update <note>]` | Shared project memory + research log (read or append) |
| `/seo outserp write <keyword>` | Generate a full article draft for a keyword |
| `/seo outserp optimize <article>` | Re-optimize an existing article against its scoring rubric |
| `/seo outserp publish <article>` | Publish an article to the connected CMS |

## Commands

### whoami — account + credits

**MCP tool:** `whoami`. Always call this first in a session: it confirms
authentication, returns the credit balance, and lists the projects the
account can operate on. If it fails, stop and route the user to setup.

### audit — AI-search visibility audit

**MCP tool:** `run_audit` (domain, optional competitor list).

Runs Outserp's audit of any domain: it asks the engines real buyer-intent
questions, records the full answers, counts how often the domain vs. each
competitor appears (head-to-head), and returns the gaps with suggested
content briefs. Credit-metered — confirm with the user before running,
and report the spend from `whoami` afterwards.

### visibility / citations / mentions — measurement over time

**MCP tools:** `get_visibility_summary`, `get_citations`, `get_mentions`.

- `get_visibility_summary`: mention rate per engine with trend deltas.
- `get_citations`: the exact URLs the engines cite for the tracked
  prompt set — use it to find pages worth pitching or emulating.
- `get_mentions`: raw mention rows (brand + competitors, per prompt,
  per engine) when the summary is too coarse.

### defects — template-defect scanner + drift

**MCP tool:** `get_template_defects`. Site-wide defects that repeat
across a page template (missing BLUF, broken schema, thin sections) plus
SEO drift since the last scan. For local, git-style baselines prefer
`/seo drift`; use this for the hosted, scheduled view.

### context — shared project memory

**MCP tools:** `get_project_context`, `update_project_context`.

Outserp projects keep a shared memory + research log that its own agents
read. Read it at the start of a working session; append durable findings
(audit conclusions, decisions) so they persist across sessions and tools.

### write / optimize / publish — the production path

**MCP tools:** `generate_article`, `optimize_article`, `publish_article`.

Closes the loop on audit gaps: generate a scored draft for a target
keyword, re-optimize an underperforming article, and publish to the CMS
connected in Outserp. Generation and publishing spend credits and create
public content — always show the user what will be produced/published
and get an explicit go-ahead before `publish_article`.

## Cost guardrails

- Audits, generation, optimization, and publishing spend account
  credits; read-only calls (`whoami`, summaries, citations, mentions,
  context) are cheap or free.
- Call `whoami` first, report the balance, and confirm before any
  credit-spending call. Report the new balance after.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|-----------|
| Outserp tools not listed | MCP not installed / not connected | Run `./extensions/outserp/install.sh`, restart Claude Code |
| `401 Unauthorized` | OAuth not completed or API key invalid | Run `/mcp` and authenticate `outserp`; or re-set `OUTSERP_API_KEY` |
| `402` / insufficient credits | Credit balance exhausted | Check `whoami`, top up at https://outserp.ai |
| `404 Not Found` on REST calls | `/api/v1` duplicated in the path | Base URL is `https://outserp.ai/api/v1`; paths must not repeat it |
| `429 Too Many Requests` | Rate limited | Wait 60s, batch fewer prompts per call |
| Audit returns no competitor data | No competitors configured | Pass a competitor list to `run_audit` or set them in the project |

**Graceful fallback:** if Outserp is unavailable, `seo-geo` covers
on-page citability locally, and `seo-profound` / `seo-seranking` cover
citation tracking via their vendors.

## Output conventions

- Cite Outserp on every metric: "Outserp (live)". Audit numbers come
  from real engine answers at query time, so note the sample date.
- Visibility rates are percentages of sampled prompts; include the
  prompt count so the confidence is legible.

## Cross-skill delegation

- For on-page citability scoring and platform-specific GEO tuning of the
  pages Outserp flags, hand to `seo-geo`.
- For time-series LLM citation triangulation, cross-check with
  `seo-profound` (ChatGPT/Perplexity) and `seo-seranking` (adds Gemini,
  AI Overviews, AI Mode).
- For local, no-account drift baselines, use `seo-drift`.
- For E-E-A-T review of drafts before `publish_article`, run
  `seo-content`.
