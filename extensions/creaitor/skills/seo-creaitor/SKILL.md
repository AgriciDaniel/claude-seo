---
name: seo-creaitor
description: Creaitor GEO analyst (extension). Reads AI-search visibility, LLM citations, cited sources, tracked prompts, audits, recommendations, competitors, and health scores for a domain configured in Creaitor, via the Creaitor remote MCP server.
metadata:
  version: "2.2.5"
  original_author: "Creaitor (creaitor.ai)"
compatibility: "Requires the creaitor-geo remote MCP server in ~/.claude.json (run extensions/creaitor/install.sh or install.ps1) and a Creaitor personal access token. Read commands need the geo:read ability; mutations need geo:write; runs need geo:execute."
---

# seo-creaitor

Creaitor tracks how a domain performs in AI answers: which prompts surface it,
which LLMs cite it, which sources they cite instead, and what to fix. This skill
reads that data live through the `creaitor-geo` remote MCP server
(`https://app.creaitor.ai/api/v2/mcp`).

Unlike `seo-geo`, which infers citability from the page itself, Creaitor reports
observed citations for prompts you already track. Use both: `seo-geo` for why a
page should be cited, `seo-creaitor` for whether it actually is.

## Prerequisites

- Run `extensions/creaitor/install.sh` (macOS/Linux) or `install.ps1` (Windows).
- A Creaitor personal access token from https://app.creaitor.ai/user/api-tokens
  with the abilities the command needs (`geo:read`, `geo:write`, `geo:execute`).
- The domain must already exist in the Creaitor workspace the token belongs to.
  This skill never creates domains.

Before the first tool call in a session, confirm a Creaitor MCP tool (for
example `list_domains`) is available. If none are, stop and tell the user the
extension is not installed, with the install command above. Do not fall back to
scraping app.creaitor.ai.

## Domain resolution

Every command except `/seo creaitor domains` takes a URL and must resolve it to
a configured Creaitor domain before anything else:

1. Call `list_domains` (read-only, free).
2. Normalize the user's URL and every configured domain the same way: lowercase,
   drop the scheme, drop a leading `www.`, drop the default port, drop any path,
   query, and fragment, drop a trailing slash.
3. Match on the normalized host. Reuse the resolved `domain_id` for the rest of
   the session instead of calling `list_domains` again.
4. **No match: stop.** Report the URL as given and list the domains returned.
   The MCP tool returns at most the 25 newest domains, so do not claim the
   domain is absent from the workspace. Ask the user to verify or add it in the
   Creaitor app. Never guess the closest domain, substitute an apex for a
   subdomain, or call an execute-tier command with an unresolved domain.
5. Ambiguous match (several configured domains normalize to the same host): ask
   which one, do not pick.

Subdomains are distinct domains. `blog.example.com` matches a configured
`blog.example.com`, not a configured `example.com`.

## Routing

| Command | Creaitor MCP tools | Ability |
|---|---|---|
| `/seo creaitor domains` | `list_domains` | `geo:read` |
| `/seo creaitor overview <url>` | `get_health_score`, `get_analytics`, `list_recommendations` | `geo:read` |
| `/seo creaitor visibility <url>` | `get_analytics`, `list_queries`, then `get_results` per query | `geo:read` |
| `/seo creaitor citations <url>` | `get_citations` | `geo:read` |
| `/seo creaitor citations <url> --export` | `export_citations` | `geo:execute` |
| `/seo creaitor sources <url>` | `get_sources` | `geo:read` |
| `/seo creaitor prompts <url>` | `list_queries` | `geo:read` |
| `/seo creaitor prompts <url> --add "<prompt>" --topic <topic-id>` | `create_query` | `geo:write` |
| `/seo creaitor prompts <url> --edit <query-id>` | `update_query` | `geo:write` |
| `/seo creaitor prompts <url> --run <query-id>` | `run_query` | `geo:execute` |
| `/seo creaitor audit <url>` | `list_audits`, `get_audit` | `geo:read` |
| `/seo creaitor audit <url> --run` | `run_audit`, then `get_audit` | `geo:execute` |
| `/seo creaitor recommendations <url>` | `list_recommendations` | `geo:read` |
| `/seo creaitor recommendations <url> --set <id> <status>` | `update_recommendation` | `geo:write` |
| `/seo creaitor competitors <url>` | `list_competitors` | `geo:read` |
| `/seo creaitor health <url>` | `get_health_score` | `geo:read` |
| `/seo creaitor llms-txt <url>` | `generate_llms_txt` (queues generation; retrieve content in Creaitor) | `geo:execute` |

Bare `/seo creaitor <url>` (no command) runs `overview`.

## Execution rules

**Read commands never trigger a run.** `overview`, `visibility`, `citations`,
`sources`, `prompts`, `recommendations`, `competitors`, `health`, and
`audit` (without `--run`) call read tools only. If the stored data is empty or
stale, say so and offer the matching execute command — do not run it to fill the
gap.

**Execute-tier tools run only when explicitly invoked.** `run_audit`,
`run_query`, and `generate_llms_txt` consume workspace quota; `export_citations`
is also gated by `geo:execute`. Call them only for the corresponding explicit
`--run`, `llms-txt`, or `--export` command. Never call them as a follow-up to a
read command, as part of `/seo audit`, or to refresh data autonomously.

`create_query` requires a real `topic_id`. Require `--topic <topic-id>` and pass
it unchanged. Existing query records may expose their topic ID; if none do,
tell the user to create or select the topic in Creaitor first. Never invent an
ID.

`generate_llms_txt` returns only a queued generation ID over MCP. Report that
honestly and direct the user to Creaitor for completion and content; do not poll
a non-existent MCP status tool.

**Writes are confirmed.** Before `create_query`, `update_query`, or
`update_recommendation`, echo the exact change and get a yes.

**Missing ability.** The MCP server returns JSON-RPC error `-32001` when the
token lacks an ability. Report which ability is missing (`geo:read` /
`geo:write` / `geo:execute`) and point at
https://app.creaitor.ai/user/api-tokens to mint a replacement, then re-run the
installer to store it.

## Output conventions

- Cite Creaitor on every live figure, with the retrieval time and the filters
  that produced it: `Creaitor (live, 2026-09-01T14:03Z, domain=example.com,
  period=last-30d, models=ChatGPT+Perplexity)`. State the timestamp in UTC.
- Name the period and model/platform filter you used, including when you used
  the API default — an unqualified "12% citation rate" is not reportable.
- Report the audit's own `completed_at` (not the current time) when summarizing
  a stored audit, and flag audits older than 30 days as stale.
- Distinguish "0 citations observed" from "prompt not tracked" and from "no run
  yet". They imply different fixes.
- When Creaitor and another source disagree (`seo-dataforseo` AI mentions,
  `seo-profound`, `seo-seranking`), report both with their timestamps rather
  than averaging: they sample different prompt sets at different times.

## Cross-skill delegation

- Page-level citability, AI crawler access, and passage structure: `seo-geo`.
- Fixing pages a recommendation points at: `seo-content` for E-E-A-T and
  passage rewriting, `seo-schema` for markup gaps, `seo-technical` for crawl or
  render blockers keeping a cited page out of AI answers.
- Competitor domains that Creaitor reports as cited instead of yours: hand the
  URLs to `seo-backlinks` or `seo-cluster` for gap analysis.
- Broader LLM citation time-series across more platforms: `seo-profound` and
  `seo-seranking`.

## Docs

Setup, token rotation, and troubleshooting:
`extensions/creaitor/docs/CREAITOR-SETUP.md`.
