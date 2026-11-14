"""Report generation survives awkward but plausible API data.

- A dollar sign in a search query is chart text, not math. matplotlib reads
  text between two dollar signs as math and raises on what it cannot parse,
  which used to stop the whole report.
- Chart labels are cut to a sane length and lose characters that cannot be
  drawn, and a chart that still fails is left out instead of ending the run.
- Workbook cells accept lone surrogates, non-characters and numbers that a
  numeric cell cannot hold, and a workbook failure keeps the other formats.
- Null score and count fields do not crash the HTML sections.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("matplotlib")
import google_report  # noqa: E402

DOLLAR_QUERIES = [
    "a$$ap rocky tickets",
    "ca$$h app",
    "$$",
    "$\\frac{$",
    "$100 vs $200 laptop",
    "price in $ and $ signs",
    "50% off $_$",
    "back\\$slash $x^2$",
]


def _gsc(query) -> dict:
    return {
        "property": "sc-domain:example.com",
        "totals": {"clicks": 1, "impressions": 500, "ctr": 0.2},
        "rows": [{"query": query, "clicks": 1, "impressions": 500, "ctr": 0.2, "position": 6.0}],
    }


def _png_size(path: Path) -> tuple[int, int]:
    with open(path, "rb") as fh:
        head = fh.read(24)
    return struct.unpack(">II", head[16:24])


def _pixels(text: str, **kwargs) -> bytes:
    fig = google_report.plt.figure(figsize=(4, 1), dpi=50)
    try:
        fig.text(0.02, 0.5, text, **kwargs)
        fig.canvas.draw()
        return bytes(fig.canvas.buffer_rgba())
    finally:
        google_report.plt.close(fig)


# ── 1. Chart text ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", DOLLAR_QUERIES)
def test_dollar_signs_in_a_query_do_not_stop_the_report(tmp_path: Path, query: str) -> None:
    result = google_report.generate_report(
        "gsc-performance", _gsc(query), "example.com", tmp_path, output_format="html",
    )
    assert result["error"] is None
    assert (tmp_path / "charts" / "top_queries.png").is_file()
    assert "top_queries.png" in Path(result["files"][0]).read_text(encoding="utf-8")


@pytest.mark.parametrize("query", DOLLAR_QUERIES)
def test_chart_text_draws_dollar_signs_literally(query: str) -> None:
    """Pixel for pixel the same as the raw text drawn with math parsing off."""
    literal = _pixels(query, parse_math=False)
    assert _pixels(google_report._chart_text(query)) == literal
    assert literal != _pixels("")


def test_chart_text_cuts_long_text_and_drops_undrawable_characters() -> None:
    text = google_report._chart_text("W" * 5000)
    assert len(text) == 60 and text.endswith("...")
    assert google_report._chart_text("$" * 5000, 10) == "\\$" * 7 + "..."
    assert google_report._chart_text("a\ud800b\x00c￾d￿\x1b[31m") == "abcd[31m"
    assert google_report._chart_text("two\nlines\tand  spaces") == "two lines and spaces"
    assert google_report._chart_text(None) == "None"
    assert google_report._chart_text(10 ** 400, 12) == "1" + "0" * 8 + "..."


def test_lone_surrogate_in_a_query_still_draws_the_chart(tmp_path: Path) -> None:
    path = google_report.chart_top_queries(_gsc("caf\ud800e near me"), tmp_path)
    assert path and Path(path).is_file()


def test_lone_surrogate_in_a_query_still_writes_every_format(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    if google_report.HTML is None:
        pytest.skip("weasyprint missing")
    result = google_report.generate_report(
        "gsc-performance", _gsc("caf\ud800e near me"), "example.com", tmp_path, output_format="all",
    )
    assert result["error"] is None
    assert sorted(Path(f).suffix for f in result["files"]) == [".html", ".pdf", ".xlsx"]
    html = next(f for f in result["files"] if f.endswith(".html"))
    assert "caf?e near me" in Path(html).read_text(encoding="utf-8")


def test_long_crux_and_history_labels_keep_charts_small(tmp_path: Path) -> None:
    long = "W" * 2000
    data = {
        "psi": {"lighthouse_scores": {"performance": 40, "accessibility": 80, "best-practices": 70, "seo": 60}},
        "crux": {"metrics": {"largest_contentful_paint": {
            "label": long, "unit": long, "p75": 2400,
            "distribution": {"good": 70, "needs_improvement": 20, "poor": 10},
        }}},
        "crux_history": {
            "collection_periods": [{"last": "2026-01-0%d" % day} for day in range(1, 4)],
            "metrics": {"largest_contentful_paint": {
                "label": long + "$", "unit": long, "p75_values": [2400, 2500, 2300],
                "good_threshold": 2500, "poor_threshold": 4000,
            }},
        },
    }
    result = google_report.generate_report("cwv-audit", data, "example.com", tmp_path, output_format="html")
    assert result["error"] is None
    for name in ("cwv_distributions.png", "cwv_timeline.png"):
        width, height = _png_size(tmp_path / "charts" / name)
        assert width < 4000 and height < 4000, (name, width, height)


def test_a_failing_chart_is_dropped_and_the_report_is_still_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    def broken(data, output_dir):
        google_report.plt.subplots()
        raise ValueError("ParseFatalException\nfake line")

    monkeypatch.setattr(google_report, "chart_top_queries", broken)
    result = google_report.generate_report(
        "gsc-performance", _gsc("plain query"), "example.com", tmp_path, output_format="html",
    )
    err = capsys.readouterr().err
    assert result["error"] is None
    html = Path(result["files"][0]).read_text(encoding="utf-8")
    assert "top_queries.png" not in html and "plain query" in html
    warning = [line for line in err.splitlines() if "skipped" in line]
    assert len(warning) == 1 and "ValueError" in warning[0]
    assert "\\nfake line" in warning[0]
    assert google_report.plt.get_fignums() == []


# ── 2. XLSX ──────────────────────────────────────────────────────────────────

def test_xlsx_cells_accept_surrogates_noncharacters_and_odd_numbers(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    google_report._xlsx_append_row(ws, [
        "a\ud800b", "￾", "a￿b", 10 ** 400, -(10 ** 400),
        float("nan"), float("inf"), float("-inf"), 10 ** 15, 2.5, True, "x" * 40000,
    ])
    path = tmp_path / "odd.xlsx"
    wb.save(path)
    row = openpyxl.load_workbook(path).active[1]

    # openpyxl reads an empty text cell back as None.
    assert [c.value for c in row[:3]] == ["ab", None, "ab"]
    assert row[3].value == str(10 ** 400) and row[3].data_type == "s"
    assert row[4].value == str(-(10 ** 400)) and row[4].quotePrefix
    assert [c.value for c in row[5:8]] == ["nan", "inf", "-inf"]
    assert [c.data_type for c in row[5:8]] == ["s", "s", "s"]
    assert [c.value for c in row[8:11]] == [10 ** 15, 2.5, True]
    assert [c.data_type for c in row[8:11]] == ["n", "n", "b"]
    assert len(row[11].value) == 32767


def test_xlsx_report_with_odd_values_is_written(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    rows = [
        {"query": "q\ud800", "clicks": 10 ** 400, "impressions": float("nan"), "ctr": 0.1, "position": 1},
        {"keys": ["￿"], "clicks": float("inf"), "impressions": 2, "ctr": 0.1, "position": 1},
    ]
    path = google_report.generate_xlsx({"gsc": {"rows": rows}}, "example.com", "full", tmp_path)
    ws = openpyxl.load_workbook(path)["Queries"]
    assert ws["A2"].value == "q"
    assert ws["B2"].value == str(10 ** 400) and ws["C2"].value == "nan"
    assert ws["B3"].value == "inf"


def test_a_workbook_failure_keeps_the_other_formats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if google_report.HTML is None:
        pytest.skip("weasyprint missing")

    def broken(*args, **kwargs):
        raise OverflowError("int too large to convert to float")

    monkeypatch.setattr(google_report, "generate_xlsx", broken)
    result = google_report.generate_report(
        "gsc-performance", _gsc("plain query"), "example.com", tmp_path, output_format="all",
    )
    assert sorted(Path(f).suffix for f in result["files"]) == [".html", ".pdf"]
    assert all(Path(f).is_file() for f in result["files"])
    assert result["error"] == "XLSX generation failed: int too large to convert to float"


# ── 3. Null score and count fields ───────────────────────────────────────────

def test_null_scores_and_counts_do_not_crash_the_report(tmp_path: Path) -> None:
    data = {
        "psi": {
            "lighthouse_scores": {"performance": 40, "accessibility": 80, "best-practices": 70, "seo": 60},
            "failed_audits": [
                {"title": "Null audit", "score": None, "display": "n/a"},
                {"title": "Low audit", "score": 0.1, "display": "slow"},
            ],
            "accessibility_audits": [{"title": "Null a11y", "score": None}],
        },
        "gsc": {
            "property": "sc-domain:example.com",
            "totals": {"clicks": None, "impressions": None, "ctr": 0},
            "rows": [{"query": "plain query", "clicks": 1, "impressions": 500, "ctr": 0.2, "position": 6.0}],
            "quick_wins": [{"query": "null win", "clicks": 1, "impressions": None, "position": None}],
        },
    }
    result = google_report.generate_report("full", data, "example.com", tmp_path, output_format="html")
    assert result["error"] is None
    html = Path(result["files"][0]).read_text(encoding="utf-8")
    for needle in ("Null audit", "Low audit", "Null a11y", "null win"):
        assert needle in html

    out = tmp_path / "gsc"
    result = google_report.generate_report("gsc-performance", data["gsc"], "example.com", out, output_format="html")
    assert result["error"] is None
