"""Managed runtime and safe-dispatch regressions."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import signal
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.doctor_agents import AgentTreeCheck

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("claude_seo_runtime", ROOT / "scripts/runtime.py")
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "plugin root"
    (root / "scripts").mkdir(parents=True)
    (root / "extensions" / "banana" / "scripts").mkdir(parents=True)
    (root / ".claude-plugin").mkdir()
    (root / "requirements.txt").write_text("requests>=2\n", encoding="utf-8")
    (root / ".claude-plugin" / "plugin.json").write_text('{"version":"2.2.4"}\n', encoding="utf-8")
    (root / "scripts" / "render_page.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "extensions" / "banana" / "scripts" / "generate.py").write_text("print('ok')\n", encoding="utf-8")
    return root


def test_dispatch_is_allowlisted_and_rejects_traversal(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    assert runtime._resolve_script(root, "render_page.py", None).name == "render_page.py"
    assert runtime._resolve_script(root, "generate.py", "banana").name == "generate.py"
    with pytest.raises(ValueError):
        runtime._resolve_script(root, "../render_page.py", None)
    with pytest.raises(ValueError):
        runtime._resolve_script(root, "runtime.py", None)
    with pytest.raises(ValueError):
        runtime._resolve_script(root, "generate.py", "../banana")


def test_manual_extension_fallback_stays_inside_installed_skill(tmp_path: Path) -> None:
    root = tmp_path / "skills" / "seo"
    scripts = tmp_path / "skills" / "seo-image-gen" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "generate.py").write_text("print('ok')\n", encoding="utf-8")
    assert runtime._resolve_script(root, "generate.py", "banana") == (
        scripts / "generate.py"
    ).resolve()


def test_status_uses_plugin_data_and_hash_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _fixture_root(tmp_path)
    data = tmp_path / "persistent data"
    python = data / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data))
    expected = runtime._expected(root)
    (data / "runtime-state.json").write_text(json.dumps({**expected, "browser_ready": True}), encoding="utf-8")
    status = runtime._status(root)
    assert status["ready"] is True
    assert status["mode"] == "plugin"
    (root / "requirements.txt").write_text("requests>=3\n", encoding="utf-8")
    assert runtime._status(root)["ready"] is False


def test_source_checkout_uses_repository_venv_without_plugin_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    (root / ".git").mkdir()
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_SEO_DATA_DIR", raising=False)
    data_dir, mode = runtime._data_dir(root)
    assert data_dir == root
    assert mode == "manual"


def test_doctor_json_omits_paths_and_environment_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _fixture_root(tmp_path)
    sensitive_path = tmp_path / "person-name" / "private"
    monkeypatch.setattr(runtime, "_root", lambda: root)
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(sensitive_path))
    rc = runtime.command_doctor(SimpleNamespace(json=True))
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert rc == 3
    assert str(sensitive_path) not in output
    assert set(payload) == {
        "browser_ready", "mode", "plugin_version", "python_version", "ready", "reasons"
    }


def test_format_agent_tree_check_ok() -> None:
    lines = runtime.format_agent_tree_check(
        AgentTreeCheck(ok=True, missing=[], broken_symlinks=[])
    )

    assert lines == ["Audit subagent check: ok"]


def test_format_agent_tree_check_incomplete() -> None:
    lines = runtime.format_agent_tree_check(
        AgentTreeCheck(
            ok=False,
            missing=["seo-content.md"],
            broken_symlinks=["seo-technical.md"],
        )
    )

    assert "Audit subagent check: incomplete" in lines
    assert "Missing agents: seo-content.md" in lines
    assert "Broken agent symlinks: seo-technical.md" in lines
    assert (
        "/seo audit will fall back to inline analysis with reduced independence "
        "until these agents resolve."
    ) in lines


def test_agent_dir_for_doctor_prefers_project_claude_agents(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    project_agents = root / ".claude" / "agents"
    package_agents = root / "agents"
    project_agents.mkdir(parents=True)
    package_agents.mkdir()

    assert runtime.agent_dir_for_doctor(root) == project_agents


def test_agent_dir_for_doctor_keeps_broken_project_agent_symlink(tmp_path: Path) -> None:
    if os.name != "posix":
        return

    root = tmp_path / "repo"
    package_agents = root / "agents"
    broken_project_agents = root / ".claude" / "agents"
    package_agents.mkdir(parents=True)
    broken_project_agents.parent.mkdir()
    broken_project_agents.symlink_to(tmp_path / "missing-agents")

    assert runtime.agent_dir_for_doctor(root) == broken_project_agents


def test_agent_dir_for_doctor_uses_packaged_agents(tmp_path: Path) -> None:
    root = tmp_path / "plugin"
    package_agents = root / "agents"
    package_agents.mkdir(parents=True)

    assert runtime.agent_dir_for_doctor(root) == package_agents


def test_agent_dir_for_doctor_falls_back_to_home_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "skills" / "seo"
    home = tmp_path / "home"
    monkeypatch.setattr(runtime.Path, "home", classmethod(lambda cls: home))

    assert runtime.agent_dir_for_doctor(root) == home / ".claude" / "agents"


def test_doctor_text_reports_agent_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _fixture_root(tmp_path)
    monkeypatch.setattr(runtime, "_root", lambda: root)
    monkeypatch.setattr(
        runtime,
        "check_agent_tree",
        lambda _: AgentTreeCheck(
            ok=False,
            missing=["seo-content.md"],
            broken_symlinks=["seo-technical.md"],
        ),
    )

    rc = runtime.command_doctor(SimpleNamespace(json=False))
    output = capsys.readouterr().out

    assert rc == 3
    assert "Audit subagent check: incomplete" in output
    assert "Missing agents: seo-content.md" in output
    assert "Broken agent symlinks: seo-technical.md" in output


def test_child_environment_forces_utf8_and_persistent_browser_path(tmp_path: Path) -> None:
    env = runtime._safe_env({"data_dir": tmp_path})
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path / "ms-playwright")


def test_configured_data_dir_rejects_filesystem_root_and_user_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError):
        runtime._configured_data_dir(str(Path(Path.cwd().anchor)))
    monkeypatch.setattr(runtime.Path, "home", classmethod(lambda cls: Path.cwd()))
    with pytest.raises(ValueError):
        runtime._configured_data_dir(str(Path.cwd()))


def test_version_only_change_does_not_stale_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _fixture_root(tmp_path)
    data = tmp_path / "data"
    python = data / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data))
    expected = runtime._expected(root)
    expected["plugin_version"] = "2.2.2"
    (data / "runtime-state.json").write_text(json.dumps(expected), encoding="utf-8")
    assert runtime._status(root)["ready"] is True


def test_error_redaction_hides_credentials_and_tokens() -> None:
    text = (
        f"{Path.home()}/private user@example.test "
        "https://user:password@example.test/path?token=visible token=abc123 api_key: xyz"
    )
    redacted = runtime._redact(text)
    assert str(Path.home()) not in redacted
    assert "user@example.test" not in redacted
    assert "password@example" not in redacted
    assert "visible" not in redacted
    assert "abc123" not in redacted
    assert " xyz" not in redacted


def test_browser_marker_requires_browser_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _fixture_root(tmp_path)
    data = tmp_path / "data"
    python = data / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data))
    expected = runtime._expected(root)
    (data / "runtime-state.json").write_text(
        json.dumps({**expected, "browser_ready": True}), encoding="utf-8"
    )
    assert runtime._status(root)["browser_ready"] is False
    (data / "ms-playwright" / "chromium-123").mkdir(parents=True)
    assert runtime._status(root)["browser_ready"] is True


def test_setup_restores_previous_environment_when_staged_swap_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_root(tmp_path)
    data = tmp_path / "data"
    final = data / ".venv"
    old_python = final / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    old_python.parent.mkdir(parents=True)
    old_python.write_text("old", encoding="utf-8")
    (final / "old-sentinel").write_text("keep", encoding="utf-8")
    data.mkdir(parents=True, exist_ok=True)
    (data / "runtime-state.json").write_text(
        json.dumps(runtime._expected(root)), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data))
    monkeypatch.setattr(runtime, "_root", lambda: root)

    def fake_checked(argv: list[str], *, env: dict[str, str], stage: str) -> subprocess.CompletedProcess[str]:
        if stage == "virtual environment creation":
            staged = Path(argv[-1])
            staged_python = runtime._venv_python(staged)
            staged_python.parent.mkdir(parents=True)
            staged_python.write_text("new", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "", "")

    original_replace = Path.replace

    def fail_staged_replace(self: Path, target: Path) -> Path:
        if self.name.startswith(".venv.next-"):
            raise OSError("injected staged swap failure")
        return original_replace(self, target)

    monkeypatch.setattr(runtime, "_run_checked", fake_checked)
    monkeypatch.setattr(Path, "replace", fail_staged_replace)
    rc = runtime.command_setup(SimpleNamespace(skip_browser=True))
    assert rc == 1
    assert (final / "old-sentinel").read_text(encoding="utf-8") == "keep"
    assert not (data / ".venv.previous").exists()
    assert not (data / ".runtime-state.next").exists()


def test_run_propagates_child_signal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _fixture_root(tmp_path)
    managed_python = tmp_path / "python"
    managed_python.write_text("", encoding="utf-8")
    status = {
        "ready": True,
        "python_path": managed_python,
        "data_dir": tmp_path,
    }
    delivered: list[tuple[int, int]] = []
    monkeypatch.setattr(runtime, "_root", lambda: root)
    monkeypatch.setattr(runtime, "_status", lambda _: status)
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], -signal.SIGTERM),
    )
    monkeypatch.setattr(runtime.os, "kill", lambda pid, sig: delivered.append((pid, sig)))
    rc = runtime.command_run(
        SimpleNamespace(script="render_page.py", extension=None, script_args=[])
    )
    assert rc == 128 + signal.SIGTERM
    assert delivered == [(os.getpid(), signal.SIGTERM)]


# Scripts run without an --extension flag are dispatched straight from the
# core scripts/ directory, so they must be listed in ALLOWED_CORE_SCRIPTS or
# `claude-seo run` refuses them at runtime, even though the SKILL.md/agent
# instructions look correct. This regression was caught by hand for
# keywordseverywhere_api.py (SKILL.md wired it up, ALLOWED_CORE_SCRIPTS did
# not list it) -- this test makes sure the next one doesn't ship silently.
_RUN_INVOCATION = re.compile(r'run\s+([A-Za-z0-9_]+\.py)(?!["\']?\s*--extension)')
_EXTENSION_FLAG = re.compile(r'run\s+[A-Za-z0-9_]+\.py[^\n]*--extension\b')


def _instruction_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ("skills/**/SKILL.md", "agents/*.md"):
        files.extend(sorted(ROOT.glob(pattern)))
    return files


def test_every_skill_invoked_script_is_runtime_allowlisted() -> None:
    missing: list[str] = []
    for path in _instruction_files():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for line in text.splitlines():
            if _EXTENSION_FLAG.search(line):
                # Extension scripts are dispatched via extensions/<name>/scripts/
                # and are not, and should not be, in ALLOWED_CORE_SCRIPTS.
                continue
            for match in _RUN_INVOCATION.finditer(line):
                script = match.group(1)
                if script not in runtime.ALLOWED_CORE_SCRIPTS:
                    missing.append(f"{rel}: {script}")
    assert not missing, (
        "scripts invoked from SKILL.md/agent instructions but missing from "
        "ALLOWED_CORE_SCRIPTS in scripts/runtime.py (claude-seo run would "
        "refuse them): " + "; ".join(missing)
    )

def test_failed_stage_reports_child_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    stderr = "\n".join(
        [
            "Looking in links: /tmp/tmp8b58vt29",
            "ERROR: Could not install packages due to an OSError: [WinError 206] "
            "Der Dateiname oder die Erweiterung ist zu lang",
            "",
        ]
    )
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 1, "", stderr),
    )
    with pytest.raises(RuntimeError) as excinfo:
        runtime._run_checked(["python", "-m", "venv", "x"], env={}, stage="virtual environment creation")
    message = str(excinfo.value)
    assert message.startswith("virtual environment creation failed with exit code 1")
    assert "[WinError 206]" in message


def test_failed_stage_falls_back_to_stdout_and_bounds_the_tail(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = "\n".join(f"line {index}" for index in range(40))
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 2, stdout, ""),
    )
    with pytest.raises(RuntimeError) as excinfo:
        runtime._run_checked(["pip"], env={}, stage="dependency installation")
    message = str(excinfo.value)
    assert "line 39" in message
    assert "line 10" in message
    assert "line 9" not in message


def test_successful_stage_returns_the_completed_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "ok", "warning noise"),
    )
    assert runtime._run_checked(["pip"], env={}, stage="dependency installation").stdout == "ok"


def test_redaction_covers_repr_quoted_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime.Path, "home", classmethod(lambda cls: Path(r"C:\Users\someone")))
    quoted = repr(r"C:\Users\someone\.claude\skills\seo\.venv.next-1\Scripts\python.exe")
    nested = repr(f"sys.path = [{quoted}]")
    redacted = runtime._redact(
        f"Command '[{quoted}, '-c', {nested}]' returned non-zero exit status 1.\n"
        "Looking in links: c:\\users\\someone\\AppData\\Local\\Temp\\tmp1"
    )
    assert "someone" not in redacted
    assert redacted.count("<home>") == 3


def test_browser_setup_warning_is_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # _run_checked now embeds the child's own stderr tail (#300), so a failed
    # Chromium install can carry the home directory (playwright's cache path,
    # a download URL, ...). That message is printed as a non-fatal warning
    # rather than routed through the fatal-error handler, so it must be
    # redacted at its own print site instead of relying on the one at the
    # bottom of command_setup.
    root = _fixture_root(tmp_path)
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "runtime-state.json").write_text(
        json.dumps(runtime._expected(root)), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data))
    monkeypatch.setattr(runtime, "_root", lambda: root)
    fake_home = tmp_path / "home" / "someone"
    monkeypatch.setattr(runtime.Path, "home", classmethod(lambda cls: fake_home))

    def fake_checked(argv: list[str], *, env: dict[str, str], stage: str) -> subprocess.CompletedProcess[str]:
        if stage == "virtual environment creation":
            staged = Path(argv[-1])
            staged_python = runtime._venv_python(staged)
            staged_python.parent.mkdir(parents=True)
            staged_python.write_text("new", encoding="utf-8")
        if stage == "Chromium installation":
            raise RuntimeError(
                "Chromium installation failed with exit code 1\n"
                f"  Failed to download to {fake_home}/.cache/ms-playwright/chromium"
            )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(runtime, "_run_checked", fake_checked)
    rc = runtime.command_setup(SimpleNamespace(skip_browser=False))
    assert rc == 10
    captured = capsys.readouterr()
    assert str(fake_home) not in captured.err
    assert "<home>" in captured.err
