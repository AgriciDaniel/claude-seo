---
name: seo-unlighthouse
description: Multi-page Lighthouse audit via the MIT-licensed Unlighthouse CLI. Free-tier alternative to running PageSpeed against every URL on a site, no API quota burn, runs locally.
metadata:
  version: "2.4.0"
compatibility: "Requires Node 18+ and the unlighthouse npm package. Run extensions/unlighthouse/install.sh to pre-warm."
---

# seo-unlighthouse

Run Lighthouse against every URL on a site (up to a configurable cap)
and aggregate the results. Useful when:

- PageSpeed Insights' free quota (25k QPD) isn't enough for a large site.
- You want offline / local CWV measurement (CI integration, restricted environments).
- You need a quick site-wide regression check after a deploy.

## Prerequisites

- Run `extensions/unlighthouse/install.sh` (no API key needed).
- Node 18+ on `$PATH`.

## Routing

| Command | Effect |
|---|---|
| `/seo unlighthouse <url>` | Mobile audit, up to 200 routes, JSON+HTML report in a temp dir |
| `/seo unlighthouse <url> --device desktop` | Desktop form factor |
| `/seo unlighthouse <url> --max-routes 50 --output-dir ./reports` | Cap + persist |

All flags forward through `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run unlighthouse_run.py`, which handles
url_safety pre-flight and subprocess timeout management.

## Output handling

The wrapper reads `ci-result.json` from the Unlighthouse output dir, normalizes
it (the default `jsonSimple` reporter writes a flat JSON array of per-route
results; a tolerant fallback also accepts the `jsonExpanded` object shape),
and returns:

- `route_count`: number of routes actually audited
- `aggregate_scores`: median score per Lighthouse category across all audited
  routes (`performance`, `accessibility`, `best-practices`, `seo`)
- `routes`: the per-route breakdown (also on disk at `<output_dir>/ci-result.json`)

Route cap and per-page timeout are set via a generated `unlighthouse.config.mjs`
passed with `--config-file` (the only CLI-documented way to set `scanner.maxRoutes`;
unlighthouse-ci has no `--max-routes` flag). Use `--page-timeout <seconds>` to
change the per-page Lighthouse task timeout (default 60s); this is separate
from the overall `--timeout` subprocess guard (default 600s).

## Cross-skill delegation

- For single-URL field data (CrUX), use `seo-google psi` / `seo-google crux`.
- For LCP subpart decomposition on slow pages, use the
  `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run lcp_subparts.py` workflow (Phase C).
