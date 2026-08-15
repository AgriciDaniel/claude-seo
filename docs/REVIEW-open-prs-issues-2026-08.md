# Open PR & Issue Review — August 2026

Skeptical triage of all 26 open PRs and 12 open issues against `main` @ `09d37c7`.

**Method.** Every claim was checked against the code, not the description. PR
branches were fetched locally (`refs/pull/N/head`), their own tests executed, merge
compatibility tested pairwise, and external claims (CVEs, config locations, API
semantics) verified against primary sources. Verdicts below cite the evidence.

---

## 0. Read this first: the test suite does not run

On **every** branch except #182, `pytest tests/` aborts during collection:

```
INTERNALERROR> SystemExit: 1
no tests ran in 0.44s
```

`scripts/gsc_query.py` calls `sys.exit(1)` at import time when
`google-api-python-client` is absent. Under pytest that `SystemExit` escapes
collection and kills the **entire session** — not one module, all of it. CI hides
this because CI installs every optional dependency.

With #182 applied: `1 failed, 232 passed, 3 skipped`. The single failure is
`test_sync_flow.py::test_dry_run_exits_zero`, which makes a live `urllib.request.urlopen`
call to the GitHub API — environmental, unrelated to the PR.

**Merge #182 before evaluating anything else.** Until it lands, a green local run
proves nothing, and no contributor can validate their own work.

---

## 1. PRs that do not do what they say

### PR #242 — "fix(agent-ux): don't emit a passing score for empty fetched documents" — ❌ **Do not merge**

The diff contains **only** `CHANGELOG.md` and `tests/test_phase_j_executable.py`.
There is no change to `scripts/agent_ux_check.py`. The CHANGELOG asserts a fix that
was never committed.

Its own tests fail on its own branch:

```
FAILED tests/test_phase_j_executable.py::test_audit_refuses_score_on_empty_html
FAILED tests/test_phase_j_executable.py::test_audit_refuses_score_on_whitespace_only_html
E       assert 90 is None
2 failed, 23 passed
```

The underlying report (**issue #210**) is real and reproduces — see §4.
The tests are well written and should be kept; they just need the actual guard in
`audit()`, which currently returns early only on `page["error"]`, so an empty body
flows into `score()` and yields 100 − 10 = **90**.

**Action:** ask for the missing `agent_ux_check.py` hunk, or land the tests together
with a maintainer-written guard.

### PRs #197 and #203 — MiniMax provider for the Banana REST fallback — ❌ **Do not merge as-is (security)**

Both come from `octo-patch`, an account with no other history in this repo, and both
add a new third-party API vendor (`api.minimax.io`, `api.minimaxi.com`).

Two concrete defects, not style objections:

1. **Unvalidated fetch of a remote-controlled URL (SSRF).** `generate.py:282`
   (#197) and `edit.py:291` (#203) do `urllib.request.urlopen(item, timeout=120)`
   where `item` comes straight out of the MiniMax JSON response, then write the
   bytes to disk. Neither file imports `url_safety` at all (`grep -c url_safety` → `0`).
   This directly violates the repo's own rule in CLAUDE.md: *"All scripts that connect
   to user-supplied URLs must use `scripts/url_safety.py`."* On `main`, the banana
   script only ever calls one hardcoded Google endpoint — these PRs introduce the
   first response-controlled fetch sink in the extension.
2. **Local file read into an outbound request.** `_encode_subject_reference()`
   accepts an arbitrary path, `resolve()`s it, base64-encodes the bytes and posts
   them to the vendor. That is a clean file-exfiltration primitive for anything that
   can influence the argument.

Credit where due: API-key redaction on the error path is handled properly and tested.

**Action:** route every image fetch through `safe_requests_get()`, constrain
subject-reference paths to an allowlisted directory, then re-review. Given an
unknown author adding a new network egress target, this warrants a careful second
look regardless.

### PR #209 — script path resolution — ❌ **Wrong fix for a real problem (issue #208)**

The problem is real: 25 `scripts/*.py` references in `agents/` and `skills/` bypass
the wrapper, while 28 already use `claude-seo run`.

But the fix pastes an 8-line shell block into 20 files:

```bash
PLUGIN_ROOT=$(dirname "$(find ~/.claude/plugins/cache -maxdepth 4 ... | head -1)")
PY="$PLUGIN_ROOT/.venv/bin/python3"
```

`scripts/runtime.py` **already solves this**, and better — it honours
`CLAUDE_PLUGIN_DATA`/`CLAUDE_PLUGIN_ROOT` and resolves the interpreter
cross-platform (`_venv_python()` returns `Scripts/python.exe` on Windows). The PR's
version is Unix-only, hardcodes one install layout, and breaks for git-clone and
marketplace installs. It also duplicates the block 20× and inserts prose above the
H1 in SKILL.md files.

**Action:** close in favour of converting the 25 raw references to `claude-seo run`.
Thank the reporter — the diagnosis in #208 is sound even though the remedy isn't.

---

## 2. Merge, in this order

| # | PR | Verdict | Evidence |
|---|----|---------|----------|
| 1 | **#182** stop module-level `sys.exit` aborting pytest | ✅ Merge first | Only branch where tests run: 232 passed vs 0 |
| 2 | **#202** cost ledgers lose concurrent writes | ✅ Merge | Genuine lost-update: old code took `LOCK_SH` to read, released, re-took `LOCK_EX` to write. Fix spans one lock, adds atomic `os.replace`, `msvcrt` fallback, fails closed on corruption. Thorough tests |
| 3 | **#240** / **#241** schema hook fixes | ✅ Merge — but see conflict | Both branches' tests pass (4 and 5 respectively) |
| 4 | **#207** install.ps1 empty-array binding | ✅ Merge | One line, correct; mandatory `[string[]]` with no args prompts on PS 5.1 |
| 5 | **#196** ponytail cleanup (−102 lines) | ✅ Merge | Verified dead: `_stream_gz_lines`, `normalize_social`, `normalize_reviews` all have **0** references outside their own file |
| 6 | **#190** requests floor | ✅ Merge; supersedes #201 | See §3 |

### ⚠️ #240 and #241 conflict with each other

Both rewrite `_validate_schema_object()` in `hooks/validate-schema.py`. Tested:

```
MERGE 240+241: CONFLICT
CONFLICT (content): Merge conflict in hooks/validate-schema.py
CONFLICT (content): Merge conflict in tests/test_schema_hook_policy.py
CONFLICT (content): Merge conflict in CHANGELOG.md
```

Merge one, then ask the author (same contributor, `ousamabenyounes`) to rebase the
other. #241 changes the function signature (`require_context`), so landing **#241
first** and rebasing #240 onto it is the smaller conflict.

### PR #204 — MCP config location — ⚠️ **Correct premise, unsafe write path**

The claim checks out against the Claude Code docs: MCP servers live in
`~/.claude.json` (local + user scope) or project `.mcp.json`. `mcpServers` is *not*
read from `~/.claude/settings.json`, so today's installers write config that
silently never loads. Real bug, correct destination.

**But the blast radius changes.** `~/.claude.json` is the user's primary state file
(every project's history), not a small settings file. Two write paths are now unsafe:

- `extensions/firecrawl/install.ps1` uses `ConvertTo-Json -Depth 10`. PowerShell
  silently truncates beyond `-Depth`; `~/.claude.json` routinely nests deeper. This
  can corrupt the user's entire config.
- `extensions/banana/scripts/setup_mcp.py` `save_settings()` rewrites the whole file
  non-atomically — a crash mid-write loses everything.

The bash installers already do argv-passed, atomic, 0600 writes and are fine.

**Action:** fix the PowerShell depth and make `setup_mcp.py` atomic, then merge.
This one is worth getting right rather than fast.

---

## 3. Dependabot & dependency PRs

| PR | Change | Verdict |
|----|--------|---------|
| #190 | requests `>=2.34.2` | ✅ Merge — supersedes #201 |
| #201 | requests `>=2.33.0` (CVE-2026-25645) | ➖ Close as superseded by #190 |
| #191 | playwright `>=1.61.0` | ✅ Merge |
| #192 | courlan `>=1.4.0` | ✅ Merge |
| #193 | numpy `>=2.2.6` | ✅ Merge — verified safe |
| #194 | google-auth `>=2.56.2` | ✅ Merge |

**On #201's CVE claim — I checked, and it is real.** CVE-2026-25645 exists: insecure
temp-file reuse in `requests.utils.extract_zipped_paths()`, fixed in 2.33.0. Two
caveats worth recording: the advisory only affects code that calls
`extract_zipped_paths()` **directly**, and this repo never does
(`grep -rn extract_zipped_paths` → no hits). So the urgency is low, and #190's
`>=2.34.2` already clears it. Close #201 with thanks, not as wrong.

**On #193 (numpy 1.26 → 2.2.6),** a major-version floor deserves scrutiny. Checked:
the only numpy API used anywhere in `scripts/` is `np.linspace` and `np.pi`, both
unchanged in 2.x, and no removed alias (`np.float_`, `np.NaN`, `np.product`, …)
appears. numpy 2.2 requires Python ≥3.10, matching `requires-python = ">=3.10"` and
the 3.10 CI matrix. Safe.

---

## 4. Issues

| Issue | Verdict | Evidence |
|-------|---------|----------|
| **#210** empty HTML scores 90/100 | ✅ **Confirmed** | Reproduced: `score()` on an empty doc returns `{'score': 90, ...}`. Fix still missing (#242 is tests-only) |
| **#187** `@graph` false positive | ✅ **Confirmed** | Reproduced on `main`: valid top-level `@graph` → `['Block 1: Missing @type']`. Fixed by #241 |
| **#188** / **#205** bare `REPLACE` substring | ✅ **Confirmed — duplicates** | Reproduced: `"renal replacement therapy"` → `Contains placeholder text: REPLACE`. Fixed by #240. Close one as a duplicate of the other |
| **#186** `UnicodeEncodeError` on Windows cp1252 | ✅ **Confirmed — no PR open** | `hooks/validate-schema.py:183,188` print `⚠️` and `🛑`. Crashes on a cp1252 stdout. **Unclaimed gap** |
| **#208** script path resolution | ✅ Confirmed, ❌ wrong fix proposed | 25 raw refs vs 28 using `claude-seo run`. See #209 above |
| **#180** trafilatura / `lxml_html_clean` | ❓ **Does not reproduce** | Fresh install of the exact pins: trafilatura 2.2.0 imports fine, `lxml.html.clean` resolves, `lxml_html_clean` pulled in automatically. Ask the reporter for their platform and `pip freeze` before acting |
| **#177** subagents write no findings on large sites | ⚠️ Plausible, unverified | `maxTurns` is 15/20/25 and `seo-audit/SKILL.md` does specify `findings/*.md`. Needs a real large-site run to confirm — not reproducible from static inspection |
| **#189** Unlighthouse `--max-routes` inert | ⚠️ Unverified | Requires the extension installed; three distinct claims that should be split |
| **#199** hosted-plugin upload failure | ⚠️ Tied to #198 | #198 touches 60 files; needs its own review pass |
| **#181** Git delivery flow docs | 📋 Docs request | Low priority, uncontroversial |
| **#239** GoAnyAPI extension proposal | 📋 Proposal | Given the #197/#203 findings, apply the same egress scrutiny to any new provider |

---

## 5. Not yet reviewed in depth

#178 (docs, 2 files), #179 (tests only, +95), #183/#184/#185 (CI: fail-fast on
install, pip-audit, Windows/macOS matrix), #195 (new templated-metadata detector,
+810), #198 (hosted-Claude compat, 60 files). #183–#185 pair naturally with #182 as
a CI-health batch. #195 and #198 are large enough to deserve dedicated passes.

---

## 6. Recommended sequence

1. Merge **#182** — restores the ability to test anything.
2. Merge **#202**, **#207**, **#196**.
3. Merge **#241**, ask for a rebase of **#240**.
4. Merge Dependabot **#190–#194**; close **#201** as superseded.
5. Return **#242** for its missing fix; return **#197**/**#203** for the SSRF and
   file-read issues; close **#209** in favour of `claude-seo run`.
6. Harden the write path in **#204**, then merge.
7. Pick up **#186** — a confirmed bug with nobody working on it.
