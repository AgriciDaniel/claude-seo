"""
Tests for scripts/commoncrawl_graph.py.

Focus: cache-path construction. `--release` reached `_get_cache_path`
completely unsanitised and the result is opened for writing in `_save_cache`,
so `--release ../../../../tmp/x` wrote outside the cache directory. The same
value is also interpolated into a download URL by `_graph_file_url`, so it is
rejected at the CLI boundary rather than silently rewritten -- otherwise the
cache key would disagree with what was actually fetched.

No network: only the pure path/validation helpers are exercised.
"""

from __future__ import annotations

import os
import sys

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import commoncrawl_graph as ccg  # noqa: E402


def _inside_cache_dir(path: str) -> bool:
    root = os.path.realpath(ccg.get_cache_dir())
    resolved = os.path.realpath(path)
    return resolved == root or resolved.startswith(root + os.sep)


# ---------------------------------------------------------------------------
# path traversal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "domain,release",
    [
        ("example.com", "../../../../tmp/pwned"),
        ("example.com", ".."),
        ("../../../../tmp/evil", "cc-main-2026-jan-feb-mar"),
        ("../..", ".."),
        ("example.com/../../etc", "cc-main-2026-jan-feb-mar"),
    ],
)
def test_cache_path_never_escapes_the_cache_dir(domain, release):
    assert _inside_cache_dir(ccg._get_cache_path(domain, release, "combined"))


def test_cache_path_preserves_legitimate_values():
    """Sanitising must not mangle real inputs, or every cache miss forever."""
    path = ccg._get_cache_path("example.com", "cc-main-2026-jan-feb-mar", "combined")
    assert os.path.basename(path) == "example.com-cc-main-2026-jan-feb-mar-combined.json"
    assert _inside_cache_dir(path)


def test_safe_cache_component_collapses_dot_runs_and_separators():
    assert ".." not in ccg._safe_cache_component("../../etc/passwd")
    assert "/" not in ccg._safe_cache_component("a/b/c")
    assert os.sep not in ccg._safe_cache_component("a\\b")
    # Never returns empty, which would produce a path like "-release-type.json".
    assert ccg._safe_cache_component("...") != ""
    assert ccg._safe_cache_component("") != ""


# ---------------------------------------------------------------------------
# release validation (also guards the URL built by _graph_file_url)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "release",
    ["cc-main-2026-jan-feb-mar", "cc-main-2024-oct-nov-dec", "CC-MAIN-2024-33", "a_b.c-1"],
)
def test_release_pattern_accepts_real_release_ids(release):
    assert ccg._RELEASE_RE.match(release)


@pytest.mark.parametrize(
    "release",
    ["../../../../tmp/pwned", "..", "a/../b", "a..b", "with space", "", "a/b", "x\ty"],
)
def test_release_pattern_rejects_traversal_and_junk(release):
    assert not ccg._RELEASE_RE.match(release)
