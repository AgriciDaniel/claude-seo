"""Managed runtime and safe-dispatch regressions."""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_xquik_manual_extension_uses_its_installed_adapter(tmp_path: Path) -> None:
    root = tmp_path / "skills" / "seo"
    scripts = tmp_path / "skills" / "seo-xquik" / "scripts"
    scripts.mkdir(parents=True)
    adapter = scripts / "xquik_research.py"
    adapter.write_text("print('ok')\n", encoding="utf-8")

    assert runtime._resolve_script(root, adapter.name, "xquik") == adapter.resolve()


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
