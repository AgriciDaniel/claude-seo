"""GSC total-limit and blank-dimension regressions for issues #130 and #173."""

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
        self.response = response

    def execute(self):
        return self.response


class _SearchAnalytics:
    def __init__(self, available=30000):
        self.available = available
        self.calls = []

    def query(self, siteUrl=None, body=None):
        self.calls.append(dict(body))
        if body.get("dimensions") == []:
            return _Exec({"rows": [{"clicks": 9, "impressions": 90, "ctr": 0.1, "position": 3}]})
        start = body.get("startRow", 0)
        count = max(0, min(body["rowLimit"], self.available - start))
        rows = [
            {"keys": [f"q{start + i}"], "clicks": 1, "impressions": 2, "ctr": 0.5, "position": 4}
            for i in range(count)
        ]
        return _Exec({"rows": rows})


class _Service:
    def __init__(self, available=30000):
        self.analytics = _SearchAnalytics(available)

    def searchanalytics(self):
        return self.analytics


def _run(limit, available=30000, dimensions=None):
    service = _Service(available)
    with mock.patch.object(gsc_query, "_build_gsc_service", return_value=service):
        result = gsc_query.query_search_analytics(
            "sc-domain:example.com",
            dimensions=["query"] if dimensions is None else dimensions,
            row_limit=limit,
        )
    return result, service.analytics.calls


def test_small_limit_is_one_small_request_plus_aggregate():
    result, calls = _run(5)
    assert result["row_count"] == 5
    assert [call["rowLimit"] for call in calls] == [5, 1]
    assert calls[0]["startRow"] == 0


def test_exact_api_page_limit_does_not_fetch_an_extra_dimension_page():
    result, calls = _run(25000)
    assert result["row_count"] == 25000
    assert [call["rowLimit"] for call in calls] == [25000, 1]


def test_limit_over_api_page_size_fetches_only_the_remaining_row():
    result, calls = _run(25001)
    assert result["row_count"] == 25001
    assert [call["rowLimit"] for call in calls] == [25000, 1, 1]
    assert calls[1]["startRow"] == 25000


def test_short_page_stops_before_total_cap():
    result, calls = _run(100, available=7)
    assert result["row_count"] == 7
    assert [call["rowLimit"] for call in calls] == [100, 1]


def test_invalid_limits_fail_before_building_service():
    with mock.patch.object(gsc_query, "_build_gsc_service") as build:
        for invalid in (0, -1, True):
            result = gsc_query.query_search_analytics("sc-domain:example.com", row_limit=invalid)
            assert result["error"] == "row_limit must be a positive integer"
    build.assert_not_called()


def test_invalid_programmatic_dimensions_fail_before_building_service():
    invalid_cases = [
        (["query", "unsupported"], "Unsupported GSC dimensions: unsupported"),
        (["query", "query"], "GSC dimensions cannot contain duplicates"),
        (("query",), "GSC dimensions must be a list or None"),
        (["query", 1], "GSC dimensions must contain only strings"),
    ]
    with mock.patch.object(gsc_query, "_build_gsc_service") as build:
        for dimensions, expected in invalid_cases:
            result = gsc_query.query_search_analytics(
                "sc-domain:example.com", dimensions=dimensions
            )
            assert result["error"] == expected
    build.assert_not_called()


def test_none_programmatic_dimensions_preserve_default():
    service = _Service(available=1)
    with mock.patch.object(gsc_query, "_build_gsc_service", return_value=service):
        result = gsc_query.query_search_analytics(
            "sc-domain:example.com", dimensions=None, row_limit=1
        )
    assert result["error"] is None
    assert service.analytics.calls[0]["dimensions"] == ["query", "page"]


def test_blank_cli_dimensions_parse_to_empty_list():
    assert gsc_query._parse_dimensions("") == []
    assert gsc_query._parse_dimensions(" , ") == []


def test_dimensionless_primary_query_is_reused_for_totals():
    result, calls = _run(1, dimensions=[])
    assert len(calls) == 1
    assert calls[0]["dimensions"] == []
    assert result["totals"]["clicks"] == 9
    assert result["totals_source"] == "dimensionless_query"
    assert result["totals_complete"] is True


def test_filters_are_copied_to_dimensionless_aggregate():
    service = _Service(available=1)
    filters = [{"dimension": "country", "operator": "equals", "expression": "USA"}]
    with mock.patch.object(gsc_query, "_build_gsc_service", return_value=service):
        gsc_query.query_search_analytics(
            "sc-domain:example.com", dimensions=["query"], row_limit=1, filters=filters
        )
    assert service.analytics.calls[-1]["dimensionFilterGroups"] == [{"filters": filters}]
