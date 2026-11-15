"""Native PageSpeed scores are already percentages when they reach XLSX."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_report  # noqa: E402
import pagespeed_check  # noqa: E402


def _native_result(monkeypatch, score):
    response = pagespeed_check.requests.Response()
    response.status_code = 200
    response._content = json.dumps({
        "lighthouseResult": {
            "categories": {category: {"score": score / 100} for category in
                           ("performance", "accessibility", "best-practices", "seo")},
            "audits": {},
        },
    }).encode()
    monkeypatch.setattr(pagespeed_check.requests, "get", lambda *args, **kwargs: response)
    monkeypatch.setattr(pagespeed_check, "validate_url", lambda url: True)
    result = pagespeed_check.run_pagespeed("https://example.com/", strategy="mobile")
    assert result["error"] is None
    assert set(result["lighthouse_scores"].values()) == {score}
    return result


def _score_cells(path):
    workbook = openpyxl.load_workbook(path)
    return {
        row[0].value: row[1] for row in workbook["Summary"].iter_rows()
        if row[0].value in {"Performance", "Accessibility", "Best Practices", "Seo"}
    }


@pytest.mark.parametrize("shape", ["flat", "native", "combined"])
def test_one_point_native_scores_stay_one_and_fail_colored(monkeypatch, tmp_path, shape):
    mobile = _native_result(monkeypatch, 1)
    native = {"url": "https://example.com/", "psi": {"mobile": mobile}}
    data = mobile if shape == "flat" else native if shape == "native" else {"psi": native}
    path = google_report.generate_xlsx(data, "example.com", "cwv-audit", tmp_path)
    cells = _score_cells(path)
    assert len(cells) == 4
    for cell in cells.values():
        assert cell.value == 1
        assert cell.data_type == "n"
        assert cell.fill.fgColor.rgb[-6:] == "F8D7DA"
    html = google_report._build_executive_summary("example.com", "today", data, "cwv-audit")
    assert "1/100" in html


@pytest.mark.parametrize("score,color", [
    (0, "F8D7DA"), (49, "F8D7DA"), (50, "FFF3CD"), (89, "FFF3CD"),
    (90, "D4EDDA"), (100, "D4EDDA"),
])
def test_native_score_thresholds_are_unchanged(monkeypatch, tmp_path, score, color):
    path = google_report.generate_xlsx(
        _native_result(monkeypatch, score), "example.com", "cwv-audit", tmp_path,
    )
    for cell in _score_cells(path).values():
        assert cell.value == score
        assert cell.fill.fgColor.rgb[-6:] == color


@pytest.mark.parametrize("legacy,expected", [(0, 0), (0.42, 42), (1.0, 100), (91, 91)])
def test_unmarked_legacy_fractional_input_keeps_existing_scale(tmp_path, legacy, expected):
    data = {"psi": {"lighthouse_scores": {"performance": legacy}}}
    path = google_report.generate_xlsx(data, "example.com", "cwv-audit", tmp_path)
    assert _score_cells(path)["Performance"].value == expected


def test_desktop_native_result_is_also_a_percentage(tmp_path):
    data = {"strategy": "desktop", "lighthouse_scores": {"performance": 1}}
    path = google_report.generate_xlsx(data, "example.com", "cwv-audit", tmp_path)
    assert _score_cells(path)["Performance"].value == 1
