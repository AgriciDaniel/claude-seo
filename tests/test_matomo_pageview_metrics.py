"""Page views must come from Matomo's page-view metric, not all actions."""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import matomo_report as report  # noqa: E402

DAILY = {
    "2026-11-12": {
        "nb_visits": 80, "nb_uniq_visitors": 60, "nb_actions": 150,
        "nb_pageviews": 120, "bounce_count": 20, "sum_visit_length": 800,
    },
    "2026-11-13": {
        "nb_visits": 20, "nb_uniq_visitors": 10, "nb_actions": 60,
        "nb_pageviews": 45, "bounce_count": 5, "sum_visit_length": 200,
    },
}


def fake_api(monkeypatch, daily):
    calls = []

    def request(url, token, params):
        calls.append(dict(params))
        if params["method"] == "Actions.getEntryPageUrls":
            return report._envelope("success", [])
        values = copy.deepcopy(daily)
        # VisitsSummary reports actions; API.get combines explicitly requested
        # VisitsSummary and Actions metrics in the same date-keyed response.
        for row in values.values():
            if params["method"] != "API.get" or "nb_pageviews" not in params.get("columns", "").split(","):
                row.pop("nb_pageviews", None)
        return report._envelope("success", values)

    monkeypatch.setattr(report, "_request", request)
    return calls


def test_organic_report_uses_authoritative_pageviews(monkeypatch):
    calls = fake_api(monkeypatch, DAILY)
    result = report.organic_traffic_report("7", "https://analytics.example.com", "token", days=2)
    data = result["data"]
    assert data["totals"]["pageviews"] == 165
    assert data["totals"]["actions"] == 210
    assert [row["pageviews"] for row in data["daily_data"]] == [120, 45]
    assert len(calls) == 2
    assert calls[0]["idSite"] == "7"
    assert calls[0]["period"] == "day"
    assert calls[0]["segment"] == "referrerType==search"
    assert calls[0]["date"] == ",".join(data["date_range"].values())


@pytest.mark.parametrize("missing_date", ["2026-11-12", "2026-11-13"])
@pytest.mark.parametrize("missing_value", ["absent", None])
def test_missing_pageviews_stay_unknown(monkeypatch, missing_date, missing_value):
    daily = copy.deepcopy(DAILY)
    if missing_value == "absent":
        daily[missing_date].pop("nb_pageviews")
    else:
        daily[missing_date]["nb_pageviews"] = None
    fake_api(monkeypatch, daily)
    result = report.organic_traffic_report("7", "https://analytics.example.com", "token", days=2)
    data = result["data"]
    assert data["totals"]["pageviews"] is None
    affected = next(row for row in data["daily_data"] if row["date"] == missing_date)
    assert affected["pageviews"] is None
    assert data["totals"]["actions"] == 210
    assert data["totals"]["visits"] == 100


def test_zero_pageviews_are_not_replaced_by_actions(monkeypatch):
    daily = copy.deepcopy(DAILY)
    for row in daily.values():
        row["nb_pageviews"] = 0
    fake_api(monkeypatch, daily)
    result = report.organic_traffic_report("7", "https://analytics.example.com", "token", days=2)
    assert result["data"]["totals"]["pageviews"] == 0
    assert result["data"]["totals"]["actions"] == 210


def test_combined_metrics_failure_is_reported(monkeypatch):
    def request(url, token, params):
        if params["method"] == "API.get":
            return report._envelope("error", None, "Metrics query unavailable", method="API.get")
        return report._envelope("success", {})

    monkeypatch.setattr(report, "_request", request)
    result = report.organic_traffic_report("7", "https://analytics.example.com", "token", days=2)
    assert result["status"] == "error"
    assert result["error"] == "Metrics query unavailable"
