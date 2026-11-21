"""Static instruction guards for full audit persistence and SPA wiring."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_seo_audit_starts_with_render_page_auto() -> None:
    text = (REPO_ROOT / "skills" / "seo-audit" / "SKILL.md").read_text(encoding="utf-8")
    process = text[text.index("## Process"):text.index("## Crawl Configuration")]
    assert '"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run render_page.py' in process
    assert "python3 scripts/render_page.py" not in process
    assert "--mode auto" in process
    assert "scripts/fetch_page.py` to retrieve HTML" not in process


def test_seo_audit_requires_persistent_artifacts() -> None:
    text = (REPO_ROOT / "skills" / "seo-audit" / "SKILL.md").read_text(encoding="utf-8")
    for artifact in (
        "FULL-AUDIT-REPORT.md",
        "ACTION-PLAN.md",
        "audit-data.json",
        "findings/",
        "screenshots/",
    ):
        assert artifact in text
    assert "{domain}-audit" in text


def test_audit_agents_use_renderer_or_capture_script() -> None:
    expectations = {
        "seo-performance.md": "render_page.py",
        "seo-visual.md": "capture_screenshot.py",
        "seo-technical.md": "render_page.py",
        "seo-content.md": "render_page.py",
        "seo-schema.md": "render_page.py",
    }
    for filename, marker in expectations.items():
        text = (REPO_ROOT / "agents" / filename).read_text(encoding="utf-8")
        assert marker in text, f"{filename} must mention {marker}"


def test_audit_agents_document_output_dir_findings_contract() -> None:
    for filename in (
        "seo-performance.md",
        "seo-visual.md",
        "seo-technical.md",
        "seo-content.md",
        "seo-schema.md",
        "seo-sitemap.md",
        "seo-geo.md",
        "seo-local.md",
        "seo-maps.md",
        "seo-google.md",
        "seo-backlinks.md",
        "seo-cluster.md",
        "seo-sxo.md",
        "seo-drift.md",
        "seo-ecommerce.md",
        "seo-agentic.md",
    ):
        text = (REPO_ROOT / "agents" / filename).read_text(encoding="utf-8")
        assert "output_dir" in text
        assert "findings/" in text


def test_seo_audit_report_command_keeps_outputs_in_audit_dir() -> None:
    text = (REPO_ROOT / "skills" / "seo-audit" / "SKILL.md").read_text(encoding="utf-8")
    assert "--output-dir {domain}-audit/" in text


def test_hub_invocation_keeps_the_command_word() -> None:
    """Claude Code indexes skill arguments from 0. $1 is the second word (#342).

    https://code.claude.com/docs/en/skills
    $ARGUMENTS is the full input. $0 is the first argument, $1 the second.
    An index with no argument stays literal, and ARGUMENTS is appended only
    when no placeholder received a value. `/seo $1 $2` therefore drops `audit`
    from `/seo audit https://example.com`.
    """
    text = (REPO_ROOT / "skills" / "seo" / "SKILL.md").read_text(encoding="utf-8")
    invocation = next(line for line in text.splitlines() if line.startswith("**Invocation:**"))
    assert "$1" not in invocation
    assert "$2" not in invocation
    assert invocation.startswith("**Invocation:** `/seo $ARGUMENTS`")


def _section(text: str, heading: str, next_heading: str | None = None) -> str:
    start = text.index(heading)
    if next_heading is None:
        return text[start:]
    return text[start:text.index(next_heading, start)]


def test_seo_audit_crawl_config_throttles_on_anti_bot_markers() -> None:
    text = (REPO_ROOT / "skills" / "seo-audit" / "SKILL.md").read_text(encoding="utf-8")
    crawl_cfg = _section(text, "## Crawl Configuration", "## Output Files").lower()
    assert "anti-bot" in crawl_cfg
    assert "1 concurrent request" in crawl_cfg
    assert "5+" in crawl_cfg
    assert "same ip" in crawl_cfg
    assert "parallel" in crawl_cfg


def test_seo_audit_error_handling_guards_against_self_triggered_403() -> None:
    text = (REPO_ROOT / "skills" / "seo-audit" / "SKILL.md").read_text(encoding="utf-8")
    errors = _section(text, "## Error Handling", "## Security").lower()
    assert "403/503" in errors
    assert "challenge" in errors
    assert "cool down" in errors
    assert "fresh session" in errors
    assert "site protection" in errors
    assert "non-200" in errors
    assert "discard" in errors


def test_seo_technical_guards_against_self_triggered_403() -> None:
    skill = (REPO_ROOT / "skills" / "seo-technical" / "SKILL.md").read_text(encoding="utf-8")
    crawlability = _section(skill, "### 1. Crawlability", "#### AI Crawler Management").lower()
    errors = _section(skill, "## Error Handling", "## Security").lower()
    agent = (REPO_ROOT / "agents" / "seo-technical.md").read_text(encoding="utf-8").lower()

    for block in (crawlability, errors, agent):
        assert "403/503" in block
        assert "challenge" in block
        assert "cool down" in block
        assert "fresh session" in block
        assert "site protection" in block
        assert "non-200" in block
        assert "discard" in block
