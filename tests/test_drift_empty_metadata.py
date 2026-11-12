"""Empty metadata must be classified consistently as absent during drift."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from drift_compare import (  # noqa: E402
    rule_02_canonical_changed,
    rule_03_canonical_removed,
    rule_10_meta_description_changed,
)


@pytest.mark.parametrize("old", [None, "", "  "])
@pytest.mark.parametrize("new", [None, "", "  "])
def test_absent_canonical_does_not_raise_a_regression(old, new):
    assert not rule_02_canonical_changed({"canonical": old}, {"canonical": new})["triggered"]
    assert not rule_03_canonical_removed({"canonical": old}, {"canonical": new})["triggered"]


@pytest.mark.parametrize("new", [None, "", "  "])
def test_canonical_removal_has_one_finding(new):
    baseline = {"canonical": "https://example.com/"}
    current = {"canonical": new}
    assert not rule_02_canonical_changed(baseline, current)["triggered"]
    assert rule_03_canonical_removed(baseline, current)["triggered"]


@pytest.mark.parametrize("new", [None, "", "  "])
def test_description_removal_is_reported(new):
    result = rule_10_meta_description_changed(
        {"meta_description": "Description visible in the baseline."}, {"meta_description": new},
    )
    assert result["triggered"]
    assert "removed" in result["message"].lower()


def test_nonempty_changes_and_whitespace_equivalence():
    assert rule_02_canonical_changed({"canonical": "https://example.com/old"},
                                     {"canonical": "https://example.com/new"})["triggered"]
    assert not rule_02_canonical_changed({"canonical": " https://example.com/ "},
                                         {"canonical": "https://example.com/"})["triggered"]
    assert rule_10_meta_description_changed({"meta_description": "old"},
                                            {"meta_description": "new"})["triggered"]
