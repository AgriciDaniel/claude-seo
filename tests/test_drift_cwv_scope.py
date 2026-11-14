"""A URL percentile cannot be compared with an origin-wide percentile."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from drift_compare import rule_11_cwv_regressed  # noqa: E402

METRIC = "largest_contentful_paint"


def compare(old, new):
    return rule_11_cwv_regressed(
        {"cwv_json": json.dumps({"field_metrics": old})}, {"field_metrics": new},
    )


def test_different_populations_do_not_create_a_regression():
    result = compare({"url_" + METRIC: {"p75": 1000}}, {"origin_" + METRIC: {"p75": 3000}})
    assert result["triggered"] is False
    assert "skipped" in result["message"].lower()


def test_common_origin_scope_is_used_when_url_coverage_changes():
    result = compare(
        {"url_" + METRIC: {"p75": 1000}, "origin_" + METRIC: {"p75": 3000}},
        {"origin_" + METRIC: {"p75": 3000}},
    )
    assert result["triggered"] is False
    assert result["old_value"][METRIC] == 3000
    assert result["new_value"][METRIC] == 3000


def test_matching_url_scope_still_detects_a_regression():
    result = compare({"url_" + METRIC: {"p75": 1000}}, {"url_" + METRIC: {"p75": 2000}})
    assert result["triggered"] is True


def test_legacy_unprefixed_scope_still_works():
    result = compare({METRIC: {"value": 1000}}, {METRIC: {"value": 2000}})
    assert result["triggered"] is True
