"""The audit-agent persistence contract (issues #177, #272).

Both reports describe the same failure: subagents complete their research and are
terminated by the turn cap before reaching a write instruction placed at the end,
so the orchestrator sees no findings and the work is lost. #272 hit it on a
five-page site, so this is not a large-site edge case.

These tests pin the two properties that make the failure mode graceful:
every audit agent has a turn budget above the observed overrun, and its write
instruction comes before its analysis instructions rather than after them.
"""
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(REPO, "agents")
AUDIT_SKILL = os.path.join(REPO, "skills", "seo-audit", "SKILL.md")

# Highest turn count observed before a stop in issue #177 (seo-sxo, seo-performance
# on resume). A budget at or below this reproduces the bug.
OBSERVED_OVERRUN = 32


def _agent_files():
    return sorted(
        os.path.join(AGENTS_DIR, n)
        for n in os.listdir(AGENTS_DIR)
        if n.endswith(".md")
    )


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _frontmatter_and_body(text):
    parts = text.split("---", 2)
    return (parts[1], parts[2]) if len(parts) >= 3 else ("", text)


def _audit_agents():
    """Agents that own a findings/<category>.md deliverable in a full audit."""
    out = []
    for path in _agent_files():
        text = _read(path)
        if re.search(r"output_dir/findings/[\w-]+\.md", text):
            out.append((os.path.basename(path)[:-3], path, text))
    return out


AUDIT_AGENTS = _audit_agents()
AUDIT_BY_NAME = {name: (path, text) for name, path, text in AUDIT_AGENTS}
AUDIT_NAMES = sorted(AUDIT_BY_NAME)


def test_audit_agents_are_discovered():
    # Guard the guard: if this collapses to nothing the suite below passes vacuously.
    assert len(AUDIT_AGENTS) >= 15, f"only found {len(AUDIT_AGENTS)} audit agents"


@pytest.mark.parametrize("name", AUDIT_NAMES)
def test_turn_budget_clears_the_observed_overrun(name):
    _, text = AUDIT_BY_NAME[name]
    fm, _ = _frontmatter_and_body(text)
    match = re.search(r"^maxTurns:\s*(\d+)\s*$", fm, re.M)
    assert match, f"{name}: no maxTurns in frontmatter"
    turns = int(match.group(1))
    assert turns > OBSERVED_OVERRUN, (
        f"{name}: maxTurns={turns} is at or below the {OBSERVED_OVERRUN} turns "
        "observed before a stop in issue #177, so the agent can still be killed "
        "before it writes"
    )


@pytest.mark.parametrize("name", AUDIT_NAMES)
def test_write_instruction_precedes_the_analysis_instructions(name):
    _, text = AUDIT_BY_NAME[name]
    _, body = _frontmatter_and_body(text)
    write_at = body.find("## Findings file")
    assert write_at != -1, f"{name}: no write-first findings section"

    # The trailing conditional section is fine to keep, but something must tell the
    # agent to write before it starts spending turns.
    later_sections = [
        m.start()
        for m in re.finditer(r"^## (Output Format|Output Rules|Output|How to Report Findings)",
                             body, re.M)
    ]
    if later_sections:
        assert write_at < min(later_sections), (
            f"{name}: the findings write is described after the output section; a turn "
            "cap will end the agent before it gets there"
        )


@pytest.mark.parametrize("name", AUDIT_NAMES)
def test_audit_agents_can_actually_write(name):
    _, text = AUDIT_BY_NAME[name]
    fm, _ = _frontmatter_and_body(text)
    tools = re.search(r"^tools:\s*(.+)$", fm, re.M)
    assert tools, f"{name}: no tools line"
    assert "Write" in tools.group(1), (
        f"{name}: owns a findings file but has no Write tool"
    )


def test_every_agent_the_audit_skill_delegates_to_owns_a_findings_file():
    """Drift guard between skills/seo-audit/SKILL.md and agents/.

    The audit skill names the specialists it spawns. Any name there that has no
    findings contract is an agent whose work the orchestrator will silently lose.
    """
    skill = _read(AUDIT_SKILL)
    delegated = set(re.findall(r"^\s*-\s*`(seo-[\w-]+)`", skill, re.M))
    assert delegated, "could not parse the delegation list out of the audit skill"

    owners = {name for name, _, _ in AUDIT_AGENTS}
    orphans = sorted(delegated - owners)
    assert not orphans, (
        f"the audit skill delegates to {orphans} but they write no findings file"
    )
