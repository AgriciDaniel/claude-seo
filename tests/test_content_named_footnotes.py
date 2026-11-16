"""Named Markdown footnotes count as nearby citation markers."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import content_verify as verifier  # noqa: E402


@pytest.mark.parametrize("label", ["source", "market_report", "report-2026", "a1", "研究"])
def test_named_footnote_is_a_citation(label):
    marker = f"[^{label}]"
    result = verifier.verify(f"47% of customers returned. {marker}")
    assert result["claim_count"] == 1
    assert result["uncited_count"] == 0
    assert result["uncited_ratio"] == 0
    assert result["claims"][0]["nearby_citation"] == marker


@pytest.mark.parametrize("marker", ["[1]", "[^1]", "[^120]"])
def test_numeric_references_keep_working(marker):
    result = verifier.verify(f"Sales grew 25%. {marker}")
    assert result["uncited_count"] == 0


@pytest.mark.parametrize("text", ["[source]", "[^]", "[^two words]", "[^unclosed"])
def test_ordinary_brackets_or_invalid_labels_are_not_citations(text):
    result = verifier.verify(f"Sales grew 25%. {text}")
    assert result["uncited_count"] == 1


def test_named_marker_obeys_the_existing_proximity_window():
    result = verifier.verify("Sales grew 25%. " + "text " * 60 + "[^source]")
    assert result["uncited_count"] == 1
