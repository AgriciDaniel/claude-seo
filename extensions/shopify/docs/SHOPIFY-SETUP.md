# Shopify Crawler Access extension setup

## What this gives you

1. **An uncapped, sitemap-complete crawl** of a Shopify storefront via
   `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run shopify_crawl.py` instead of
   the 500-page link-following crawl in `seo-audit`.
2. **No storefront rate limiting** while crawling, because every request
   carries the store's Crawler Access signature (RFC 9421 message signature,
   tag `web-bot-auth`), read from a project-local `.shopify-env`.
3. A `seo-shopify` skill that runs the precheck, the crawl, and then hands the
   artifacts to the standard `seo-audit` pipeline.

The signature is minted in the store's own admin, so this only works for stores
you or your client administer. Everything else keeps crawling unsigned.

## Install

```bash
./extensions/shopify/install.sh
.\extensions\shopify\install.ps1
```

No API keys. The installer copies the `seo-shopify` skill next to the other
skills; the scripts ship with claude-seo already.

## 1. Issue the signature

Shopify admin > **Online Store** > **Preferences** > **Crawler access** > create
a signature. The admin shows three header values:

```
Signature-Agent: "https://shopify.com"
Signature-Input: sig1=("@authority" "signature-agent");keyid="...";nonce="...";tag="web-bot-auth";created=...;expires=...
Signature: sig1=:...:
```

Only `Signature-Agent` is constant. The signature covers `@authority`, so it is
bound to exactly one host, and it expires after roughly 90 days.

## 2. Write `.shopify-env`

Create `.shopify-env` in the folder you run audits from; it is also found up to
five parent folders up. Alternatively `$SHOPIFY_ENV` names a file anywhere on disk,
for credentials shared across several audit folders. One
block per shop; a new `Domain=` line starts the next block. Keys before the first
`Domain=` are crawl settings shared by every shop in the file.

```
Max-Pages   = 0
Concurrency = 6

Domain          = shop.example
Signature-Input = sig1=("@authority" "signature-agent");keyid="...";tag="web-bot-auth";created=...;expires=...
Signature       = sig1=:...:

Domain          = second-shop.example
Signature-Input = ...
Signature       = ...
Concurrency     = 3
```

`Signature-Agent` is optional and defaults to `"https://shopify.com"`. Header
values are used byte-exact; do not strip their quotes. Recognised crawl keys:
`Max-Pages` (0 = no cap, the default), `Concurrency`, `Delay`, `Timeout`,
`Sample-Per-Template`, `Include`, `Exclude`, `Save-HTML`, `Ignore-Robots`. Inside
a block they override the shared values for that shop only.

A copy of this layout lives at `extensions/shopify/.shopify-env.example`.

**Never commit it.** `.shopify-env` holds a client credential. It is in the
repository's `.gitignore`; the scripts also warn when the file sits in a git
work tree without being ignored.

## 3. Check and crawl

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run shopify_env.py list
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run shopify_env.py check https://shop.example
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run shopify_crawl.py https://shop.example --out ./crawl
```

Or in Claude Code: `/seo shopify https://shop.example`.

## Security notes

- The crawler validates the root with `url_safety.validate_url_strict`, pins DNS
  for the session, crawls the signed host only, and records redirects without
  following them.
- The signature is attached only to requests whose scheme and host equal the
  origin it was issued for; an `http://` entry for an `https://` store is skipped
  rather than signed in cleartext. Sitemap entries on other hosts are skipped.
- No command prints the signature values; `list` and `check` report key id and
  expiry only.
- The sitemap walk stops at 5 index levels, 500 sitemaps or 250,000 URLs, and
  every body is read up to a byte limit (1 MiB robots.txt, 50 MiB sitemap, 10 MiB
  page). A crawl that hit one of those caps reports `discovery_capped` in
  `summary.json`.
- On `429`, `430` or `503` the crawler backs off exponentially. If that happens
  on a signed request, it exits with code 5 after finishing, because Shopify's
  documented meaning of a rate-limit response to a signed request is that the
  signature is not valid.
