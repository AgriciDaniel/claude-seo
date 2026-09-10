---
name: seo-shopify
description: "Uncapped, sitemap-complete crawl of a Shopify storefront using the merchant's Crawler Access signature from a project-local .shopify-env, feeding the standard seo-audit pipeline. Use when the user says 'Shopify audit', 'crawl the whole store', 'Crawler access', 'signature-agent', 'web-bot-auth', 'rate limited while crawling', or audits a host listed in .shopify-env."
metadata:
  version: "2.3.0"
compatibility: "Requires a Shopify store the user administers (the signature is minted in the store's admin) and a .shopify-env file in the folder the audit runs from. Without it, seo-audit runs unchanged."
---

# seo-shopify

Shopify rate-limits storefront crawling, and `seo-audit` caps its link-following
crawl at 500 pages. A merchant can mint a **Crawler Access** signature in their
admin (Online Store > Preferences > Crawler access). A crawler that replays the
three resulting headers is treated as an authenticated crawler and is not rate
limited, and Shopify publishes a complete nested sitemap for every store. Together
that makes an uncapped, sitemap-complete crawl possible without guessing at a cap.

This skill adds that crawl. It replaces **step 3 only** of `seo-audit` (the crawl).
Business-type detection, subagent delegation, scoring and reports stay as
`seo-audit` defines them.

## Hard limits (state these before promising a crawl)

- Only for stores the user administers. The signature exists only inside the
  merchant's admin; competitor and prospect stores crawl unsigned, capped, via
  plain `seo-audit`.
- One signature per host. `shop.example`, `www.shop.example` and
  `shop.myshopify.com` are different authorities; crawl the host the signature was
  issued for. The crawler never sends it to any other host.
- Signatures expire after roughly 90 days and cannot be extended. The merchant
  issues a new one.
- Checkout is excluded from signature access by Shopify.

## Routing

| Command | Effect |
|---|---|
| `/seo shopify <url>` | Precheck, signed uncapped crawl, then the `seo-audit` pipeline on the artifacts |
| `/seo shopify crawl <url>` | Crawl only, artifacts in `./crawl` |
| `/seo shopify check <url>` | Report whether `.shopify-env` holds a valid signature for the host |

## Step 1: decide the mode

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run shopify_env.py precheck <url>
```

Always exits 0 and always prints JSON. Read `mode`:

- `"signed"`: continue with step 2.
- `"fallback"`: run the plain `seo-audit` skill, completely unchanged, cap and
  link-following crawl included. Tell the user in one sentence why (the `detail`
  field says it) and get on with the audit. A capped audit is a normal result.

Fallback reasons: `no_env_file`, `no_signature`, `signature_expired`,
`env_unreadable`. Before accepting `no_signature`, remember the signature is bound
to one host: if the store serves on the other of apex/www, re-run the precheck
against that host.

## Step 2: crawl

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run shopify_crawl.py <url> --out ./crawl
```

No `--max-pages`. The crawl covers the complete sitemap; a cap applies only when
`.shopify-env` or the command line sets one, and the summary then carries
`"truncated": true`. Report the real number of pages crawled, never a rounded cap.

Exit codes:

- `0`: crawl complete, continue.
- `5`: crawl complete and artifacts usable, but the storefront rate limited a
  signed request. Shopify treats that as an invalid signature. Continue the audit
  on the artifacts and flag in the report that the signature should be reissued.
- `1`: nothing crawled (no sitemap reachable, password-protected store, wrong
  host, or the URL failed `url_safety`). Fall back to plain `seo-audit` and say why.

Large stores: the crawl is resumable (`--resume`). If it was interrupted, resume it
instead of auditing a partial crawl.

Defaults: no page limit; concurrency 6 and a 0.2 s delay when signed, 2 and 1 s
unsigned; robots.txt respected; redirects recorded, not followed; bodies read up to
10 MiB per page and the sitemap walk bounded at 5 levels, 500 sitemaps and 250,000
URLs (`discovery_capped` in `summary.json` names the cap that was hit). Precedence is
command line > domain block > global keys > these defaults. Useful flags:
`--include`/`--exclude` (regex), `--save-html`, `--sample-per-template N`,
`--no-signature` to measure the unsigned baseline.

## Step 3: audit on the crawl artifacts

Follow `seo-audit` from its step 4 onwards. The crawl is done; nobody crawls again.
Business type is settled: a Shopify storefront is E-commerce, so `seo-ecommerce` is
in scope.

What each subagent gets:

- `crawl/summary.json`: aggregate counts across all crawled pages. The evidence
  base for anything quantitative: status distribution, per-template counts,
  missing and duplicate titles, meta description lengths, missing canonicals,
  noindex, h1 problems, thin pages, images without alt, schema coverage, latency
  percentiles.
- `crawl/sample.json`: a stratified sample, N pages per template type, for the
  agents that need real page content (`seo-content`, `seo-schema`, `seo-sxo`,
  `seo-ecommerce`).
- `crawl/pages.jsonl`: never passed to a subagent. It is the raw record set and
  will not fit in a context window on any store worth crawling uncapped. Query it
  with a script when a specific number is missing from `summary.json`.

Say in each subagent prompt that the pages were already fetched, so they analyze
the artifacts instead of re-fetching the site. Agents that need live requests
(`seo-performance`, `seo-visual`, `seo-google`) make their handful of unsigned
requests as usual.

## Step 4: score and report

Unchanged from `seo-audit`: same weights, same `FULL-AUDIT-REPORT.md` and
`ACTION-PLAN.md`. Two additions to the executive summary, because they change how
the numbers read: the pages crawled and that the crawl was signed and complete,
and any truncation with what was left out.

## Setup

See `extensions/shopify/docs/SHOPIFY-SETUP.md` for issuing the signature and the
`.shopify-env` format. `.shopify-env` holds a client credential: keep it out of git.
