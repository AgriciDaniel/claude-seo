"""Search Console reports must preserve the producer's incomplete-total status."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_report  # noqa: E402


def _gsc_result():
    return {
        "property": "sc-domain:example.com",
        "date_range": {"start": "2026-11-01", "end": "2026-11-10"},
        "totals": {"clicks": 12, "impressions": 100, "ctr": 12.0, "position": 0},
        "totals_complete": False,
        "totals_source": "partial_row_sum",
        "row_count": 1,
        "rows": [{"query": "example query", "keys": ["example query"], "clicks": 12,
                  "impressions": 100, "ctr": 12.0, "position": 6}],
        "quick_wins": [], "error": None,
        "warnings": ["The dimensionless totals query failed. Reported totals are an "
                     "incomplete sum of returned rows and must not be presented as site-wide totals."],
    }


def _render(tmp_path, monkeypatch, gsc, *, report_type="gsc-performance", wrapped=False):
    monkeypatch.setattr(google_report, "chart_top_queries", lambda *args: "")
    data = {"gsc": gsc} if wrapped else gsc
    result = google_report.generate_report(report_type, data, "example.com", tmp_path, "html")
    assert result["error"] is None
    return Path(result["files"][0]).read_text(encoding="utf-8")


@pytest.mark.parametrize("report_type,wrapped", [
    ("gsc-performance", False), ("gsc-performance", True), ("full", True),
])
def test_partial_totals_are_labelled_in_every_report_surface(
    tmp_path, monkeypatch, report_type, wrapped,
):
    gsc = _gsc_result()
    original = copy.deepcopy(gsc)
    html = _render(tmp_path, monkeypatch, gsc, report_type=report_type, wrapped=wrapped)

    assert "Total Clicks" not in html
    assert "Total Impressions" not in html
    assert "total impressions during this period" not in html
    assert "Clicks in Returned Rows" in html
    assert "Impressions in Returned Rows" in html
    assert "CTR in Returned Rows" in html
    assert "Site-wide totals are unavailable" in html
    assert "example query" in html
    assert gsc == original


@pytest.mark.parametrize("metadata", [
    {"totals_complete": False}, {"totals_source": "partial_row_sum"},
])
def test_either_incomplete_metadata_field_is_respected(tmp_path, monkeypatch, metadata):
    gsc = _gsc_result()
    del gsc["totals_complete"]
    del gsc["totals_source"]
    gsc.update(metadata)
    gsc["warnings"] = []
    html = _render(tmp_path, monkeypatch, gsc)
    assert "Clicks in Returned Rows" in html
    assert "Site-wide totals are unavailable" in html


@pytest.mark.parametrize("legacy", [False, True])
def test_complete_and_legacy_totals_keep_their_labels(tmp_path, monkeypatch, legacy):
    gsc = _gsc_result()
    gsc.update(totals_complete=True, totals_source="dimensionless_aggregate", warnings=[])
    if legacy:
        del gsc["totals_complete"]
        del gsc["totals_source"]
    html = _render(tmp_path, monkeypatch, gsc, wrapped=True)
    assert "Total Clicks" in html
    assert "Total Impressions" in html
    assert "Average CTR" in html
    assert "Clicks in Returned Rows" not in html
    assert "Site-wide totals are unavailable" not in html


def test_successful_zero_totals_are_not_marked_unavailable(tmp_path, monkeypatch):
    gsc = _gsc_result()
    gsc.update(totals={"clicks": 0, "impressions": 0, "ctr": 0, "position": 0},
               totals_complete=True, totals_source="dimensionless_aggregate",
               rows=[], row_count=0, warnings=[])
    html = _render(tmp_path, monkeypatch, gsc, wrapped=True)
    assert "Total Clicks" in html
    assert "Site-wide totals are unavailable" not in html


def test_failed_aggregate_query_remains_partial_in_generated_report(tmp_path, monkeypatch):
    pytest.importorskip("googleapiclient")
    import gsc_query

    service = Mock()

    def query(*, siteUrl, body):
        if not body["dimensions"]:
            return Mock(execute=Mock(side_effect=RuntimeError("aggregate unavailable")))
        return Mock(execute=Mock(return_value={"rows": [
            {"keys": ["example query"], "clicks": 12, "impressions": 100,
             "ctr": 0.12, "position": 6},
        ]}))

    service.searchanalytics.return_value.query.side_effect = query
    monkeypatch.setattr(gsc_query, "_build_gsc_service", lambda: service)
    gsc = gsc_query.query_search_analytics(
        "sc-domain:example.com", start_date="2026-11-01", end_date="2026-11-10",
        dimensions=["query"],
    )
    assert gsc["totals_complete"] is False
    assert gsc["totals_source"] == "partial_row_sum"

    html = _render(tmp_path, monkeypatch, gsc, wrapped=True)

    assert "Total Clicks" not in html
    assert "Site-wide totals are unavailable" in html
    assert "example query" in html
