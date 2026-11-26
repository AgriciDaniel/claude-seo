"""Claim extraction preserves priority without rescanning every previous claim."""

from __future__ import annotations

import random
import re
import sys
from itertools import permutations
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import content_verify  # noqa: E402


def _reference(text):
    """Simple exhaustive oracle for the documented pattern-priority rule."""
    spans = []
    occupied = set()
    for pattern, kind in content_verify._CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            positions = set(range(start, end))
            if occupied.intersection(positions):
                continue
            spans.append((start, end, kind))
            occupied.update(positions)
    return [
        (text[start:end].strip(), kind, start)
        for start, end, kind in sorted(spans)
    ]


@pytest.mark.parametrize("seed", range(8))
def test_pattern_priority_and_offsets_match_exhaustive_oracle(seed):
    fragments = [
        "47% of marketers report gains.",
        "A 60% improvement.",
        "Revenue reached $3.2 billion by 2030.",
        "Forrester said adoption grew in 2025.",
        "The product is 3x faster and twice as useful.",
        "A survey of 1,000 people.",
        "No numeric claim here.",
        "[Source](https://example.org/study)",
        "Η βελτίωση ήταν 15%.",
    ]
    rng = random.Random(seed)
    text = " ".join(rng.choices(fragments, k=70))
    actual = content_verify.extract_claims(text)
    assert [(c["text"], c["kind"], c["position"]) for c in actual] == _reference(text)
    for claim in actual:
        citation = content_verify._has_citation_near(text, claim["position"])
        assert claim["has_citation"] == (citation is not None)
        assert claim["nearby_citation"] == citation


@pytest.mark.parametrize("with_overlap", [False, True])
def test_overlap_comparisons_are_linear_in_claim_count(monkeypatch, with_overlap):
    """Count endpoint comparisons, including a quadratic scan of cached positions."""
    comparisons = 0

    class Position(int):
        def __lt__(self, other):
            nonlocal comparisons
            comparisons += 1
            return super().__lt__(other)

        def __le__(self, other):
            nonlocal comparisons
            comparisons += 1
            return super().__le__(other)

    class CountedMatch:
        def __init__(self, match):
            self.match = match

        def start(self):
            return Position(self.match.start())

        def end(self):
            return Position(self.match.end())

        def span(self):
            return tuple(Position(value) for value in self.match.span())

    class CountedPattern:
        def __init__(self, pattern):
            self.pattern = pattern

        def finditer(self, text):
            for match in self.pattern.finditer(text):
                yield CountedMatch(match)

    monkeypatch.setattr(content_verify, "_CLAIM_PATTERNS", tuple(
        (CountedPattern(pattern), kind)
        for pattern, kind in content_verify._CLAIM_PATTERNS
    ))
    count = 600
    fragment = "47% of marketers report gains. " if with_overlap else "47%. "
    result = content_verify.verify(fragment * count)
    assert result["claim_count"] == count
    assert result["uncited_count"] == count
    # The overlapping longer and shorter percentage patterns each see the
    # same 600 claims. Caching their positions alone must not satisfy this
    # bound: checking every previous span still performs quadratic comparisons.
    assert comparisons <= count * 12


def test_cross_pattern_overlap_priority_for_every_order(monkeypatch):
    text = "abcdef"
    fragments = ("bc", "abcd", "cd", "de", "ab", "f")
    for order in permutations(fragments):
        monkeypatch.setattr(content_verify, "_CLAIM_PATTERNS", tuple(
            (re.compile(fragment), fragment) for fragment in order
        ))
        actual = content_verify.extract_claims(text)
        assert [(c["text"], c["kind"], c["position"]) for c in actual] == _reference(text), order


def test_identical_span_keeps_the_first_pattern_label(monkeypatch):
    monkeypatch.setattr(content_verify, "_CLAIM_PATTERNS", (
        (re.compile("abc"), "first"), (re.compile("abc"), "second"),
    ))
    assert content_verify.extract_claims("abc")[0]["kind"] == "first"


def test_empty_and_adjacent_claims_keep_independent_offsets():
    assert content_verify.extract_claims("") == []
    text = "47%60%80%"
    claims = content_verify.extract_claims(text)
    assert [(c["text"], c["position"]) for c in claims] == [
        ("47%", 0), ("60%", 3), ("80%", 6),
    ]
