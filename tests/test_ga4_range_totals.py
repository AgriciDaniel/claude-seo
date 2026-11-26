"""GA4 users are distinct over the report period, not additive by date."""

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("google.analytics.data_v1beta")

import ga4_report  # noqa: E402
from google.analytics.data_v1beta.types import RunReportResponse  # noqa: E402


def row(dimension, values):
    return {
        "dimension_values": [{"value": dimension}] if dimension is not None else [],
        "metric_values": [{"value": str(value)} for value in values],
    }


@pytest.fixture
def client(monkeypatch):
    client = Mock()
    daily = RunReportResponse(rows=[
        row("20261101", (15, 8, 25, 0.2, 30, 0.8)),
        row("20261103", (15, 8, 25, 0.2, 30, 0.8)),
    ])
    totals = RunReportResponse(rows=[row(None, (30, 10, 50))])
    pages = RunReportResponse(rows=[row("/guide", (30, 10, 50, 0.2, 0.8))])

    def run_report(request):
        if not request.dimensions:
            return totals
        return daily if request.dimensions[0].name == "date" else pages

    client.run_report.side_effect = run_report
    monkeypatch.setattr(ga4_report, "_build_ga4_client", lambda: client)
    return client


def test_period_users_use_deduplicated_aggregate(client):
    result = ga4_report.organic_traffic_report("123456789", days=3)

    assert result["error"] is None
    assert [day["users"] for day in result["daily_data"]] == [8, 8]
    assert result["totals"] == {
        "sessions": 30, "users": 10, "pageviews": 50, "avg_daily_sessions": 10.0,
    }
    requests = [call.args[0] for call in client.run_report.call_args_list]
    daily = next(request for request in requests if request.dimensions
                 and request.dimensions[0].name == "date")
    aggregate = next(request for request in requests if not request.dimensions)
    assert aggregate.property == daily.property == "properties/123456789"
    assert aggregate.date_ranges == daily.date_ranges
    assert aggregate.dimension_filter == daily.dimension_filter
    assert aggregate.dimension_filter.filter.string_filter.value == "Organic Search"
    assert [metric.name for metric in aggregate.metrics] == [
        "sessions", "totalUsers", "screenPageViews",
    ]


@pytest.mark.parametrize("json_output", [False, True])
def test_failed_totals_keep_partial_data_and_unknown_users(client, monkeypatch, capsys, json_output):
    successful_request = client.run_report.side_effect

    def fail_totals(request):
        if not request.dimensions:
            raise RuntimeError("aggregate quota exhausted")
        return successful_request(request)

    client.run_report.side_effect = fail_totals
    monkeypatch.setattr(sys, "argv", [
        "ga4_report.py", "--property", "123456789", "--days", "3",
    ] + (["--json"] if json_output else []))

    ga4_report.main()

    output = capsys.readouterr()
    assert "aggregate quota exhausted" in output.err
    if json_output:
        result = json.loads(output.out)
        assert result["error"] is None
        assert result["totals"]["users"] is None
        assert result["totals"]["sessions"] == 30
        assert len(result["daily_data"]) == 2
        assert result["top_pages"][0]["landing_page"] == "/guide"
        assert "aggregate quota exhausted" in result["totals_error"]
    else:
        assert "Users: unavailable" in output.out
        assert "Sessions: 30" in output.out
        assert "/guide" in output.out


def test_empty_period_has_zero_totals(client):
    client.run_report.side_effect = None
    client.run_report.return_value = RunReportResponse()

    result = ga4_report.organic_traffic_report("123456789", days=3)

    assert result["totals"] == {
        "sessions": 0, "users": 0, "pageviews": 0, "avg_daily_sessions": 0.0,
    }
    assert result["error"] is None
    assert "totals_error" not in result


def test_top_pages_preserves_aggregate_failure_warning(client):
    successful_request = client.run_report.side_effect

    def fail_totals(request):
        if not request.dimensions:
            raise RuntimeError("aggregate unavailable")
        return successful_request(request)

    client.run_report.side_effect = fail_totals

    result = ga4_report.top_pages_report("123456789", days=3)

    assert result["error"] is None
    assert result["total_organic_sessions"] == 30
    assert result["pages"][0]["landing_page"] == "/guide"
    assert "aggregate unavailable" in result["totals_error"]
