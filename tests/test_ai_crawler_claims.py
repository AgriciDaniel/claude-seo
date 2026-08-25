"""Stage 4 gap fixes: schema severity, link heuristics, merge gate, crawler claims."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / "skills"
AGENTS = REPO_ROOT / "agents"


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


# ─── AI crawler claims are checked against the right bot ────────────────────


def test_gptbot_is_not_described_as_the_chatgpt_search_crawler() -> None:
    text = _read("skills/seo-geo/SKILL.md")
    assert "| GPTBot | OpenAI | ChatGPT web search | yes |" not in text
    assert "OAI-SearchBot" in text
    assert "ChatGPT Search citability" in text


def test_geo_skill_separates_training_crawlers_from_search_crawlers() -> None:
    text = _read("skills/seo-geo/SKILL.md")
    assert "Check the right bot for the claim you are making" in text
    assert "does not affect inclusion in ordinary Google Search" in text
    assert "tells\n  you nothing about whether ChatGPT Search can cite the page" in text


def test_google_extended_is_never_a_google_search_readiness_signal() -> None:
    """Named claim, checked in both the skill and the agent that runs it."""
    for rel in ("skills/seo-geo/SKILL.md", "agents/seo-geo.md"):
        text = _read(rel)
        assert "Google-Extended" in text, rel
        lowered = text.lower()
        assert "not google search" in lowered or "never google search" in lowered, rel

    skill = _read("skills/seo-geo/SKILL.md")
    assert 'Never score\n  `Google-Extended` as a "Google Search readiness" signal' in skill


def test_technical_skill_checks_oai_searchbot_separately_from_gptbot() -> None:
    text = _read("skills/seo-technical/SKILL.md")
    assert "| OAI-SearchBot | OpenAI | `OAI-SearchBot` | ChatGPT Search citability |" in text
    assert "governed by `OAI-SearchBot`" in text


def test_geo_output_reports_training_and_citability_separately() -> None:
    text = _read("skills/seo-geo/SKILL.md")
    assert "must never be merged into one line" in text
