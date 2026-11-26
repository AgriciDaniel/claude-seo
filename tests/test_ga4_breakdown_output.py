"""The text CLI must display the data returned by each GA4 breakdown query."""

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("google.analytics.data_v1beta")

import ga4_report  # noqa: E402
from google.analytics.data_v1beta.types import RunReportResponse  # noqa: E402


@pytest.mark.parametrize("report,dimension,label,values", [
    ("device", "deviceCategory", "mobile", ("1234", "980", "0.25", "0.75")),
    ("country", "country", "United Kingdom", ("1234", "980")),
])
@pytest.mark.parametrize("json_output", [False, True])
def test_breakdown_cli_preserves_returned_rows(
    monkeypatch, capsys, report, dimension, label, values, json_output,
):
    client = Mock()
    client.run_report.return_value = RunReportResponse(rows=[{
        "dimension_values": [{"value": label}],
        "metric_values": [{"value": value} for value in values],
    }])
    monkeypatch.setattr(ga4_report, "_build_ga4_client", lambda: client)
    argv = ["ga4_report.py", "--property", "123456789", "--report", report]
    monkeypatch.setattr(sys, "argv", argv + (["--json"] if json_output else []))

    ga4_report.main()

    output = capsys.readouterr()
    assert output.err == ""
    request = client.run_report.call_args.args[0]
    assert request.dimensions[0].name == dimension
    assert request.dimension_filter.filter.string_filter.value == "Organic Search"
    if json_output:
        data = json.loads(output.out)
        rows = data["devices" if report == "device" else "countries"]
        assert rows[0]["sessions"] == 1234
        assert rows[0]["users"] == 980
        assert rows[0]["category" if report == "device" else "country"] == label
    else:
        assert label in output.out
        assert "1,234 sessions | 980 users" in output.out
        assert "Sessions: 0" not in output.out
        assert "Period:" in output.out
        if report == "device":
            assert "Bounce: 25.0% | Engagement: 75.0%" in output.out


@pytest.mark.parametrize("report", ["device", "country"])
def test_empty_breakdown_is_reported_without_fabricating_totals(monkeypatch, capsys, report):
    client = Mock()
    client.run_report.return_value = RunReportResponse()
    monkeypatch.setattr(ga4_report, "_build_ga4_client", lambda: client)
    monkeypatch.setattr(sys, "argv", [
        "ga4_report.py", "--property", "123456789", "--report", report,
    ])

    ga4_report.main()

    output = capsys.readouterr().out
    assert "No organic traffic data for this period." in output
    assert "Sessions: 0" not in output
