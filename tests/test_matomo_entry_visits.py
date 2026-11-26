"""Landing-page reports rank session entrances, not all visits to a page."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import matomo_report  # noqa: E402


@pytest.mark.parametrize("reporter,key", [
    (matomo_report.organic_traffic_report, "top_pages"),
    (matomo_report.top_pages_report, "pages"),
])
def test_limited_landing_report_ranks_and_counts_entrances(monkeypatch, reporter, key):
    pages = [
        {"label": "/navigation", "nb_visits": 1000, "entry_nb_visits": 10,
         "entry_bounce_count": 5, "entry_nb_actions": 30},
        {"label": "/landing", "nb_visits": 150, "entry_nb_visits": 100,
         "nb_uniq_visitors": 120, "entry_nb_uniq_visitors": 80,
         "entry_bounce_count": 20, "entry_nb_actions": 300},
    ]

    def request(url, token, params, **kwargs):
        assert url == "https://analytics.example.com/"
        assert params["segment"] == "referrerType==search"
        if params["method"] == "API.get":
            # The daily summary: VisitsSummary and Actions metrics in one call.
            assert "nb_pageviews" in params["columns"].split(",")
            data = {"2026-11-01": {"nb_visits": 110, "nb_actions": 330}}
        else:
            assert params["method"] == "Actions.getEntryPageUrls"
            # Apply the requested server-side ordering before the row cap.
            # Re-sorting a wrong subset locally cannot recover the top entrance.
            data = sorted(pages, key=lambda row: row[params["filter_sort_column"]], reverse=True)
            data = data[:int(params["filter_limit"])]
        return {"status": "success", "data": data, "error": None}

    monkeypatch.setattr(matomo_report, "_request", request)

    result = reporter("1", "https://analytics.example.com/", "fixture-token", days=1, limit=1)

    assert result["status"] == "success"
    page = result["data"][key][0]
    assert page["url"] == "/landing"
    assert page["visits"] == 100
    assert page["unique_visitors"] == 80
    assert page["bounce_rate"] == 20.0
    assert page["actions"] == 300


@pytest.mark.parametrize("visitor_key", ["entry_nb_uniq_visitors", "sum_daily_entry_nb_uniq_visitors"])
def test_entry_only_response_keeps_its_visit_count(monkeypatch, visitor_key):
    def request(url, token, params, **kwargs):
        data = {} if params["method"] == "API.get" else [{
            "label": "/landing", "entry_nb_visits": 80, "entry_bounce_count": 8,
            visitor_key: 60,
        }]
        return {"status": "success", "data": data, "error": None}

    monkeypatch.setattr(matomo_report, "_request", request)

    result = matomo_report.top_pages_report("1", "https://analytics.example.com/", "fixture-token")

    assert result["data"]["pages"][0]["visits"] == 80
    assert result["data"]["pages"][0]["unique_visitors"] == 60
    assert result["data"]["pages"][0]["bounce_rate"] == 10.0
