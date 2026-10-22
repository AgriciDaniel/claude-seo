"""Supported Python range: one policy, enforced by every launcher (CI 2026-10-22).

The Windows runner image gained Python 3.15, and ``py -3`` picked it even
though google-ads does not support it yet. Every copy of the range must agree
with ``runtime.py``, and the launcher must skip an unsupported default.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import runtime  # noqa: E402

LAUNCHER = ROOT / "scripts" / "claude-seo"
MIN_MINOR = runtime.MIN_PYTHON[1]
MAX_MINOR = runtime.MAX_PYTHON[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_runtime_range_is_three_eleven_to_three_fourteen() -> None:
    assert runtime.MIN_PYTHON == (3, 11)
    assert runtime.MAX_PYTHON == (3, 14)


def test_every_copy_of_the_range_matches_runtime() -> None:
    launcher = _read("scripts/claude-seo")
    assert f"min_minor={MIN_MINOR}" in launcher
    assert f"max_minor={MAX_MINOR}" in launcher
    ps1 = _read("install.ps1")
    assert f"$MinMinor = {MIN_MINOR}" in ps1
    assert f"$MaxMinor = {MAX_MINOR}" in ps1
    assert f'requires-python = ">=3.{MIN_MINOR}"' in _read("pyproject.toml")
    assert f'target-version = "py3{MIN_MINOR}"' in _read("pyproject.toml")
    assert f'requires-python = ">=3.{MIN_MINOR}"' in _read("uv.lock")
    ci = _read(".github/workflows/ci.yml")
    matrix = re.search(r'python-version: \[([^\]]+)\]', ci)
    assert matrix, "ci.yml needs a python-version matrix"
    versions = [v.strip().strip('"') for v in matrix.group(1).split(",")]
    assert versions[0] == f"3.{MIN_MINOR}" and versions[-1] == f"3.{MAX_MINOR}"
    range_text = f"3.{MIN_MINOR} to 3.{MAX_MINOR}"
    for doc in ("README.md", "docs/INSTALLATION.md"):
        assert range_text in _read(doc), f"{doc} must state Python {range_text}"


def test_no_launcher_or_workflow_still_accepts_three_ten() -> None:
    for relative in ("scripts/claude-seo", "install.ps1", ".github/workflows/ci.yml",
                     ".github/workflows/v2.yml", ".github/workflows/windows-smoke.yml"):
        text = _read(relative)
        assert "(3, 10)" not in text, relative
        assert "'3.10'" not in text and '"3.10"' not in text, relative


def test_powershell_installer_honors_override_and_versioned_fallbacks() -> None:
    ps1 = _read("install.ps1")
    assert "$env:CLAUDE_SEO_PYTHON" in ps1
    assert "\"-3.$minor\"" in ps1
    assert "\"python3.$minor\"" in ps1


def test_setup_refuses_an_unsupported_interpreter(monkeypatch, capsys) -> None:
    monkeypatch.setattr(runtime, "_python_supported", lambda: False)
    monkeypatch.setattr(runtime, "_root", lambda: pytest.fail("setup must stop first"))
    assert runtime.command_setup(None) == 2
    assert "needs Python 3.11 to 3.14" in capsys.readouterr().err


posix_only = pytest.mark.skipif(os.name != "posix", reason="stub interpreters are shell scripts")


def _stub_dir(tmp_path: Path, versions: dict[str, str]) -> Path:
    """Make a PATH holding only fake interpreters plus the tools the launcher needs."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("dirname", "basename"):
        real = shutil.which(tool)
        assert real, tool
        (bin_dir / tool).symlink_to(real)
    for name, version in versions.items():
        stub = bin_dir / name
        stub.write_text(
            "#!/bin/sh\n"
            f'if [ "$1" = "-c" ]; then echo {version}; exit 0; fi\n'
            f'echo "picked {name} $(basename "$1")"\n',
            encoding="utf-8",
        )
        stub.chmod(0o755)
    return bin_dir


def _launch(bin_dir: Path, **env: str) -> subprocess.CompletedProcess:
    bash = shutil.which("bash")
    assert bash
    return subprocess.run(
        [bash, str(LAUNCHER), "doctor"],
        env={"PATH": str(bin_dir), **env},
        capture_output=True,
        text=True,
        timeout=30,
    )


@posix_only
def test_launcher_skips_unsupported_default_for_newest_supported(tmp_path) -> None:
    bin_dir = _stub_dir(tmp_path, {"python3": "3.15", "python3.14": "3.14", "python3.12": "3.12"})
    result = _launch(bin_dir)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "picked python3.14 runtime.py"


@posix_only
def test_launcher_keeps_a_supported_default(tmp_path) -> None:
    bin_dir = _stub_dir(tmp_path, {"python3": "3.12", "python3.14": "3.14"})
    assert _launch(bin_dir).stdout.strip() == "picked python3 runtime.py"


@posix_only
def test_launcher_names_the_range_when_nothing_fits(tmp_path) -> None:
    bin_dir = _stub_dir(tmp_path, {"python3": "3.15", "python3.10": "3.10"})
    result = _launch(bin_dir)
    assert result.returncode == 2
    assert "needs Python 3.11 to 3.14" in result.stderr
    assert "3.15 (python3)" in result.stderr


@posix_only
def test_launcher_rejects_an_unsupported_override(tmp_path) -> None:
    bin_dir = _stub_dir(tmp_path, {"python3": "3.12", "py315": "3.15"})
    result = _launch(bin_dir, CLAUDE_SEO_PYTHON=str(bin_dir / "py315"))
    assert result.returncode == 2
    assert "CLAUDE_SEO_PYTHON must be Python 3.11 to 3.14. Found 3.15" in result.stderr
