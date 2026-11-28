"""Windows PowerShell 5.1 reads a BOM-less script as ANSI, not UTF-8.

A multibyte symbol such as a check mark then decodes to bytes that include a
quote character, and the script fails to parse ("The string is missing the
terminator"). Keep every shipped .ps1 file pure ASCII so it parses on 5.1 and
on pwsh alike.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _ps1_files() -> list[str]:
    """Tracked .ps1 files, or every .ps1 on disk when there is no git checkout
    (a release zip or tarball), so the suite still collects outside git."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.ps1"], cwd=ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            str(p.relative_to(ROOT)) for p in ROOT.rglob("*.ps1") if ".git" not in p.parts
        )
    return result.stdout.split()


PS1_FILES = _ps1_files()


@pytest.mark.parametrize("rel", PS1_FILES)
def test_ps1_is_ascii(rel: str) -> None:
    data = (ROOT / rel).read_bytes()
    bad = [(i + 1, line) for i, line in enumerate(data.splitlines()) if any(b > 127 for b in line)]
    assert not bad, f"{rel}: non-ASCII bytes break Windows PowerShell 5.1 on lines {[n for n, _ in bad]}"
