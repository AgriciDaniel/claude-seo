"""Stage 4 gap fixes: schema severity, link heuristics, merge gate, crawler claims."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / "skills"
AGENTS = REPO_ROOT / "agents"


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _norm(text: str) -> str:
    """Collapse all whitespace runs to a single space.

    Doc prose gets rewrapped and re-indented whenever a nearby line is
    edited; asserting against the literal wrapped string (with an exact
    ``\\n  `` in the middle) breaks on every unrelated reflow. Matching at
    sentence level, over normalised whitespace, survives that churn while
    still failing if the actual claim goes missing.
    """
    return re.sub(r"\s+", " ", text)


# ─── AI crawler claims are checked against the right bot ────────────────────


def test_gptbot_is_not_described_as_the_chatgpt_search_crawler() -> None:
    text = _read("skills/seo-geo/SKILL.md")
    assert "| GPTBot | OpenAI | ChatGPT web search | yes |" not in text
    assert "OAI-SearchBot" in text
    assert "ChatGPT Search citability" in text


def test_geo_skill_separates_training_crawlers_from_search_crawlers() -> None:
    text = _norm(_read("skills/seo-geo/SKILL.md"))
    assert "Check the right bot for the claim you are making" in text
    assert "does not affect inclusion in ordinary Google Search" in text
    assert "tells you nothing about whether ChatGPT Search can cite the page" in text


def test_google_extended_is_never_a_google_search_readiness_signal() -> None:
    """Named claim, checked in both the skill and the agent that runs it."""
    for rel in ("skills/seo-geo/SKILL.md", "agents/seo-geo.md"):
        text = _read(rel)
        assert "Google-Extended" in text, rel
        lowered = _norm(text).lower()
        assert "not google search" in lowered or "never google search" in lowered, rel

    skill = _norm(_read("skills/seo-geo/SKILL.md"))
    assert 'Never score `Google-Extended` as a "Google Search readiness" signal' in skill


def test_technical_skill_checks_oai_searchbot_separately_from_gptbot() -> None:
    text = _read("skills/seo-technical/SKILL.md")
    assert "| OAI-SearchBot | OpenAI | `OAI-SearchBot` | ChatGPT Search citability |" in text
    assert "governed by `OAI-SearchBot`" in text


def test_geo_output_reports_training_and_citability_separately() -> None:
    text = _read("skills/seo-geo/SKILL.md")
    assert "must never be merged into one line" in text


# ─── Claude: ClaudeBot (training) vs Claude-SearchBot (search citability) ───
# Source: https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
# ("ClaudeBot" collects training data; "Claude-SearchBot" is described as
# improving search-result quality; both respect robots.txt).


def test_claudebot_is_not_described_as_a_search_visibility_crawler() -> None:
    """ClaudeBot is Anthropic's training crawler; conflating it with Claude's
    own search crawler is exactly the GPTBot/OAI-SearchBot bug this file
    exists to catch, just for a different vendor."""
    for rel in ("skills/seo-geo/SKILL.md", "skills/seo-technical/SKILL.md"):
        text = _norm(_read(rel))
        assert "claudebot" in text.lower()
        assert "claude web features" not in text.lower(), rel


def test_geo_and_technical_skills_agree_on_what_claudebot_governs() -> None:
    """Both docs must describe ClaudeBot the same way: training, not search."""
    for rel in ("skills/seo-geo/SKILL.md", "skills/seo-technical/SKILL.md"):
        text = _norm(_read(rel)).lower()
        assert "model training" in text
        # A ClaudeBot row/sentence should carry a training claim near it.
        idx = text.find("claudebot")
        assert idx != -1, rel
        window = text[max(0, idx - 20):idx + 120]
        assert "training" in window, (rel, window)


def test_claude_searchbot_is_documented_as_the_citability_crawler() -> None:
    for rel in ("skills/seo-geo/SKILL.md", "skills/seo-technical/SKILL.md"):
        text = _read(rel)
        assert "Claude-SearchBot" in text, rel

    geo = _norm(_read("skills/seo-geo/SKILL.md"))
    assert "citable in Claude's search features" in geo or "Claude search-result citability" in geo


def test_geo_agent_recommends_claude_searchbot_not_claudebot_for_search_visibility() -> None:
    text = _read("agents/seo-geo.md")
    assert "Claude-SearchBot" in text
    # The old (wrong) recommendation line listed ClaudeBot alongside the two
    # actual search crawlers for "AI search visibility".
    assert "Allow for AI search visibility: OAI-SearchBot, ClaudeBot, PerplexityBot" not in text


# ─── Apple: Applebot-Extended (training opt-out) vs Applebot (search) ───────
# Source: https://support.apple.com/en-us/119829 (disallowing Applebot-Extended
# opts out of generative-model training use; pages remain discoverable via
# Siri/Spotlight/Safari as long as Applebot itself is allowed).


def test_applebot_extended_is_documented_as_training_only() -> None:
    text = _norm(_read("skills/seo-geo/SKILL.md"))
    assert "Applebot-Extended" in text
    lowered = text.lower()
    assert "training" in lowered
    idx = lowered.find("applebot-extended")
    window = lowered[idx:idx + 200]
    assert "siri" in window or "spotlight" in window or "safari" in window, window


def test_applebot_extended_never_cited_as_a_search_discoverability_signal() -> None:
    text = _norm(_read("skills/seo-geo/SKILL.md")).lower()
    assert "never cite a blocked `applebot-extended`".lower() in text or (
        "applebot-extended" in text and "discoverable" in text
    )


# ─── Sources: every vendor claim is cited to its own primary documentation ──


def test_geo_skill_cites_the_four_vendor_crawler_docs() -> None:
    text = _read("skills/seo-geo/SKILL.md")
    for url in (
        "https://platform.openai.com/docs/bots",
        "https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers",
        "https://support.anthropic.com/en/articles/8896518",
        "https://support.apple.com/en-us/119829",
    ):
        assert url in text, f"missing citation: {url}"


def test_claude_user_is_documented_as_honoring_robots_txt() -> None:
    """Anthropic: all three bots, including Claude-User, honor robots.txt."""
    geo = (REPO_ROOT / "skills/seo-geo/SKILL.md").read_text(encoding="utf-8")
    row = next(line for line in geo.splitlines() if line.startswith("| Claude-User |"))
    assert "yes" in row.lower() and "no (user-triggered)" not in row
    policy = (REPO_ROOT / "skills/seo-agentic/references/access-policy.md").read_text(encoding="utf-8")
    assert "| Claude-User | Anthropic | user-initiated fetches | honoured |" in policy


def test_perplexitybot_is_never_described_as_a_training_crawler() -> None:
    """Perplexity: PerplexityBot "is not used to crawl content for AI foundation models"."""
    for rel in ("skills/seo-geo/SKILL.md", "skills/seo-technical/SKILL.md"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if line.startswith("| PerplexityBot |"))
        assert "+ training" not in row, rel


def test_no_live_project_mariner_claims() -> None:
    """Mariner's status is secondary-only; describe Google-Agent by what it does."""
    for rel in ("skills/seo-geo/SKILL.md", "skills/seo-technical/SKILL.md"):
        assert "Mariner" not in (REPO_ROOT / rel).read_text(encoding="utf-8"), rel


def test_ttfb_guidance_matches_web_dev_threshold() -> None:
    """web.dev: good TTFB is 0.8s or less; no file may call >200ms a TTFB problem."""
    for rel in ("skills/seo/references/cwv-thresholds.md", "agents/seo-performance.md"):
        assert "TTFB >200ms" not in (REPO_ROOT / rel).read_text(encoding="utf-8"), rel
