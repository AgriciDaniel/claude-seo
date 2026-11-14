"""URL Inspection API failures retain null index_status in the CLI output."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_report  # noqa: E402


def test_failed_inspection_is_rendered_instead_of_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr(google_report, "chart_index_status", lambda *args: "")
    data = {
        "total": 2, "summary": {"pass": 1, "error": 1},
        "results": [
            {"url": "https://example.com/one", "verdict": "PASS", "error": None,
             "index_status": {"coverage_state": "Submitted and indexed", "last_crawl_time": "2026-11-01T12:00:00Z"}},
            {"url": "https://example.com/two", "verdict": None, "index_status": None,
             "error": "URL Inspection quota exceeded"},
        ],
    }
    result = google_report.generate_report("indexation", data, "example.com", tmp_path, "html")
    assert result["error"] is None
    html = Path(result["files"][0]).read_text(encoding="utf-8")
    assert "Submitted and indexed" in html
    assert "URL Inspection quota exceeded" in html
    assert ">ERROR</td>" in html
