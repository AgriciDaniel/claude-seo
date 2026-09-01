"""Full audit report generation from non-Google audit data."""

from __future__ import annotations

import builtins
import os
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

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
