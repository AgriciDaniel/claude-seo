"""Full audit report generation from non-Google audit data."""

from __future__ import annotations

import builtins
import os
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import google_report  # noqa: E402


def test_module_import_is_safe_without_native_report_dependencies() -> None:
    real_import = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"matplotlib", "weasyprint"}:
            raise ImportError(f"{name} unavailable")
        return real_import(name, *args, **kwargs)

    with patch.object(builtins, "__import__", side_effect=unavailable):
        namespace = runpy.run_path(str(Path(google_report.__file__)))

    assert namespace["plt"] is None
    assert namespace["HTML"] is None


def test_html_report_without_chart_data_does_not_require_native_report_dependencies(
    tmp_path: Path,
) -> None:
    with patch.object(google_report, "plt", None), \
         patch.object(google_report, "np", None), \
         patch.object(google_report, "HTML", None), \
         patch.object(google_report, "_CHART_IMPORT_ERROR", ImportError("missing")):
        result = google_report.generate_report(
            "full",
            {"summary": {"health_score": 80}},
            "example.com",
            tmp_path,
            output_format="html",
        )

    assert result["error"] is None
    assert Path(result["files"][0]).is_file()


def test_chart_report_returns_dependency_error_at_runtime(tmp_path: Path) -> None:
    with patch.object(google_report, "plt", None), \
         patch.object(google_report, "np", None), \
         patch.object(google_report, "_CHART_IMPORT_ERROR", ImportError("missing")):
        result = google_report.generate_report(
            "cwv-audit",
            {"lighthouse_scores": {"performance": 90}},
            "example.com",
            tmp_path,
            output_format="html",
        )

    assert result["files"] == []
    assert "matplotlib and numpy are required" in result["error"]


def test_pdf_report_returns_dependency_error_at_runtime(tmp_path: Path) -> None:
    with patch.object(google_report, "HTML", None), \
         patch.object(google_report, "_PDF_IMPORT_ERROR", ImportError("missing")):
        result = google_report.generate_report(
            "full",
            {"summary": {"health_score": 80}},
            "example.com",
            tmp_path,
            output_format="pdf",
        )

    assert result["files"] == []
    assert "weasyprint is required" in result["error"]


def test_full_audit_html_includes_summary_categories_and_roadmap(tmp_path: Path) -> None:
    data = {
        "summary": {
            "health_score": 82,
            "business_type": "SaaS",
            "top_findings": [
                {"title": "Canonical mismatch", "severity": "Critical"},
                "Thin service pages",
            ],
            "quick_wins": ["Add missing meta descriptions"],
        },
        "categories": [
            {
                "name": "Technical SEO",
                "score": 74,
                "what_works": ["HTTPS is enabled", "Robots.txt is reachable"],
                "findings": [
                    {
                        "title": "Canonical mismatch",
                        "severity": "Critical",
                        "description": "Homepage canonical points to a staging URL.",
                        "recommendation": "Set canonical to the production HTTPS URL.",
                    }
                ],
            },
            {
                "name": "Content Quality",
                "score": 68,
                "what_works": ["Clear product positioning"],
                "findings": [
                    {
                        "title": "Thin comparison pages",
                        "severity": "High",
                        "description": "Several pages have fewer than 300 words.",
                    }
                ],
            },
        ],
        "action_plan": {
            "phases": [
                {
                    "name": "Phase 1: Indexing Fixes",
                    "timeframe": "Week 1",
                    "items": ["Fix canonical mismatch", "Resubmit sitemap"],
                },
                {
                    "name": "Phase 2: Content Expansion",
                    "timeframe": "Weeks 2-3",
                    "items": ["Expand comparison page copy"],
                },
            ]
        },
    }

    result = google_report.generate_report(
        "full",
        data,
        "example.com",
        tmp_path,
        output_format="html",
    )

    assert result["error"] is None
    html_path = Path(result["files"][0])
    html = html_path.read_text(encoding="utf-8")
    assert "Executive Summary" in html
    assert "SaaS" in html
    assert "Technical SEO" in html
    assert "What Works" in html
    assert "Canonical mismatch" in html
    assert "Action Plan" in html
    assert "Phase 1: Indexing Fixes" in html
    assert "Content Quality" in html


# --- unsevered ("Info"-prefix) findings -------------------------------------
#
# summary.top_findings and category.findings are documented as plain arrays
# (seo-audit/SKILL.md), so the common case is a list of strings. Both
# _build_executive_summary and _build_full_audit_categories must render a
# plain-string finding without inventing an "Info" severity, while a dict
# finding that carries an explicit severity keeps its prefix/badge.


def test_executive_summary_plain_string_finding_has_no_info_prefix() -> None:
    data = {
        "summary": {
            "health_score": 70,
            "top_findings": ["Thin service pages"],
        }
    }

    html = google_report._build_executive_summary("example.com", "2026-01-01", data, "full")

    assert "Thin service pages" in html
    assert "Info:" not in html


def test_executive_summary_dict_finding_keeps_explicit_severity() -> None:
    data = {
        "summary": {
            "health_score": 70,
            "top_findings": [{"title": "Canonical mismatch", "severity": "Critical"}],
        }
    }

    html = google_report._build_executive_summary("example.com", "2026-01-01", data, "full")

    assert "<strong>Critical:</strong> Canonical mismatch" in html


def test_full_audit_categories_plain_string_finding_has_no_info_badge() -> None:
    data = {
        "categories": [
            {
                "name": "Technical SEO",
                "findings": ["Thin service pages"],
            }
        ]
    }

    html = google_report._build_full_audit_categories(data)

    assert "<h4>Thin service pages</h4>" in html
    assert "Info" not in html


def test_full_audit_categories_dict_finding_keeps_explicit_severity() -> None:
    data = {
        "categories": [
            {
                "name": "Technical SEO",
                "findings": [{"title": "Canonical mismatch", "severity": "Critical"}],
            }
        ]
    }

    html = google_report._build_full_audit_categories(data)

    assert '<h4>Canonical mismatch <span class="status-warn">Critical</span></h4>' in html


def test_cwv_trend_table_renders_zero_baseline_change_as_not_available() -> None:
    """crux_history reports change_pct None for a rise from zero (PR #393)."""
    pytest.importorskip("requests")
    import crux_history

    trends = crux_history.detect_trends({
        "cumulative_layout_shift": {
            "p75_values": [0] * 4 + [0.2] * 4, "label": "CLS", "unit": "",
        },
        "largest_contentful_paint": {
            "p75_values": [2000] * 4 + [3000] * 4, "label": "LCP", "unit": "ms",
        },
    })
    assert trends["cumulative_layout_shift"]["change_pct"] is None

    html, _ = google_report._build_cwv_section({}, {}, {}, history_data={"trends": trends})

    assert '<td class="status-fail">DEGRADING</td>\n      <td>n/a</td>' in html
    assert "<td>+50.0%</td>" in html
    assert "None" not in html


def test_pdf_dependency_error_names_missing_system_libraries() -> None:
    with patch.object(google_report, "_PDF_IMPORT_ERROR", OSError("cannot load library 'libgobject-2.0-0'")), \
         patch.object(google_report.sys, "platform", "darwin"):
        message = google_report._pdf_dependency_error()
    assert "brew install pango" in message and "libgobject" in message
    with patch.object(google_report, "_PDF_IMPORT_ERROR", ImportError("No module named 'weasyprint'")):
        assert "requirements.txt" in google_report._pdf_dependency_error()


def test_pdf_review_passes_without_pypdf(tmp_path: Path) -> None:
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    html = '<div class="section">' + "Enough real section text to pass the thin check. " * 3 + "</div>"
    with patch.dict("sys.modules", {"pypdf": None}):
        review = google_report._review_pdf(str(pdf), html)
    assert review["status"] == "PASS"
    assert review["issues"] == [] and "pypdf" in review["notes"][0]


def test_full_audit_is_not_branded_as_google_report(tmp_path: Path) -> None:
    audit = google_report.generate_report(
        "full", {"summary": {"health_score": 70}}, "example.com", tmp_path, output_format="html")
    path = Path(audit["files"][0])
    assert path.name == "SEO-Audit-Report-example.com-full.html"
    assert "example.com SEO Audit Report" in path.read_text(encoding="utf-8")

    cwv = google_report.generate_report("cwv-audit", {}, "example.com", tmp_path, output_format="html")
    assert Path(cwv["files"][0]).name.startswith("Google-SEO-Report-")
