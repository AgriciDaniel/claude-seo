"""The banana setup checks show no part of the key, only whether one is set.

They used to print the first eight characters and later the last four. Any
part of a secret in a log is flagged by CodeQL
(py/clear-text-logging-sensitive-data), so the output now says "set" or
"(not set)" and nothing else about the key.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FAKE_KEY = "AIzaSyFAKEFAKEFAKEFAKEFAKEFAKEFAKEwxyz"


def _load(monkeypatch, home: Path, name: str):
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {"nanobanana-mcp": {
        "command": "npx", "args": ["-y", "@ycse/nanobanana-mcp"],
        "env": {"GOOGLE_AI_API_KEY": FAKE_KEY},
    }}}))
    spec = importlib.util.spec_from_file_location(
        f"banana_{name}", REPO_ROOT / f"extensions/banana/scripts/{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name,call", [
    ("setup_mcp", lambda m: m.check_setup()),
    ("validate_setup", lambda m: m.main()),
])
def test_no_part_of_the_key_is_shown(monkeypatch, tmp_path, capsys, name, call):
    module = _load(monkeypatch, tmp_path, name)
    monkeypatch.setattr(sys, "argv", [name])
    call(module)
    out = capsys.readouterr().out
    assert FAKE_KEY[-4:] not in out
    assert FAKE_KEY[:8] not in out
