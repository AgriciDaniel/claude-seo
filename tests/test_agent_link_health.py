from __future__ import annotations

import os
from pathlib import Path

from scripts.doctor_agents import REQUIRED_AUDIT_AGENTS, check_agent_tree


def test_required_audit_agent_list_matches_skill_contract() -> None:
    assert REQUIRED_AUDIT_AGENTS == (
        "seo-technical",
        "seo-content",
        "seo-schema",
        "seo-sitemap",
        "seo-performance",
        "seo-visual",
        "seo-geo",
        "seo-sxo",
    )


def test_check_agent_tree_passes_with_real_files(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agents"
    agent_dir.mkdir()
    for name in REQUIRED_AUDIT_AGENTS:
        (agent_dir / f"{name}.md").write_text("# agent\n", encoding="utf-8")

    result = check_agent_tree(agent_dir)

    assert result.ok is True
    assert result.missing == []
    assert result.broken_symlinks == []


def test_check_agent_tree_reports_missing_files(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agents"
    agent_dir.mkdir()
    (agent_dir / "seo-technical.md").write_text("# agent\n", encoding="utf-8")

    result = check_agent_tree(agent_dir)

    assert result.ok is False
    assert "seo-content.md" in result.missing
    assert "seo-schema.md" in result.missing


def test_check_agent_tree_reports_broken_symlinks(tmp_path: Path) -> None:
    if os.name != "posix":
        return

    agent_dir = tmp_path / "agents"
    agent_dir.mkdir()
    (agent_dir / "seo-technical.md").symlink_to(
        tmp_path / "missing" / "seo-technical.md"
    )

    result = check_agent_tree(agent_dir)

    assert result.ok is False
    assert "seo-technical.md" in result.broken_symlinks
