"""Packaging metadata and lint-config guards."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_has_authors_and_keywords() -> None:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'authors = [' in text
    assert 'name = "Daniel Agrici"' in text
    assert "email =" not in text
    for keyword in ("seo", "claude-code", "schema-markup", "e-e-a-t", "geo"):
        assert f'"{keyword}"' in text


def test_pyproject_has_minimal_ruff_config_only() -> None:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.ruff]" in text
    assert 'target-version = "py310"' in text
    assert "line-length = 100" in text
    assert "[tool.ruff.lint]" in text
    assert 'select = ["E", "F", "W", "I"]' in text
    assert 'ignore = ["E501"]' in text


def _floor(text: str, package: str) -> tuple[int, ...]:
    match = re.search(rf"^{re.escape(package)}>=([0-9.]+),<", text, re.MULTILINE)
    assert match, f"{package} needs a bounded '>=floor,<ceiling' requirement"
    return tuple(int(part) for part in match.group(1).split("."))


def test_requirements_keep_security_and_compatibility_floors() -> None:
    """Floors may rise (Dependabot bumps) but never fall below these minimums."""
    text = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    minimums = {
        "lxml": (6, 1, 1),
        "lxml_html_clean": (0, 4, 5),   # advisories fixed in 0.4.4 and 0.4.5
        "urllib3": (2, 7, 0),
        "numpy": (2, 2, 6),
        "google-auth-httplib2": (0, 4, 0),
        "google-ads": (25, 0, 0),
    }
    for package, minimum in minimums.items():
        assert _floor(text, package) >= minimum, f"{package} floor is below {minimum}"
