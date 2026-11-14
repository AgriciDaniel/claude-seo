"""Unavailable PDF support must not skip an independent XLSX export."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import google_report as report  # noqa: E402


@pytest.mark.parametrize("failure", ["missing", "render_error"])
def test_all_preserves_html_and_workbook_when_pdf_is_unavailable(tmp_path, monkeypatch, failure):
    openpyxl = pytest.importorskip("openpyxl")
    monkeypatch.setattr(report, "chart_index_status", lambda *_: None)

    class BrokenPDF:
        def __init__(self, **_kwargs):
            pass

        def write_pdf(self, _path):
            raise RuntimeError("PDF renderer unavailable")

    monkeypatch.setattr(report, "HTML", None if failure == "missing" else BrokenPDF)
    result = report.generate_report("indexation", {}, "example.com", tmp_path, "all")

    paths = [Path(path) for path in result["files"]]
    assert {path.suffix for path in paths} == {".html", ".xlsx"}
    assert result["error"]
    assert all(path.is_file() for path in paths)
    workbook = openpyxl.load_workbook(next(path for path in paths if path.suffix == ".xlsx"))
    try:
        assert "Summary" in workbook.sheetnames
    finally:
        workbook.close()


def test_both_keeps_pdf_error_and_does_not_generate_workbook(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "chart_index_status", lambda *_: None)
    monkeypatch.setattr(report, "HTML", None)
    result = report.generate_report("indexation", {}, "example.com", tmp_path, "both")
    assert len(result["files"]) == 1
    assert Path(result["files"][0]).suffix == ".html"
    assert "weasyprint" in result["error"]
