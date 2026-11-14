"""Tests for scripts/sync_flow.py"""

import importlib.util as _ilu
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "scripts" / "sync_flow.py"
REF_DIR = REPO_ROOT / "skills" / "seo-flow" / "references"

# The dry run calls the live GitHub API. Unauthenticated parallel runs hit 429
# and 403 rate limits, so these tests only run when explicitly enabled; CI sets
# the flag together with GH_TOKEN.
network = pytest.mark.skipif(
    os.environ.get("CLAUDE_SEO_NETWORK_TESTS") != "1",
    reason="live GitHub API call; set CLAUDE_SEO_NETWORK_TESTS=1 to run",
)

# sync_flow.py's own markers for "GitHub or the network said no". Kept as
# literals so a change to the script's contract fails
# test_script_keeps_the_markers_the_skip_relies_on below.
EXIT_RATE_LIMITED = 75
RATE_LIMIT_MESSAGE = "GitHub API rate limit exceeded"
NETWORK_ERROR_MESSAGE = "Network error reaching GitHub"


def _skip_if_github_unavailable(result):
    """Skip when the dry run failed on a rate limit or the network.

    Many CI runs starting at once exhaust the GitHub API quota even with a
    token. That is not a defect in the sync, so the test is skipped with the
    reason. Any other failure is left for the caller's assertions.
    """
    stderr = result.stderr or ""
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    if result.returncode == EXIT_RATE_LIMITED or RATE_LIMIT_MESSAGE in stderr:
        pytest.skip(f"GitHub rate limit, not a sync defect: {stderr.strip()[-300:]}")
    if result.returncode != 0 and NETWORK_ERROR_MESSAGE in stderr:
        pytest.skip(f"GitHub unreachable, not a sync defect: {stderr.strip()[-300:]}")


def _dry_run():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    _skip_if_github_unavailable(result)
    return result


@network
def test_dry_run_exits_zero():
    result = _dry_run()
    assert result.returncode == 0, f"Dry run failed:\n{result.stderr}"


@network
def test_dry_run_produces_valid_json():
    result = _dry_run()
    assert result.returncode == 0, f"Dry run failed:\n{result.stderr}"
    data = json.loads(result.stdout)
    assert "added" in data, "JSON missing 'added' key"
    assert "updated" in data, "JSON missing 'updated' key"
    assert "unchanged" in data, "JSON missing 'unchanged' key"


@network
def test_dry_run_does_not_write_files():
    files_before = set(REF_DIR.rglob("*.md"))
    _dry_run()
    files_after = set(REF_DIR.rglob("*.md"))
    assert files_before == files_after, (
        f"Dry run created unexpected files: {files_after - files_before}"
    )


def test_real_sync_produces_prompts_per_stage():
    """After a real sync, every FLOW stage directory must contain at least one prompt file."""
    prompts_dir = REF_DIR / "prompts"
    if not prompts_dir.exists():
        return  # sync not yet run — skip silently

    expected_stages = ["find", "leverage", "optimize", "win", "local"]
    missing = [
        stage for stage in expected_stages
        if not (prompts_dir / stage).exists() or not list((prompts_dir / stage).glob("*.md"))
    ]
    assert not missing, f"Stages with no prompts after sync: {missing}"

    prompt_files = [f for f in prompts_dir.rglob("*.md") if f.name != "README.md"]
    assert len(prompt_files) > 0, "Sync produced no prompt files"


def test_synced_files_have_attribution_headers():
    """Every synced prompt file must start with the CC BY 4.0 attribution comment."""
    prompts_dir = REF_DIR / "prompts"
    if not prompts_dir.exists():
        return  # sync not yet run — skip silently

    attribution_prefix = "<!-- Source: github.com/AgriciDaniel/flow"
    failures = []
    for md_file in prompts_dir.rglob("*.md"):
        if md_file.name == "README.md":
            continue
        content = md_file.read_text(encoding="utf-8")
        if not content.startswith(attribution_prefix):
            failures.append(str(md_file.relative_to(REPO_ROOT)))

    assert not failures, (
        "Files missing attribution headers:\n" + "\n".join(failures)
    )


# ── Task 1 tests ──────────────────────────────────────────────────────────────

def test_agent_tools_does_not_include_bash():
    """agents/seo-flow.md must not grant Bash to the agent (VULN-A01)."""
    agent_file = REPO_ROOT / "agents" / "seo-flow.md"
    content = agent_file.read_text(encoding="utf-8")
    tools_line = next(
        (line for line in content.splitlines() if line.startswith("tools:")),
        ""
    )
    assert "Bash" not in tools_line, (
        f"Bash found in tools grant: {tools_line!r}\n"
        "Remove 'Bash' from the tools line in agents/seo-flow.md"
    )


def test_agent_has_untrusted_webfetch_rule():
    """agents/seo-flow.md must warn the agent that WebFetch responses are untrusted (VULN-A05)."""
    agent_file = REPO_ROOT / "agents" / "seo-flow.md"
    content = agent_file.read_text(encoding="utf-8")
    assert "WebFetch responses are untrusted" in content, (
        "Missing untrusted-WebFetch security rule in agents/seo-flow.md"
    )


def _load_sync_flow_module():
    path = REPO_ROOT / "scripts" / "sync_flow.py"
    spec = _ilu.spec_from_file_location("sync_flow", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# ── Task 2 tests ──────────────────────────────────────────────────────────────

def test_base_headers_has_no_authorization():
    """_base_headers() must not include an Authorization header (VULN-A02)."""
    sf = _load_sync_flow_module()
    headers = sf._base_headers()
    assert "Authorization" not in headers, (
        "Authorization found in _base_headers() — anon headers must be token-free"
    )
    assert "Accept" in headers
    assert "X-GitHub-Api-Version" in headers


def test_authed_headers_degrades_when_gh_missing(monkeypatch):
    """_authed_headers() returns base headers if gh CLI is not on PATH (VULN-A06)."""
    sf = _load_sync_flow_module()

    def _fake_run(*args, **kwargs):
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr(sf.subprocess, "run", _fake_run)
    headers = sf._authed_headers()
    assert "Authorization" not in headers


def test_api_get_retries_unauthenticated_429_with_cli_token(monkeypatch):
    """GitHub may return 429 instead of 403 when the anonymous pool is spent."""
    sf = _load_sync_flow_module()
    import io

    rate_limited = sf.urllib.error.HTTPError(
        "https://api.github.com/example", 429, "too many requests", {}, io.BytesIO()
    )

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def read(_limit):
            return b'{"content":""}'

    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if len(calls) == 1:
            raise rate_limited
        return _Response()

    monkeypatch.setattr(sf.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        sf,
        "_authed_headers",
        lambda: {**sf._base_headers(), "Authorization": "Bearer test-token"},
    )

    assert sf.api_get("file.md", None, sf._base_headers()) == {"content": ""}
    assert len(calls) == 2
    assert calls[1].get_header("Authorization") == "Bearer test-token"


def _completed(returncode, stderr):
    return subprocess.CompletedProcess(["sync_flow.py", "--dry-run"], returncode, "", stderr)


def _http_error(sf, code, reason, headers=None):
    import io

    return sf.urllib.error.HTTPError(
        "https://api.github.com/example", code, reason, headers or {}, io.BytesIO()
    )


def _raise_on_urlopen(monkeypatch, sf, exc):
    def fake_urlopen(request, timeout):
        raise exc

    monkeypatch.setattr(sf.urllib.request, "urlopen", fake_urlopen)
    # No gh token to fall back on, as in a rate-limited CI job.
    monkeypatch.setattr(sf, "_authed_headers", sf._base_headers)


def test_script_keeps_the_markers_the_skip_relies_on():
    sf = _load_sync_flow_module()
    assert sf.EXIT_RATE_LIMITED == EXIT_RATE_LIMITED
    assert sf.RATE_LIMIT_MESSAGE == RATE_LIMIT_MESSAGE
    assert sf.NETWORK_ERROR_MESSAGE == NETWORK_ERROR_MESSAGE


@pytest.mark.parametrize("code, reason, headers", [
    (403, "rate limit exceeded", {}),
    (403, "Forbidden", {"x-ratelimit-remaining": "0"}),
    (403, "Forbidden", {"retry-after": "60"}),
    (429, "too many requests", {}),
])
def test_rate_limit_exits_with_a_recognisable_code_and_message(
        monkeypatch, capsys, code, reason, headers):
    sf = _load_sync_flow_module()
    _raise_on_urlopen(monkeypatch, sf, _http_error(sf, code, reason, headers))
    with pytest.raises(SystemExit) as exc:
        sf.api_get("file.md", None, sf._base_headers())
    assert exc.value.code == EXIT_RATE_LIMITED
    err = capsys.readouterr().err
    assert RATE_LIMIT_MESSAGE in err and f"HTTP {code}" in err


def test_rate_limit_after_the_token_retry_is_still_reported(monkeypatch, capsys):
    sf = _load_sync_flow_module()
    _raise_on_urlopen(monkeypatch, sf, _http_error(sf, 403, "rate limit exceeded"))
    monkeypatch.setattr(
        sf, "_authed_headers",
        lambda: {**sf._base_headers(), "Authorization": "Bearer test-token"},
    )
    with pytest.raises(SystemExit) as exc:
        sf.api_get("file.md", None, sf._base_headers())
    assert exc.value.code == EXIT_RATE_LIMITED
    assert RATE_LIMIT_MESSAGE in capsys.readouterr().err


@pytest.mark.parametrize("code, reason", [(403, "Forbidden"), (404, "Not Found"), (500, "boom")])
def test_other_http_errors_are_not_reported_as_rate_limits(monkeypatch, capsys, code, reason):
    sf = _load_sync_flow_module()
    _raise_on_urlopen(monkeypatch, sf, _http_error(sf, code, reason))
    with pytest.raises(sf.urllib.error.HTTPError):
        sf.api_get("file.md", None, sf._base_headers())
    assert RATE_LIMIT_MESSAGE not in capsys.readouterr().err


def test_timeout_while_reading_is_a_network_error(monkeypatch):
    sf = _load_sync_flow_module()
    _raise_on_urlopen(monkeypatch, sf, TimeoutError("timed out"))
    with pytest.raises(SystemExit) as exc:
        sf.api_get("file.md", None, sf._base_headers())
    assert str(exc.value.code).startswith(NETWORK_ERROR_MESSAGE)


@pytest.mark.parametrize("returncode, stderr", [
    (EXIT_RATE_LIMITED, f"{RATE_LIMIT_MESSAGE} (HTTP 403: rate limit exceeded)."),
    (1, f"fetch: docs/x.md\n{NETWORK_ERROR_MESSAGE}: [Errno -3] Temporary failure"),
])
def test_dry_run_tests_skip_when_github_is_unavailable(returncode, stderr):
    with pytest.raises(pytest.skip.Exception):
        _skip_if_github_unavailable(_completed(returncode, stderr))


@pytest.mark.parametrize("returncode, stderr", [
    (0, ""),
    (1, "Traceback (most recent call last):\nKeyError: 'content'"),
    (1, "urllib.error.HTTPError: HTTP Error 404: Not Found"),
    (2, "usage: sync_flow.py [-h] [--dry-run] [--ref SHA]"),
])
def test_dry_run_tests_do_not_skip_on_a_real_defect(returncode, stderr):
    _skip_if_github_unavailable(_completed(returncode, stderr))  # must not raise


# ── Task 3 tests ──────────────────────────────────────────────────────────────

def test_validate_github_url_blocks_non_github_host():
    """_validate_github_url must reject any host other than api.github.com (VULN-A10)."""
    sf = _load_sync_flow_module()
    import pytest
    with pytest.raises(ValueError, match="Blocked"):
        sf._validate_github_url("https://evil.example.com/repos/AgriciDaniel/flow/contents/file.md")


def test_validate_github_url_blocks_userinfo_ssrf():
    """_validate_github_url must block @evil.com userinfo bypass (VULN-A10)."""
    sf = _load_sync_flow_module()
    import pytest
    with pytest.raises(ValueError, match="Blocked"):
        sf._validate_github_url("https://api.github.com@evil.com/repos/AgriciDaniel/flow/contents/file.md")


def test_validate_github_url_allows_github_api():
    """_validate_github_url must not raise for api.github.com URLs (VULN-A10)."""
    sf = _load_sync_flow_module()
    # Should not raise
    sf._validate_github_url("https://api.github.com/repos/AgriciDaniel/flow/contents/README.md")


def test_record_write_blocks_path_traversal(tmp_path):
    """record_write must raise ValueError if path escapes the root directory (VULN-A03)."""
    sf = _load_sync_flow_module()
    root = tmp_path / "root"
    root.mkdir()
    # Path outside root
    escape_path = tmp_path / "escaped_file.txt"
    changes = {"added": [], "updated": [], "unchanged": [], "hashes": {}}
    import pytest
    with pytest.raises(ValueError, match="Path traversal blocked"):
        sf.record_write(root, escape_path, "bad content", dry_run=False, changes=changes)


# ── Task 4 tests ──────────────────────────────────────────────────────────────

def test_sha256_is_deterministic():
    """_sha256 must return the same hash for the same input, SHA-256 format (VULN-A04)."""
    sf = _load_sync_flow_module()
    assert sf._sha256("hello") == sf._sha256("hello")
    assert sf._sha256("hello") != sf._sha256("world")
    digest = sf._sha256("test")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


# ── Task 5 tests ──────────────────────────────────────────────────────────────

def test_prompts_readme_has_cc_attribution():
    """references/prompts/README.md must contain the CC BY 4.0 attribution header (INFO-A14)."""
    readme = REPO_ROOT / "skills" / "seo-flow" / "references" / "prompts" / "README.md"
    content = readme.read_text(encoding="utf-8")
    assert "CC BY 4.0" in content, (
        "Missing CC BY 4.0 attribution in skills/seo-flow/references/prompts/README.md"
    )
    assert "github.com/AgriciDaniel/flow" in content, (
        "Missing source URL in prompts README attribution"
    )
