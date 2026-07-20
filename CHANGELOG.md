# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.3] - 2026-07-14

Prompt-hygiene alignment to the Fable 5 prompt principles. No behavior, routing, or output changes.

- Removed CAPS emphasis words (MUST, NEVER, ALWAYS, and a CRITICAL RULES heading) used as emphasis
  across skills and agents; severity status tokens left intact.
- Swept em-dashes and en-dashes from prose to commas, colons, and hyphens across the prompt surface
  (code fences untouched).
- Trimmed five over-long skill descriptions.

## [2.2.2] - 2026-07-10

Full-review maintenance pass (2026-07-09/10). 319 adversarially verified findings from a
multi-engine review (7 Google research streams, 20 currency audit slices, 6 refuter slices);
all fix bundles applied. No breaking changes.

### Fixed

- GBP Q&A false-deprecation removed from `scripts/gbp_deprecation_lint.py` and
  `skills/seo/references/local-seo-signals.md` (Google: Q&A is category/region-limited, not retired).
- AI Mode model claim corrected to Google's confirmed "custom version of Gemini 2.5";
  AI Overviews / AI Mode user counts attributed to third-party I/O 2026 reporting.
- Stale Gemini image-model IDs refreshed across seo-image-gen and the banana extension;
  dead `scripts/presets.py` / `cost_tracker.py` invocations repointed.
- rel=next/prev pagination and Publisher Center news-sitemap guidance corrected; WebMCP audit
  IDs aligned with Lighthouse 13.2.0 release notes; GA4 AI Assistants source list fixed.
- CLAUDE.md tree/table brought to v2.2.1; PRIVACY.md now discloses the Bing Webmaster /
  IndexNow extension; README offline phrasing corrected; TROUBLESHOOTING de-v1'd.
- `hooks/validate-schema.py` now supports the documented stdin hook-event contract.

### Added

- `scripts/consistency_check.py`: path-aware reference-graph gate (dead refs, routing tables,
  FLOW lock, orphans) with CI coverage via `tests/test_consistency_check.py`.

## [2.2.1] - 2026-06-22

Google-currency refresh. Reconfirms the suite against the latest Google updates, verified against Google-primary sources via a multi-agent reconfirmation run. Documentation/data accuracy only — no code behavior change beyond two added IPTC vocabulary values. No breaking changes.

### Fixed (stale → current)

- **Lighthouse**: `13.0 (Oct 2025)` → `13.4.0 (June 2026, latest stable)`; corrected the 13.0 description (insight-based audits, not "reorganized scoring weights"); documented the new **Agentic Browsing** category (created 13.2.0, default 13.3.0, disabled in the PSI REST API in 13.4.0) as a **fractional pass-ratio**, not a 0–100 score. (`agents/seo-performance.md`, `skills/seo/references/cwv-thresholds.md`, `skills/seo-technical/**`)
- **WebMCP**: replaced the "early preview / not before 2027" framing with the live **Chrome 149 origin trial** (sign-up open 2026-06-09) and the three shipped Lighthouse audits (`registered-webmcp-tools`, `forms-missing-declarative-webmcp`, `webmcp-schema-validity`).
- **GEO**: AI Overviews reach `1.5B` → **2.5B+ MAU** (I/O 2026); added that **Google Search ignores llms.txt** (docs, 2026-06-15); reconciled the unified AI-Search experience with the two-citation-engines model.
- **E-commerce**: UCP `"version": "1.0"` → **date-based** (current `2026-04-08`) with canonical URLs; **AP2 donated to FIDO** (2026-04-28); Universal Cart / Native-vs-Embedded checkout / Lodging+Food verticals.
- **Content/E-E-A-T**: removed the fabricated "December 2025 watershed / 71-67-52% drops" claim; set the plugin's internal E-E-A-T scorecard weights to **20/25/25/30** (Trust highest) — an internal scoring model; Google publishes no numeric E-E-A-T weights, only that 'trust is most important'.
- **Schema**: Dataset is **not discontinued** (Dataset Search still consumes it); corrected the deprecated-types tooling-removal timeline.
- **Technical**: softened mobile-first absolutism + added content-parity; added the **back-button hijacking** spam policy; page-experience framing; Googlebot **2MB/64MB** fetch limits; crawling-docs migration to developers.google.com/crawling; user-triggered fetchers (Google-Agent etc.) ignore robots.txt.
- **Verticals**: JPEG XL shipped (Chrome 145, flag-gated); two new IPTC DigitalSourceType values; hreflang ISO-15924 script subtags + signal hierarchy; sitemap 50MB/extension-subtype rules; **Apple Business** rename; Ask Maps / AI local pack.
- **Ledger**: refreshed `data/google-updates.json` (Feb 2026 Discover, March 2026 spam, May 2026 core completion, back-button policy, GSC gen-AI report, etc.); fixed the INP date and replaced 301'd `ranking-update-history` URLs with the Search Status Dashboard.

### Added

- `seo-google`: Search Console **Generative AI performance report**, GSC impressions logging-error caveat (2025-05-13 → 2026-04-27), GA4 **AI Assistants** channel.
- `scripts/iptc_ai_label.py`: `algorithmicMedia` and `compositeWithTrainedAlgorithmicMedia` DigitalSourceType values.
- Documentation: primary-source reconfirmation details folded into public references.

### Fixed (command audit)

Full audit of every `/seo` command + subcommand (25 skills + 8 extensions), via deterministic wiring checks + 5 Codex sub-agents; findings were folded into this release.

- **Wiring bugs:** `seo-sxo` agent called `parse_html.py "<url>"` (script needs `--url`); `seo-sxo` and `seo-local` referenced DataForSEO tools not in the catalog (`google_organic_serp`/`keyword_data`/`local_business_data`/`google_local_pack_serp`/`business_listings` → `serp_organic_live_advanced` / `kw_data_google_ads_search_volume` / `business_data_business_listings_search`); `content-brief` used `serp_google_organic_live_advanced` → `serp_organic_live_advanced`; Bing `submit-batch`/`verify-indexnow` were missing the required `--host` flag.
- **Broken docs:** `docs/COMMANDS.md` google examples used non-existent command names (`psi`/`gsc-queries`/`indexing-notify`/`ga4-organic`/`check`) → real `pagespeed`/`gsc`/`inspect`/`index`/`ga4`; maps used `geogrid`/`audit` → `grid`/`gbp`; "7 specialist subagents" → "up to 15".
- **Shared-reference paths:** `seo-schema`/`seo-backlinks` pointed at `` `references/...` `` as if local → repointed to the shared `seo/references/` location.
- **COMMANDS.md completeness:** documented every previously-unlisted subcommand (backlinks, ecommerce, dataforseo cost/serp-images, flow, cluster, sxo, hreflang, images) and added the missing extension command tables (ahrefs, bing, profound, seranking, unlighthouse). Coverage now 100% (every skill subcommand is indexed).

### Fixed (docs consistency)

Reconciled the public docs/manifests with the v2.1.0–v2.2.1 code state via a parallel per-file pass with an independent verifier gate. No behavior change.

- **README.md:** added a "Since v2.0.0" recap (v2.1.0–v2.2.1); reframed the command surface to **30 user-invocable `/seo` commands** and added the five missing extension commands (`ahrefs`, `seranking`, `profound`, `bing`, `unlighthouse`) to the table; corrected stale figures: DataForSEO `22 → 23` commands, manifest `14 → 15` assertions, audit fan-out "6 parallel" → "up to 15 core audit agents; optional extension agents such as seo-dataforseo may run in addition", and the v2 test narrative to `39 → 326` (url_safety suite = 91 cases); reworded the "zero-network" overclaim (audits still fetch target URLs) and the Playwright optional/auto-install wording.
- **docs/COMMANDS.md:** added the five extension commands to the Quick Reference table (detail sections already existed).
- **docs/ARCHITECTURE.md:** extension tree and capability table now cover all **8** extensions (added Ahrefs, SE Ranking, Profound, Bing Webmaster, Unlighthouse).
- **PRIVACY.md:** data-transfer disclosure for the five newer extensions (Unlighthouse marked local-only — no third-party egress); same zero-network reword.
- **SECURITY.md:** reconciled the internal `tests/test_url_safety.py` count contradiction (`52+` vs `122`) to the verified **91 cases (31 functions)** in both places.
- **CONTRIBUTING.md:** corrected the SSRF guidance — fetchers route through `scripts/url_safety.py` (`validate_url()` / `safe_requests_session()`), not `google_auth.py` (OAuth-only).
- **AGENTS.md:** removed the non-existent "ASO" extension (listed the real 8); added `seo-content-brief` and `seo-flow` to the tree and command table.
- **Other docs:** `MIGRATION-v1-to-v2.md` ("Three" → six rich-result types + v2.1–2.2.1 forward pointer), `MCP-INTEGRATION.md` (DataForSEO `22 → 23`), `TROUBLESHOOTING.md` (schema false-positive note now covers the 2025 retirements + the 2026-05-07 FAQ retirement), `INSTALLATION.md` (Playwright wording), `WORKFLOW-public-private.md` (state section refreshed to v2.2.1 / 2026-06-22).
- **`.claude-plugin/marketplace.json`:** descriptions refreshed for the 2.1–2.2.1 currency + command audit, and both trimmed under the 500-char registry cap (the plugin-entry description was previously over cap at 573).
- **`extensions/dataforseo/`:** `README.md`, `install.sh`, and `install.ps1` corrected `22 → 23` commands.

### Fixed (fact accuracy)

Corrections from a live re-confirmation of every time-sensitive Google claim against Google-primary sources fetched 2026-06-22. Confirmed claims were updated and uncertain claims relabeled. All are precision/labeling fixes — the v2.2.1 currency substance was confirmed accurate.

- **E-E-A-T weights are an internal model, not Google's.** Google publishes no numeric E-E-A-T weights (only "trust is most important"). Relabeled the 20/25/25/30 split as the plugin's own scoring model in `agents/seo-content.md`, `skills/seo-content/SKILL.md`, README, and this changelog.
- **FID was never in Lighthouse.** Removed "Lighthouse" from the FID-removal tool list across 7 files (it is a lab tool and never reported the field-only FID metric); the removal applies to Chrome's field-data tools (CrUX API, PageSpeed Insights).
- **QAPage is not the "FAQ replacement."** Reworded README + the v2.1.0 changelog note: QAPage is the type for genuine Q&A pages, not a replacement for FAQ rich results (per the primary `qapage` doc).
- **June 2025 deprecation date** corrected `2025-06-19 → 2025-06-12` (announcement date) in `data/google-updates.json` and the deprecated-types reference.
- **January-2026 tooling sunset scoped to Practice Problems** (the only type Google documents it for) in the deprecated-types reference, instead of generalizing it to all retired types.
- **Dead citation repaired:** the HowTo retirement source `…/2023/09/structured-data-changes` (HTTP 404) repointed to the real post `…/2023/08/howto-faq-changes`.

## [2.2.0] - 2026-06-12

Security, cross-platform, and data-accuracy release. Folds the v2.1.0 currency content into the first public ship and closes the full open-issue and PR backlog. No breaking changes.

### Security

- **Installer credential injection (blocker).** The DataForSEO, Firecrawl, and Banana installers interpolated user-supplied credentials into a `python3 -c` source string, allowing arbitrary code execution at install time when a credential contained `'''`. Credentials now pass as `argv` through a quoted heredoc, and the settings file is written atomically with `0600` permissions (shell installers plus the DataForSEO PowerShell installer). Found by an independent audit.
- **SSRF parser-differential bypass.** `url_safety.validate_url` accepted authority-confusion URLs such as `https://127.0.0.1:6666\@1.1.1.1`, which `requests` connects to the internal host. The validator now rejects backslash and userinfo authority confusion, covering every caller. Reported by @Fushuling (#110).
- **Google API key leak.** `pagespeed_check`, `crux_history`, `nlp_analyze`, and `lcp_subparts` put the API key in the request URL and echoed it on error. Keys now travel in the `X-Goog-Api-Key` header with redacted error output. Reported by @webgunnz (#122); header approach from #104 (@fayerman-source).
- **Post-audit hardening pass.** Extended the credential-injection fix to the extension uninstallers and the Banana config probe (argv through quoted heredocs). Added Bing Webmaster API key redaction on transport errors. Switched the DataForSEO and Firecrawl PowerShell installers from `PtrToStringAuto` to `PtrToStringBSTR` so SecureString credentials decode correctly under PowerShell on Linux and macOS.
- **Secret-scan CI gate.** A new job in `ci.yml` and `v2.yml` fails the build when any tracked file contains a high-signal credential pattern (Google, GitHub, AWS, Google OAuth, OpenAI, Slack); test fixtures and documented placeholders are allowlisted. `.gitignore` extended to cover more credential and key formats. Verified against the full history and tracked tree: no real secret present.

### Fixed

- **GSC false "0 clicks" totals (#130).** Site totals were summed from per-query rows, which GSC anonymizes for low-volume queries. Totals now come from a dimensionless aggregate query. Reported by @fayerman-source.
- **Windows drift_baseline portability (#114, #124).** Removed `/dev/stdout`, use a tempfile fetch-to-parse handoff with `errors="replace"`, and handle the Microsoft Store Python alias (PRs #117, #128, #111, #115, #125).
- **Cross-platform PostToolUse hook (#102, #112, #120).** The JSON-LD validator runs through a Node launcher that resolves `python3`/`py`, fixing failures on macOS and Linux without a bare `python` (PR #101).
- **fetch_page UTF-8 double-encode (#121).** Honor the Content-Type and `<meta>` charset deterministically when the server omits a charset.
- **GSC deprecated `indexed` field (#113).** No longer surfaced (it always returned 0).
- **NLP entity metadata (#103).** Use the V1 `analyzeEntities` endpoint so Knowledge Graph `mid`/`wikipedia_url` and salience are returned.
- **Moz free-tier auth (#100).** Use the Links API REST endpoint with HTTP Basic auth.
- **FAQ schema hook.** FAQPage is no longer flagged (FAQ rich results were retired in May 2026, but the markup still aids AI Mode); deprecated and retired types still block.
- **Broken sub-skill reference paths.** `/seo local` and `/seo maps` instructed the model to load `references/*.md` from directories that do not exist; both now point to the shared `skills/seo/references/` files they always intended.
- **seo-cluster template now ships.** `templates/cluster-map.html` was excluded by an over-broad `.gitignore` rule, so installed users never received the interactive cluster visualization. It is now tracked.
- **Unlighthouse and Ahrefs extension invocations.** The Unlighthouse extension called a non-existent npm package (`unlighthouse-cli`); it now uses `unlighthouse@0.13.5`. The Ahrefs extension is pinned to `@ahrefs/mcp@0.0.11` and invokes the package's real `mcp` binary.
- **FLOW prompt dead links.** 82 links across the 41 FLOW prompt files pointed at the upstream folder layout that does not exist in this plugin. `sync_flow.py` now rewrites them to the flattened layout on every sync, and the existing files were repaired.
- **sync_flow offline crash.** `--dry-run` raised an uncaught network error when GitHub was unreachable; it now exits cleanly with an actionable message.
- **Install slug and stale figures.** Corrected the marketplace slug in the install docs to `claude-seo@agricidaniel-claude-seo`, the `CITATION.cff` release date, the README test count (326), the AGENTS.md script count (50), and the README FAQ guidance.

### Added

- Full-audit report persistence and audit-aware report builders (#51, #61).
- ruff configuration (#123) and `pyproject.toml` authors and keywords (#118).
- Regression tests for installer injection, GSC totals, and the schema hook policy.

### Changed

- Plugin description trimmed under the 500-character registry cap (#99).
- Docs normalized from bare `python` to `python3`; CLAUDE.md and AGENTS.md script inventory corrected to 50; README test count updated.
- Corrected the inert `user-invokable` frontmatter key to `user-invocable`.
- Pinned the Ahrefs, Unlighthouse, and DataForSEO npm packages to exact versions across installers and prewarm steps.
- Documented the `/seo content-brief` command in the command reference and README, added `/seo flow` to the project command table, and reconciled the command count to the 25 the orchestrator routes.

### Housekeeping

- Removed the duplicate root `CODEOWNERS`; CI compiles every `scripts/*.py` dynamically; marketplace extension count corrected from 7 to 8; dependency floor bumps (Dependabot #105 to #109, #116).
- Removed the orphaned `branding/` preview tooling (it referenced deleted diagram assets) and the inactive npm Dependabot watcher (the repo ships no npm manifest). Hardened the Python hook probe against environment-specific `EPERM`, gave Banana `validate_setup.py --help` proper argument handling, and repaired stale internal documentation links. Full suite at 326 passing.

## [2.1.0] - 2026-05-25

Knowledge-currency refresh for Google's May 2026 wave: the **May 2026 core update**, **Google I/O 2026** (Gemini 3.5 Flash now powers AI Mode globally; AI Mode past 1B monthly users), and the **May 7 2026 retirement of FAQ rich results**. No architecture, API, or command changes — every v2.0.0 entry point still works.

### Added

- **`data/google-updates.json`:** four primary-source-verified entries — March 2026 Core Update (promoted from `unverified[]` after Google status-dashboard confirmation; Mar 27 to Apr 8 rollout), FAQ rich result retirement (May 7), Google I/O 2026 / Gemini 3.5 Flash in AI Mode (May 19), and the May 2026 Core Update (May 21). `unverified[]` is now empty; `last_verified` bumped to 2026-05-25.
- **`skills/seo-geo/SKILL.md`:** AI Mode is now modeled as a **distinct citation engine** from AI Overviews (Ahrefs: only 13.7% URL overlap across 540K query pairs), with its own row in the platform table, the Gemini 3.5 Flash + 1B-user stats, content **recency** as a citation lever (~3x for content under 3 months, SE Ranking), and the "~44% of AI citations come from the first 30% of the page" finding.
- **`skills/seo/references/schema-types.md`:** `QAPage` added as the active type for genuine user Q&A (the active type for real Q&A pages — not a replacement for FAQ rich results).
- **`tests/test_schema_v2.py`:** `test_faq_rich_results_retirement_documented` locks the May 7 2026 FAQ retirement + QAPage-for-Q&A guidance across the canonical schema references.

### Changed

- **FAQ schema guidance** corrected across the canonical sources (`schema-types.md`, `deprecated-types-2024-2026.md`, `seo-schema/SKILL.md`, `agents/seo-schema.md`, `seo/SKILL.md`, `seo-page/SKILL.md`, `seo-content/SKILL.md`, `seo-plan/assets/saas.md`): FAQ rich results are **fully retired for all sites as of May 7, 2026**, superseding the Aug 2023 gov/health framing. FAQPage stays Info-priority as an AI/entity signal (never a Critical removal); `QAPage` is the type for genuine Q&A pages.
- **`skills/seo-content/SKILL.md`:** AI Mode description updated to the Gemini 3.5 Flash / 1B-user / two-citation-engine reality.
- Version bumped to `2.1.0` across `plugin.json`, `pyproject.toml`, `CITATION.cff`, `install.sh`, `install.ps1`, and 32 SKILL.md files (`seo-content-brief` stays at 1.0.0 per COMMUNITY_OVERRIDES). Gated by `tests/test_manifest_consistency.py`.

## [2.0.0] - 2026-05-17

v2 is backward-compatible by design — every v1.x command, script signature, and skill entry point still works. The release lands a hardened SSRF + DNS-rebinding safety layer, shared headless rendering across every fetcher, QRG-aligned content gates, four new Schema.org generators, five new MCP extensions, and multi-platform portability. Full narrative in [`docs/MIGRATION-v1-to-v2.md`](docs/MIGRATION-v1-to-v2.md).

### Highlights

- 248 tests (6.4× the v1.9.9 baseline of 39), every known SSRF bypass class closed at parse time.
- 5 new MCP extensions: Ahrefs, SE Ranking, Profound, Bing Webmaster, Unlighthouse.
- 4 new Schema.org generators: Reservation, OrderAction (potentialAction), DiscussionForumPosting, ProfilePage.
- Multi-platform portability for Codex CLI, Cline, Aider (alongside existing Cursor + Antigravity).

### Added

- **Foundation:** `scripts/url_safety.py` (canonical SSRF + DNS-rebinding module, 83 test cases), `scripts/render_page.py` (shared Playwright Chromium renderer with `--mode auto` SPA detection, trafilatura extraction, htmldate publication-date extraction, 27 test cases). 8 fetcher subagents (seo-technical, seo-content, seo-schema, seo-geo, seo-local, seo-ecommerce, seo-backlinks, seo-sxo) now route through `render_page`.
- **Content quality:** `content_quality.py` (QRG filler / AI-pattern / information-density scorer), `content_humanize.py` (40+ deterministic AI-phrasing replacements), `content_verify.py` (claim extraction + citation-gap detection), `domain_history.py` (WHOIS-driven expired-domain abuse check), `seo_updates.py` + `data/google-updates.json` (18 primary-source-verified Google updates, 1 documented-unverified gap-analysis claim).
- **Technical depth:** `preload_check.py` (Speculation Rules + bfcache + prerender + LCP preload audit), `indexnow_submit.py` (Bing/Yandex/Seznam/Naver IndexNow submitter), `lcp_subparts.py` (LCP decomposition via CrUX), `unlighthouse_run.py` (multi-page Lighthouse via Unlighthouse CLI).
- **Schema completeness:** `schema_generate.py` (`reservation`, `order`, `discussion`, `profile` subcommands), `schema_ecommerce_validate.py` (Product schema policy validator: `hasMerchantReturnPolicy`, `shippingDetails`, `MemberProgram`, EU `energyEfficiencyClass`, `ProductGroup`), reference doc `skills/seo-schema/references/deprecated-types-2024-2026.md`.
- **AI search:** `parasite_risk.py` (site-reputation-abuse risk scanner per Nov 2024 Google policy), `skills/seo-geo/references/llmstxt-evidence.md` (evidence-based reframe of llms.txt as dev-tooling, not citation lever).
- **Local + international + privacy:** `gbp_deprecation_lint.py` (retired GBP chat / `.business.site` / Q&A detector), `skills/seo-google/references/dma-consent-mode-v2.md` (EU CTR diagnostic + softened cookieless framing), `skills/seo-hreflang/references/machine-translation-qa.md` (untranslated-MT detection per Jan 2025 QRG §4.6.5).
- **Portability:** `portability_check.py` (cross-platform SKILL.md frontmatter lint), AGENTS.md tool-name compatibility table for Codex CLI, Cline, Aider.
- **Release signing:** `release_sign.py` (SHA-256 manifest of every git-tracked file), `verify_release.py` (verify a checkout against a signed manifest).
- **Governance:** `.github/CODEOWNERS`, `.github/dependabot.yml` extended with npm ecosystem, `.github/workflows/v2.yml` (workflow_dispatch only), `SECURITY.md` uplift (threat model, 90-day coordinated disclosure timeline, residual risks).

### Changed

- `scripts/google_auth.py:validate_url` now delegates to `url_safety.validate_url`. Strict variant available as `url_safety.validate_url_strict`.
- `scripts/fetch_page.py` exposes `--render {auto,always,never}`. Default `auto` runs raw fetch then renders if SPA signals detected; `always` forces Playwright; `never` preserves v1 behaviour.
- `scripts/capture_screenshot.py` uses `url_safety.make_safe_playwright_route_handler` as defense-in-depth against subresource SSRF (data: allowed, private resolutions aborted, AF_UNSPEC IPv6-aware).
- OAuth token files are now written with `os.open(path, O_WRONLY|O_CREAT|O_TRUNC, 0o600)` + explicit `os.fchmod(fd, 0o600)`. Legacy `0o644` files are remediated in place on next `_load_oauth_token`.
- `plugin.json` / `marketplace.json` / `pyproject.toml` / `CITATION.cff` / `install.sh` / `install.ps1` / 32 SKILL.md files: version bumped to `2.0.0`. The 13-assertion manifest test (`tests/test_manifest_consistency.py`) gates this.

### Fixed

- **HIGH — DNS rebinding via redirect target.** `_pin_dns` previously intercepted only the originally-pinned hostname; redirect targets fell through to the unpatched resolver. Patched `socket.getaddrinfo` now validates every resolution while pinned. Closed in `a601268`.
- **HIGH — Obfuscated IPv4 bypass in `validate_url`.** Decimal (`2130706433`), hex (`0x7f000001`), octal (`017700000001`), leading-zero (`127.0.0.001`, `0177.0.0.1`), and mixed-radix (`0x7f.0.0.1`) forms all returned safe. New `normalize_hostname()` canonicalizes via `socket.inet_aton`. Closed in `3c595c2`.
- **HIGH — FQDN trailing-dot bypass.** `metadata.google.internal.` (single trailing dot) bypassed the exact-string blocklist. `normalize_hostname` now strips a single trailing dot. Closed in `3c595c2`.
- **MEDIUM — IPv6 blind spot in Playwright route handler.** Resolver queried only `AF_INET`. Now uses `AF_UNSPEC` to catch dual-stack subresources whose AAAA record points at a private range. Closed in `3c595c2`.
- **LOW — OAuth file-permission TOCTOU.** `os.open`'s mode argument is ignored if the file pre-existed. Explicit `os.fchmod(fd, 0o600)` on the open fd closes the race. Closed in `3c595c2`.

### Breaking

Two intentional behavioural breaks; full mitigation guidance in `docs/MIGRATION-v1-to-v2.md`.

1. `scripts/backlinks_auth.py` no longer ships a silent SSRF-disabled fallback. If `url_safety` cannot be imported, the module raises `RuntimeError` at import time.
2. `seo-schema` flags six retired rich-result types as **Critical** findings (`Vehicle`, `ClaimReview`, `EstimatedSalary`, `LearningVideo`, `SpecialAnnouncement`, `CourseInfo` carousel). Replacements documented in `skills/seo-schema/references/deprecated-types-2024-2026.md`.

### Test coverage delta

| Suite | v1.9.9 | v2.0.0 |
|---|---:|---:|
| Pre-existing (manifest + lazy + sync FLOW) | 39 | 39 |
| `url_safety` (new) | — | 83 |
| `render_page` (new) | — | 27 |
| Content quality (new) | — | 25 |
| Technical depth (new) | — | 17 |
| Schema v2 (new) | — | 17 |
| Parasite risk + extensions (new) | — | 22 |
| GBP lint + polish (new) | — | 8 |
| Portability (new) | — | 10 |
| **Total** | **39** | **248** |

## [1.9.9] - 2026-05-11

Final 1.x patch release. v2 is in design; this release leaves the v1.x
branch in a clean, well-documented, dependency-current state.

Independently verified across 5 rounds of GPT-5.5 xhigh code review via
the Codex CLI before each PR push. Issue #92 + issue #41 closed.

### Highlights
- Five top-level versions, 24 in-tree skills, 3 extension SKILL.md files,
  and both install scripts triangulate to `1.9.9` atomically. CI guard
  extended from 9 to 13 assertions covering the orchestrator SKILL.md,
  per-skill `metadata.version`, marketplace.json metadata.description + author
  parity, and Sub-Skills/Subagents list consistency with disk.
- Five Dependabot dependency floor bumps merged as one batched PR after
  isolated-venv smoke-testing of the full API surface we actually use.
- Image audit now correctly detects JS lazy-loaders (Perfmatters, EWWW,
  generic) rather than reporting "not lazy-loaded" on heavily-optimized
  WordPress sites.

### Fixed

- **Orchestrator drift in `skills/seo/SKILL.md`** (issue #92): line 9
  `metadata.version: "1.9.6"` was stale; descriptive headline at lines 19-21
  still claimed "21 specialized sub-skills"; Sub-Skills numbered list at
  176-199 included `seo-firecrawl` (which is an extension, not in `skills/`)
  and was missing `seo-content-brief` (the PR #56 contribution). Subagents
  bullet list had the same drift pattern (included `seo-firecrawl`, no agent
  file on disk; missing `seo-flow`, file exists). Reconciled. Numbered list
  now reaches 24 (the orchestrator itself is the 25th in `skills/` but does
  not orchestrate itself), `seo-firecrawl` moved to a new "Optional
  Extensions" subsection, Subagents list now matches `agents/seo-*.md` set
  exactly.
- **`marketplace.json` drift** (issue #92): `metadata.description` was
  missing the "sub-agents" count claim that `plugins[0].description` carried;
  plugin entry had no `author` object despite v1.9.8 release notes claiming
  one was added in commit `8514999` (verification showed it was not). Both
  fixed. v1.9.8 entry in this CHANGELOG corrected to reflect what actually
  shipped.
- **`AGENTS.md:109`** said "17 subagents"; disk has 18. Fixed.
- **`install.sh` and `install.ps1` default tag pinned to `v1.9.0`** across 4
  missed release bumps (v1.9.5/.6/.7/.8). Anyone running
  `curl -fsSL .../install.sh | bash` got the April 14 release, missing FLOW
  integration, the security audit pass, doc reconciliation, the manifest CI
  guard plus v1.9.8 Phase B bug fixes (Windows hook, OAuth refresh, missing
  imports, None guards). Bumped to `v1.9.9` atomically with this release.
- **`pyproject.toml`** had drifted to `1.9.6` while plugin.json + CITATION
  shipped at 1.9.8. Bumped to 1.9.9 with the release.
- **23 in-tree skill `metadata.version` fields** were stuck at `1.9.6`; 3
  extension SKILL.md files were at `1.9.0`/`1.7.2`. All bumped to `1.9.9`.
  `seo-content-brief` deliberately stays at `1.0.0` (community contribution,
  CI allowlist).
- **Image audit (issue #41)**: `scripts/parse_html.py` now classifies each
  image's lazy-loading mechanism in a `lazy_method` field with five values:
  `native | perfmatters | ewww | js-generic | none`. Sites running Perfmatters,
  EWWW Image Optimizer, lazysizes, vanilla-lazyload, or jQuery lazy-loaders
  are no longer mis-reported as "not lazy-loaded". `skills/seo-page/SKILL.md`
  and `skills/seo-images/SKILL.md` are updated to consume the new field.

### Added

- **CI guard extension (9 -> 13 assertions)** in
  `tests/test_manifest_consistency.py`:
  - `test_orchestrator_sub_skills_list_matches_disk`: Sub-Skills list must
    equal `set(skills/*) - {seo}`; no duplicates. Regex scoped to the
    `## Sub-Skills` section via a new `_extract_section()` helper.
  - `test_orchestrator_subagents_list_matches_disk`: Subagents bullet list
    must equal `set(agents/seo-*.md)`; no duplicates. Bullet-anchored regex.
  - `test_skill_metadata_versions_match_plugin_json`: every
    `skills/*/SKILL.md` and `extensions/*/skills/*/SKILL.md` `metadata.version`
    must equal `plugin.json` version, with `COMMUNITY_OVERRIDES` allowlist
    `{"seo-content-brief": "1.0.0"}`. Scoped to YAML frontmatter only via
    a new `_extract_frontmatter()` helper, so a fenced code example showing
    `version: "..."` cannot satisfy the check.
  - `test_marketplace_metadata_and_author_parity`: marketplace.json
    `metadata.description` includes both counts and they match plugin.json;
    plugin entry `author` parities plugin.json author for `name`, `email`,
    AND `url`.
- **`tests/test_lazy_detection.py`** (new): 11 unit tests covering all
  `_detect_lazy_method()` branches plus an integration check on `parse_html()`.
- **CI workflow** (`.github/workflows/ci.yml`): test job now installs
  `beautifulsoup4` alongside `pytest`, required by the new lazy-detection
  test that exercises real BeautifulSoup parsing.

### Changed

- **5 Python dependency floor bumps** (batched as a single PR after isolated-
  venv smoke testing — see [PR #94]):

  | Package | Floor before | Floor after | Source PR |
  |---|---|---|---|
  | `playwright` | 1.56.0 | 1.59.0 | #80 |
  | `weasyprint` | 61.0 | 68.1 | #78 |
  | `openpyxl` | 3.1.0 | 3.1.5 | #76 |
  | `google-api-python-client` | 2.100.0 | 2.196.0 | #77 |
  | `google-auth-oauthlib` | 1.0.0 | 1.4.0 | #79 |

  All five upper bounds preserved. No CVE-driven escalations.

  **Caveat**: `google-auth-oauthlib` 1.4.0 drops Python 3.9 support. This
  repo's `pyproject.toml` requires Python `>=3.10` already, so no impact for
  the declared support matrix. External consumers still on 3.9 should pin
  `google-auth-oauthlib<1.4.0` themselves.

### Deferred to v2

The following items are out of scope for v1.9.9 to keep this a clean patch
release. v2 will be a separate design conversation:

- **#11** SPA / CSR audit support (7-phase implementation; PR #90 Limitations
  section remains the patch-appropriate response)
- **#51** Subagent research persistence (changes documented output contract
  across 15 agent files; v2 will define a persistence convention shared by
  `seo-audit`, `seo-drift`, `seo-cluster`)
- **#61** `google_report.py --type full` audit-schema handling (no regression
  baseline fixture corpus exists; v2 will ship one with the bug fix)
- **#89** uv adoption (issue itself labels v2.x candidate; preserves
  `requirements.txt` format as migration headroom)
- **#53** seo-notebooklm skill (depends on unofficial wrapper, 536 lines of
  unreviewed credential code; v2 will define an "experimental skills" tier)
- **PR #46** path resolution + macOS SSL: `pip-system-certs` is a new
  dependency that violates v1.9.9's no-new-deps non-goal. v2 will land the
  full macOS support story.

### Compatibility / migration

- No breaking changes. Patch release per SemVer.
- The orchestrator's Sub-Skills numbered list was renumbered (insertion of
  `seo-content-brief`, removal of `seo-firecrawl`). Any downstream consumer
  that referenced sub-skills by **index** rather than **name** would break;
  grep found no such consumer in this repo, but third-party docs that
  hard-coded "skill 21 is seo-firecrawl" would need updating.
- `/seo audit` still does NOT persist subagent research/findings between
  runs (this is the intentional v1.x contract; v2 will revisit per #51).

## [1.9.8] - 2026-05-09

### Fixed
- **Skill-count drift returned via PR #56.** When the `seo-content-brief` skill
  was merged into v1.9.7 it added a 21st core skill, but the manifest
  reconciliation in v1.9.7 had locked the canonical phrasing at "20 core" and
  was not re-run after Phase C. Result: plugin.json, marketplace.json,
  README.md, CLAUDE.md, AGENTS.md, and docs/ARCHITECTURE.md all under-claimed
  by one. Reconciled to "25 sub-skills (21 core + 1 orchestrator + 1 framework
  integration + 2 extension mirrors)".

### Added
- **`tests/test_manifest_consistency.py`**: pytest suite that asserts
  plugin.json + marketplace.json claimed counts match the actual on-disk
  count of `skills/*/SKILL.md` and `agents/seo-*.md`, that plugin.json and
  marketplace.json descriptions agree on the canonical math, that user-visible
  docs (README, CLAUDE.md, AGENTS.md) reference the same skill count, and that
  plugin.json `version` and CITATION.cff `version` triangulate. Closes the
  systemic gap that allowed two skill-count drift incidents in v1.9.7.
- **`pytest tests/` job in `.github/workflows/ci.yml`**: runs the new manifest
  consistency suite on every push to main and every pull request, gating
  future skill additions behind matching documentation updates.

### Changed
- **`uninstall.sh` and `uninstall.ps1` now use glob enumeration** rather than a
  hardcoded skill list. The previous scripts had been frozen at v1.4.0-era
  state and missed 12 sub-skills and 11 sub-agents added between v1.5 and
  v1.9.8 (`seo-backlinks`, `seo-cluster`, `seo-content-brief`, `seo-dataforseo`,
  `seo-drift`, `seo-ecommerce`, `seo-flow`, `seo-google`, `seo-image-gen`,
  `seo-local`, `seo-maps`, `seo-sxo` and the corresponding agents). Anyone who
  ran the old uninstaller got half a cleanup. Glob enumeration auto-tracks
  future skill additions without requiring uninstaller maintenance. Sandbox
  test confirms the new scripts remove every `seo` and `seo-*` skill plus
  every `seo-*.md` agent while leaving sibling skills (e.g. `blog-writer`,
  `security`) untouched.
- This release rolls forward two commits that landed on main after the v1.9.7
  tag was cut:
  - `8514999`: marketplace metadata polish (added `category: "marketing"`,
    `homepage: https://claude-seo.md`, and a 14-keyword array to the
    marketplace.json plugin entry). The `author` object for the plugin entry
    was intentionally scoped here too but did not land in this commit; it
    lands in v1.9.9 (issue #92).
  - `66a7485`: em-dash sweep on user-visible AGENTS.md and CHANGELOG.md
  Both were intentionally scoped at v1.9.7 but landed post-tag. v1.9.8 captures
  them properly.

## [1.9.7] - 2026-05-09

### Fixed
- **Skill-count drift across 5 manifests**: `plugin.json` ("20 core sub-skills"),
  `marketplace.json` ("21 core sub-skills"), `CLAUDE.md` line 7 ("21 core sub-skills"),
  `AGENTS.md` line 8 ("20 core sub-skills") + line 84 ("23 skills"), and `README.md`
  line 7 ("21 core sub-skills") all contradicted each other. Reconciled to canonical
  phrasing: "24 sub-skills (20 core + 1 orchestrator + 1 framework integration +
  2 extension mirrors)".
- **Sub-agent count drift**: `CLAUDE.md` claimed "16 core subagents (+ 2 extension
  agents, 18 total)" while `AGENTS.md` claimed "15 core subagents (+ 2 extension
  agents, 17 total)". Reconciled to: "18 sub-agents (15 core + 1 framework integration +
  2 extension mirrors)".
- **`CLAUDE.md` self-contradiction**: line 23 stated `plugin.json (v1.9.0)`; updated
  to current `v1.9.7`.
- **`marketplace.json` description fields**: both `metadata.description` (top-level)
  and `plugins[0].description` now use canonical phrasing.
- **`CITATION.cff` version drift**: was stuck at `1.8.2` (six minor versions behind);
  bumped to match `plugin.json` at `1.9.7` with current release date.

### Added
- **`.github/dependabot.yml`**: weekly Dependabot updates for pip and GitHub Actions
  ecosystems (closes supply-chain hygiene gap).
- **`CODE_OF_CONDUCT.md`**: Contributor Covenant 2.1, closing GitHub Community
  Standards gap.
- **`.github/workflows/ci.yml` `permissions:` block**: restricts `GITHUB_TOKEN` to
  `contents: read` at workflow root (least-privilege; was previously default scope).

### Changed
- Patch release driven by repository hygiene + marketplace-readiness preparation.
  No skill behavior changes, no breaking changes, no script changes.

### Removed
- **`translations/uk/`**: the Ukrainian localization (originally contributed by
  @edocltd in PR #50, shipped in v1.9.0) has been retired. The translation drifted
  across v1.9.0 to v1.9.7 with no maintenance signal, and a partially translated set
  is worse than no translation at all when readers cannot tell what is current.
  @edocltd's contribution remains credited in `CONTRIBUTORS.md`. If a maintained
  translation is desired in the future, it should land via a contributor who can
  commit to keeping it in sync release over release.

## [1.9.6] - 2026-04-26

### Security
- **VULN-A01 (HIGH):** Removed `Bash` from `seo-flow` agent tool grant, agent no
  longer has shell access, eliminating prompt-injection-to-shell attack surface
- **VULN-A02/A07 (MEDIUM/LOW):** Switched `sync_flow.py` to anonymous-first GitHub API
  requests; PAT only used as 403-triggered fallback, eliminates token-on-redirect leak
- **VULN-A03 (MEDIUM):** Added `Path.resolve()` containment check in `record_write()`,
  blocks path-traversal writes outside the skill reference directory
- **VULN-A04 (MEDIUM):** Introduced `flow-prompts.lock` SHA-256 baseline file; sync now
  diffs against baseline and reports upstream drift before writing
- **VULN-A05 (MEDIUM):** Added explicit "WebFetch is untrusted" security rule to agent
  body, agent warned not to execute or relay fetched content verbatim
- **VULN-A06 (LOW):** `gh` CLI absence now degrades to anonymous API rather than
  hard-exiting, sync works without gh CLI on public repos
- **VULN-A08 (LOW):** All file writes are now atomic (tempfile + shutil.move),
  eliminates partial-write corruption on interrupt
- **VULN-A09 (LOW):** GitHub API responses capped at 5 MB with 15s timeout,
  prevents memory exhaustion from malformed or oversized API payloads
- **VULN-A10 (LOW):** URL allowlist validates every request targets `api.github.com`
  over HTTPS, blocks SSRF if `API_ROOT` constant is modified
- **INFO-A14:** Added CC BY 4.0 attribution header to `references/prompts/README.md`

### Tests
- Added 10 new unit/integration tests covering all above findings
- Test count: 5 → 15

## [1.9.5] - 2026-04-26

### Added
- **seo-flow**: FLOW framework integration, Find → Leverage → Optimize → Win. 41 evidence-led AI prompts (CC BY 4.0) bundled as `skills/seo-flow/references/prompts/` (find:5, leverage:1, optimize:21, win:3, local:11). Commands: `/seo flow [find|leverage|optimize|win|local|prompts|sync]`.
- **Context-matching orchestration**: `/seo flow optimize` selects 2-3 most relevant prompts from 21 based on URL industry signals and prior skill output, not a full dump.
- **`scripts/sync_flow.py`**: GitHub API sync script, pulls latest FLOW prompts, framework doc, and bibliography from AgriciDaniel/flow. Supports `--dry-run` and `--ref <sha>` pinning. Outputs JSON summary.
- **`agents/seo-flow.md`**: FLOW subagent, applies stage prompts to target URLs, returns structured evidence-tagged findings.
- **FLOW cross-references**: Integration notes added to seo-geo, seo-local, seo-content, and seo-cluster skills.

### License
- FLOW content bundled under CC BY 4.0. Attribution header on every prompt file (automated by `sync_flow.py`). Claude SEO's MIT license unchanged, applies to skill code only.

## [1.9.0] - 2026-04-14

### Added
- **seo-cluster**: SERP-based semantic topic clustering for content architecture (skill + 3 references + interactive cluster-map.html visualization + agent). Contributed by Lutfiya Miller (Pro Hub Challenge Winner).
- **seo-sxo**: Search Experience Optimization, reads SERPs backwards to detect page-type mismatches, derives user stories, scores pages from persona perspectives (skill + 4 references + agent). Contributed by Florian Schmitz.
- **seo-drift**: SEO drift monitoring, baseline, diff, and track changes to on-page SEO with 17 comparison rules across 3 severity levels. SQLite persistence (skill + 1 reference + agent + 4 Python scripts). Contributed by Dan Colta. Security-hardened: all curl usage eliminated, SSRF protection enforced.
- **seo-ecommerce**: E-commerce SEO, Google Shopping intelligence, Amazon marketplace analysis, product schema validation (skill + 1 reference + agent + 2 Python scripts). Contributed by Matej Marjanovic.
- **DataForSEO cost guardrails**: `scripts/dataforseo_costs.py` with threshold-based approval, session budget tracking, daily spend summaries. `references/cost-tiers.md` pricing table. Contributed by Matej Marjanovic.
- **seo-hreflang cultural profiles**: 4 cultural adaptation profiles (DACH, Francophone, Hispanic, Japanese) with locale format tables, content parity audit, and freshness tracking. 3 new reference files. Contributed by Chris Muller.
- **CONTRIBUTORS.md**: Community credits file for Pro Hub Challenge and PR contributors
- **AGENTS.md**: Multi-platform discovery file for Cursor/Antigravity (concept by Matej Marjanovic, rewritten for v1.9.0)
- **Schema templates**: Product (Full E-commerce) and ItemList (hub/pillar pages) added to `schema/templates.json`
- 5 new commands: `/seo cluster`, `/seo sxo`, `/seo drift baseline|compare|history`, `/seo ecommerce`

### Changed
- Orchestrator spawns up to 15 subagents (was 12): +seo-cluster, +seo-sxo, +seo-drift, +seo-ecommerce
- seo-hreflang SKILL.md enhanced with Cultural Adaptation Assessment, Content Parity Audit, and Locale Format Validation sections
- seo-dataforseo SKILL.md enhanced with Cost Guardrails section requiring cost checks before API calls
- All 23 SKILL.md files stamped to v1.9.0
- Install scripts (install.sh, install.ps1) pinned to v1.9.0
- plugin.json updated with 9 new keywords

### Community
- Pro Hub Challenge: Lutfiya Miller (Winner - Semantic Cluster Engine), Florian Schmitz (SXO Skill), Dan Colta (SEO Drift Monitor), Chris Muller (Multi-lingual SEO), Matej Marjanovic (E-commerce + Cost Config + Platform Support), Benjamin Samar (SEO Dungeon - reviewed)
- 5 out of 6 submissions scored Proficient or above
- See CONTRIBUTORS.md for full credits and original repo links

## [1.8.2] - 2026-04-10

### Added
- **Ukrainian localization**: first i18n, README, CONTRIBUTING, PRIVACY, SECURITY, INSTALLATION, TROUBLESHOOTING translated (PR #50)
- **Firecrawl extension section** in README with install and example commands
- **Backlink API privacy disclosures** in PRIVACY.md (Moz, Bing Webmaster, Common Crawl, verify crawler)
- 4 missing commands added to README table: `/seo backlinks`, `/seo firecrawl`, `/seo dataforseo`, `/seo image-gen`
- 6 missing scripts added to CI syntax check (backlinks_auth, moz_api, bing_webmaster, commoncrawl_graph, verify_backlinks, validate_backlink_report)
- 6 missing skill directories added to INSTALLATION.md manual uninstall list

### Fixed
- **Install scripts pinned to stale version**: REPO_TAG bumped from v1.7.2 to v1.8.2 in install.sh and install.ps1, new curl-based installs now get the current release
- **Supply chain risk in docs**: removed deprecated `irm | iex` pattern from docs/INSTALLATION.md, replaced with safe `git clone` + `powershell -File` method
- **Version sync**: pyproject.toml (1.7.2→1.8.2), CITATION.cff (1.7.2→1.8.2, date 2026-04-10), all 19 SKILL.md files
- **Python requirement**: pyproject.toml corrected from `>=3.11` to `>=3.10` (matches README and install scripts)
- **README architecture counts**: sub-skills "15+2" → "16+3", agents "10+2" → "11+2"
- **Orchestrator SKILL.md**: stale count "15+2" → "16+3" at line 119
- **CLAUDE.md**: sub-skill count 17→16 core, script count "20+2" → "21+2"
- **Extension install hang**: merged PR #43, npx pre-warm no longer starts MCP server binary

### Community
- Merged PR #43 (fix stuck extension install) by @olivierroy
- Merged PR #45 (correct sub-skills count) by @MalteBerlin
- Merged PR #50 (Ukrainian localization) by @edocltd
- Closed issue #42 (marketplace discovery, resolved)
- Reviewed PRs #47, #46, #30, #36 with detailed feedback

## [1.8.1] - 2026-04-06

### Added
- **Google Images SERP**: `/seo dataforseo serp-images <keyword>` command for competitive image search analysis
- **Image SERP Analysis**: `/seo images serp <keyword>` cross-skill command combining DataForSEO image results with on-page audit
- **Image File Optimization**: `/seo images optimize <path>` for WebP/AVIF conversion, IPTC/XMP metadata injection, responsive variants, and compression
- **Image ranking factors table**: documents what matters (alt text, filename, page context) vs what does not (EXIF camera data, IPTC keywords)
- **DataForSEO field-config**: `serp.items.images` filter with 10 SEO-relevant fields (type, rank, title, alt, url, source_url, image_url, domain, encoded_url)
- **Tool catalog reference**: `skills/seo-dataforseo/references/tool-catalog.md` for 35+ utility MCP tools (moved from inline list)
- **Table of Contents**: added to `seo-image-gen/references/prompt-engineering.md` (326 lines, per >300 line standard)
- Plugin keywords: `image-serp`, `google-images` added to plugin.json

### Fixed
- **Version mismatch**: unified all 19 SKILL.md files, plugin.json, and CLAUDE.md to v1.8.0 (was 1.7.0/1.7.2/1.8.0 three-way split)
- **Broken reference path**: seo-backlinks now correctly points to `skills/seo/references/backlink-quality.md` (shared reference)
- **Hardcoded absolute paths**: removed `~/.claude/skills/` from `agents/seo-visual.md`, `agents/seo-schema.md`, `skills/seo-image-gen/SKILL.md`, and banana extension copy (now use plugin-relative paths)
- **seo-dataforseo line count**: moved 35-line utility tools list to reference file, reduced from 416 to 380 lines

### Changed
- seo-images description: added trigger phrases for image SERP, metadata, WebP conversion
- seo-dataforseo description: added "Google Images" and image ranking trigger phrases
- seo orchestrator: updated images command to reflect new SERP + optimize capabilities
- CLAUDE.md: updated plugin version reference, images command description

## [1.7.2] - 2026-03-30

### Added
- **Firecrawl extension**: Full-site crawling, scraping, and site mapping via Firecrawl MCP (`extensions/firecrawl/`)
  - 4 commands: crawl, map, scrape, search
  - JS rendering support for SPA/CSR sites (addresses #11)
  - Cross-skill integration with audit, technical, sitemap, and content skills
  - Self-contained install/uninstall scripts (Bash + PowerShell)
- **Backlink analysis skill**: `skills/seo-backlinks/SKILL.md` with `/seo backlinks` command
  - 7-section analysis: profile overview, anchor text, referring domain quality, toxic links, top pages, competitor gap, new/lost links
  - Backlink health score (0-100) with weighted factors
  - Disavow recommendations with export format
  - Requires DataForSEO extension for live data
- **Backlink quality reference**: `skills/seo/references/backlink-quality.md` with 30 toxic link patterns, anchor text benchmarks by industry
- **Excel export**: `--format xlsx` option in `scripts/google_report.py`
  - Sheets: Summary, Queries, Pages, Indexation (conditional on data available)
  - Navy header styling matching PDF palette, auto-column-width, frozen headers, auto-filter
  - New format options: `xlsx`, `all` (pdf+html+xlsx)
- **Ecosystem cross-links**: AI Marketing Claude added to README and CLAUDE.md ecosystem sections

### Changed
- Sub-skill count: 18 -> 19 (added seo-backlinks)
- Extension count: 2 -> 3 (added Firecrawl)
- Orchestrator routing table updated with `/seo backlinks` and `/seo firecrawl` commands
- Audit orchestration: Firecrawl `map` used for URL discovery when available
- `requirements.txt`: added `openpyxl>=3.1.0` for Excel export

## [1.7.1] - 2026-03-30

### Fixed
- install.sh: broken skill copy path `seo/` corrected to `skills/seo/` (h/t @hieu-e via #39)
- install.sh: version tag pinned to v1.7.1 (was stuck at v1.6.0)
- install.ps1: version tag pinned to v1.7.1 (was stuck at v1.6.0)
- install.ps1: removed unnecessary `seo/` fallback path, uses `skills\seo` directly

### Changed
- CI: syntax check expanded from 4 to 15 Python scripts (all v1.7.0 Google API scripts now covered)

## [1.7.0] - 2026-03-28

### Added
- **Google SEO APIs skill**: `skills/seo-google/SKILL.md` with 21 commands across 4 credential tiers
- **Google subagent**: `agents/seo-google.md` for enriched audit data (CWV field data, indexation status, organic traffic)
- **11 Python scripts**: google_auth.py, gsc_query.py, gsc_inspect.py, pagespeed_check.py, crux_history.py, indexing_notify.py, ga4_report.py, google_report.py, youtube_search.py, nlp_analyze.py, keyword_planner.py
- **10 reference files**: auth-setup.md, search-console-api.md, pagespeed-crux-api.md, indexing-api.md, ga4-data-api.md, youtube-api.md, nlp-api.md, keyword-planner-api.md, supplementary-apis.md, rate-limits-quotas.md
- **PDF report generator**: `scripts/google_report.py` with enterprise A4 template, WeasyPrint + matplotlib charts, post-generation quality review
- **OAuth web credential flow**: Browser-based auth with localhost:8085 callback, token refresh, manual code exchange fallback
- **4-tier credential system**: Tier 0 (API key: PSI/CrUX), Tier 1 (+OAuth/SA: GSC/Indexing), Tier 2 (+GA4), Tier 3 (+Ads Keyword Planner)
- **Python dependencies**: google-api-python-client, google-auth, google-auth-oauthlib, google-auth-httplib2, google-analytics-data, matplotlib, weasyprint

### Security
- SSRF protection: `validate_url()` blocks private IPs, loopback, and GCP metadata endpoints in all Google API scripts
- `.gitignore` hardened with 8 credential patterns: `.env`, `client_secret*.json`, `oauth-token.json`, `service_account*.json`
- OAuth tokens no longer store `client_secret` (reads from client_secret.json file only)
- Removed hardcoded user paths from all scripts (mobile_analysis.py, capture scripts)

### Changed
- Sub-skill count: 14 -> 15 core (+ 2 extensions)
- Subagent count: 9 -> 10 core (+ 2 extension) with conditional Google API spawning
- seo-audit spawns seo-google agent when Google API credentials detected
- seo-technical and seo-performance can use CrUX field data when available
- Report Generation Rules added to CLAUDE.md with color palette, dependency, and cross-skill enforcement
- README updated with Google APIs, local SEO, maps, and PDF report features

---

## [1.6.1] - 2026-03-27

### Added
- **Marketplace distribution**: Created `.claude-plugin/marketplace.json` for plugin marketplace submission. Users can now install via `/plugin marketplace add AgriciDaniel/claude-seo`
- **Agent model and turn limits**: All 11 subagents now specify `model: sonnet` and `maxTurns` (15-25) for predictable cost and behavior
- **Plugin keywords**: Added 12 discovery keywords to `plugin.json` for marketplace searchability

### Changed
- **Standard directory structure**: Moved `seo/` orchestrator to `skills/seo/` for auto-discovery compliance. Extension skills (seo-dataforseo, seo-image-gen) and agents copied to standard `skills/` and `agents/` directories
- **plugin.json rewrite**: Removed non-standard `entry_point` field and individual file-path arrays for `skills`/`agents`. All 17 skills and 11 agents now rely on directory auto-discovery per Anthropic plugin spec
- **allowed-tools format**: Converted from YAML arrays to comma-separated strings across all 17 SKILL.md files
- **Metadata standardized**: Added `license: MIT` and `metadata:` block (author, version, category) to all SKILL.md frontmatters
- **Cross-references**: Updated all agent and skill files referencing `seo/references/` to `skills/seo/references/`
- **CLAUDE.md**: Architecture tree updated to reflect new structure

### Fixed
- **Plugin validation**: `claude plugin validate .` now passes cleanly (previously would fail on non-standard fields)

---

## [1.6.0] - 2026-03-23

### Added
- **Local SEO skill**: `skills/seo-local/SKILL.md` for GBP, NAP, citations, reviews, and map pack analysis
- **Maps intelligence skill**: `skills/seo-maps/SKILL.md` for geo-grid rank tracking, GBP auditing, review intelligence, competitor radius mapping
- **Maps subagent**: `agents/seo-maps.md` for parallel maps analysis during audits
- **Local subagent**: `agents/seo-local.md` for parallel local SEO analysis
- **Maps reference files**: 4 new reference files (maps-geo-grid.md, maps-gbp-checklist.md, maps-api-endpoints.md, maps-free-apis.md)
- **Local reference files**: 2 new reference files (local-seo-signals.md, local-schema-types.md)
- **Installer fixes**: Cross-platform install script improvements

### Changed
- Subagent count: 7 -> 9 core (+ 2 extension) with conditional local/maps spawning
- Sub-skill count: 12 -> 14 core (+ 2 extension)

---

## [1.5.0] - 2026-03-19

### Added
- **Frontmatter fields**: `user-invokable`, `argument-hint`, and `allowed-tools` added to all SKILL.md files per Anthropic best practices
- **Error handling sections**: Added to all SKILL.md files with skill-specific guidance
- **Plugin manifest**: `.claude-plugin/plugin.json` updated with all skills and agents registered
- **Version tracking**: `pyproject.toml` with project metadata

### Fixed
- **Em dash elimination**: Replaced em dashes (U+2014) across files with appropriate punctuation (colons, commas, semicolons, periods) to reduce AI detection signals
- **HTML comments before frontmatter**: Removed `<!-- Updated: ... -->` comments from SKILL.md files that preceded the YAML frontmatter delimiter
- **Anthropic compliance audit**: Full audit against official skill-building guidelines, all checks now pass

### Changed
- **Technical SEO**: Updated from "8 categories" to "9 categories" in description (IndexNow added in prior update)

---

## [1.4.0] - 2026-03-12

### Security
- **Install script supply chain fix**: Replaced `irm | iex` Windows PowerShell one-liner with `git clone + powershell -File` as primary install method. Claude Code's own security guardrails flagged the old pattern as a supply chain risk (reported by community member). Added collapsible "review before running" section for Unix curl method.
- **Version pinning**: `install.sh` and `install.ps1` now clone a specific release tag (`v1.3.0`) by default rather than `main`, preventing silent updates. Override with `CLAUDE_SEO_TAG=main`.
- **PowerShell Invoke-External hardening**: Comprehensive `PSNativeCommandUseErrorActionPreference` handling in `Invoke-External` wrapper (fixes Windows git clone stderr false-positive termination, from PR #13 + PR #15).

### Added
- **GEO agent deployed**: `agents/seo-geo.md` created -- `/seo audit` now spawns 7 parallel agents (was 6). GEO analysis covers AI crawler access, llms.txt, passage-level citability, brand mention signals, platform-specific scoring (Google AI Overviews, ChatGPT, Perplexity, Bing Copilot).
- **`--googlebot` flag in `fetch_page.py`**: Detect prerender/dynamic rendering services by comparing response size with default UA vs Googlebot UA. First phase of SPA/CSR support (Issue #11).

### Fixed
- **URL normalization**: `capture_screenshot.py` and `analyze_visual.py` now accept bare domains (`example.com` -> `https://example.com`) via shared `normalize_url()` helper (from PR #16 by @shuofengzhang).
- **GEO weight**: AI Search Readiness weight increased from 5% to 10% in overall SEO Health Score. Technical SEO adjusted to 22%, Content Quality to 23%.
- **FAQPage guidance**: Blanket "remove FAQPage on commercial sites" updated to nuanced guidance -- existing FAQPage -> Info priority (not Critical), noting AI/LLM citation benefit. Adding new FAQPage -> not recommended for Google, note AI benefit. Updated in `seo/SKILL.md`, `agents/seo-schema.md`, `seo/references/schema-types.md`.
- **Uninstall agents list**: Added `seo-geo` to `uninstall.sh` and `uninstall.ps1` removal lists.
- **Python requirement**: Corrected from `3.8+` to `3.10+` in `README.md` and `docs/INSTALLATION.md`.

### Changed
- Subagent count: 6 -> 7 (added seo-geo to core audit pipeline)
- `.gitignore`: Added generated audit artifacts (charts/, PDFs, report.html, firebase-debug.log, generated-schema.json)

---

## [1.3.0] - 2026-03-06

### Added
- **Extension system**: `extensions/` directory convention for self-contained add-ons with install/uninstall scripts
- **DataForSEO extension**: 22 commands across 9 API modules (SERP, keywords, backlinks, on-page, content, business listings, AI visibility, LLM mentions). Install: `./extensions/dataforseo/install.sh`
- **DataForSEO integration**: seo-audit, seo-content, seo-geo, seo-page, seo-plan, seo-technical auto-detect DataForSEO MCP tools for enriched analysis
- **Plugin manifest**: `.claude-plugin/plugin.json` for official plugin directory submission
- **Documentation**: Extensions architecture in ARCHITECTURE.md, 22 new commands in COMMANDS.md, updated MCP integration guide

### Fixed
- **Title tag threshold**: Pre-commit hook now uses 60-char max, aligned with quality-gates.md and echo message
- **SSRF prevention**: Added to `capture_screenshot.py` (defense-in-depth, matching `fetch_page.py`)
- **Frontmatter cleanup**: Removed non-standard `allowed-tools` from main SKILL.md

### Changed
- Sub-skill count: 12 + 1 extension (added seo-dataforseo via DataForSEO extension)
- Subagent count: 6 + 1 optional (added seo-dataforseo agent via extension)
- DataForSEO promoted from "Community" to "Official extension" in MCP docs

---

## [1.2.1] - 2026-02-28

### Fixed
- **User-Agent header**: Changed default from bot-style `ClaudeSEO/1.0` to Chrome-like string with `ClaudeSEO/1.2` suffix. SSR frameworks (Next.js, Nuxt, Angular) now pre-render properly instead of serving empty client-side shells (#9)
- **Custom User-Agent support**: Added `--user-agent` flag to `fetch_page.py` for configurable UA strings

### Added
- **install.cat support**: Added alternative install method via `curl install.cat/AgriciDaniel/claude-seo | bash` to README (#10)

---

## [1.2.0] - 2026-02-19

### Security
- **SSRF prevention**: Added private IP blocking to `fetch_page.py` and `analyze_visual.py`
- **Path traversal prevention**: Added output path sanitization to `capture_screenshot.py` and file validation to `parse_html.py`
- **Install hardening**: Removed `--break-system-packages`, switched to venv-based pip install
- **requirements.txt**: Now persisted to `~/.claude/skills/seo/` for user retry

### Fixed
- **YAML frontmatter parsing**: Removed HTML comments before `---` delimiter in 8 files (skills: seo-content, seo-images, seo-programmatic, seo-schema, seo-technical; agents: seo-content, seo-performance, seo-technical). Thanks @kylewhirl for identifying this in the codex-seo fork.
- **Windows installer**: Merged @kfrancis improvements -- `python3 -m pip`, `py -3` launcher fallback, requirements.txt persistence, non-fatal subagent copy, better error diagnostics (PR #6)
- **requirements.txt missing after install**: Now copied to skill directory so users can retry (#1)

### Changed
- Python dependencies now installed in a venv at `~/.claude/skills/seo/.venv/` with `--user` fallback (#2)
- Playwright marked as explicitly optional in install output
- Windows installer uses `Resolve-Python` helper for robust Python detection (#5)

---

## [1.1.0] - 2026-02-07

### Security (CRITICAL)
- **urllib3 >=2.6.3**: Fixes CVE-2026-21441 (CVSS 8.9) - decompression bypass vulnerability
- **lxml >=6.0.2**: Updated from 5.3.2 for additional libxml2 security patches
- **Pillow >=12.1.0**: Fixes CVE-2025-48379
- **playwright >=1.55.1**: Fixes CVE-2025-59288 (macOS)
- **requests >=2.32.4**: Fixes CVE-2024-47081, CVE-2024-35195

### Added
- **GEO (Generative Engine Optimization) major enhancement**:
  - Brand mention analysis (3x more important than backlinks for AI visibility)
  - AI crawler detection (GPTBot, OAI-SearchBot, ClaudeBot, PerplexityBot, etc.)
  - llms.txt standard detection and recommendations
  - RSL 1.0 (Really Simple Licensing) detection
  - Passage-level citability scoring (optimal 134-167 words)
  - Platform-specific optimization (Google AI Overviews vs ChatGPT vs Perplexity)
  - Server-side rendering checks for AI crawler accessibility
- **LCP Subparts analysis**: TTFB, resource load delay, resource load time, render delay
- **Soft Navigations API detection** for SPA CWV measurement limitations
- **Schema.org v29.4 additions**: ConferenceEvent, PerformingArtsEvent, LoyaltyProgram
- **E-commerce schema updates**: returnPolicyCountry now required, organization-level policies

### Changed
- **E-E-A-T framework**: Updated for December 2025 core update - now applies to ALL competitive queries, not just YMYL
- **SKILL.md description**: Expanded to leverage new 1024-character limit
- **Schema deprecations expanded**: Added ClaimReview, VehicleListing (June 2025)
- **WebApplication schema**: Added as correct type for browser-based SaaS (vs SoftwareApplication)

### Fixed
- Schema-types.md now correctly distinguishes SoftwareApplication (apps) vs WebApplication (SaaS)

---

## [1.0.0] - 2026-02-07

### Added
- Initial release of Claude SEO
- 9 specialized skills: audit, page, sitemap, schema, images, technical, content, geo, plan
- 6 subagents for parallel analysis: seo-technical, seo-content, seo-schema, seo-sitemap, seo-performance, seo-visual
- Industry templates: SaaS, local service, e-commerce, publisher, agency, generic
- Schema library with deprecation tracking:
  - HowTo schema marked deprecated (September 2023)
  - FAQ schema restricted to government/healthcare sites only (August 2023)
  - SpecialAnnouncement schema marked deprecated (July 31, 2025)
- AI Overviews / GEO optimization skill (seo-geo) - new for 2026
- Core Web Vitals analysis using current metrics:
  - LCP (Largest Contentful Paint): <2.5s
  - INP (Interaction to Next Paint): <200ms - replaced FID on March 12, 2024
  - CLS (Cumulative Layout Shift): <0.1
- E-E-A-T framework updated to September 2025 Quality Rater Guidelines
- Quality gates for thin content and doorway page prevention:
  - Warning at 30+ location pages
  - Hard stop at 50+ location pages
- Pre-commit and post-edit automation hooks
- One-command install and uninstall scripts (Unix and Windows)
- Bounded Python dependency pinning with CVE-aware minimums (lxml >= 5.3.2)

### Architecture
- Follows Anthropic's official Claude Code skill specification (February 2026)
- Standard directory layout: `scripts/`, `references/`, `assets/`
- Valid hook matchers (tool name only, no argument patterns)
- Correct subagent frontmatter fields (name, description, tools)
- CLI command is `claude` (not `claude-code`)
