# Migrating from claude-seo v1.x to v2.0.0

v2 is **backward-compatible by design**. Every v1.x CLI invocation, every
script signature, and every skill command still works. The breaking
changes are limited to two narrow surfaces:

1. `backlinks_auth.py`'s legacy fallback (silently allowed private IPs)
   has been removed. If `scripts/url_safety.py` cannot be imported, the
   module now raises `RuntimeError` at import time instead of running
   with SSRF protection disabled.
2. Six `Schema.org` rich-result types Google retired in 2025 are now
   marked as Critical findings when the `seo-schema` skill detects them
   (Vehicle Listing, Claim Review, Estimated Salary, Learning Video,
   Special Announcement, Course Info carousel). Sites still generating
   these in `<script type="application/ld+json">` blocks will see a new
   Critical row in the audit output.

Everything else is additive — new commands, new scripts, new reference
files, new extensions. Existing audit reports will look slightly fuller
but use exactly the same overall structure.

This guide covers the v1.x → v2.0.0 jump only; the v2.1.0 through v2.2.3
releases are documented in [../CHANGELOG.md](../CHANGELOG.md), and the
suite is now at 326 tests.

## What's new in v2

### Foundation

- **`scripts/url_safety.py`** is the canonical SSRF + DNS-rebinding
  module. Every fetcher now routes through it. Five distinct bypass
  classes are closed at parse time, including obfuscated IPv4 (decimal,
  hex, octal, leading zeros), FQDN trailing-dot bypasses, and the
  redirect-rebinding chain.
- **`scripts/render_page.py`** is the shared headless renderer. Every
  fetcher subagent now calls it with `--mode auto`, so SPA sites (React,
  Next.js, Vue, Nuxt, Svelte, Astro islands) are audited correctly
  without per-skill retrofits.
- **OAuth token file permissions** are forced to `0o600` on every load
  and save. Legacy `0o644` files (pre-v2 default) are remediated in
  place at the next call to `_load_oauth_token`.

### Content quality (Phase B)

| New | What it does |
|---|---|
| `python3 scripts/content_quality.py` | QRG-aligned filler / AI-pattern / information-density scorer |
| `python3 scripts/content_humanize.py` | 40+ deterministic AI-phrasing replacements |
| `python3 scripts/content_verify.py` | Claim extraction + citation-gap detection |
| `python3 scripts/domain_history.py` | WHOIS-driven expired-domain abuse check |
| `python3 scripts/seo_updates.py` | Primary-source Google updates changelog |
| `data/google-updates.json` | 18 confirmed Google updates 2024-03 → 2025-12 |

### Technical / CWV depth (Phase C)

| New | What it does |
|---|---|
| `python3 scripts/preload_check.py` | Speculation Rules + bfcache + prerender + LCP preload audit |
| `python3 scripts/indexnow_submit.py` | Submit up to 10k URLs to IndexNow (Bing/Yandex/Seznam/Naver) |
| `python3 scripts/lcp_subparts.py` | LCP decomposition via CrUX (TTFB, load delay, load duration, render delay) |
| `python3 scripts/unlighthouse_run.py` | Multi-page Lighthouse via the MIT Unlighthouse CLI |

### Schema completeness (Phase D)

| New | What it does |
|---|---|
| `python3 scripts/schema_generate.py reservation/order/discussion/profile` | JSON-LD generators for the four high-leverage v2 types |
| `python3 scripts/schema_ecommerce_validate.py` | Product schema policy validator (hasMerchantReturnPolicy, shippingDetails, MemberProgram, EU energy class, ProductGroup) |
| `skills/seo-schema/references/deprecated-types-2024-2026.md` | Reference: every retired rich-result type with its replacement |

### AI search + 5 new extensions (Phase E)

| New | What it does |
|---|---|
| `python3 scripts/parasite_risk.py` | Site-reputation-abuse risk scanner per Nov 2024 Google policy |
| `extensions/ahrefs/` | Official `@ahrefs/mcp` server wired into Claude Code |
| `extensions/seranking/` | AI Share-of-Voice across ChatGPT/Gemini/Perplexity/AI Overviews/AI Mode |
| `extensions/profound/` | Time-series LLM citation tracker |
| `extensions/bing-webmaster/` | Bing Webmaster + IndexNow unified |
| `extensions/unlighthouse/` | MIT multi-page Lighthouse runner |
| `skills/seo-geo/references/llmstxt-evidence.md` | Evidence-based reframe: llms.txt is not a citation lever |

### Local + International + Privacy polish (Phase F)

| New | What it does |
|---|---|
| `python3 scripts/gbp_deprecation_lint.py` | Detects retired GBP chat; treats `.business.site` as unresolved and Q&A as review-only |
| `skills/seo-google/references/dma-consent-mode-v2.md` | EU CTR diagnostic + softened cookieless framing |
| `skills/seo-hreflang/references/machine-translation-qa.md` | Untranslated-MT detection per Jan 2025 QRG §4.6.5 |

### Multi-platform portability (Phase G)

| New | What it does |
|---|---|
| `AGENTS.md` (extended) | Codex CLI, Cline, Aider added to supported-harnesses list |
| `python3 scripts/portability_check.py` | Cross-platform SKILL.md frontmatter lint |
| Tool-name compatibility table | Read/Write/Edit/Bash/Glob/Grep/WebFetch mappings across Codex/Cline/Aider/Cursor/Antigravity |

### Release signing (Phase H)

| New | What it does |
|---|---|
| `python3 scripts/release_sign.py` | Generate a SHA-256 manifest of every git-tracked file |
| `python3 scripts/verify_release.py` | Verify a checkout against a signed manifest |

### Hardening

- **DNS rebinding via redirect target** (HIGH severity) — closed.
- **Obfuscated IPv4 bypass** in `validate_url` (HIGH) — closed.
- **FQDN trailing-dot bypass** of metadata-endpoint blocklist (HIGH) — closed.
- **IPv6 blind spot in Playwright route handler** (MEDIUM) — closed.
- **OAuth file-permission TOCTOU** (LOW) — closed.
- **Unsigned install scripts:** partially closed; release manifest
  tooling shipped in v2.0.0, install.sh integration tracked for v2.3.

## Breaking changes (full list)

There are exactly two surface-visible breaks:

### 1. `backlinks_auth.py` hard-fails without `url_safety`

```python
# v1.x
from backlinks_auth import validate_url  # silently uses unsafe fallback
                                          # if url_safety not importable

# v2.x
from backlinks_auth import validate_url  # raises RuntimeError if
                                          # url_safety can't be imported
```

This is the closure of a deferred security item from v1.9.0. The v1.x
fallback shipped without IP-range checks; we'd rather refuse to run than
silently allow private-IP fetches.

### 2. `seo-schema` flags retired rich-result types as Critical

If your generated JSON-LD includes `@type: ClaimReview`, `Vehicle`,
`EstimatedSalary`, `LearningVideo`, `SpecialAnnouncement`, or
`CourseInfo` (carousel variant), the new
`scripts/schema_ecommerce_validate.py` will emit a `Critical` finding.

**Action:** consult `skills/seo-schema/references/deprecated-types-2024-2026.md`
for the recommended replacement per type. If you need to keep the
markup for non-Google purposes, you can suppress the finding by removing
the type from the validator's deprecated list (not recommended — the
rich result is dead).

## Things that were going to break but didn't

We considered but ultimately did **not** break the following:

- `validate_url` boolean return contract. v2 still returns `bool` for
  back-compat. Use `validate_url_strict` if you want the new strict
  DNS-rebinding behaviour.
- `fetch_page()` function signature. The `--render` flag was added at the
  CLI layer only; the underlying function stays raw-mode by default.
- `capture_screenshot()` API. Pre-flight is upgraded but the call
  signature and result dict are unchanged.
- All v1.x command names (`/seo audit`, `/seo content`, …). Every
  one of them works in v2.

## How to upgrade

Caution: Prefer downloading, inspecting, then running remote scripts; the pipe-to-shell form below is the less-safe convenience option.

```bash
# Pull v2.0.0
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash

# Verify the new requirements pin landed
pip install -r requirements.txt

# Confirm Playwright Chromium is installed (used by render_page)
playwright install chromium

# Verify manifest consistency
python3 -m pytest tests/test_manifest_consistency.py -v
```

That's it. The first time you run anything that touches
`~/.config/claude-seo/oauth-token.json`, v2 will silently re-chmod it
to `0o600` — no user action required.

## Test coverage

| Suite | v1.9.9 | v2.0.0 |
|---|---:|---:|
| Manifest consistency | 13 | 13 |
| Lazy detection | 11 | 11 |
| Sync FLOW | 15 | 15 |
| **`url_safety` (new)** | — | **83** |
| **`render_page` (new)** | — | **27** |
| **Content quality (new)** | — | **25** |
| **Technical depth (new)** | — | **17** |
| **Schema v2 (new)** | — | **17** |
| **Parasite risk + extensions (new)** | — | **22** |
| **GBP lint + polish (new)** | — | **8** |
| **Portability (new)** | — | **10** |
| **Total** | **39** | **248** |

v2 adds 209 new test cases (5.4× the v1 baseline) covering every new
function's failure modes plus every known SSRF bypass class.
