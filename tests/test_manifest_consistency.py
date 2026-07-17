"""
Tests that ensure OpenCode manifest claims match reality on disk.

Updated for OpenCode-native rewrite. plugin.json/marketplace.json/CLAUDE.md
are removed; consistency now checks commands/, agents/, and opencode.jsonc.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _count_skill_dirs() -> int:
    skills_dir = REPO_ROOT / "skills"
    return sum(
        1 for d in skills_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    )


def _count_agent_files() -> int:
    agents_dir = REPO_ROOT / "agents"
    return sum(
        1 for f in agents_dir.iterdir()
        if f.is_file() and f.suffix == ".md" and f.name.startswith("seo-")
    )


def _count_command_files() -> int:
    commands_dir = REPO_ROOT / "commands"
    if not commands_dir.exists():
        return 0
    return sum(
        1 for f in commands_dir.iterdir()
        if f.is_file() and f.suffix == ".md" and f.name.startswith("seo")
    )


def test_canonical_phrasing_in_user_visible_docs():
    """README and AGENTS.md must reference the canonical sub-skills count."""
    skill_count = _count_skill_dirs()
    target_phrase = f"{skill_count} sub-skills"
    for filename in ["README.md", "AGENTS.md"]:
        path = REPO_ROOT / filename
        head = "\n".join(path.read_text().splitlines()[:120])
        assert target_phrase in head, (
            f"{filename} does not reference '{target_phrase}' in its first "
            f"120 lines."
        )


def test_command_count_matches_skill_count():
    """commands/ count must equal skills/ count (minus orchestrator)."""
    skill_count = _count_skill_dirs()
    command_count = _count_command_files()
    assert command_count == skill_count, (
        f"commands/ has {command_count} files but skills/ has "
        f"{skill_count} SKILL.md dirs. Counts must match."
    )


def test_agent_frontmatter_has_no_claude_fields():
    """No agent file should contain model:, maxTurns:, tools:, or name: in frontmatter."""
    agents_dir = REPO_ROOT / "agents"
    errors = []
    for agent_file in agents_dir.glob("seo-*.md"):
        text = agent_file.read_text()
        m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not m:
            errors.append(f"{agent_file.name}: no frontmatter")
            continue
        fm = m.group(1)
        for banned in ["model:", "maxTurns:", "tools:", "name:"]:
            if banned in fm:
                errors.append(f"{agent_file.name}: contains '{banned}' in frontmatter")
    assert not errors, "Agent frontmatter contains Claude-specific fields:\n  " + "\n  ".join(errors)


def test_agent_frontmatter_has_mode_subagent():
    """Every agent file must have mode: subagent in frontmatter."""
    agents_dir = REPO_ROOT / "agents"
    errors = []
    for agent_file in agents_dir.glob("seo-*.md"):
        text = agent_file.read_text()
        m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not m:
            errors.append(f"{agent_file.name}: no frontmatter")
            continue
        fm = m.group(1)
        if "mode: subagent" not in fm:
            errors.append(f"{agent_file.name}: missing 'mode: subagent'")
    assert not errors, "Agent files missing mode: subagent:\n  " + "\n  ".join(errors)


def _strip_jsonc_comments(text: str) -> str:
    """Strip // and /* */ comments from JSONC, respecting quoted strings."""
    result = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '"':
            result.append('"')
            i += 1
            while i < n:
                ch = text[i]
                result.append(ch)
                if ch == '\\' and i + 1 < n:
                    i += 1
                    result.append(text[i])
                elif ch == '"':
                    i += 1
                    break
                i += 1
        elif text[i] == '/' and i + 1 < n and text[i+1] == '/':
            while i < n and text[i] != '\n' and text[i] != '\r':
                i += 1
        elif text[i] == '/' and i + 1 < n and text[i+1] == '*':
            i += 2
            while i < n:
                if text[i] == '*' and i + 1 < n and text[i+1] == '/':
                    i += 2
                    break
                i += 1
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def test_agent_count_matches_opencode_config():
    """opencode.jsonc agent entries must match agents/ directory count."""
    agents_dir = REPO_ROOT / "agents"
    agent_files = list(agents_dir.glob("seo-*.md"))

    opencode_jsonc = REPO_ROOT / "opencode.jsonc"
    text = opencode_jsonc.read_text()
    text = _strip_jsonc_comments(text)
    text = re.sub(r',\s*[\n\r]+\s*(\}|\])', r'\n\1', text)
    config = json.loads(text)

    config_agents = config.get("agent", {})
    errors = []
    for af in agent_files:
        name = af.stem
        if name not in config_agents:
            errors.append(f"{name} is on disk but not in opencode.jsonc agent config")
    for name in config_agents:
        if not (agents_dir / f"{name}.md").exists():
            errors.append(f"{name} is in opencode.jsonc but no agent file on disk")
    assert not errors, "Agent config/drift:\n  " + "\n  ".join(errors)


def _extract_section(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\b.*?(?=^## |\Z)"
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return m.group(0) if m else ""


def test_orchestrator_sub_skills_list_matches_disk():
    """skills/seo/SKILL.md Sub-Skills numbered list must equal set(skills/*) minus orchestrator itself."""
    text = (REPO_ROOT / "skills" / "seo" / "SKILL.md").read_text()
    section = _extract_section(text, "Sub-Skills")
    listed_list = re.findall(r"^\d+\.\s+\*\*(seo-[a-z-]+)\*\*", section, re.MULTILINE)
    assert len(listed_list) == len(set(listed_list)), (
        f"Duplicate entries in Sub-Skills list"
    )
    listed = set(listed_list)
    on_disk = {
        d.name for d in (REPO_ROOT / "skills").iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    }
    expected = on_disk - {"seo"}
    assert listed == expected, (
        f"Sub-Skills list != skills/ dir. "
        f"Missing from list: {sorted(expected - listed)}. "
        f"Extra in list: {sorted(listed - expected)}."
    )


def test_orchestrator_subagents_list_matches_disk():
    """skills/seo/SKILL.md Subagents bullet list must equal set(agents/seo-*.md)."""
    text = (REPO_ROOT / "skills" / "seo" / "SKILL.md").read_text()
    section = _extract_section(text, "Subagents")
    listed_list = re.findall(r"^- `(seo-[a-z-]+)`", section, re.MULTILINE)
    assert len(listed_list) == len(set(listed_list)), (
        f"Duplicate entries in Subagents list"
    )
    listed = set(listed_list)
    on_disk = {
        p.stem for p in (REPO_ROOT / "agents").iterdir()
        if p.is_file() and p.suffix == ".md" and p.name.startswith("seo-")
    }
    assert listed == on_disk, (
        f"Subagents list != agents/ dir. "
        f"Missing from list: {sorted(on_disk - listed)}. "
        f"Extra in list: {sorted(listed - on_disk)}."
    )


def test_reference_files_have_at_least_one_link():
    """Every skills/*/references/*.md file must be cited somewhere in the repo."""
    ref_files = list((REPO_ROOT / "skills").glob("*/references/*.md"))
    if not ref_files:
        return

    search_paths = []
    search_paths += list((REPO_ROOT / "skills").glob("*/SKILL.md"))
    search_paths += list((REPO_ROOT / "agents").glob("*.md"))
    search_paths += list((REPO_ROOT / "commands").glob("*.md"))
    search_paths += list((REPO_ROOT / "docs").glob("*.md"))
    for doc in ("README.md", "CHANGELOG.md", "AGENTS.md", "CONTRIBUTING.md"):
        candidate = REPO_ROOT / doc
        if candidate.exists():
            search_paths.append(candidate)
    search_paths += ref_files

    text_by_path = {p: p.read_text() for p in search_paths}

    orphans = []
    for ref in ref_files:
        slug = ref.stem
        filename = ref.name
        wikilink = f"[[{slug}]]"
        found = False
        for other_path, text in text_by_path.items():
            if other_path == ref:
                continue
            if filename in text or wikilink in text:
                found = True
                break
        if not found:
            orphans.append(str(ref.relative_to(REPO_ROOT)))

    assert not orphans, (
        "Orphan reference files:\n  " + "\n  ".join(orphans)
    )


def test_version_triangulation():
    """pyproject.toml version must equal CITATION.cff version."""
    citation_text = (REPO_ROOT / "CITATION.cff").read_text()
    citation_match = re.search(r"^version:\s*(\S+)", citation_text, re.MULTILINE)
    assert citation_match, "CITATION.cff has no 'version:' line"
    citation_version = citation_match.group(1)

    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text()
    pyproject_match = re.search(
        r'^version\s*=\s*"([^"]+)"', pyproject_text, re.MULTILINE
    )
    assert pyproject_match, "pyproject.toml has no 'version = \"...\"' line"
    pyproject_version = pyproject_match.group(1)
    assert citation_version == pyproject_version, (
        f"CITATION.cff version is {citation_version} but pyproject.toml has "
        f"{pyproject_version}. They must match every release."
    )
