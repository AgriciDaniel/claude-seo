"""PSI field CLS is an integer in hundredths, including percentile 1.

Lighthouse and the direct CrUX API already return the unscaled CLS score.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

pytest.importorskip("requests")
import pagespeed_check  # noqa: E402


def _response(payload):
    response = mock.Mock(status_code=200)
    response.json.return_value = payload
    return response


@pytest.mark.parametrize(
    "experience,source",
    [("loadingExperience", "url"), ("originLoadingExperience", "origin")],
)
@pytest.mark.parametrize(
    "percentile,expected",
    [(0, 0.0), (1, 0.01), (10, 0.1), (25, 0.25), (100, 1.0), (125, 1.25)],
)
def test_psi_field_cls_is_reported_in_score_units(experience, source, percentile, expected):
    payload = {
        experience: {
            "metrics": {
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {
                    "percentile": percentile,
                    "category": (
                        "FAST" if percentile <= 10 else "AVERAGE" if percentile <= 25 else "SLOW"
                    ),
                },
            },
        },
    }
    with mock.patch.object(pagespeed_check.requests, "get", return_value=_response(payload)):
        result = pagespeed_check.run_pagespeed("https://example.com/")

    assert result["error"] is None
    metric = result["field_metrics"][f"{source}_cumulative_layout_shift"]
    assert metric["p75"] == expected
    assert metric["source"] == f"PSI {source}-level"


def test_other_psi_metrics_and_lighthouse_cls_keep_their_units():
    payload = {
        "loadingExperience": {
            "metrics": {
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 1, "category": "FAST"},
                "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2100, "category": "FAST"},
                "INTERACTION_TO_NEXT_PAINT": {"percentile": 170, "category": "FAST"},
                "FIRST_CONTENTFUL_PAINT_MS": {"percentile": 1000, "category": "FAST"},
                "EXPERIMENTAL_TIME_TO_FIRST_BYTE": {"percentile": 100, "category": "FAST"},
            },
        },
        "lighthouseResult": {
            "audits": {
                "cumulative-layout-shift": {"numericValue": 1.0, "displayValue": "1.000"},
            },
        },
    }
    with mock.patch.object(pagespeed_check.requests, "get", return_value=_response(payload)):
        result = pagespeed_check.run_pagespeed("https://example.com/")

    assert result["error"] is None
    assert result["field_metrics"]["url_cumulative_layout_shift"]["rating"] == "fast"
    expected = {
        "largest_contentful_paint": 2100,
        "interaction_to_next_paint": 170,
        "first_contentful_paint": 1000,
        "experimental_time_to_first_byte": 100,
    }
    for metric, value in expected.items():
        assert result["field_metrics"][f"url_{metric}"]["p75"] == value
    assert result["lab_metrics"]["cumulative-layout-shift"]["value"] == 1.0


@pytest.mark.parametrize("percentile", [None, "missing"])
def test_missing_psi_percentile_is_not_reported_as_zero(percentile):
    metric = {"category": "NONE"}
    if percentile is None:
        metric["percentile"] = None
    payload = {
        experience: {"metrics": {"CUMULATIVE_LAYOUT_SHIFT_SCORE": metric}}
        for experience in ("loadingExperience", "originLoadingExperience")
    }
    with mock.patch.object(pagespeed_check.requests, "get", return_value=_response(payload)):
        result = pagespeed_check.run_pagespeed("https://example.com/")

    assert result["error"] is None
    assert result["field_metrics"] == {}


@pytest.mark.parametrize("percentile,expected", [("0.01", 0.01), ("1.00", 1.0), (1, 1.0)])
def test_direct_crux_cls_is_not_rescaled(percentile, expected):
    payload = {
        "record": {
            "metrics": {"cumulative_layout_shift": {"percentiles": {"p75": percentile}}},
        },
    }
    with mock.patch.object(pagespeed_check.requests, "post", return_value=_response(payload)):
        result = pagespeed_check.query_crux("https://example.com/", "test-api-token")

    assert result["error"] is None
    assert result["metrics"]["cumulative_layout_shift"]["p75"] == expected
