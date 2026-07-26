"""Regression for issue #130: GSC site totals must come from a dimensionless
aggregate query, not from summing per-query rows (which GSC anonymizes,
producing a false "0 clicks" site total).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# gsc_query calls sys.exit(1) at import time when google-api-python-client is
# missing. Under pytest that SystemExit escapes collection as an INTERNALERROR
# and aborts the whole session, so no test in tests/ runs. Skip this module
# instead when the optional Google stack is absent.
pytest.importorskip("googleapiclient")

import gsc_query  # noqa: E402


class _Exec:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _SearchAnalytics:
    """Query-dimension rows hide clicks (anonymized); the dimensionless
    aggregate carries the real totals."""

    def query(self, siteUrl=None, body=None):
        if body.get("dimensions") == []:
            return _Exec({"rows": [
                {"clicks": 24, "impressions": 2734, "ctr": 0.0088, "position": 12.3},
            ]})
        return _Exec({"rows": [
            {"keys": ["kw a"], "clicks": 0, "impressions": 500, "ctr": 0, "position": 8},
            {"keys": ["kw b"], "clicks": 0, "impressions": 428, "ctr": 0, "position": 9},
        ]})


class _Service:
    def searchanalytics(self):
        return _SearchAnalytics()


def test_totals_use_aggregate_not_query_sum():
    with mock.patch.object(gsc_query, "_build_gsc_service", return_value=_Service()):
        result = gsc_query.query_search_analytics("sc-domain:example.com", dimensions=["query"])
    # Summing the query rows would yield 0 clicks; the aggregate is the truth.
    assert result["totals"]["clicks"] == 24, result["totals"]
    assert result["totals"]["impressions"] == 2734, result["totals"]
    assert result["totals_source"] == "dimensionless_aggregate"
    assert result["totals_complete"] is True
    assert result["row_count"] == 2  # rows still come from the dimensioned query


def test_totals_fall_back_to_row_sum_when_aggregate_fails():
    class _FailingSA(_SearchAnalytics):
        def query(self, siteUrl=None, body=None):
            if body.get("dimensions") == []:
                raise RuntimeError("aggregate query failed")
            return super().query(siteUrl=siteUrl, body=body)

    class _FailingService:
        def searchanalytics(self):
            return _FailingSA()

    with mock.patch.object(gsc_query, "_build_gsc_service", return_value=_FailingService()):
        result = gsc_query.query_search_analytics("sc-domain:example.com", dimensions=["query"])
    # Aggregate failed -> fall back to the summed rows (impressions still add up).
    assert result["totals"]["impressions"] == 928, result["totals"]
    assert result["totals_source"] == "partial_row_sum"
    assert result["totals_complete"] is False
    assert any("incomplete" in warning for warning in result["warnings"])
