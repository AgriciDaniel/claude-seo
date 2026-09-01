"""Static contracts for the Windows manual uninstaller."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_uninstaller_counts_removed_items_in_main_scope() -> None:
    """Pipeline child scopes must not lose counts before the summary is printed."""
    text = (ROOT / "uninstall.ps1").read_text(encoding="utf-8")

    assert "foreach ($subSkill in @(Get-ChildItem" in text
    assert "foreach ($agentFile in @(Get-ChildItem" in text
    assert "$removedSkills++" in text
    assert "$removedAgents++" in text
    assert "$script:removedSkills++" not in text
    assert "$script:removedAgents++" not in text


def test_windows_smoke_checks_full_partial_and_empty_uninstalls() -> None:
    text = (ROOT / ".github/workflows/windows-smoke.yml").read_text(encoding="utf-8")

    assert "$expectedSummary" in text
    assert "-Filter \"seo\" -ErrorAction SilentlyContinue) +" not in text
    assert "Partial-install summary was incorrect" in text
    assert "Nothing to remove" in text
