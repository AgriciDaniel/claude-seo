"""Lighthouse emits `score: null` for categories it could not evaluate
(scoreDisplayMode "error" or "notApplicable"). `cat_data.get("score", 0)`
only defaults on a *missing* key, so an explicit null reached the multiply
and raised TypeError, losing the whole PSI run — including the categories
that did score.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pagespeed_check  # noqa: E402


class _Response:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _psi_payload():
    return {
        "analysisUTCTimestamp": "2026-08-29T00:00:00.000Z",
        "lighthouseResult": {
            "categories": {
                "performance": {"score": 0.91},
                "accessibility": {"score": None},  # not evaluated
                "seo": {"score": 0.5},
            },
            "audits": {},
        },
    }


def test_null_category_score_does_not_crash_the_run():
    with mock.patch.object(
        pagespeed_check.requests, "get", return_value=_Response(_psi_payload())
    ):
        result = pagespeed_check.run_pagespeed("https://example.com")

    assert result["error"] is None, result["error"]
    assert result["lighthouse_scores"]["performance"] == 91
    assert result["lighthouse_scores"]["seo"] == 50


def test_unscored_category_is_omitted_not_reported_as_zero():
    with mock.patch.object(
        pagespeed_check.requests, "get", return_value=_Response(_psi_payload())
    ):
        result = pagespeed_check.run_pagespeed("https://example.com")

    # A category Lighthouse refused to score is absent, not a 0/100 failure.
    assert "accessibility" not in result["lighthouse_scores"], result["lighthouse_scores"]
