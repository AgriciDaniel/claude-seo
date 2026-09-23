---
name: seo-matomo
description: Matomo Reporting API extension. Self-hosted or Matomo Cloud analytics as a GA4 alternative or complement. Organic traffic, landing pages, device / country breakdowns, referrers, search keywords. Triggers on "Matomo", "self-hosted analytics", "analytics ohne Google", "GA4 alternative", "Matomo Reporting", "Piwik".
metadata:
  version: "2.4.0"
compatibility: "Requires a Matomo instance URL and API token in ~/.config/claude-seo/matomo.json (0600), or MATOMO_URL / MATOMO_API_TOKEN / MATOMO_SITE_ID in the environment. Run extensions/matomo/install.sh to configure."
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
| `/seo matomo check` | `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_auth.py --check` |
| `/seo matomo organic [site-id]` | `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_report.py organic --site-id <id>` |
| `/seo matomo top-pages` | `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_report.py top-pages` |
| `/seo matomo device` | `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_report.py device` |
| `/seo matomo country` | `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_report.py country` |
| `/seo matomo referrers` | `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_report.py referrers` |
| `/seo matomo keywords` | `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_report.py keywords` |

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
  (analogous to `seo-google`) whenever `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_auth.py
  --check` succeeds. Both agents can be active simultaneously when the
  user has both GA4 and Matomo configured.

## Self-hosted instance on a private address

Every Matomo request goes through claude-seo's SSRF guard: the instance URL
is validated and DNS-pinned, and a redirect off the instance is refused.
Private, loopback, and link-local addresses are refused by default. When the
user's instance lives on one (`http://matomo.internal:8080`,
`http://192.168.1.20`, `http://localhost:8080`), tell them to name it in the
`CLAUDE_SEO_LOCAL_TARGETS` allowlist:

```bash
export CLAUDE_SEO_LOCAL_TARGETS="matomo.internal:8080"
```

Entries are `host` or `host:port`, comma-separated, matched exactly. The
allowlist covers only the top-level instance URL; redirect targets and every
other host stay fail-closed, and cloud metadata addresses are refused even
when listed. Never suggest disabling the guard or editing `url_safety.py`:
the allowlist is the supported route. Details in
`extensions/matomo/docs/MATOMO-SETUP.md` and SECURITY.md.

## Error Handling

- Refused by the SSRF guard (error names `CLAUDE_SEO_LOCAL_TARGETS`): the
  instance is on a private address that has not been allowlisted. Give the
  user the exact export line from the error, which already carries the right
  `host:port`.
- Refused redirect: the instance answered a 30x pointing at another host.
  `MATOMO_URL` is pointing at a redirector rather than at the Reporting API.
  Ask the user for the URL their instance actually serves the API from.
- Missing credentials: report which env vars / config keys are unset and
  remind the user to run `extensions/matomo/install.sh` or
  `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_auth.py --setup`.
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