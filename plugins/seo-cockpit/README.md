# seo-cockpit

An optional mods companion for [claude-seo](../../README.md). It runs inside Claude Code as a mod (a function-hook plugin), so it can enforce things a skill can only ask for.

Tested on Claude Code 2.1.288. Mods need Claude Code 2.1.287 or newer; on older builds, install claude-seo alone.

## What it does (0.1.0)

**Spend guard.** Before a paid SEO API call runs, seo-cockpit checks it against the claude-seo DataForSEO budget (`scripts/dataforseo_costs.py`):

| The call | What happens |
|---|---|
| DataForSEO MCP tool or the Merchant script, budget says approved | Runs. Afterwards each billed endpoint is logged at its table price, and Claude is told not to log it again |
| DataForSEO, budget says needs approval (warn endpoint, unknown endpoint, above threshold) | You are asked, with the price and today's spend |
| DataForSEO, daily cap would be exceeded | Held. Claude gets the reason |
| Free DataForSEO lookups (locations, languages, filters, categories, model lists) | Run, with no check and nothing logged |
| Ahrefs, Firecrawl, image generation (MCP or script), Moz, Keywords Everywhere, Google Cloud NLP, Indexing API, and curl or WebFetch calls to SE Ranking, Profound or the DataForSEO API | You are asked: hold, run once, or allow until reload |
| Anything goes wrong (claude-seo not found, Python missing, unreadable ledger) | Held, with the fix in the message |

The guard fails closed: if it cannot check a paid call before it runs, the call does not run. A call that already ran keeps its real result.

Shell lines are checked one command at a time, so a cost check chained in front of a paid script does not hide it. The Merchant script is priced by what it bills: `search` (Google, or Amazon with `--marketplace amazon`), `sellers`, or `compare` (both).

What is logged: only calls that succeeded and have a price in the cost table. A failed call, or an endpoint with no listed price, is not logged; Claude is told to log the real cost from the response instead.

**Commands that cost no tokens.** These answer directly without starting a turn:

- `/seo-spend`: DataForSEO spend today, over 7 and 30 days, by endpoint, with a 30-day spark row.
- `/seo-doctor`: claude-seo runtime readiness, install location, and guard state.

## Install

```bash
/plugin marketplace add AgriciDaniel/claude-seo
/plugin install claude-seo@agricidaniel-claude-seo
/plugin install seo-cockpit@agricidaniel-claude-seo
```

Auto-update is off by default for third-party marketplaces. Run `claude plugin update seo-cockpit@agricidaniel-claude-seo` to update.

## Settings (`/config`)

| Setting | Default | Meaning |
|---|---|---|
| claude-seo folder | empty | Where claude-seo lives. When empty, it looks next to this plugin (a checkout) and in the plugin cache (an install) |
| Python command | `python3` | Runs the stdlib-only ledger scripts |
| Spend guard | on | Turn off to let paid calls through unchecked |

## What it can and cannot see

- It reads no credentials and no environment variables. The Python scripts handle auth.
- It runs only `dataforseo_costs.py` and `runtime.py` from your claude-seo folder.
- Spend is checked for DataForSEO only. Other providers have no cost table, so you decide.
- "Allow until reload" is forgotten when the plugin reloads (a restart, or a change in `/config`), after which it asks again.

## Known limits

- **It matches what it can see.** A paid API reached by some route it does not recognise (a new script, an unknown host, a custom MCP server name) is not held.
- **Parallel calls can overshoot the cap a little.** Each call is checked against the ledger before the others are logged, so several approved calls made at once can together pass the daily cap.
- **`claude -p` and headless runs:** there is no one to ask, so every call that needs approval is held. Calls the budget approves still run.
- **CLI only:** it needs `$.process` to run the ledger script. Where that is missing, DataForSEO calls are held and the commands report an error.
- **Ask before rules:** a call your permission rules would deny can still raise its cost question first.

## Status

The kit tests in `tests/` are written against the Claude Code 2.1.288 typings but have not yet been executed: mods are switched off remotely for the maintainer's account (`claude plugin test` refuses to run). Verified on 2026-10-03:

- type-check (`tsc`, strict)
- `claude plugin validate --strict`
- the brain's static scan (reach L2, no critical or high flags)
- 34 end-to-end scenarios run through a stand-in for the hook chain against the real claude-seo scripts and an isolated ledger

## Development

```bash
# Type-check against the typings Claude Code writes beside the plugin on load
npx -p typescript@5.9 tsc -p plugins/seo-cockpit
claude plugin validate plugins/seo-cockpit --strict
claude plugin test plugins/seo-cockpit
```

Layout: `hooks/register.ts` is the only file that calls `on()`. The rules live in `hooks/lib/` (pure, no `$`), and the tests are in `tests/`.

## Roadmap

- 0.2.0: an audit progress band (agents running and done, findings written, spend), a receipt when an audit finishes, an economy mode that routes the Opus agents to Sonnet, and compaction that keeps audit state.
- 0.3.0: a visual cockpit pane covering Search Console, rankings and trends, Core Web Vitals, the audit scorecard, the Maps geo-grid, and spend. Charts draw in the terminal and on desktop, with an HTML export for VS Code.
