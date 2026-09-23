"""Audit subagent turn-budget and early-write regressions (issues #177, #272).

Reporters found that seo-audit subagents were hitting their `maxTurns` cap on
large sites before ever writing a findings file, so a turn-budget stop threw
away all completed work. The fix has two parts for every subagent
`skills/seo-audit/SKILL.md` can spawn:

1. `maxTurns` raised well above the old defaults (seo-technical was 20,
   seo-content was 15; both need real headroom for a 500-page crawl).
2. An explicit instruction to write a partial findings file after the first
   analysis pass and overwrite it with the complete findings at the end, so
   a maxTurns stop mid-audit still leaves usable output on disk.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_SKILL = ROOT / "skills" / "seo-audit" / "SKILL.md"
AGENTS_DIR = ROOT / "agents"
EXTENSION_AGENTS_GLOB = "extensions/*/agents"

EARLY_WRITE_SENTENCE = (
    "write a partial findings\nfile after the first analysis pass and overwrite it with the complete findings\nbefore finishing, so a turn-budget stop never loses completed work"
)

MIN_MAX_TURNS = 30
NAMED_HIGH_BUDGET_AGENTS = {"seo-technical": 40, "seo-content": 40}


def _discover_audit_agents() -> set[str]:
    text = AUDIT_SKILL.read_text(encoding="utf-8")
    return set(re.findall(r"`(seo-[a-z-]+)`", text))


def _agent_path(name: str) -> Path:
    """Resolve an audit subagent to its file, core tree first, then extensions.

    Extension-supplied agents (``seo-matomo``) ship under
    ``extensions/<name>/agents/`` and are installed into ``~/.claude/agents/``
    by the extension installer, so they carry the same turn-budget and
    early-write obligations as the core agents the orchestrator spawns.
    """
    core = AGENTS_DIR / f"{name}.md"
    if core.is_file():
        return core
    matches = sorted(ROOT.glob(f"{EXTENSION_AGENTS_GLOB}/{name}.md"))
    return matches[0] if matches else core


def test_audit_skill_still_names_the_known_subagent_set():
    # Locks the known set so a future addition/removal to seo-audit's
    # delegation list is a deliberate, reviewed change.
    assert _discover_audit_agents() == {
        "seo-technical", "seo-content", "seo-schema", "seo-sitemap",
        "seo-performance", "seo-visual", "seo-geo", "seo-local", "seo-maps",
        "seo-google", "seo-backlinks", "seo-cluster", "seo-sxo", "seo-drift",
        "seo-ecommerce", "seo-dataforseo", "seo-matomo", "seo-agentic",
    }


def _max_turns(text: str) -> int | None:
    match = re.search(r"^maxTurns:\s*(\d+)", text, re.MULTILINE)
    return int(match.group(1)) if match else None


def test_every_audit_agent_has_a_turn_budget_at_least_30():
    agents = _discover_audit_agents()
    assert agents, "expected at least one audit subagent"
    failures = []
    for name in sorted(agents):
        path = _agent_path(name)
        assert path.is_file(), f"missing agent file for {name}"
        turns = _max_turns(path.read_text(encoding="utf-8"))
        if turns is None or turns < MIN_MAX_TURNS:
            failures.append((name, turns))
    assert not failures, f"agents below maxTurns={MIN_MAX_TURNS}: {failures}"


def test_named_reporters_agents_have_at_least_40_turns():
    for name, minimum in NAMED_HIGH_BUDGET_AGENTS.items():
        path = AGENTS_DIR / f"{name}.md"
        turns = _max_turns(path.read_text(encoding="utf-8"))
        assert turns is not None and turns >= minimum, (
            f"{name} maxTurns={turns} is below the required {minimum}"
        )


def test_every_audit_agent_has_the_early_write_instruction():
    missing = []
    for name in sorted(_discover_audit_agents()):
        text = _agent_path(name).read_text(encoding="utf-8")
        if EARLY_WRITE_SENTENCE not in text:
            missing.append(name)
    assert not missing, f"agents missing the early-write instruction: {missing}"


def test_dataforseo_extension_mirror_also_has_the_early_write_instruction():
    mirror = ROOT / "extensions" / "dataforseo" / "agents" / "seo-dataforseo.md"
    text = mirror.read_text(encoding="utf-8")
    assert EARLY_WRITE_SENTENCE in text
