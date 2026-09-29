"""Development rules from CLAUDE.md: SKILL.md files stay under 500 lines and
reference files stay under 200 lines, so on-demand loading stays cheap.

Six references had grown past 200 lines by v2.4.0; they were split in v2.4.1.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_LIMIT = 500
REFERENCE_LIMIT = 200


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_skill_files_under_limit() -> None:
    files = [*ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("extensions/*/skills/*/SKILL.md")]
    assert files
    over = {str(p.relative_to(ROOT)): n for p in files if (n := _line_count(p)) > SKILL_LIMIT}
    assert not over, f"SKILL.md over {SKILL_LIMIT} lines: {over}"


def test_reference_files_under_limit() -> None:
    files = [*ROOT.glob("skills/*/references/**/*.md"),
             *ROOT.glob("extensions/*/skills/*/references/**/*.md"),
             *ROOT.glob("extensions/*/references/**/*.md")]
    assert files
    over = {str(p.relative_to(ROOT)): n for p in files if (n := _line_count(p)) > REFERENCE_LIMIT}
    assert not over, f"reference files over {REFERENCE_LIMIT} lines: {over}"
