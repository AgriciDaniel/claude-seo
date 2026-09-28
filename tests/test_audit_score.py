"""Coverage-aware health score, verification gate, and their report rendering."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = str(REPO_ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import audit_score  # noqa: E402
import google_report  # noqa: E402


def _cat(name, score, measured=None, findings=None):
    category = {"name": name, "score": score, "findings": findings or []}
    if measured is not None:
        category["measured"] = measured
    return category


def _finding(title, severity, status=None, evidence=""):
    finding = {"title": title, "severity": severity, "source": "seo-technical"}
    if status:
        finding["verification"] = {"status": status, "method": "direct fetch", "evidence": evidence}
    return finding


def test_weights_match_skill_table() -> None:
    text = (REPO_ROOT / "skills" / "seo-audit" / "SKILL.md").read_text(encoding="utf-8")
    table = text[text.index("## Scoring Weights"):text.index("## Verification Pass")]
    rows = dict(
        (name.strip().lower(), int(weight))
        for name, weight in re.findall(r"^\| ([^|]+?) \| (\d+)% \|$", table, re.MULTILINE)
    )
    assert rows == audit_score.WEIGHTS
    assert sum(audit_score.WEIGHTS.values()) == 100


def test_full_coverage_is_plain_weighted_mean() -> None:
    data = {"categories": [_cat(name, 50) for name in audit_score.WEIGHTS]}
    result = audit_score.compute(data)
    assert result["health_score"] == 50
    assert result["coverage"] == 1.0
    assert result["unmeasured"] == []


def test_unmeasured_categories_are_excluded_not_zeroed() -> None:
    data = {"categories": [
        _cat("Technical SEO", 80),
        _cat("Content Quality", 80),
        _cat("On-Page SEO", 80),
        _cat("Schema", 80),
        _cat("Performance (CWV)", None, measured=False),
        _cat("AI Search Readiness", 0, measured=False),
        _cat("Images", None),
    ]}
    result = audit_score.compute(data)
    # 22 + 23 + 20 + 10 = 75% coverage, all at 80 -> 80, not dragged down by zeros.
    assert result["coverage"] == 0.75
    assert result["health_score"] == 80
    assert result["unmeasured"] == ["performance (cwv)", "ai search readiness", "images"]


def test_low_coverage_withholds_the_score() -> None:
    data = {"categories": [_cat("Technical SEO", 90), _cat("Schema", 85), _cat("Images", 70)]}
    result = audit_score.compute(data)
    assert result["health_score"] is None
    assert "37%" in result["withheld_reason"]


def test_no_categories_withholds_the_score() -> None:
    assert audit_score.compute({})["health_score"] is None


@pytest.mark.parametrize("bad", [True, "80", float("nan"), -1, 101, None])
def test_non_numeric_or_out_of_range_scores_are_unmeasured(bad) -> None:
    result = audit_score.compute({"categories": [_cat("Technical SEO", bad)]})
    assert "technical seo" in result["unmeasured"]


def test_unknown_category_names_are_reported_not_scored() -> None:
    result = audit_score.compute({"categories": [_cat("Backlinks", 10)]})
    assert result["unknown_categories"] == ["Backlinks"]
    assert result["health_score"] is None


def test_gate_flags_only_unverified_critical_and_high() -> None:
    data = {"categories": [_cat("Technical SEO", 70, findings=[
        _finding("A", "Critical", "verified"),
        _finding("B", "High"),
        _finding("C", "High", "unverified"),
        _finding("D", "Medium"),
        _finding("E", "Critical", "bogus-status"),
    ])]}
    titles = [f["title"] for f in audit_score.compute(data)["unverified_high_severity"]]
    assert titles == ["B", "C", "E"]


def test_write_moves_disproved_findings_to_corrections(tmp_path: Path) -> None:
    path = tmp_path / "audit-data.json"
    data = {
        "summary": {"health_score": 99},
        "categories": [
            _cat("Technical SEO", 60, findings=[
                _finding("Example claim A", "High", "disproved", "re-fetch contradicted it"),
                _finding("Example claim B", "Critical", "verified"),
            ]),
            _cat("Content Quality", None, measured=False),
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    assert audit_score.main([str(path), "--write", "--json"]) == 0
    written = json.loads(path.read_text(encoding="utf-8"))

    assert [f["title"] for f in written["categories"][0]["findings"]] == ["Example claim B"]
    assert written["corrections"] == [{
        "category": "Technical SEO",
        "claim": "Example claim A",
        "source": "seo-technical",
        "disproof": "re-fetch contradicted it",
    }]
    # 22% coverage: the stale hand-entered 99 is removed, not kept.
    assert "health_score" not in written["summary"]
    assert "below the 70% minimum" in written["summary"]["health_score_withheld"]
    assert written["summary"]["score_coverage"] == 0.22


def test_strict_exits_2_on_unverified_high(tmp_path: Path, capsys) -> None:
    path = tmp_path / "audit-data.json"
    path.write_text(json.dumps({"categories": [_cat("Technical SEO", 60, findings=[
        _finding("Unchecked", "High"),
    ])]}), encoding="utf-8")
    assert audit_score.main([str(path), "--strict"]) == 2
    assert "Unverified Critical/High findings: 1" in capsys.readouterr().out


def test_unreadable_input_is_an_error_not_a_traceback(tmp_path: Path) -> None:
    path = tmp_path / "audit-data.json"
    path.write_text("[1, 2", encoding="utf-8")
    assert audit_score.main([str(path)]) == 1
    path.write_text("[]", encoding="utf-8")
    assert audit_score.main([str(path)]) == 1


def test_script_is_allowlisted_for_the_runtime() -> None:
    import runtime

    assert "audit_score.py" in runtime.ALLOWED_CORE_SCRIPTS


# ── Report rendering ─────────────────────────────────────────────────────────


def _html(tmp_path: Path, data: dict) -> str:
    result = google_report.generate_report("full", data, "example.com", tmp_path, output_format="html")
    assert result["error"] is None
    return Path(result["files"][0]).read_text(encoding="utf-8")


def test_report_shows_coverage_and_unmeasured_categories(tmp_path: Path) -> None:
    html = _html(tmp_path, {
        "summary": {"health_score": 72, "score_coverage": 0.75,
                    "unmeasured_categories": ["performance (cwv)", "images"]},
        "categories": [_cat("Technical SEO", 72), _cat("Images", None, measured=False)],
    })
    assert "SEO Health Score (75% of categories measured)" in html
    assert "Not measured: performance (cwv), images." in html
    assert "Not measured</span>" in html


def test_report_explains_a_withheld_score(tmp_path: Path) -> None:
    html = _html(tmp_path, {
        "summary": {"health_score_withheld": "measured categories cover 42% of the scoring weight",
                    "unmeasured_categories": ["content quality"]},
        "categories": [_cat("Technical SEO", 60)],
    })
    assert "No composite health score issued:" in html
    assert "Not measured: content quality." in html
    assert 'class="score-box"' not in html


def test_report_badges_unverified_findings_only(tmp_path: Path) -> None:
    html = _html(tmp_path, {"categories": [_cat("Technical SEO", 60, findings=[
        _finding("Checked claim", "High", "verified"),
        _finding("Unchecked claim", "High", "unverified"),
    ])]})
    assert html.count('<span class="status-warn">Unverified</span>') == 1
    assert "Unchecked claim" in html.split('Unverified</span>')[0].rsplit("<h4>", 1)[-1]


def test_review_pdf_fails_on_unreadable_file(tmp_path: Path) -> None:
    pytest.importorskip("pypdf")
    bad = tmp_path / "report.pdf"
    bad.write_bytes(b"%PDF-1.7\nnot really a pdf")
    review = google_report._review_pdf(str(bad), "<div class=\"section\">" + "x" * 100 + "</div>")
    assert review["status"].startswith("FAIL")


def test_review_pdf_fails_when_file_is_missing(tmp_path: Path) -> None:
    review = google_report._review_pdf(str(tmp_path / "absent.pdf"), "")
    assert review["status"].startswith("FAIL")
    assert os.path.exists(tmp_path / "absent.pdf") is False


@pytest.mark.parametrize("name, bucket", [
    ("Performance (Core Web Vitals)", "performance (cwv)"),
    ("AI Search Readiness (GEO)", "ai search readiness"),
    ("Sitemap & Indexation", "technical seo"),
    ("Internal Linking & Crawl Architecture", "technical seo"),
    ("Schema & Structured Data", "schema / structured data"),
    ("Image Optimization", "images"),
    ("On-Page SEO", "on-page seo"),
    ("Backlinks", None),
])
def test_category_names_map_by_keyword(name, bucket) -> None:
    assert audit_score.canonical_category(name) == bucket


def test_explicit_scoring_category_overrides_keywords() -> None:
    data = {"categories": [
        {"name": "Content Architecture", "score": 40, "scoring_category": "On-Page SEO"},
    ]}
    result = audit_score.compute(data)
    assert result["measured"] == {"on-page seo": 40.0}
    assert result["category_mapping"] == {"Content Architecture": "on-page seo"}


def test_categories_sharing_a_bucket_are_averaged() -> None:
    data = {"categories": [_cat("Sitemap & Indexation", 60), _cat("Crawlability", 25)]}
    assert audit_score.compute(data)["measured"] == {"technical seo": 42.5}
