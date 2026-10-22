"""Static installer/runtime contract checks that do not mutate a real home."""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_unix_installer_delegates_to_runtime_without_global_pip() -> None:
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert '"${SKILL_DIR}/scripts/claude-seo" setup' in text
    assert "pip install --user" not in text
    assert "python3 -m venv" not in text
    assert '"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run' in text
    assert '"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" setup' in text
    assert '"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" doctor' in text
    assert '"${runtime_status}" -ne 0 ] && [ "${runtime_status}" -ne 10' in text
    assert 'find "${HOME}/.claude/skills"' not in text


def test_windows_installer_delegates_to_runtime_without_path_mutation() -> None:
    text = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert "scripts\\runtime.py" in text
    assert "'setup'" in text
    assert "SetEnvironmentVariable('PATH'" not in text
    assert "pip','install" not in text
    assert "UTF8Encoding($false)" in text
    assert "(3, $MinMinor) <= sys.version_info[:2] <= (3, $MaxMinor)" in text
    assert "$runtime.ExitCode -ne 0 -and $runtime.ExitCode -ne 10" in text
    assert "-Directory -Filter 'seo*'" not in text


@pytest.mark.skipif(
    os.name != "posix", reason="the executable bit is a POSIX mode bit; Windows has none"
)
def test_launcher_is_executable() -> None:
    assert (ROOT / "scripts/claude-seo").stat().st_mode & 0o100


def test_launcher_uses_safe_exec() -> None:
    text = (ROOT / "scripts/claude-seo").read_text(encoding="utf-8")
    assert 'exec "${CLAUDE_SEO_PYTHON}" "${runtime}" "$@"' in text
    assert 'exec "$@" "${runtime}" "${script_args[@]+"${script_args[@]}"}"' in text
    assert "eval " not in text
