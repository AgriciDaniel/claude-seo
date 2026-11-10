"""Noindex drift follows robots directives, including the none shorthand."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from drift_compare import rule_04_noindex_added  # noqa: E402


@pytest.mark.parametrize("current", ["none", "NONE", " none , max-snippet:0"])
def test_none_added_blocks_indexing(current):
    result = rule_04_noindex_added({"robots": "index, follow"}, {"meta_robots": current})
    assert result["triggered"] is True
    assert result["severity"] == "CRITICAL"


@pytest.mark.parametrize("previous", ["none", "NONE", "noindex, nofollow"])
def test_equivalent_existing_restriction_is_not_new(previous):
    result = rule_04_noindex_added({"robots": previous}, {"meta_robots": "noindex"})
    assert result["triggered"] is False


@pytest.mark.parametrize("current", [
    "max-image-preview:none", "max-image-preview: none",
    "max-image-preview: none, follow", "not-noindex", "index, follow",
])
def test_values_or_substrings_are_not_noindex_directives(current):
    assert rule_04_noindex_added({}, {"meta_robots": current})["triggered"] is False


def test_comma_separated_noindex_still_triggers():
    assert rule_04_noindex_added({}, {"meta_robots": "follow, NOINDEX"})["triggered"] is True


@pytest.mark.parametrize("current", [
    "follow none", "max-image-preview: none noindex",
    "max-image-preview: none, NOINDEX",
])
def test_parameter_values_do_not_hide_an_independent_directive(current):
    assert rule_04_noindex_added({}, {"meta_robots": current})["triggered"] is True


def test_previous_parameter_value_does_not_hide_a_new_restriction():
    assert rule_04_noindex_added(
        {"robots": "max-image-preview: none"}, {"meta_robots": "none"},
    )["triggered"] is True
