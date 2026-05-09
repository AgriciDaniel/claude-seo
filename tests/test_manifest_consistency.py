"""
Tests that ensure the plugin's manifest and user-visible docs claim
counts that match reality on disk.

Background: this guard exists because the v1.9.7 release process suffered
two distinct skill-count drift incidents in a single release window. The
first was caught by manual reconciliation (pre-Phase-A); the second slipped
through when PR #56 merged a 21st core skill but the canonical phrasing
locked in Phase A was not re-run. v1.9.8 closes the systemic gap.

Tests run via `pytest tests/` and are wired into `.github/workflows/ci.yml`.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CITATION_CFF = REPO_ROOT / "CITATION.cff"


def _count_skill_dirs() -> int:
    """Count subdirectories of skills/ that contain a SKILL.md."""
    skills_dir = REPO_ROOT / "skills"
    return sum(
        1 for d in skills_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    )


def _count_agent_files() -> int:
    """Count agents/seo-*.md files."""
    agents_dir = REPO_ROOT / "agents"
    return sum(
        1 for f in agents_dir.iterdir()
        if f.is_file() and f.suffix == ".md" and f.name.startswith("seo-")
    )


def _extract_count(text: str, unit: str) -> int:
    """Find the first occurrence of 'N <unit>' in text and return N."""
    match = re.search(rf"(\d+)\s+{re.escape(unit)}", text)
    if not match:
        raise AssertionError(f"No '{unit}' count claim found in text")
    return int(match.group(1))


def test_plugin_json_skill_count_matches_disk():
    """plugin.json description's 'N sub-skills' claim must equal skills/ dir count."""
    plugin = json.loads(PLUGIN_JSON.read_text())
    claimed = _extract_count(plugin["description"], "sub-skills")
    actual = _count_skill_dirs()
    assert claimed == actual, (
        f"plugin.json description claims {claimed} sub-skills "
        f"but disk has {actual}. "
        f"Update the description to match the new count."
    )


def test_plugin_json_subagent_count_matches_disk():
    """plugin.json description's 'N sub-agents' claim must equal agents/ count."""
    plugin = json.loads(PLUGIN_JSON.read_text())
    claimed = _extract_count(plugin["description"], "sub-agents")
    actual = _count_agent_files()
    assert claimed == actual, (
        f"plugin.json description claims {claimed} sub-agents "
        f"but disk has {actual}. "
        f"Update the description to match the new count."
    )


def test_marketplace_json_skill_count_matches_plugin_json():
    """marketplace.json plugin entry must claim the same skill count as plugin.json."""
    plugin = json.loads(PLUGIN_JSON.read_text())
    marketplace = json.loads(MARKETPLACE_JSON.read_text())
    plugin_count = _extract_count(plugin["description"], "sub-skills")
    market_count = _extract_count(
        marketplace["plugins"][0]["description"], "sub-skills"
    )
    assert plugin_count == market_count, (
        f"plugin.json claims {plugin_count} sub-skills, "
        f"marketplace.json plugin entry claims {market_count}. "
        f"They must agree."
    )


def test_marketplace_json_subagent_count_matches_plugin_json():
    """marketplace.json plugin entry must claim the same sub-agent count as plugin.json."""
    plugin = json.loads(PLUGIN_JSON.read_text())
    marketplace = json.loads(MARKETPLACE_JSON.read_text())
    plugin_count = _extract_count(plugin["description"], "sub-agents")
    market_count = _extract_count(
        marketplace["plugins"][0]["description"], "sub-agents"
    )
    assert plugin_count == market_count, (
        f"plugin.json claims {plugin_count} sub-agents, "
        f"marketplace.json plugin entry claims {market_count}. "
        f"They must agree."
    )


def test_canonical_phrasing_in_user_visible_docs():
    """README, CLAUDE.md, AGENTS.md must reference the canonical sub-skills count."""
    plugin = json.loads(PLUGIN_JSON.read_text())
    canonical_count = _extract_count(plugin["description"], "sub-skills")
    target_phrase = f"{canonical_count} sub-skills"
    for filename in ["README.md", "CLAUDE.md", "AGENTS.md"]:
        path = REPO_ROOT / filename
        head = "\n".join(path.read_text().splitlines()[:120])
        assert target_phrase in head, (
            f"{filename} does not reference '{target_phrase}' in its first "
            f"120 lines. Update it to match plugin.json's canonical phrasing."
        )


def test_version_triangulation():
    """plugin.json version must equal CITATION.cff version."""
    plugin = json.loads(PLUGIN_JSON.read_text())
    citation_text = CITATION_CFF.read_text()
    citation_match = re.search(r"^version:\s*(\S+)", citation_text, re.MULTILINE)
    assert citation_match, "CITATION.cff has no 'version:' line"
    plugin_version = plugin["version"]
    citation_version = citation_match.group(1)
    assert plugin_version == citation_version, (
        f"plugin.json version is {plugin_version} but CITATION.cff has "
        f"{citation_version}. They must match every release."
    )


def test_pyproject_version_matches_plugin_json():
    """pyproject.toml version must equal plugin.json version.

    Background: pyproject.toml drifted to 1.9.6 while plugin.json was at
    1.9.8. The original triangulation test only covered CITATION.cff,
    so pyproject.toml drift slipped past CI. This guard closes that gap.
    """
    plugin = json.loads(PLUGIN_JSON.read_text())
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text()
    pyproject_match = re.search(
        r'^version\s*=\s*"([^"]+)"', pyproject_text, re.MULTILINE
    )
    assert pyproject_match, "pyproject.toml has no 'version = \"...\"' line"
    plugin_version = plugin["version"]
    pyproject_version = pyproject_match.group(1)
    assert plugin_version == pyproject_version, (
        f"plugin.json version is {plugin_version} but pyproject.toml has "
        f"{pyproject_version}. Bump pyproject.toml on every release."
    )


def test_install_scripts_default_tag_matches_plugin_version():
    """install.sh and install.ps1 default REPO_TAG must equal v{plugin version}.

    Background: install.sh and install.ps1 default tag was v1.9.0 while
    plugin.json shipped at 1.9.8 (4 missed bumps across v1.9.5/.6/.7/.8).
    Manual-install users via curl | bash got 8 versions stale. This guard
    forces the default tag to track plugin.json on every release.
    """
    plugin = json.loads(PLUGIN_JSON.read_text())
    expected_tag = f"v{plugin['version']}"

    sh_text = (REPO_ROOT / "install.sh").read_text()
    sh_match = re.search(
        r'REPO_TAG="\$\{CLAUDE_SEO_TAG:-([^}]+)\}"', sh_text
    )
    assert sh_match, "install.sh has no recognizable REPO_TAG default"
    sh_tag = sh_match.group(1)
    assert sh_tag == expected_tag, (
        f"install.sh default tag is {sh_tag} but plugin.json is at "
        f"version {plugin['version']} (expected {expected_tag}). "
        f"Bump install.sh's CLAUDE_SEO_TAG default on every release."
    )

    ps_text = (REPO_ROOT / "install.ps1").read_text()
    ps_match = re.search(r"else\s*\{\s*'([^']+)'\s*\}", ps_text)
    assert ps_match, "install.ps1 has no recognizable RepoTag default"
    ps_tag = ps_match.group(1)
    assert ps_tag == expected_tag, (
        f"install.ps1 default tag is {ps_tag} but plugin.json is at "
        f"version {plugin['version']} (expected {expected_tag}). "
        f"Bump install.ps1's RepoTag default on every release."
    )


def test_canonical_math_adds_up():
    """The canonical phrasing's parenthetical breakdown must sum to the headline count."""
    plugin = json.loads(PLUGIN_JSON.read_text())
    desc = plugin["description"]
    headline_match = re.search(r"(\d+)\s+sub-skills\s+\(([^)]+)\)", desc)
    assert headline_match, (
        "plugin.json description must use the canonical 'N sub-skills (...)' "
        "phrasing with a parenthetical breakdown"
    )
    headline = int(headline_match.group(1))
    breakdown = headline_match.group(2)
    parts = [int(n) for n in re.findall(r"(\d+)\s+(?:core|orchestrator|framework|extension)", breakdown)]
    assert sum(parts) == headline, (
        f"plugin.json canonical phrasing breakdown {breakdown!r} sums to "
        f"{sum(parts)} but headline claims {headline}. Math must add up."
    )
