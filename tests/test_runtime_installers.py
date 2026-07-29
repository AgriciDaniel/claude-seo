"""Static installer/runtime contract checks that do not mutate a real home."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_unix_installer_delegates_to_runtime_without_global_pip() -> None:
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert '"${SKILL_DIR}/bin/claude-seo" setup' in text
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
    assert "version_info >= (3, 10)" in text
    assert "$runtime.ExitCode -ne 0 -and $runtime.ExitCode -ne 10" in text
    assert "-Directory -Filter 'seo*'" not in text


def test_launcher_is_executable_and_uses_safe_exec() -> None:
    launcher = ROOT / "scripts/claude-seo"
    assert launcher.stat().st_mode & 0o100
    text = launcher.read_text(encoding="utf-8")
    assert 'exec py -3 "${runtime}" "$@"' in text
    assert 'exec python3 "${runtime}" "$@"' in text
    assert 'exec python "${runtime}" "$@"' in text
    assert "eval " not in text


def test_plugin_has_no_implicit_path_executables() -> None:
    """claude.ai rejects top-level bin/ because it bypasses admin review."""
    assert not any((ROOT / "bin").glob("**/*"))
