---
name: seo-notebooklm
description: >
  Google NotebookLM research automation for SEO: bulk-import competitor
  pages, SERP results, and reference docs into a NotebookLM notebook, then
  generate research artifacts (study guides, mind maps, podcasts, quizzes,
  flashcards) to speed up content briefs, topic authority mapping, and
  competitor analysis. Use when user says "notebooklm", "research notebook",
  "competitor research", "topic cluster research", "content brief research",
  "study guide", "mind map", "audio overview", "podcast summary",
  "bulk import sources", or "NotebookLM podcast".
user-invokable: true
argument-hint: "[command] [args]"
license: MIT
metadata:
  author: AgriciDaniel
  version: "1.8.2"
  category: seo
---

# NotebookLM Research Automation

Bridges Google NotebookLM into claude-seo workflows via the `notebooklm-py`
unofficial Python API. Useful whenever an SEO task benefits from synthesizing
many sources into a single researched artifact: competitor content clusters,
topic authority mapping, content brief generation, and SERP synthesis.

> **Caveat:** `notebooklm-py` talks to undocumented Google endpoints. APIs may
> break and heavy usage may be throttled. Treat this skill as *research
> acceleration*, not a production data source. Never cite NotebookLM outputs
> without verifying against primary sources.

## Prerequisites

Install the library once (into the shared seo venv):

```bash
pip install "notebooklm-py[browser]"
playwright install chromium
```

Then authenticate once with a real Google login:

```bash
notebooklm login            # default browser
notebooklm login --browser msedge
notebooklm auth check --test
```

Credentials are cached by `notebooklm-py` under its own storage path.
Re-run `notebooklm login` whenever `auth check --test` reports `expired`.

Before any command, check connectivity:

```bash
python scripts/notebooklm_client.py check --json
```

If the check fails with an auth error, walk the user through
`notebooklm login` rather than guessing credentials.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/seo notebooklm setup` | Show install + login instructions |
| `/seo notebooklm check` | Verify auth and list accessible notebooks |
| `/seo notebooklm create <name>` | Create a new notebook, return its id |
| `/seo notebooklm import <nb> <urls-file>` | Bulk-import URLs from a newline file |
| `/seo notebooklm import-pdf <nb> <path>` | Attach a local PDF source |
| `/seo notebooklm ask <nb> "<question>"` | Ask a question against notebook sources |
| `/seo notebooklm study-guide <nb>` | Generate a study guide report |
| `/seo notebooklm mind-map <nb>` | Generate and export a mind map (JSON) |
| `/seo notebooklm podcast <nb> [instructions]` | Generate and download an audio overview |
| `/seo notebooklm quiz <nb> [difficulty]` | Generate a quiz (easy/medium/hard) |
| `/seo notebooklm flashcards <nb>` | Generate flashcards (JSON export) |
| `/seo notebooklm brief <topic> <urls-file>` | Full research brief pipeline |

All commands are thin wrappers around `scripts/notebooklm_client.py`, which
exposes the `notebooklm-py` async API through a sync CLI with JSON output.

## Workflows

### Competitor research brief

Given a list of competitor URLs (e.g. top-10 SERP for a target keyword),
build a research brief with a single command:

```bash
python scripts/notebooklm_client.py brief \
  --topic "best crm for freelancers" \
  --urls ./serp-top10.txt \
  --artifacts study-guide,mind-map \
  --output ./out/crm-brief/ \
  --json
```

The pipeline:

1. Creates a notebook named after `--topic`
2. Bulk-imports each URL (skipping failures, reporting per-source status)
3. Generates the requested artifacts in parallel where the API allows
4. Downloads exports into `--output`
5. Emits a JSON summary mapping each artifact to its file path

Feed the resulting study guide or mind map into `seo-content` or
`seo-plan` for follow-up content-brief generation.

### Topic cluster authority check

For content gap analysis, import your existing pages plus the top-ranking
competitors for the cluster's head term:

```bash
python scripts/notebooklm_client.py create --name "Cluster: email deliverability" --json
python scripts/notebooklm_client.py import --nb <id> --urls ./cluster-urls.txt --json
python scripts/notebooklm_client.py ask --nb <id> \
  "Which subtopics are covered by competitors but missing from our pages?" --json
```

The `ask` output becomes a gap list; pipe it into `seo-plan` to schedule
missing pages.

### Podcast digest for stakeholder updates

Turn a month of newly published content plus Google updates into a short
audio overview:

```bash
python scripts/notebooklm_client.py podcast \
  --nb <id> \
  --instructions "Summarize the SEO implications for a B2B SaaS audience in under 10 minutes" \
  --output ./reports/monthly-seo.mp3 --json
```

## Source Budget

NotebookLM has per-notebook source and generation limits that change over
time. Stay conservative:

- Prefer **≤ 50 sources** per notebook (NotebookLM's historical free cap)
- Deduplicate URLs before import (one canonical per page)
- Strip tracking params; normalize trailing slashes
- For very long PDFs, split into logical chunks before `add_file`
- Space out back-to-back artifact generations (NotebookLM rate limits
  audio/video generation tighter than text)

If an import fails with a quota error, the script returns
`{"status": "rate_limited", "retry_after": <seconds>}`. Respect it; do not
retry in a tight loop.

## Security & Privacy

- **Do not import private URLs** (intranet pages, unpublished drafts) without
  explicit user consent. NotebookLM stores sources on Google servers under
  the authenticated user's account.
- **Never import credentials or PII.** The `brief` pipeline filters obvious
  secrets (bearer tokens, `Authorization:` headers), but the caller is
  responsible for the URL list.
- **URL validation:** `notebooklm_client.py` calls `validate_url()` from
  `scripts/google_auth.py` before every import to block private IPs, GCP
  metadata endpoints, and loopback (SSRF protection).
- **No credential storage in repo.** Auth lives inside `notebooklm-py`'s own
  storage (platform-dependent); do not copy it into `~/.config/claude-seo/`.

## Error Handling

| Scenario | Action |
|----------|--------|
| `notebooklm-py` not installed | Report the exact `pip install` command, do not attempt workarounds |
| `auth check` reports `expired` / `unauthenticated` | Instruct user to re-run `notebooklm login`; do not guess creds |
| Source import returns `unsupported_format` | Skip, log, continue; report the failed URL in the summary |
| Artifact generation task stays in `pending` > 5 min | Abort the wait, return `{"status": "timeout"}`; do not block indefinitely |
| NotebookLM API schema changes break the wrapper | Report upstream error verbatim; do not fall back to web scraping |
| User asks to import > 200 sources | Warn about the practical cap, chunk into multiple notebooks |

## Cross-Skill Integration

- **`seo-content`** -- feed NotebookLM-generated study guides into E-E-A-T
  scoring; use the mind map JSON to verify topical coverage.
- **`seo-plan`** -- convert the `ask` gap list into a content calendar.
- **`seo-geo`** -- NotebookLM's audio overviews double as a quick readout of
  AI-citation readiness (if it can summarize the page cleanly, AI engines
  probably can too).
- **`seo-competitor-pages`** -- use `brief` on the competitor URL set to
  seed comparison page content.
- **`seo-google report`** -- attach the study guide PDF or mind map PNG as
  an appendix to the canonical report.

## Output Conventions

All commands emit JSON on `--json` with this envelope:

```json
{
  "status": "ok | error | rate_limited | timeout",
  "command": "brief",
  "notebook_id": "nb_abc123",
  "artifacts": {
    "study_guide": "./out/crm-brief/study-guide.md",
    "mind_map": "./out/crm-brief/mind-map.json"
  },
  "imported": 9,
  "failed": [{"url": "https://...", "reason": "unsupported_format"}],
  "warnings": []
}
```

Human-readable output (no `--json`) prints a short table plus the same file
paths; prefer `--json` when piping into other skills.
