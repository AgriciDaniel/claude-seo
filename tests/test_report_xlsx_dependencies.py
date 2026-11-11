"""Workbook-only reports do not require the chart or PDF renderers."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_report  # noqa: E402


def test_xlsx_without_chart_or_pdf_dependencies(tmp_path, monkeypatch):
    openpyxl = pytest.importorskip("openpyxl")
    monkeypatch.setattr(google_report, "plt", None)
    monkeypatch.setattr(google_report, "HTML", None)
    data = {"gsc": {"rows": [
        {"keys": ["example query"], "clicks": 12, "impressions": 80,
         "ctr": 0.15, "position": 3.2},
    ]}}

    result = google_report.generate_report(
        "gsc-performance", data, "example.com", tmp_path / "output", "xlsx",
    )

    assert result["error"] is None
    assert len(result["files"]) == 1
    workbook = openpyxl.load_workbook(result["files"][0])
    assert workbook["Queries"]["A2"].value == "example query"
    assert workbook["Queries"]["B2"].value == 12
    assert not (tmp_path / "output" / "charts").exists()


def test_xlsx_reports_a_missing_workbook_dependency(tmp_path, monkeypatch):
    monkeypatch.setattr(google_report, "generate_xlsx", lambda *args: None)
    result = google_report.generate_report("full", {}, "example.com", tmp_path, "xlsx")
    assert result["files"] == []
    assert "openpyxl" in result["error"]
