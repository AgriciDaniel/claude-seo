---
name: seo-matomo
description: Matomo Reporting API extension. Self-hosted or Matomo Cloud analytics as a GA4 alternative or complement. Organic traffic, landing pages, device / country breakdowns, referrers, search keywords. Triggers on "Matomo", "self-hosted analytics", "analytics ohne Google", "GA4 alternative", "Matomo Reporting", "Piwik".
metadata:
  version: "2.2.5"
compatibility: "Requires MATOMO_URL, MATOMO_API_TOKEN, and (optionally) MATOMO_SITE_ID in ~/.claude/settings.json env. Run extensions/matomo/install.sh to configure."
---

# seo-matomo

Self-hosted analytics surface. Use Matomo as a privacy-first GA4 alternative
when you own your analytics data, want zero Google dependency, or operate
behind a strict data-residency boundary. The same `seo-matomo` skill works
against Matomo Cloud and self-hosted instances.

## Prerequisites

- Run `extensions/matomo/install.sh` or `install.ps1`.
- A Matomo instance URL (https://analytics.example.com).
- A Matomo API `token_auth` with `view` access on the sites you analyze.
- (Optional) A default `idSite` to avoid passing `--site-id` on every call.

## Routing

| Command | Underlying script |
|---|---|
| `/seo matomo check` | `claude-seo run matomo_auth.py --check` |
| `/seo matomo organic [site-id]` | `claude-seo run matomo_report.py organic --site-id <id>` |
| `/seo matomo top-pages` | `claude-seo run matomo_report.py top-pages` |
| `/seo matomo device` | `claude-seo run matomo_report.py device` |
| `/seo matomo country` | `claude-seo run matomo_report.py country` |
| `/seo matomo referrers` | `claude-seo run matomo_report.py referrers` |
| `/seo matomo keywords` | `claude-seo run matomo_report.py keywords` |

All commands accept `--days` (default 28), `--limit`, `--site-id`, and
`--json`. The site ID falls back to `MATOMO_SITE_ID` from settings.

## When this skill applies

- The user wants Google-free analytics or has a Matomo instance already
  configured. Common in EU privacy-first setups, regulated industries,
  and teams who own their analytics.
- The user explicitly says "Matomo", "self-hosted analytics", or asks to
  replace GA4. For Google Search performance use `seo-google`; this
  skill is the reporting substitute.
- The user is migrating from GA4 and wants the same report types
  (organic trend, landing pages, device / country split, referrer split)
  sourced from Matomo's Reporting API.

## Cross-skill delegation

- For Google Search Console / CrUX / Indexing, route to `seo-google`.
  `seo-matomo` covers reporting (visits / pages / referrers), not search
  performance metrics.
- For AI Overview / GEO citability work, route to `seo-geo`. Matomo
  offers no LLM-specific signals.
- During `/seo audit`, the orchestrator spawns the `seo-matomo` agent
  (analogous to `seo-google`) whenever `claude-seo run matomo_auth.py
  --check` succeeds. Both agents can be active simultaneously when the
  user has both GA4 and Matomo configured.

## Error Handling

- Missing credentials: report which env vars / config keys are unset and
  remind the user to run `extensions/matomo/install.sh` or
  `python scripts/matomo_auth.py --setup`.
- HTTP 401/403 from Matomo: the token lacks view access for the given
  site. Verify the token scope in Matomo Administration -> Personal ->
  Security -> API Tokens. The skill never logs the token.
- `result=error` payloads from Matomo (e.g. invalid `idSite`): surface
  the message verbatim; do not guess.
- Connection / SSL / timeout: report the network failure class
  (`ConnectionError`, `SSLError`, `timeout`) and confirm
  `MATOMO_URL` resolves.

## Output Formatting

- Tables for time-series, device, and country data.
- Critical / High / Medium / Low priority for any cross-skill actions
  surfaced from Matomo data.
- Always label the data source as "Matomo Reporting API (live)" to
  distinguish from GA4, CrUX, or static crawl analysis.
- For organic keywords, surface the `anonymized_share_pct` prominently.
  Many keywords will be "(not provided)" due to browser privacy and
  Matomo's anonymization rules; this is normal, not a data bug.