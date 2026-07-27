"""
Tests for scripts/metadata_template.py — the templated-metadata detector.

The true-positive corpus is the real metadata that got a live site demoted
by the June 2026 spam update for scaled content abuse: a bulk CSV metadata
job wrote a description for every page that restates the page title and
then appends a stock CTA.

The false-positive corpus is the harder half. Every entry is legitimate
metadata that a naive "description contains the title" rule would flag —
pages that open with their own topic phrase because that is how a sentence
about that topic starts, plus one page that ends on a genuine call to
action without echoing its title.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import metadata_template  # noqa: E402


# ---------------------------------------------------------------------------
# True positives: templated title + description pairs
# ---------------------------------------------------------------------------

_TEMPLATED_PAIRS = [
    (
        "Readability Checker Tool: Improve Writing Score Fast",
        "Readability Checker Tool: Improve Writing Score Fast analyzes readability, "
        "boosts writing clarity & improves content score. Try it free now.",
    ),
    (
        "Text Summarizer Tool: Complete AI Summary Generator",
        "Text Summarizer Tool: Complete AI Summary Generator creates instant, accurate "
        "summaries and saves reading time. Try it free now.",
    ),
    (
        "Google Penalty Risk Scanner: Best SEO Audit Tool",
        "Google Penalty Risk Scanner: Best SEO Audit Tool detects SEO risks, penalties "
        "& ranking issues. Start your free scan now.",
    ),
    (
        "Keyword Density Checker: Free SEO Optimization Tool",
        "Keyword Density Checker: Free SEO Optimization Tool analyzes keyword usage, "
        "improves SEO balance & boosts rankings. Try it free now.",
    ),
    (
        "Online Notepad: Free Auto-Save Writing Editor Tool",
        "Online Notepad: Free Auto-Save Writing Editor Tool lets you write, edit & save "
        "notes instantly with auto-save. Try it free now.",
    ),
    (
        "E-E-A-T Audit Guide: Complete Website Quality Review System",
        "E-E-A-T Audit Guide: Complete Website Quality Review System | Acme Improve SEO "
        "quality, trust & rankings fast. Start your audit now!",
    ),
]


@pytest.mark.parametrize("title,description", _TEMPLATED_PAIRS)
def test_templated_pairs_are_flagged_high(title: str, description: str) -> None:
    result = metadata_template.analyse(title, description)
    assert result["templated"] is True, result
    assert result["severity"] == "high"
    assert "templated-metadata" in result["flags"]
    assert [s["id"] for s in result["signals"]][0] == "templated_metadata"


@pytest.mark.parametrize("title,description", _TEMPLATED_PAIRS)
def test_templated_pairs_report_the_matched_cta(title: str, description: str) -> None:
    result = metadata_template.analyse(title, description)
    assert result["cta_phrase"], result
    assert result["cta_phrase"] == result["cta_phrase"].lower()


# ---------------------------------------------------------------------------
# False positives: legitimate metadata that must stay clean
# ---------------------------------------------------------------------------

_LEGITIMATE_PAIRS = [
    # Description covers the same topic but opens with new information.
    (
        "Readability Checker: Flesch Reading Ease & Grade Level Score",
        "Free readability checker: get a Flesch Reading Ease score, Flesch-Kincaid grade "
        "level, Gunning Fog index, passive voice share, and sentence-length distribution.",
    ),
    (
        "Citation Generator: Free APA, MLA & Chicago Citations",
        "Free citation generator for APA 7th, MLA 9th, and Chicago 17th edition. Cite "
        "websites by URL or enter books and journals manually. No signup required.",
    ),
    # Opens with its own topic phrase, but adds substance and no stock CTA.
    (
        "Helpful Content Update Survival Guide: How to Recover & Stay Safe",
        "Helpful content update survival guide: how to tell if you were hit, the "
        "people-first content checklist, and how to recover from the update in 2026.",
    ),
    # Short title a sentence can legitimately open with.
    (
        "Word Counter",
        "Word counter that gives instant word, character, sentence and paragraph counts, "
        "with Common App and IELTS presets built in.",
    ),
    # The brand name is genuinely the subject of the page.
    (
        "About Acme | Our Story",
        "Acme was built by two brothers after a client site lost its rankings overnight. "
        "Here is what we learned and why we made the tools free.",
    ),
    # Genuine call to action, but the description never echoes the title.
    (
        "Free Grammar Checker Online: Fix Errors in Any Language",
        "Catch grammar, spelling, punctuation and style mistakes across 20+ languages "
        "with no word limit and no account. Try it free now.",
    ),
    # Echoes the title (editorially fine) and happens to end on the word
    # "now" in its ordinary sense, not as a CTA.
    (
        "Core Web Vitals Thresholds: The Numbers Google Uses Today",
        "Core Web Vitals thresholds: the numbers Google uses today, including the INP "
        "cutoff that replaced FID and what a passing score actually means now.",
    ),
    # Echoes the title and closes on the word "free" as a pricing fact, not as
    # an instruction to start a free trial.
    (
        "Schema Markup Validator: Test JSON-LD Against Google's Rules",
        "Schema Markup Validator: Test JSON-LD Against Google's Rules for Product, "
        "Article and Event, see every required property, and check 200 URLs for free.",
    ),
]


@pytest.mark.parametrize("title,description", _LEGITIMATE_PAIRS)
def test_legitimate_pairs_are_not_flagged_templated(title: str, description: str) -> None:
    result = metadata_template.analyse(title, description)
    assert result["templated"] is False, result
    assert "templated-metadata" not in result["flags"]
    assert result["severity"] != "high"


def test_cta_alone_is_not_enough_to_flag() -> None:
    """A stock CTA is only evidence when the description also echoes the title."""
    title = "Free Grammar Checker Online: Fix Errors in Any Language"
    description = (
        "Catch grammar, spelling, punctuation and style mistakes across 20+ languages "
        "with no word limit and no account. Try it free now."
    )
    assert (title, description) in _LEGITIMATE_PAIRS
    assert metadata_template._CTA_TAIL_RE.search(description) is not None
    assert metadata_template.analyse(title, description)["templated"] is False


def test_short_title_echo_is_not_flagged() -> None:
    """Titles under the length floor can be echoed by a normal sentence."""
    result = metadata_template.analyse(
        "Word Counter",
        "Word counter that counts words, characters and sentences. Try it free now.",
    )
    assert result["signals"] == []


# ---------------------------------------------------------------------------
# The secondary signals
# ---------------------------------------------------------------------------


def test_brand_suffix_leaked_into_description() -> None:
    result = metadata_template.analyse(
        "Word to HTML Converter | Acme",
        "Word to HTML Converter | Acme Generate clean, fast HTML from any Word document.",
    )
    ids = [s["id"] for s in result["signals"]]
    assert "brand_suffix_in_description" in ids


def test_brand_named_first_in_description_is_not_a_leak() -> None:
    result = metadata_template.analyse(
        "Acme Pricing | Acme",
        "Acme costs nothing for the free tier and $9/month for Pro, billed annually.",
    )
    assert "brand_suffix_in_description" not in [s["id"] for s in result["signals"]]


def test_description_identical_to_title() -> None:
    title = "Complete Guide to Structured Data for Ecommerce Sites"
    result = metadata_template.analyse(title, title)
    ids = [s["id"] for s in result["signals"]]
    assert "description_duplicates_title" in ids
    assert result["severity"] == "medium"


def test_title_echo_without_cta_is_medium_not_high() -> None:
    result = metadata_template.analyse(
        "Complete Guide to Structured Data for Ecommerce Sites",
        "Complete Guide to Structured Data for Ecommerce Sites covering Product, Offer "
        "and AggregateRating, with validator output for each type.",
    )
    assert result["templated"] is False
    assert result["severity"] == "medium"
    assert "description-echoes-title" in result["flags"]


# ---------------------------------------------------------------------------
# Edge cases: nothing here may raise
# ---------------------------------------------------------------------------

_EDGE_CASES = [
    ("", ""),
    ("", "Some description"),
    ("A title", ""),
    ("x", "x"),
    ("|", "|"),
    ("Title | Brand", "Title | Brand"),
    ("A" * 500, "A" * 500),
    (
        "Title <script>alert(1)</script>",
        "Title <script>alert(1)</script> and more text here to pad it out nicely",
    ),
    ("Café Niño — Über Guide", "Café Niño — Über Guide teaches you everything. Learn more now!"),
    ("Title: Sub — Part | Brand", "Title: Sub — Part | Brand does the thing you need. Start free!"),
]


@pytest.mark.parametrize("title,description", _EDGE_CASES)
def test_edge_cases_return_a_well_formed_result(title: str, description: str) -> None:
    result = metadata_template.analyse(title, description)
    assert set(result) >= {"templated", "severity", "flags", "signals"}
    assert isinstance(result["signals"], list)
    assert result["severity"] in ("none", "low", "medium", "high")


def test_missing_metadata_is_reported_not_flagged() -> None:
    result = metadata_template.analyse("", "")
    assert result["flags"] == ["missing-metadata"]
    assert result["templated"] is False


def test_none_inputs_are_tolerated() -> None:
    assert metadata_template.analyse(None, None)["templated"] is False


# ---------------------------------------------------------------------------
# Site-level roll-up (the unit the spam signal actually operates on)
# ---------------------------------------------------------------------------


def _pairs(templated: int, clean: int) -> list[dict]:
    rows = []
    for i in range(templated):
        title, description = _TEMPLATED_PAIRS[i % len(_TEMPLATED_PAIRS)]
        rows.append({"url": f"https://example.com/t{i}", "title": title,
                     "description": description})
    for i in range(clean):
        title, description = _LEGITIMATE_PAIRS[i % len(_LEGITIMATE_PAIRS)]
        rows.append({"url": f"https://example.com/c{i}", "title": title,
                     "description": description})
    return rows


def test_site_wide_templating_is_high_risk() -> None:
    result = metadata_template.analyse_pairs(_pairs(templated=6, clean=6))
    assert result["templated_count"] == 6
    assert result["templated_ratio"] == 0.5
    assert result["site_risk"] == "high"
    assert "site-wide-templated-metadata" in result["site_flags"]


def test_one_templated_page_is_not_a_site_pattern() -> None:
    result = metadata_template.analyse_pairs(_pairs(templated=1, clean=20))
    assert result["templated_count"] == 1
    assert result["site_risk"] == "low"
    assert result["site_flags"] == ["templated-metadata-isolated"]


def test_clean_site_has_no_flags() -> None:
    result = metadata_template.analyse_pairs(_pairs(templated=0, clean=6))
    assert result["templated_count"] == 0
    assert result["site_flags"] == []
    assert result["site_risk"] == "low"


def test_shared_cta_tail_is_counted_across_pages() -> None:
    result = metadata_template.analyse_pairs(_pairs(templated=6, clean=0))
    assert "shared-cta-tail" in result["site_flags"]
    assert sum(result["shared_cta_phrases"].values()) == 6
    assert max(result["shared_cta_phrases"].values()) >= 3


def test_empty_site_does_not_divide_by_zero() -> None:
    result = metadata_template.analyse_pairs([])
    assert result["pages_checked"] == 0
    assert result["templated_ratio"] == 0.0
    assert result["site_risk"] == "low"


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, os.path.join(_SCRIPTS, "metadata_template.py"), *args],
        capture_output=True, text=True,
    )


def test_cli_emits_valid_json() -> None:
    title, description = _TEMPLATED_PAIRS[0]
    proc = _run_cli("--title", title, "--description", description, "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["templated_count"] == 1
    assert payload["pages"][0]["signals"][0]["id"] == "templated_metadata"


def test_cli_fail_on_any_exits_nonzero() -> None:
    title, description = _TEMPLATED_PAIRS[0]
    proc = _run_cli("--title", title, "--description", description,
                    "--json", "--fail-on", "any")
    assert proc.returncode == 1, proc.stdout


def test_cli_without_input_returns_usage_error() -> None:
    proc = _run_cli("--json")
    assert proc.returncode == 2
    assert "Error:" in proc.stderr


def test_cli_reads_a_pairs_file(tmp_path) -> None:
    path = tmp_path / "pairs.json"
    path.write_text(json.dumps(_pairs(templated=4, clean=4)), encoding="utf-8")
    proc = _run_cli("--pairs-file", str(path), "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["pages_checked"] == 8
    assert payload["templated_count"] == 4
    assert payload["site_risk"] == "high"


def test_pairs_file_accepts_parse_html_meta_description_key(tmp_path) -> None:
    title, description = _TEMPLATED_PAIRS[0]
    path = tmp_path / "parsed.json"
    path.write_text(
        json.dumps({"url": "https://example.com/", "title": title,
                    "meta_description": description}),
        encoding="utf-8",
    )
    proc = _run_cli("--pairs-file", str(path), "--json")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["templated_count"] == 1
