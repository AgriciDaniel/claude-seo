# seo-cockpit

An optional mods companion for [claude-seo](../../README.md). It runs inside Claude Code as a mod (a function-hook plugin), so it can enforce things a skill can only ask for.

Tested on Claude Code 2.1.288 and 2.1.289. Mods need Claude Code 2.1.287 or newer; on older builds, install claude-seo alone.

## What it does (0.3.0)

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

**Audit band.** While a `/seo audit` runs, a line above the prompt shows it live:

```
seo audit example.com  3 running, 9 done  findings 9  spend $0.42  4m12s
```

It starts from the `/seo audit <url>` prompt or command, or from the first file written into a `<domain>-audit/` folder (so an audit asked for in plain words is caught too). Agents count as running when spawned and done when they finish (a background agent when its own turn ends). Other mods' bands stay visible below this one. A reload mid-audit keeps the band. Spend is what the guard logged during the audit. The band yields to Claude Code's surveys, has a hide button, and clears at your next prompt after the audit ends.

**Receipt.** When the audit writes `audit-data.json`, one line appears under Claude's answer:

```
seo audit example.com: score 72/100  |  weakest Schema 40, Content 55  |  17 agents  |  12 findings files  |  spend $0.42  |  6m03s  |  example.com-audit/FULL-AUDIT-REPORT.md
```

**Economy mode** (off by default). Runs the five agents that use Opus (content, geo, sxo, cluster, drift) on Sonnet, to cut the cost of an audit. Their analysis may be less thorough. An agent call that names its own model is left alone.

**Compaction.** If the conversation is compacted mid-audit, the summary is asked to keep the output folder, which agents finished and which are running, and the findings files written.

**Visual cockpit** (`/seo-cockpit`). Opens on one Overview for the site this folder is about, with no setup:

```
claude-seo.md  from this folder
1: ● Audit     85/100 · weakest Schema 76
2: ● Vitals    good · LCP 703ms · INP 48ms · CLS 0.00
3: ○ Search    no Search Console access
4: ○ Rankings  no Search Console access
5: ○ Maps      no grid yet (/seo maps grid)
6: ● Spend     today $0.00 · 30 days $0.18
r: Refresh  e: Export
```

- **The site**, most specific first: one you chose in this folder (typed in the pane, or `/seo-cockpit <site>`), the site of this folder's newest `<domain>-audit/`, your **Default site** from `/config`, then the last site you used. Set a Default site once and the cockpit opens on it from any folder; the Audit row finds that site's audit wherever it was last seen.
- **Google access** uses claude-seo's own setup, or the two Google settings in `/config`. If Search Console says "no access" for a property you own, a service account is being used: set "Google account" to `gcloud` after `gcloud auth application-default login --scopes=https://www.googleapis.com/auth/webmasters.readonly,https://www.googleapis.com/auth/cloud-platform`. Core Web Vitals needs a Google API key ("Google API key" in `/config`).
- **Where it sits:** in a normal terminal the pane opens above the prompt and asks for as many rows as the screen can spare (drag it to resize; your size is kept). In Claude Code's fullscreen layout, 110 columns or wider, it docks beside the conversation at full height.
- **Everything loads on open**, from free sources only (the audit and grid files, the cost ledger, and Search Console and CrUX through claude-seo's own Google setup). The last result shows at once and is replaced when the fresh one arrives.
- **Missing data stays visible** as a dim line saying what to do, instead of an error screen.
- **A row opens its detail** (Enter, a click, or its number): charts and tables for that source, `b` to go back.
- **Keys** work while the pane has focus; otherwise the footer says `ctrl+x tab`. `r` refreshes everything, `e` exports HTML. Esc or Claude Code's own close mark closes the pane, and `/seo-cockpit` again toggles it.
- **A status line** under the prompt keeps the summary in view: `SEO · claude-seo.md · audit 85/100 · CWV good`.

Charts are drawn with block characters in the terminal and as SVG on the desktop app. Every view names its source and when it was fetched.

**HTML dashboard.** `e` in the pane, or `/seo-cockpit export`, writes one self-contained page (`seo-cockpit-<time>.html` in the working folder) with every view as SVG charts and tables, readable in light and dark. Where no pane can be drawn (the VS Code chat panel), `/seo-cockpit` writes this page instead and says where it is.

**Commands that cost no tokens.** These answer directly without starting a turn:

- `/seo-spend`: DataForSEO spend today, over 7 and 30 days, by endpoint, with a 30-day spark row.
- `/seo-doctor`: claude-seo runtime readiness, install location, and guard state.
- `/seo-cockpit [site | export]`: the visual cockpit (for a given site, remembered), or with `export` the HTML dashboard.

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
| Audit band | on | The live line above the prompt during an audit |
| Economy mode | off | Run the five Opus agents on Sonnet |
| Default site | empty | The site the cockpit opens on when a folder shows none (`claude-seo.md`, `sc-domain:claude-seo.md` or `https://claude-seo.md/`). A site chosen in a folder, or its audit, comes first |
| Page for Core Web Vitals | empty | For the Vitals and drift views. Empty uses the property's site |
| Audits folder | empty | Where you keep your `<site>-audit/` folders. The cockpit finds the shown site's audit there from any folder |
| Google account | auto | `auto`: claude-seo's own order (its sign-in, a service account, then your gcloud account). `gcloud`: always your own account from `gcloud auth application-default login`, for properties you own |
| Google API key | empty | For Core Web Vitals (CrUX). Sensitive: kept in Claude Code's secure storage. Empty uses claude-seo's own setup |

## What it can and cannot see

- It reads no credentials and no environment variables. The Python scripts handle auth.
- It runs only `dataforseo_costs.py` and `runtime.py` from your claude-seo folder; the cockpit runs `gsc_query.py`, `crux_history.py` and `drift_history.py` through `runtime.py`, so they use claude-seo's own Google setup.
- It writes one kind of file: the HTML dashboard, in the working folder, when you ask for it.
- Spend is checked for DataForSEO only. Other providers have no cost table, so you decide.
- "Allow until reload" is forgotten when the plugin reloads (a restart, or a change in `/config`), after which it asks again.

## Known limits

- **It matches what it can see.** A paid API reached by some route it does not recognise (a new script, an unknown host, a custom MCP server name) is not held.
- **Parallel calls can overshoot the cap a little.** Each call is checked against the ledger before the others are logged, so several approved calls made at once can together pass the daily cap.
- **`claude -p` and headless runs:** there is no one to ask, so every call that needs approval is held. Calls the budget approves still run.
- **CLI only:** it needs `$.process` to run the ledger script. Where that is missing, DataForSEO calls are held and the commands report an error.
- **Ask before rules:** a call your permission rules would deny can still raise its cost question first.
- **The band and the pane draw in the terminal and the desktop app,** not in the VS Code chat panel or `claude -p`. The receipt line is plain text and shows wherever the answer does; the cockpit falls back to the HTML dashboard.
- **The Maps view needs a saved grid.** Grids from before this release were only drawn in the chat; run the scan again to save one.

## Status

Verified on Claude Code 2.1.289, 2026-10-04:

- `claude plugin test`: 85 of 85 kit tests pass (spend guard, Google settings, commands, audit band and receipt, economy mode, compaction, the cockpit Overview and details, site choice, export, and the pure logic)
- type-check (`tsc`, strict) and `claude plugin validate --strict`
- a static security scan (reach L2, no critical or high flags)
- live in Claude Code on a real site: the cockpit inline and docked, every Overview row with live CrUX and Search Console data, `/seo-spend` and `/seo-doctor`
- the HTML export rendered in Chromium, light and dark

Not yet observed live: the audit band during a running `/seo audit` (covered by kit tests).

## Development

```bash
# Type-check against the typings Claude Code writes beside the plugin on load
npx -p typescript@5.9 tsc -p plugins/seo-cockpit
claude plugin validate plugins/seo-cockpit --strict
claude plugin test plugins/seo-cockpit
```

Layout: `hooks/register.ts` is the only file that calls `on()`. The rules live in `hooks/lib/` (pure, no `$`), and the tests are in `tests/`.
