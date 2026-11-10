"""A failed GA4 top landing pages query must keep its error."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("google.analytics.data_v1beta")

import ga4_report  # noqa: E402
from google.analytics.data_v1beta.types import RunReportResponse  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    client = Mock()
    monkeypatch.setattr(ga4_report, "_build_ga4_client", lambda: client)
    return client


def daily_response():
    return RunReportResponse(rows=[{
        "dimension_values": [{"value": "20261101"}],
        "metric_values": [{"value": value} for value in ("10", "8", "12", "0.2", "15", "0.8")],
    }])


def test_top_pages_surfaces_failed_landing_page_query(client):
    client.run_report.side_effect = [daily_response(), RuntimeError("landing pages unavailable")]

    result = ga4_report.top_pages_report("123456789")

    assert result["error"] == "Error fetching top pages: landing pages unavailable"
    assert result["pages"] == []
    assert result["total_organic_sessions"] == 10
    assert client.run_report.call_count == 2
    assert client.run_report.call_args.args[0].dimensions[0].name == "landingPage"


@pytest.mark.parametrize("has_pages", [False, True])
def test_successful_top_pages_keeps_its_response(client, has_pages):
    rows = [{
        "dimension_values": [{"value": "/guide"}],
        "metric_values": [{"value": value} for value in ("10", "8", "12", "0.2", "0.8")],
    }] if has_pages else []
    client.run_report.side_effect = [daily_response(), RunReportResponse(rows=rows)]

    result = ga4_report.top_pages_report("123456789")

    assert result["error"] is None
    assert result["total_organic_sessions"] == 10
    assert len(result["pages"]) == int(has_pages)
    if has_pages:
        assert result["pages"][0]["landing_page"] == "/guide"


def test_top_pages_retains_primary_daily_query_error(client):
    client.run_report.side_effect = RuntimeError("daily report unavailable")

    result = ga4_report.top_pages_report("123456789")

    assert result["error"] == "GA4 API error: daily report unavailable"
    assert client.run_report.call_count == 1


def test_organic_report_preserves_partial_daily_data(client):
    client.run_report.side_effect = [daily_response(), RuntimeError("landing pages unavailable")]

    result = ga4_report.organic_traffic_report("123456789")

    assert result["error"] is None
    assert result["pages_error"] == "Error fetching top pages: landing pages unavailable"
    assert result["daily_data"][0]["sessions"] == 10


@pytest.mark.parametrize("json_output", [False, True])
def test_cli_exposes_landing_page_query_failure(client, monkeypatch, capsys, json_output):
    client.run_report.side_effect = [daily_response(), RuntimeError("landing pages unavailable")]
    argv = ["ga4_report.py", "--property", "123456789", "--report", "top-pages"]
    monkeypatch.setattr(sys, "argv", argv + (["--json"] if json_output else []))

    if json_output:
        ga4_report.main()
    else:
        with pytest.raises(SystemExit) as exc:
            ga4_report.main()
        assert exc.value.code == 1

    output = capsys.readouterr()
    assert "landing pages unavailable" in output.err
    if json_output:
        assert json.loads(output.out)["error"] == "Error fetching top pages: landing pages unavailable"
    else:
        assert "Top Organic Landing Pages" not in output.out
