"""Portability regressions for drift baseline subprocess handoff."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import drift_baseline  # noqa: E402


def test_fetch_page_data_uses_tempfile_not_dev_stdout_or_stdin() -> None:
    calls: list[tuple[list[str], dict]] = []
    temp_paths: list[Path] = []

    def fake_run(cmd: list[str], **kwargs):
        calls.append((cmd, kwargs))
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"

        if cmd[1].endswith("fetch_page.py"):
            assert "/dev/stdout" not in cmd
            output_path = Path(cmd[cmd.index("--output") + 1])
            temp_paths.append(output_path)
            output_path.write_bytes(b"<html><title>caf\xc3\xa9 \x8f</title></html>")
            return SimpleNamespace(returncode=0, stdout="", stderr="Status: 203\n")

        if cmd[1].endswith("parse_html.py"):
            assert "input" not in kwargs
            assert Path(cmd[2]) == temp_paths[0]
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"title": "café �", "h1": [], "h2": [], "schema": []}),
                stderr="",
            )

        raise AssertionError(f"unexpected command: {cmd}")

    with patch.object(drift_baseline.subprocess, "run", side_effect=fake_run):
        result = drift_baseline.fetch_page_data("https://example.com/")

    assert result["error"] is None
    assert result["status_code"] == 203
    assert "café" in result["html"]
    assert result["parsed"]["title"] == "café �"
    assert all("/dev/stdout" not in cmd for cmd, _kwargs in calls)
    assert temp_paths and not os.path.exists(temp_paths[0])
