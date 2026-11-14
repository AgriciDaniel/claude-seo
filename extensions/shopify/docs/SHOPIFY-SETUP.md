# Shopify Crawler Access extension setup

## What this gives you

1. **An uncapped, sitemap-complete crawl** of a Shopify storefront via
   `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run shopify_crawl.py` instead of
   the 500-page link-following crawl in `seo-audit`.
2. **An authorized crawler** in the storefront's eyes, because every request
   carries the store's Crawler Access signature (RFC 9421 message signature,
   tag `web-bot-auth`), read from a project-local `.shopify-env`. Shopify's help
   page says rate-limit errors on a signed crawl mean the signature is not valid;
   it does not promise that a signed crawl is never throttled, so the crawler
   still backs off on `429`, `430` and `503`.
3. A `seo-shopify` skill that runs the precheck, the crawl, and then hands the
   artifacts to the standard `seo-audit` pipeline.

The signature is minted in the store's own admin, so this only works for stores
you or your client administer. Everything else keeps crawling unsigned.

## Install

```bash
./extensions/shopify/install.sh
.\extensions\shopify\install.ps1
```

No API keys. The `seo-shopify` skill ships with the claude-seo plugin, so on a
plugin install the installer copies nothing; run it from the plugin or repository
folder. On a manual install (`~/.claude/skills/seo`) it copies the skill next to
the other skills with its launcher path rewritten. The scripts ship with
claude-seo already. In both cases it offers to create `.shopify-env` in the
current folder from the template, readable by you only (mode 0600), and never
overwrites an existing file. `uninstall.sh` removes the copied skill of a manual
install and leaves `.shopify-env` alone.

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
`Max-Pages` (0 = no cap; the default is no cap for a signed crawl and 500 for an
unsigned one), `Concurrency` (1 to 16), `Delay` (0 to 60 seconds),
`Timeout` (1 to 120 seconds), `Sample-Per-Template` (1 to 50), `Include`,
`Exclude`, `Save-HTML`. Inside a block they override the shared values for that
shop only. A number outside its range is ignored with a warning and the default
applies.

For an unsigned crawl (no block for the host, or a block that is invalid or
expired) the file can only make the crawl gentler: a lower `Max-Pages`, a lower
`Concurrency`, a longer `Delay`. Values that would go past the unsigned limits
(500 pages, concurrency 2, 1 second delay) are ignored with a note. To lift them,
pass `--max-pages`, `--concurrency` or `--delay` on the command line.

A block is used for signing only when its `Signature-Input` has the
`web-bot-auth` tag, covers `@authority`, has a `keyid` and a future `expires`,
and the three values are plain header values with a `Signature` of the form
`label=:base64:` under the same label. Otherwise `list`, `check` and `precheck`
report the block as not usable (`signature_invalid`), its headers are never
sent, and the store is crawled at the unsigned limits. This checks the form of
the block only; the crawler has no way to verify the signature itself.

### robots.txt

The crawler respects robots.txt by default, signed or not. It skips disallowed
URLs, applies a `Crawl-delay` that is longer than its own delay, and stops when
robots.txt answers with a server error, because the rules are then unknown.

The `--ignore-robots` command-line flag switches that off: disallowed URLs are
crawled and `Crawl-delay` is not applied. It exists for a merchant auditing
their own store, including the sections its robots.txt hides from crawlers. It
is a command-line flag only. `.shopify-env` cannot set it: an `Ignore-Robots`
line in the file is ignored with a warning.

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
  rather than signed in cleartext, and an `http://` store URL is crawled unsigned
  (the precheck reports `insecure_scheme`). Sitemap entries on other hosts are
  skipped.
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
- Sustained rate limiting stops the crawl early, signed or not. The rule: 8
  rate-limit responses in a row across all workers, with no other response in
  between. No further request is sent, `summary.json` is written for the pages
  crawled so far with `"aborted": "rate_limited"`, and the exit code is 5.
  Run again later with `--resume`. A rate-limited sitemap is retried at most 3
  times.
- A store that redirects to another host (apex to `www`, for example) is not
  followed. The crawler names the redirect target so you can audit that host,
  with a signature issued for it.
- Stored page fields are capped in length, and the signature values are removed
  from error messages and from any page content that echoes them.
