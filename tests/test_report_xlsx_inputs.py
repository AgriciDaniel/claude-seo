"""XLSX exports accept the same script outputs as the HTML reports."""
import sys
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_report  # noqa: E402


@pytest.mark.parametrize("wrapped", [False, True])
def test_normalized_gsc_queries_keep_their_values(tmp_path, wrapped):
    gsc = {"property": "sc-domain:example.com", "row_count": 1, "rows": [
        {"keys": ["https://example.com/", "test query"], "query": "test query",
         "page": "https://example.com/", "clicks": 3, "impressions": 20,
         "ctr": 15.0, "position": 2.4},
    ]}
    data = {"gsc": gsc} if wrapped else gsc
    path = google_report.generate_xlsx(data, "example.com", "gsc-performance", tmp_path)
    workbook = openpyxl.load_workbook(path)
    assert list(workbook["Queries"].values)[1] == ("test query", 3, 20, "15.00%", 2.4)


@pytest.mark.parametrize("wrapped", [False, True])
def test_normalized_inspection_rows_are_exported(tmp_path, wrapped):
    inspection = {"total": 2, "results": [
        {"url": "https://example.com/", "verdict": "PASS", "error": None,
         "index_status": {"coverage_state": "Submitted and indexed",
                          "indexing_state": "INDEXING_ALLOWED", "crawled_as": "MOBILE",
                          "last_crawl_time": "2026-11-01T12:00:00Z"}},
        {"url": "https://example.com/two", "verdict": None, "index_status": None,
         "error": "Quota exceeded"},
    ]}
    data = {"inspection": inspection} if wrapped else inspection
    path = google_report.generate_xlsx(data, "example.com", "indexation", tmp_path)
    rows = list(openpyxl.load_workbook(path)["Indexation"].values)
    assert rows[1] == ("https://example.com/", "PASS", "Submitted and indexed",
                       "INDEXING_ALLOWED", "MOBILE", "2026-11-01T12:00:00Z")
    assert rows[2][:3] == ("https://example.com/two", "ERROR", "Quota exceeded")


def test_raw_api_rows_remain_supported(tmp_path):
    data = {
        "gsc": {"rows": [{"keys": ["raw query"], "ctr": 0.15}]},
        "inspection": {"results": [{"inspectionResult": {
            "inspectedUrl": "https://example.com/",
            "indexStatusResult": {"verdict": "PASS", "coverageState": "Indexed"},
        }}]},
    }
    path = google_report.generate_xlsx(data, "example.com", "full", tmp_path)
    workbook = openpyxl.load_workbook(path)
    assert workbook["Queries"]["D2"].value == "15.00%"
    assert workbook["Indexation"]["B2"].value == "PASS"
    assert workbook["Indexation"]["C2"].value == "Indexed"
