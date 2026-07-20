"""
Tests for the v2 Checkpoint 2 content-quality scripts:
    scripts/content_quality.py
    scripts/content_humanize.py
    scripts/content_verify.py
    scripts/seo_updates.py
    data/google-updates.json

domain_history.py is covered by integration smoke (it hits the system
``whois`` binary) and is not unit-tested here to avoid flaking when
network or whois egress is unavailable.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import content_quality  # noqa: E402
import content_humanize  # noqa: E402
import content_verify  # noqa: E402
import seo_updates  # noqa: E402


# ---------------------------------------------------------------------------
# content_quality
# ---------------------------------------------------------------------------


def test_content_quality_empty_input() -> None:
    result = content_quality.analyse("")
    assert result["flags"] == ["empty-input"]
    assert result["overall_quality"] == 0


def test_content_quality_filler_heavy_text_scores_low() -> None:
    text = (
        "In today's fast-paced world, when it comes to SEO, "
        "it's important to note that delving into the ever-evolving "
        "landscape requires us to leverage the power of cutting-edge "
        "tools. In essence, this guide will dive into the rich tapestry "
        "of optimization strategies. Needless to say, at the end of the "
        "day, the bottom line is that we need to revolutionize the way "
        "we approach search."
    )
    result = content_quality.analyse(text)
    assert result["overall_quality"] < 40, result
    assert "filler" in result["flags"]
    assert "ai-patterns" in result["flags"]
    assert result["filler_score"] >= 50
    assert result["ai_pattern_score"] >= 40


def test_content_quality_rich_content_scores_high() -> None:
    # 300+ tokens with specific numbers, named entities, no filler.
    text = (
        "On 2025-08-21 Google extended AI Mode to 180 countries. "
        "The Hreflang spec has not changed since RFC 1034 was clarified "
        "in 1987 by Paul Mockapetris. Stanford's CRFM published a 312 "
        "page report measuring 47 vendor models on 18 evaluation tasks. "
        "John Mueller confirmed via Bluesky on 2025-04-12 that llms.txt "
        "is not consumed by any Google system. SE Ranking analysed "
        "300000 domains and found one llms.txt among the top 50 "
        "most-cited domains, putting the adoption rate at 0.1 percent. "
        "Robby Stein, Google VP of Search, demonstrated AI Mode "
        "executing 4 restaurant reservations across Resy and OpenTable "
        "in a single session. Forrester analysts updated their B2B "
        "Marketing Wave on 2026-02-04, downgrading 3 vendors that "
        "previously held Leader positions in the 2024 edition." * 2
    )
    result = content_quality.analyse(text)
    assert result["overall_quality"] >= 50, result
    assert "filler" not in result["flags"]
    assert result["information_density"] > 0.2


def test_content_quality_thin_content_flag() -> None:
    text = "Hello world. This is a short page."
    result = content_quality.analyse(text)
    assert "thin-content" in result["flags"]


@pytest.mark.parametrize(
    "phrase",
    [
        "delve into",
        "ever-evolving landscape",
        "tapestry of",
        "leverage the power of",
        "leveraging the power of",
        "unlock the potential",
        "in essence,",
    ],
)
def test_content_quality_detects_known_ai_patterns(phrase: str) -> None:
    # Wrap in enough other text that the score doesn't reject as thin.
    text = (phrase + " example sentence. ") * 30
    result = content_quality.analyse(text)
    assert result["ai_pattern_score"] > 0
    assert phrase.lower() in [m.lower() for m in result["matches"]["ai_patterns"]]


# ---------------------------------------------------------------------------
# content_humanize
# ---------------------------------------------------------------------------


def test_humanize_removes_canonical_ai_patterns() -> None:
    text = (
        "Let's dive into the ever-evolving landscape of SEO. "
        "When it comes to ranking, it's important to note that we should "
        "leverage the power of cutting-edge tools to unlock the potential "
        "of our content. In essence, this is a game-changer."
    )
    result = content_humanize.humanize(text)
    assert result["change_count"] >= 5
    cleaned_lower = result["cleaned"].lower()
    for forbidden in (
        "delve into",
        "ever-evolving",
        "leverage the power of",
        "cutting-edge",
        "unlock the potential",
        "in essence,",
        "game-changer",
    ):
        assert forbidden not in cleaned_lower, (
            f"{forbidden!r} should have been replaced; cleaned text: "
            f"{result['cleaned']!r}"
        )


def test_humanize_preserves_capitalization_at_sentence_start() -> None:
    text = "Delve into our guide."
    result = content_humanize.humanize(text)
    assert result["cleaned"].startswith("Explore"), result["cleaned"]


def test_humanize_idempotent_on_clean_text() -> None:
    text = (
        "Google released the December 2025 Core Update on 2025-12-11. "
        "The rollout took 18 days and showed a measurable eCommerce skew "
        "according to Amsive's analysis."
    )
    result = content_humanize.humanize(text)
    assert result["change_count"] == 0
    assert result["cleaned"] == text


def test_humanize_collapses_extra_spaces_from_deleted_phrases() -> None:
    text = "In essence, we ship features."
    result = content_humanize.humanize(text)
    # "In essence, " gets removed; result must not start with a space.
    assert not result["cleaned"].startswith(" ")
    assert "  " not in result["cleaned"]


# ---------------------------------------------------------------------------
# content_verify
# ---------------------------------------------------------------------------


def test_verify_extracts_basic_claim_kinds() -> None:
    text = (
        "47% of marketers report better results. "
        "The market reached $3.2 billion by 2025. "
        "Forrester said the trend will continue. "
        "The product is 3x faster than alternatives. "
        "In 2024, adoption doubled."
    )
    result = content_verify.verify(text)
    kinds = {c["kind"] for c in result["claims"]}
    assert {"statistic", "quantity", "authority", "temporal", "comparative"} <= kinds


def test_verify_flags_uncited_claims() -> None:
    text = "47% of marketers do X. 60% report success. 80% see growth."
    result = content_verify.verify(text)
    assert result["uncited_count"] == result["claim_count"]
    assert result["uncited_ratio"] == 1.0


def test_verify_accepts_markdown_link_as_citation() -> None:
    text = (
        "According to a recent study, 47% of marketers do X "
        "[Source](https://example.com/study)."
    )
    result = content_verify.verify(text)
    assert all(c["has_citation"] for c in result["claims"])


def test_verify_accepts_footnote_marker() -> None:
    text = "Adoption hit 60% in 2025 [^1]."
    result = content_verify.verify(text)
    assert all(c["has_citation"] for c in result["claims"])


def test_verify_empty_text_returns_zero_claims() -> None:
    result = content_verify.verify("")
    assert result["claim_count"] == 0
    assert result["uncited_ratio"] == 0.0


# ---------------------------------------------------------------------------
# seo_updates
# ---------------------------------------------------------------------------


def test_seo_updates_data_file_is_valid_json() -> None:
    data_path = Path(__file__).resolve().parents[1] / "data" / "google-updates.json"
    assert data_path.is_file()
    with data_path.open() as fh:
        data = json.load(fh)
    assert "updates" in data
    assert "source_of_truth" in data
    assert data["source_of_truth"].startswith("https://status.search.google.com/")


def test_seo_updates_every_entry_has_google_owned_source() -> None:
    """Policy: every entry must cite a Google-owned URL. Third-party-only
    claims belong in unverified[]."""
    data_path = Path(__file__).resolve().parents[1] / "data" / "google-updates.json"
    with data_path.open() as fh:
        data = json.load(fh)
    google_hosts = (
        "developers.google.com",
        "blog.google",
        "status.search.google.com",
        "web.dev",
        "services.google.com",
        "support.google.com",
    )
    for entry in data["updates"]:
        url = entry.get("source", "")
        assert any(host in url for host in google_hosts), (
            f"{entry['name']!r} cites non-Google URL: {url}. "
            "Move third-party-only entries to unverified[]."
        )


def test_seo_updates_unverified_entries_call_out_status() -> None:
    """Unverified entries must include a primary_source_check pointer."""
    data_path = Path(__file__).resolve().parents[1] / "data" / "google-updates.json"
    with data_path.open() as fh:
        data = json.load(fh)
    for entry in data.get("unverified", []):
        assert "primary_source_check" in entry
        assert "status" in entry
        assert entry["primary_source_check"].startswith(
            "https://status.search.google.com/"
        )


def test_seo_updates_filter_by_kind() -> None:
    data = seo_updates._load()
    cores = seo_updates._filter(data["updates"], kinds={"core"})
    assert all(u["kind"] == "core" for u in cores)
    assert any("December 2025 Core Update" in u["name"] for u in cores)


def test_seo_updates_filter_by_year() -> None:
    data = seo_updates._load()
    since_2025 = seo_updates._filter(data["updates"], since="2025")
    assert all(u["date"] >= "2025-01-01" for u in since_2025)
