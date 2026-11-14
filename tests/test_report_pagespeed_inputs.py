"""PageSpeed's native CLI envelope must reach every report consumer."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_report  # noqa: E402

MOBILE = {"lighthouse_scores": {"performance": 45, "accessibility": 91,
                                 "best-practices": 83, "seo": 94}}


def _input(shape):
    if shape == "flat":
        return MOBILE
    native = {"url": "https://example.com/", "psi": {"mobile": MOBILE}}
    return {"psi": native} if shape == "combined" else native


@pytest.mark.parametrize("shape", ["flat", "native", "combined"])
def test_html_consumers_receive_mobile_metrics(tmp_path, monkeypatch, shape):
    received = []
    monkeypatch.setattr(google_report, "chart_lighthouse_gauges",
                        lambda data, path: received.append(data) or "")
    monkeypatch.setattr(google_report, "chart_cwv_distributions", lambda *args: "")
    data = _input(shape)
    result = google_report.generate_report("cwv-audit", data, "example.com", tmp_path, "html")
    assert result["error"] is None
    assert received == [MOBILE]
    html = Path(result["files"][0]).read_text(encoding="utf-8")
    assert "45/100" in html
    summary = google_report._build_executive_summary("example.com", "today", data, "cwv-audit")
    assert "45/100" in summary
    section, _ = google_report._build_cwv_section(data, {}, {})
    assert "45/100" in section


@pytest.mark.parametrize("shape", ["flat", "native", "combined"])
def test_xlsx_keeps_all_lighthouse_categories(tmp_path, shape):
    openpyxl = pytest.importorskip("openpyxl")
    path = google_report.generate_xlsx(_input(shape), "example.com", "cwv-audit", tmp_path)
    rows = list(openpyxl.load_workbook(path)["Summary"].values)
    scores = {row[0]: row[1] for row in rows if row[0] in {
        "Performance", "Accessibility", "Best Practices", "Seo",
    }}
    assert scores == {"Performance": 45, "Accessibility": 91, "Best Practices": 83, "Seo": 94}
