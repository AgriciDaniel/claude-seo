---
name: seo-umami
description: >
  Self-hosted Umami analytics queries for SEO behavioral analysis. Reads
  pageviews, visitors, bounces, totaltime, referrers, and per-page
  engagement from a self-hosted Umami instance. Cookieless on-site
  behavioral data without GA4 or a consent banner. Use when the user says
  "umami", "cookieless analytics", "self-hosted analytics", "on-site
  engagement", "per-page bounce", "engagement data", "behavioral data",
  or for the engagement validation layer in SXO and content audits.
user-invokable: true
argument-hint: "[command] [args]"
license: MIT
metadata:
  category: seo
---

# Umami Self-Hosted Analytics

Reads on-site engagement data from a self-hosted Umami instance for SEO
behavioral analysis. This is the cookieless alternative to GA4 in the
upstream `seo-google` skill: bounce, time on page, referrers, and
per-landing-page engagement, with no cookies and no consent banner.

This skill is **specific to this fork**. Upstream `claude-seo` does not
ship it. See the fork-rationale note in the repo README.

## Prerequisites

Set `UMAMI_USERNAME` and `UMAMI_PASSWORD` in the environment, or in a
`.env` file at the repo root. Optional: `UMAMI_BASE_URL` (default
`https://analytics.crafts.software`), `UMAMI_WEBSITE_ID` (default for
`--website-id`).

Credentials follow the Foundry service-credentials standard. Source of
truth: 1Password TSE vault, item `Umami`. The `.env` is a gitignored
consumer copy. See `.env.example` at the repo root and
`tse/the-foundry/standards/service-credentials.md`.

To verify setup:

```bash
python scripts/umami_stats.py check
```

This returns the list of available website UUIDs you can pass as
`--website-id`.

## Quick Reference

| Command | What it does |
|---|---|
| `/seo umami setup` | Walk through credential setup (env + .env). |
| `/seo umami check` | Verify credentials and list available website IDs. |
| `/seo umami stats <website-id>` | Pageviews, visitors, visits, bounces, totaltime over 28 days. |
| `/seo umami pageviews <website-id>` | Pageviews + sessions timeseries (day buckets). |
| `/seo umami referrers <website-id>` | Top referrers (search engines, direct, social, etc.). |
| `/seo umami pages <website-id>` | Per-page engagement: pageviews, visitors, bounces, totaltime. |
| `/seo umami events <website-id>` | Custom events captured in Umami. |
| `/seo umami active <website-id>` | Visitors active in the last 5 minutes. |

## Script Mapping

All commands wrap `scripts/umami_stats.py`. JSON output by default.

| Skill command | Script call |
|---|---|
| `check` | `python scripts/umami_stats.py check` |
| `stats <id>` | `python scripts/umami_stats.py stats --website-id <id>` |
| `pageviews <id>` | `python scripts/umami_stats.py pageviews --website-id <id>` |
| `referrers <id>` | `python scripts/umami_stats.py metrics --website-id <id> --type referrer` |
| `pages <id>` | `python scripts/umami_stats.py metrics-expanded --website-id <id> --type url` |
| `events <id>` | `python scripts/umami_stats.py metrics --website-id <id> --type event` |
| `active <id>` | `python scripts/umami_stats.py active --website-id <id>` |

Add `--days N` (default 28) to change the lookback window. Add
`--limit N` to control row count on metrics calls (default 100).

## When to use this in audits

This skill provides the **post-click behavioral layer** that GSC and
PageSpeed don't cover. Best paired with:

- **`seo-sxo`** -- search experience validation. Bounce + time per
  landing page tells you whether a ranking page actually satisfies
  intent.
- **`seo-content`** -- content quality. Engagement signals validate
  whether content holds the reader.
- **Full `seo audit`** -- spawn the `seo-umami` subagent alongside the
  other parallel agents when Umami credentials are configured.

Do **not** spawn this skill for technical, schema, sitemap, or
performance work. Those depend on crawl-based data, not behavioral
data.

## Cross-Skill Integration

- **`seo-audit`** -- spawns `seo-umami` agent when `python
  scripts/umami_stats.py check` returns `status: ok`. Otherwise skips
  the behavioral layer silently.
- **`seo-sxo`** -- consults `pages` (per-URL engagement) to validate
  page-type recommendations.
- **`seo-content`** -- consults `pages` for engagement per landing page
  and `referrers` for traffic-source mix.

## Output Format

- Pure JSON from the script (suitable for piping to `jq` or feeding
  another agent).
- When the skill renders for a user, summarise top numbers in a small
  markdown table and call out engagement outliers (high bounce + short
  time = intent mismatch candidate; high time + low bounce = strong
  match).

## Setup walkthrough (`/seo umami setup`)

When invoked:

1. Read `~/Users/theo/tse/claude-seo/.env.example` and explain the four
   variables.
2. Check whether `.env` already exists; if it does, confirm with the
   user before overwriting.
3. Instruct the user to fetch `username` and `password` from the
   1Password TSE vault `Umami` item (the same credential `bearings`
   uses). Do **not** retrieve secrets yourself.
4. After the user has populated `.env`, run `python
   scripts/umami_stats.py check` and report the website IDs returned.

## Limitations

- **Self-hosted only.** Umami Cloud (API key flow on
  `https://api.umami.is`) is out of scope for v1.
- **Read only.** No write endpoints (events ingestion, website
  CRUD, user management).
- **Per-event property breakdowns** (`event_data`) are not yet wrapped;
  use the script's `metrics --type event` for event names only.
- **`metrics-expanded` may 400 on older self-hosted Umami.** The
  endpoint is documented but not present on all deployments. When it
  fails, fall back to top URLs via `metrics --type url` and (planned
  follow-up) per-URL `stats` with a `filters` parameter for engagement
  breakdown.
