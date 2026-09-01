"""Regression: extension installers must not source-inject credentials.

Before the fix, the DataForSEO / Firecrawl / Banana shell installers
interpolated user-supplied credentials directly into a ``python3 -c``
source string, so a credential containing ``'''`` broke out of the string
literal and executed arbitrary code at install time. The fix passes
credentials as ``sys.argv`` via a quoted heredoc and writes the
credential-bearing settings file atomically with ``0600`` perms.

The Creaitor section at the bottom holds the same line for the one installer
that writes the Claude user config (``~/.claude.json``) instead of
``settings.json``, and additionally pins that the merge is non-destructive.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# rel path -> number of argv slots the heredoc consumes (incl. settings path)
INSTALLERS = {
    "extensions/dataforseo/install.sh": 4,  # settings, username, password, field_config
    "extensions/firecrawl/install.sh": 2,   # settings, api_key
    "extensions/banana/install.sh": 2,      # settings, api_key
}

_HEREDOC_RE = re.compile(r"<<'PY'\n(.*?)\nPY\n", re.DOTALL)


def _extract_writer(text: str) -> str:
    match = _HEREDOC_RE.search(text)
    assert match, "no quoted <<'PY' heredoc found in installer"
    return match.group(1)


@pytest.mark.parametrize("rel,argc", INSTALLERS.items())
def test_installer_uses_safe_credential_pattern(rel: str, argc: int) -> None:
    text = (ROOT / rel).read_text(encoding="utf-8")
    # The unsafe signature was a shell variable interpolated into a Python
    # triple-quoted string literal (e.g. '''${DFSE_PASSWORD}''').
    assert "'''${" not in text, f"{rel} still interpolates a credential into Python source"
    assert "<<'PY'" in text, f"{rel} missing quoted heredoc"
    assert "sys.argv" in text, f"{rel} not reading credentials from argv"
    assert "0o600" in text, f"{rel} not writing settings with 0600 perms"


@pytest.mark.parametrize("rel,argc", INSTALLERS.items())
def test_installer_credential_injection_is_inert(tmp_path: Path, rel: str, argc: int) -> None:
    writer = _extract_writer((ROOT / rel).read_text(encoding="utf-8"))
    script = tmp_path / "writer.py"
    script.write_text(writer, encoding="utf-8")

    settings = tmp_path / "settings.json"
    marker = tmp_path / "PWNED"
    payload = f"x'''; open({str(marker)!r}, 'w').write('pwned'); y='''"

    # settings path + credential slots; the first credential carries the payload
    argv = [sys.executable, str(script), str(settings), payload]
    argv += ["filler"] * (argc - 2)
    subprocess.run(argv, check=True, cwd=tmp_path)

    assert not marker.exists(), f"{rel}: credential injection executed code"
    blob = json.dumps(json.loads(settings.read_text(encoding="utf-8")))
    assert payload in blob, f"{rel}: credential not stored literally"
    assert (settings.stat().st_mode & 0o777) == 0o600, f"{rel}: settings not 0600"


# ---------------------------------------------------------------------------
# Creaitor: remote MCP server, so the entry lands in the Claude *user config*
# (~/.claude.json) rather than settings.json. That file holds the whole Claude
# Code user state, which raises the stakes on two fronts the tests below pin:
# the merge must preserve unrelated keys, and the token must never reach the
# Python source, argv, or stdout.
# ---------------------------------------------------------------------------

CREAITOR_INSTALL = "extensions/creaitor/install.sh"
CREAITOR_UNINSTALL = "extensions/creaitor/uninstall.sh"
CREAITOR_MCP_URL = "https://app.creaitor.ai/api/v2/mcp"


def _creaitor_config(**extra: object) -> dict:
    """A ~/.claude.json with unrelated state the installer must not disturb."""
    config = {
        "numStartups": 7,
        "installMethod": "native",
        "projects": {"/tmp/demo": {"allowedTools": ["Read"]}},
        "mcpServers": {
            "unrelated": {"command": "npx", "args": ["-y", "some-server"]},
        },
    }
    config.update(extra)
    return config


def _clean_env(**extra: str) -> dict[str, str]:
    """Minimal subprocess environment: never leak unrelated CI/user secrets."""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    env.update(extra)
    return env


def test_creaitor_installer_keeps_the_token_out_of_source_and_argv() -> None:
    text = (ROOT / CREAITOR_INSTALL).read_text(encoding="utf-8")
    writer = _extract_writer(text)

    assert "'''${" not in text, "credential interpolated into Python source"
    assert "<<'PY'" in text, "heredoc must be quoted so the shell expands nothing"
    assert "${CREAITOR_TOKEN}" not in writer, "token interpolated into the writer"
    assert 'os.environ["CREAITOR_TOKEN"]' in writer, "token must arrive via the environment"
    # argv carries the config path only; a token in argv is world-readable via `ps`.
    assert 'python3 - "${CLAUDE_JSON}" <<' in text, "token must not be passed in argv"
    assert "read -rsp" in text, "token prompt must not echo"
    assert "0o600" in writer, "config must be written 0600"
    assert 'CLAUDE_JSON="${HOME}/.claude.json"' in text, (
        "remote MCP servers are configured in ~/.claude.json, not settings.json"
    )
    assert 'url = "https://app.creaitor.ai/api/v2/mcp"' in writer
    assert "CREAITOR_MCP_URL" not in text, "token endpoint must not be environment-overridable"


def test_creaitor_windows_installer_checks_native_python_exit() -> None:
    text = (ROOT / "extensions/creaitor/install.ps1").read_text(encoding="utf-8")
    assert "$LASTEXITCODE -ne 0" in text
    assert "throw \"Failed to update $ClaudeJson" in text


def test_creaitor_config_writer_injection_is_inert_and_preserves_config(
    tmp_path: Path,
) -> None:
    writer = _extract_writer((ROOT / CREAITOR_INSTALL).read_text(encoding="utf-8"))
    script = tmp_path / "writer.py"
    script.write_text(writer, encoding="utf-8")

    config = tmp_path / ".claude.json"
    existing = _creaitor_config()
    config.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    marker = tmp_path / "PWNED"
    payload = f"tok'''; open({str(marker)!r}, 'w').write('pwned'); x='''"

    proc = subprocess.run(
        [sys.executable, str(script), str(config)],
        env=_clean_env(CREAITOR_TOKEN=payload),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    assert not marker.exists(), "token payload executed code"

    data = json.loads(config.read_text(encoding="utf-8"))
    for key in ("numStartups", "installMethod", "projects"):
        assert data[key] == existing[key], f"installer clobbered unrelated key {key}"
    assert data["mcpServers"]["unrelated"] == existing["mcpServers"]["unrelated"], (
        "installer clobbered an unrelated MCP server"
    )
    assert data["mcpServers"]["creaitor-geo"] == {
        "type": "http",
        "url": CREAITOR_MCP_URL,
        "headers": {
            "Authorization": f"Bearer {payload}",
            "Content-Type": "application/json",
        },
    }, "remote MCP entry is not the expected http/url/headers object"

    assert (config.stat().st_mode & 0o777) == 0o600, "~/.claude.json not written 0600"
    assert payload not in proc.stdout + proc.stderr, "token leaked to the terminal"


def test_creaitor_installer_refuses_to_overwrite_unparseable_config(
    tmp_path: Path,
) -> None:
    """A corrupt ~/.claude.json must abort, not get replaced by our single key."""
    writer = _extract_writer((ROOT / CREAITOR_INSTALL).read_text(encoding="utf-8"))
    script = tmp_path / "writer.py"
    script.write_text(writer, encoding="utf-8")

    config = tmp_path / ".claude.json"
    config.write_text('{"projects": {', encoding="utf-8")  # truncated write

    proc = subprocess.run(
        [sys.executable, str(script), str(config)],
        env=_clean_env(CREAITOR_TOKEN="tok"),
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert config.read_text(encoding="utf-8") == '{"projects": {'


def test_creaitor_uninstaller_removes_only_its_own_entry(tmp_path: Path) -> None:
    writer = _extract_writer((ROOT / CREAITOR_UNINSTALL).read_text(encoding="utf-8"))
    script = tmp_path / "remover.py"
    script.write_text(writer, encoding="utf-8")

    config = tmp_path / ".claude.json"
    existing = _creaitor_config()
    existing["mcpServers"]["creaitor-geo"] = {
        "type": "http",
        "url": CREAITOR_MCP_URL,
        "headers": {"Authorization": "Bearer secret", "Content-Type": "application/json"},
    }
    config.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(script), str(config)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    data = json.loads(config.read_text(encoding="utf-8"))
    assert "creaitor-geo" not in data["mcpServers"]
    assert data["mcpServers"]["unrelated"] == _creaitor_config()["mcpServers"]["unrelated"]
    assert data["projects"] == _creaitor_config()["projects"]
    assert (config.stat().st_mode & 0o777) == 0o600
    assert "secret" not in proc.stdout + proc.stderr


def test_creaitor_full_installer_invalid_config_leaves_no_skill(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude/skills/seo").mkdir(parents=True)
    config = home / ".claude.json"
    config.write_text('{"broken":', encoding="utf-8")

    proc = subprocess.run(
        ["bash", str(ROOT / CREAITOR_INSTALL)],
        input="dummy-token\n",
        env=_clean_env(HOME=str(home)),
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert config.read_text(encoding="utf-8") == '{"broken":'
    assert not (home / ".claude/skills/seo-creaitor").exists()
    assert "dummy-token" not in proc.stdout + proc.stderr


def test_creaitor_full_installer_reinstall_has_no_nested_skill_dirs(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude/skills/seo").mkdir(parents=True)
    for token in ("first-token", "second-token"):
        subprocess.run(
            ["bash", str(ROOT / CREAITOR_INSTALL)],
            input=token + "\n",
            env=_clean_env(HOME=str(home)),
            capture_output=True,
            text=True,
            check=True,
        )
    skill = home / ".claude/skills/seo-creaitor"
    assert (skill / "references/mcp-tools.json").is_file()
    assert (skill / "scripts" / "resolve_domain.py").is_file()
    assert not (skill / "references/references").exists()
    config = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert config["mcpServers"]["creaitor-geo"]["headers"]["Authorization"] == (
        "Bearer second-token"
    )


def test_creaitor_full_uninstaller_invalid_config_keeps_skill(tmp_path: Path) -> None:
    home = tmp_path / "home"
    skill = home / ".claude/skills/seo-creaitor"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("installed", encoding="utf-8")
    config = home / ".claude.json"
    config.write_text('{"broken":', encoding="utf-8")

    proc = subprocess.run(
        ["bash", str(ROOT / CREAITOR_UNINSTALL)],
        env=_clean_env(HOME=str(home)),
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert config.read_text(encoding="utf-8") == '{"broken":'
    assert (skill / "SKILL.md").is_file()


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell not installed")
def test_creaitor_windows_uninstaller_removes_config_then_skill(tmp_path: Path) -> None:
    home = tmp_path / "home"
    skill = home / ".claude/skills/seo-creaitor"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("installed", encoding="utf-8")
    config = home / ".claude.json"
    existing = _creaitor_config()
    existing["mcpServers"]["creaitor-geo"] = {
        "type": "http",
        "url": CREAITOR_MCP_URL,
        "headers": {"Authorization": "Bearer windows-secret"},
    }
    config.write_text(json.dumps(existing), encoding="utf-8")

    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(ROOT / "extensions/creaitor/uninstall.ps1")],
        env=_clean_env(HOME=str(home)),
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(config.read_text(encoding="utf-8"))
    assert "creaitor-geo" not in data["mcpServers"]
    assert "unrelated" in data["mcpServers"]
    assert not skill.exists()
    assert "windows-secret" not in proc.stdout + proc.stderr
