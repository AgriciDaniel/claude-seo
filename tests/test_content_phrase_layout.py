"""Existing phrase signals should survive ordinary typography and wrapping."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import content_quality  # noqa: E402

PLAIN = (
    "In today's fast-paced world, when it comes to SEO, "
    "it's important to note that results need evidence."
)


@pytest.mark.parametrize("separator", ["\t", "\n", "\r\n", "  ", "\u00a0", "\u202f"])
def test_phrase_scores_survive_wrapped_and_nonbreaking_spaces(separator):
    reference = content_quality.analyse(PLAIN)
    result = content_quality.analyse(PLAIN.replace(" ", separator))

    assert reference["filler_score"] == 75
    assert result["matches"]["filler"] == reference["matches"]["filler"]
    assert result["filler_score"] == reference["filler_score"]
    assert "filler" in result["flags"]


@pytest.mark.parametrize("separator", [" ", "\u00a0", "\n"])
def test_typographic_apostrophes_preserve_existing_filler_signals(separator):
    reference = content_quality.analyse(PLAIN)
    text = PLAIN.replace("'", "\u2019").replace(" ", separator)
    result = content_quality.analyse(text)

    assert result["matches"]["filler"] == reference["matches"]["filler"]
    assert result["filler_score"] == 75


def test_layout_folding_keeps_the_longer_phrase_a_single_hit():
    result = content_quality.analyse("Let\u2019s\u00a0dive\u00a0into the details today.")

    assert result["matches"]["filler"] == ["let's dive into"]
    assert result["filler_score"] == 25


def test_existing_ai_pattern_accepts_a_wrapped_phrase():
    result = content_quality.analyse("By\nleveraging the available evidence, we can compare results.")

    assert result["matches"]["ai_patterns"] == ["by leveraging"]
    assert result["ai_pattern_score"] == 15


def test_layout_folding_does_not_match_part_of_a_longer_word():
    result = content_quality.analyse("We delve\nintoxication and when it comes together.")

    assert result["matches"]["ai_patterns"] == []
    assert result["matches"]["filler"] == []
