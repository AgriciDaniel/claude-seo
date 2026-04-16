# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.9.0] - 2026-04-14

### Added
- **seo-cluster**: SERP-based semantic topic clustering for content architecture (skill + 3 references + interactive cluster-map.html visualization + agent). Contributed by Lutfiya Miller (Pro Hub Challenge Winner).
- **seo-sxo**: Search Experience Optimization — reads SERPs backwards to detect page-type mismatches, derives user stories, scores pages from persona perspectives (skill + 4 references + agent). Contributed by Florian Schmitz.
- **seo-drift**: SEO drift monitoring — baseline, diff, and track changes to on-page SEO with 17 comparison rules across 3 severity levels. SQLite persistence (skill + 1 reference + agent + 4 Python scripts). Contributed by Dan Colta. Security-hardened: all curl usage eliminated, SSRF protection enforced.
- **seo-ecommerce**: E-commerce SEO — Google Shopping intelligence, Amazon marketplace analysis, product schema validation (skill + 1 reference + agent + 2 Python scripts). Contributed by Matej Marjanovic.
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
- **Ukrainian localization**: first i18n — README, CONTRIBUTING, PRIVACY, SECURITY, INSTALLATION, TROUBLESHOOTING translated (PR #50)
- **Firecrawl extension section** in README with install and example commands
- **Backlink API privacy disclosures** in PRIVACY.md (Moz, Bing Webmaster, Common Crawl, verify crawler)
- 4 missing commands added to README table: `/seo backlinks`, `/seo firecrawl`, `/seo dataforseo`, `/seo image-gen`
- 6 missing scripts added to CI syntax check (backlinks_auth, moz_api, bing_webmaster, commoncrawl_graph, verify_backlinks, validate_backlink_report)
- 6 missing skill directories added to INSTALLATION.md manual uninstall list

### Fixed
- **Install scripts pinned to stale version**: REPO_TAG bumped from v1.7.2 to v1.8.2 in install.sh and install.ps1 — new curl-based installs now get the current release
- **Supply chain risk in docs**: removed deprecated `irm | iex` pattern from docs/INSTALLATION.md, replaced with safe `git clone` + `powershell -File` method
- **Version sync**: pyproject.toml (1.7.2→1.8.2), CITATION.cff (1.7.2→1.8.2, date 2026-04-10), all 19 SKILL.md files
- **Python requirement**: pyproject.toml corrected from `>=3.11` to `>=3.10` (matches README and install scripts)
- **README architecture counts**: sub-skills "15+2" → "16+3", agents "10+2" → "11+2"
- **Orchestrator SKILL.md**: stale count "15+2" → "16+3" at line 119
- **CLAUDE.md**: sub-skill count 17→16 core, script count "20+2" → "21+2"
- **Extension install hang**: merged PR #43 — npx pre-warm no longer starts MCP server binary

### Community
- Merged PR #43 (fix stuck extension install) by @olivierroy
- Merged PR #45 (correct sub-skills count) by @MalteBerlin
- Merged PR #50 (Ukrainian localization) by @edocltd
- Closed issue #42 (marketplace discovery — resolved)
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
- **Windows installer**: Merged @kfrancis improvements -- `python -m pip`, `py -3` launcher fallback, requirements.txt persistence, non-fatal subagent copy, better error diagnostics (PR #6)
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
