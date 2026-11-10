"""Cross-platform hook configuration regressions."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"
HOOK_LAUNCHER = REPO_ROOT / "hooks" / "run-python-hook.js"
INSTALL_PS1 = REPO_ROOT / "install.ps1"


def _post_tool_handler() -> dict:
    config = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    return config["hooks"]["PostToolUse"][0]["hooks"][0]


def test_schema_hook_uses_exec_form_args_and_tool_input_placeholder() -> None:
    handler = _post_tool_handler()
    serialized = json.dumps(handler)

    assert handler["type"] == "command"
    assert handler["command"] == "node"
    assert "args" in handler
    assert handler["args"][0] == "${CLAUDE_PLUGIN_ROOT}/hooks/run-python-hook.js"
    assert handler["args"][1] == "${CLAUDE_PLUGIN_ROOT}/hooks/validate-schema.py"
    assert handler["args"][2] == "${tool_input.file_path}"
    # Seconds. The hook runs one local Python validator; a hung interpreter
    # probe must not stall every Edit or Write for the default 10 minutes.
    assert handler["timeout"] == 30
    assert "$FILE_PATH" not in serialized
    assert "$" not in handler["command"]
    assert handler["command"] != "sh"


def test_hook_launcher_documents_python_probe_order() -> None:
    text = HOOK_LAUNCHER.read_text(encoding="utf-8")
    for marker in ("CLAUDE_SEO_PYTHON", "py", "-3", "python3", "python"):
        assert marker in text


def test_hook_launcher_preserves_blocking_exit_code_two(tmp_path: Path) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available in this test environment")

    script = tmp_path / "block.py"
    script.write_text(
        "import sys\n"
        "assert sys.argv[1] == 'payload'\n"
        "sys.exit(2)\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["CLAUDE_SEO_PYTHON"] = sys.executable

    proc = subprocess.run(
        [node, str(HOOK_LAUNCHER), str(script), "payload"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert proc.returncode == 2


def test_hook_launcher_skips_files_that_cannot_hold_schema(tmp_path: Path) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available in this test environment")

    # The skip is keyed on the script's basename, so the stand-in carries the
    # schema hook's name.
    script = tmp_path / "validate-schema.py"
    script.write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
    env = os.environ.copy()
    env["CLAUDE_SEO_PYTHON"] = sys.executable

    def run(path_arg: str) -> int:
        return subprocess.run(
            [node, str(HOOK_LAUNCHER), str(script), path_arg],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        ).returncode

    # Python never starts for files the validator would ignore anyway.
    assert run("notes.md") == 0
    assert run("app/main.py") == 0
    # Schema-bearing files, and an unsubstituted placeholder, still reach Python.
    assert run("Page.HTML") == 2
    assert run("${tool_input.file_path}") == 2


def test_hook_launcher_extension_skip_applies_only_to_schema_hook(tmp_path: Path) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available in this test environment")

    script = tmp_path / "other-hook.py"
    script.write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
    env = os.environ.copy()
    env["CLAUDE_SEO_PYTHON"] = sys.executable

    # Any other hook script runs whatever the file argument looks like.
    for path_arg in ("notes.md", "app/main.py", "page.html"):
        proc = subprocess.run(
            [node, str(HOOK_LAUNCHER), str(script), path_arg],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 2, path_arg


def test_hook_launcher_extensions_match_validator() -> None:
    launcher = HOOK_LAUNCHER.read_text(encoding="utf-8")
    validator = (REPO_ROOT / "hooks" / "validate-schema.py").read_text(encoding="utf-8")
    js_list = re.search(r"SCHEMA_FILE_EXTENSIONS = \[([^\]]*)\]", launcher).group(1)
    py_list = re.search(r"valid_extensions = \(([^)]*)\)", validator).group(1)

    assert re.findall(r'"([^"]+)"', js_list) == re.findall(r'"([^"]+)"', py_list)


def test_windows_installer_prefers_py_launcher_and_rejects_store_stubs() -> None:
    text = INSTALL_PS1.read_text(encoding="utf-8")
    py_pos = text.index("Exe = 'py'; Args = @('-3')")
    python3_pos = text.index("Exe = 'python3'; Args = @()")
    python_pos = text.index("Exe = 'python'; Args = @()")

    assert py_pos < python3_pos < python_pos
    assert "Microsoft Store|WindowsApps|App execution alias|was not found" in text
