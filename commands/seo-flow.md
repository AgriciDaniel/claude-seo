---
description: FLOW framework for evidence-led SEO strategy. Executes staged Find-Leverage-Optimize-Win prompts with search-and-conversion output.
agent: general
---
The user ran /seo-flow with argument: $ARGUMENTS

Execute the FLOW framework for evidence-led SEO strategy.

---

# FLOW Framework — Find · Leverage · Optimize · Win

> Framework and prompts © Daniel Agrici, CC BY 4.0 — github.com/AgriciDaniel/flow

FLOW is an evidence-led SEO operating model built for the AI-search era. Claude SEO
integrates the FLOW prompt library (41 prompts across 5 stages) so every analysis can
be driven by structured, evidence-backed AI prompts rather than improvised queries.

**Runtime context:** Load `~/.config/opencode/seo-skills/seo-flow/references/flow-framework.md` on every `/seo flow` activation.
Load prompt files on demand — only for the stage the user requests.

---

## Commands

| Command | What it does |
|---------|-------------|
| `/seo flow` | Show FLOW overview + stage menu |
| `/seo flow find [url\|topic]` | Find-stage: keyword research, gap analysis, SERP intent mapping (5 prompts) |
| `/seo flow leverage [url]` | Leverage-stage: backlink strategy, off-site authority (1 prompt) |
| `/seo flow optimize [url]` | Optimize-stage: select 2-3 most relevant of 21 prompts based on context |
| `/seo flow win [url]` | Win-stage: BOFU, conversion rate, dual-surface scorecard (3 prompts) |
| `/seo flow local [url]` | Local-stage: GBP optimization, meta, title tags, local audits (11 prompts) |
| `/seo flow prompts` | Full index of all 41 prompts — stage, name, trigger conditions |
| `/seo flow sync` | Pull latest prompt files from github.com/AgriciDaniel/flow |

---

## Orchestration Logic

### On `/seo flow` (no sub-command)
1. Read `~/.config/opencode/seo-skills/seo-flow/references/flow-framework.md`
2. Show the FLOW stage overview with a one-line description of each stage
3. Ask: which stage matches the user's current situation?

### On `/seo flow find [url|topic]`
1. Read all files in `~/.config/opencode/seo-skills/seo-flow/references/prompts/find/`
2. Apply each prompt to the URL or topic
3. Cross-reference: "For deeper SERP clustering, see `/seo cluster <seed-keyword>`"

### On `/seo flow leverage [url]`
1. Read the file in `~/.config/opencode/seo-skills/seo-flow/references/prompts/leverage/`
2. Apply to the URL's current backlink context
3. Cross-reference: "For raw backlink data, see `/seo backlinks <url>`"

### On `/seo flow optimize [url]`
1. Read all file names in `~/.config/opencode/seo-skills/seo-flow/references/prompts/optimize/`
2. Read prior analysis context (URL, industry vertical, any prior skill output in conversation)
3. Select 2-3 most relevant prompts; load only those files
4. Apply selected prompts; note the others are accessible via `/seo flow prompts`
5. Cross-reference: "For full content quality analysis, see `/seo content <url>` and `/seo geo <url>`"

### On `/seo flow win [url]`
1. Read all files in `~/.config/opencode/seo-skills/seo-flow/references/prompts/win/`
2. Apply each prompt to the URL's conversion and BOFU context
3. Cross-reference: "For SXO persona scoring, see `/seo sxo <url>`"

### On `/seo flow local [url]`
1. Read all files in `~/.config/opencode/seo-skills/seo-flow/references/prompts/local/`
2. Apply to the URL's local SEO context
3. Cross-reference: "For full local SEO analysis, see `/seo local <url>` and `/seo maps [command]`"

### On `/seo flow prompts`
1. Read `~/.config/opencode/seo-skills/seo-flow/references/prompts/README.md`
2. Display the full index: all 41 prompts with stage, name, trigger conditions

### On `/seo flow sync`
1. Run: `python3 scripts/sync_flow.py`
2. Display the JSON summary (files added, updated, unchanged)
3. Show attribution notice after sync completes

---

## Context Matching (Optimize stage)

The optimize stage has 21 prompts. Dumping all 21 is noise. Select by priority:

1. **Industry vertical** (SaaS → on-page + technical; local → citations + GBP; publisher → E-E-A-T + freshness)
2. **Prior skill output** (seo-technical flagged crawl issues → technical optimize prompts; seo-content flagged E-E-A-T gaps → content optimize prompts)
3. **URL signals** (product pages → conversion; blog → freshness + authority)

Always surface exactly 2-3 prompts. State which prompts you chose and why.

---

## Reference Files

Load on-demand — do NOT load all at startup:
- `~/.config/opencode/seo-skills/seo-flow/references/flow-framework.md` — FLOW operating model (load on every `/seo flow` activation)
- `~/.config/opencode/seo-skills/seo-flow/references/bibliography.md` — Evidence sources; load when citing studies or statistics
- `~/.config/opencode/seo-skills/seo-flow/references/prompts/README.md` — Prompt index; load for `/seo flow prompts`
- `~/.config/opencode/seo-skills/seo-flow/references/prompts/find/` — 5 prompts; load for `/seo flow find`
- `~/.config/opencode/seo-skills/seo-flow/references/prompts/leverage/` — 1 prompt; load for `/seo flow leverage`
- `~/.config/opencode/seo-skills/seo-flow/references/prompts/optimize/` — 21 prompts; load selectively for `/seo flow optimize`
- `~/.config/opencode/seo-skills/seo-flow/references/prompts/win/` — 3 prompts; load for `/seo flow win`
- `~/.config/opencode/seo-skills/seo-flow/references/prompts/local/` — 11 prompts; load for `/seo flow local`

---

## Attribution

Every `/seo flow` activation (any sub-command) outputs before analysis:

```
Framework and prompts © Daniel Agrici, CC BY 4.0 — github.com/AgriciDaniel/flow
```

Do not omit or modify the attribution.

---

## Error Handling

| Scenario | Action |
|----------|--------|
| `~/.config/opencode/seo-skills/seo-flow/references/flow-framework.md` missing | "FLOW reference files not synced. Run: `/seo flow sync`" |
| Prompt file missing | "Run `/seo flow sync` to pull the latest prompts from the FLOW repo." |
| `sync_flow.py` network error | Display the script's stderr. Check rate limits: `gh api rate_limit`. |
| `sync_flow.py` auth error | Run `gh auth login` then retry. |
