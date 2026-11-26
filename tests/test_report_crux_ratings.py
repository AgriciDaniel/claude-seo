"""Excel field ratings must retain the values produced by query_crux()."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")
pytest.importorskip("requests")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_report  # noqa: E402
import pagespeed_check  # noqa: E402


def _field_rows(path):
    workbook = openpyxl.load_workbook(path)
    return {
        row[0].value: (row[1].value, row[2].value)
        for row in workbook["Summary"].iter_rows()
        if row[0].value in pagespeed_check.CWV_THRESHOLDS
    }


@pytest.mark.parametrize("report_type", ["cwv-audit", "full"])
def test_native_crux_percentiles_keep_their_ratings(monkeypatch, tmp_path, report_type):
    percentiles = {
        "largest_contentful_paint": 2400,
        "interaction_to_next_paint": 300,
        "cumulative_layout_shift": "0.3",
    }
    response = pagespeed_check.requests.Response()
    response.status_code = 200
    response._content = json.dumps({
        "record": {"metrics": {
            metric: {"percentiles": {"p75": value}} for metric, value in percentiles.items()
        }},
    }).encode()
    monkeypatch.setattr(pagespeed_check.requests, "post", lambda *args, **kwargs: response)
    monkeypatch.setattr(pagespeed_check, "validate_url", lambda value: True)
    crux = pagespeed_check.query_crux("https://example.com/", "fixture-key")
    assert crux["error"] is None
    path = google_report.generate_xlsx({"crux": crux}, "example.com", report_type, tmp_path)
    assert _field_rows(path) == {
        "largest_contentful_paint": (2400, "good"),
        "interaction_to_next_paint": (300, "needs-improvement"),
        "cumulative_layout_shift": (0.3, "poor"),
    }


def test_legacy_category_rating_is_still_exported(tmp_path):
    crux = {"metrics": {"largest_contentful_paint": {
        "percentile_p75": 3100, "category": "AVERAGE",
    }}}
    path = google_report.generate_xlsx({"crux": crux}, "example.com", "cwv-audit", tmp_path)
    assert _field_rows(path) == {"largest_contentful_paint": (3100, "AVERAGE")}


def test_native_rating_takes_precedence_over_a_legacy_label(tmp_path):
    crux = {"metrics": {"cumulative_layout_shift": {
        "p75": 0.3, "rating": "poor", "category": "FAST",
    }}}
    path = google_report.generate_xlsx({"crux": crux}, "example.com", "cwv-audit", tmp_path)
    assert _field_rows(path) == {"cumulative_layout_shift": (0.3, "poor")}
