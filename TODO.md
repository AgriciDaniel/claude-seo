# TODO — claude-seo

## Completed in v1.2.0

- [x] **Fix YAML frontmatter parsing** — Removed HTML comments before `---` in 8 files (from @kylewhirl fork)
- [x] **SSRF prevention in Python scripts** — Private IP blocking in fetch_page.py and analyze_visual.py (from @artyomsv #7)
- [x] **Install hardening** — venv-based pip, no `--break-system-packages` (from @JawandS #2)
- [x] **Windows install fixes** — `python -m pip`, `py -3` fallback, requirements.txt persistence (from @kfrancis #5, PR #6)
- [x] **requirements.txt persistence** — Copied to skill dir after install (from @edustef #1)
- [x] **Path traversal prevention** — Output path sanitization in capture_screenshot.py, file validation in parse_html.py

## Completed — Extensions

- [x] **Extension system** — `extensions/` directory convention with self-contained add-ons
- [x] **DataForSEO extension** — 22 commands across 9 API modules (SERP, keywords, backlinks, on-page, content, business listings, AI visibility, LLM mentions). Install: `./extensions/dataforseo/install.sh`

## Deferred from Community Feedback

- [ ] **Reduce Bash scope on agents** (Priority: Medium, from @artyomsv #7)
  Evaluate which agents truly need Bash access. Consider replacing with WebFetch where possible.

- [ ] **Docker-based script execution** (Priority: Low, from @artyomsv #7)
  Sandbox Python scripts in Docker for users who want extra isolation.

- [ ] **Opencode compatibility** (Priority: Low, from @Ehtz #4)
  Adapt skill architecture for Opencode. @kylewhirl already ported to OpenAI Codex.

- [ ] **Subagent timeout/compact handling** (Priority: Medium, from @JawandS #3)
  Primary agent sometimes terminates before subagents finish. Consider encouraging subagents
  to run /compact and adding explicit wait logic.

- [ ] **Native Chrome tools vs Playwright** (Priority: Medium, from @artyomsv #7, @btafoya PR #8)
  Claude Code has native browser automation. Evaluate replacing Playwright with built-in tools
  to eliminate the ~200MB Chromium dependency.

## Deferred from v1.4 CEO Review (2026-04-16)

These items were scoped out of v1.4 (Priority Scoring + Fix Generation) during the
CEO/adversarial review. Full design doc available in gstack project artifacts (local only, not in repo).

- [ ] **Audit delta / history tracking** (Priority: P1, target: v1.5)
  Commit structured audit JSON to `seo-history/` branch after each `/seo audit` run.
  Diff against previous run to show: net new P1 issues, resolved issues, regression count.
  Blocked on: JSON schema definition + storage location decision (repo root vs. user dir).
  Requires separate design doc before starting.

- [ ] **Confidence scoring on generated fixes** (Priority: P2, target: v1.4.1)
  Add `confidence: int` (0–100) to `FixResult` dataclass. Show warning when < 60%.
  Calibration: meta_tags = 95 (deterministic), alt_text = 70 (Claude-generated),
  schema = 55–80 (context-dependent). Ship after core fix generation proves out in v1.4.

- [ ] **Two-phase alt-text resumability** (Priority: P3, target: v1.4.1)
  Serialize `alt_suggestions` dict to `/tmp/seo-alt-state-{url-hash}.json` after each batch.
  On next run: check if file exists and resume from it. Prevents re-running Claude for
  already-processed images if orchestrator is interrupted mid-batch. ~20 lines of Python.

- [ ] **File-write locking for concurrent /seo fix calls** (Priority: P3, target: v1.5)
  Use a cross-platform file lock (e.g., `filelock` library or `fcntl.flock()` on POSIX /
  `msvcrt.locking()` on Windows) per source path to prevent two concurrent `/seo fix`
  calls on the same repo from generating overlapping diffs that corrupt the file.
  Edge case (CLI tool, unlikely concurrent use), but relevant for multi-agent setups.

- [ ] **fix_schema on .tsx/.jsx source files** (Priority: P2, target: v1.5)
  v1.4 `fix_schema` targets HTML only. JSX/TSX requires syntax-aware insertion of
  JSON-LD `<script>` tags without corrupting JSX output. Requires design spike on
  AST manipulation strategy (ts-morph vs. layout-pattern injection).
  Blocked on: safe insertion strategy when JSON-LD contains template literals.

## Deferred from February 2026 Research Report

- [ ] **Fake freshness detection** (Priority: Medium)
  Compare visible dates (`datePublished`, `dateModified`) against actual content modification signals.
  Flag pages with updated dates but unchanged body content.

- [ ] **Mobile content parity check** (Priority: Medium)
  Compare mobile vs desktop meta tags, structured data presence, and content completeness.
  Flag discrepancies that could affect mobile-first indexing.

- [ ] **Discover optimization checks** (Priority: Low-Medium)
  Clickbait title detection, content depth scoring, local relevance signals, sensationalism flags.

- [ ] **Brand mention analysis Python implementation** (Priority: Low)
  Currently documented in `seo-geo/SKILL.md` but no programmatic scoring.

---

*Last updated: April 16, 2026*
