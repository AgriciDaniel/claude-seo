"""SEO Health Score aggregation. The model must not be the calculator.

Called by pytest. Exercises audit_score.score_audit / main and the
google_report partial-score label. Input is a synthetic audit envelope:
categories[].name, categories[].score (0-100 or null), and summary fields
health_score, health_score_status, health_score_coverage, health_score_omitted.
No dates. No production data.

User instruction: complete the health-score work locally, test it hard, and
do not open a pull request.
"""

from __future__ import annotations

import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import audit_score  # noqa: E402
import google_report  # noqa: E402

_EXACT = Decimal("0.0001")


def _categories(scores: dict[str, object]) -> list[dict]:
    return [{"name": name, "score": score} for name, score in scores.items()]


def _full(score: object) -> dict:
    return {"categories": _categories({name: score for name, _weight in audit_score.WEIGHTS})}


def _expected(scores: dict[str, Decimal]) -> tuple[int, str, int]:
    numerator = Decimal(0)
    denominator = 0
    for name, weight in audit_score.WEIGHTS:
        if name not in scores:
            continue
        numerator += scores[name] * weight
        denominator += weight
    quotient = numerator / Decimal(denominator)
    exact = quotient.quantize(_EXACT, rounding=ROUND_HALF_UP)
    display = int(quotient.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return display, f"{exact:.4f}", denominator


def _published_weights(path: Path, heading: str) -> list[tuple[str, int]]:
    text = path.read_text(encoding="utf-8")
    section = text[text.index(heading):]
    lines = []
    for index, line in enumerate(section.splitlines()):
        if index > 0 and line.startswith("#"):
            break
        lines.append(line)
    rows = re.findall(r"^\| ([A-Za-z0-9 /()-]+) \| (\d+)% \|$", "\n".join(lines), re.M)
    return [(name, int(weight)) for name, weight in rows]


def test_weights_sum_to_100_and_match_both_published_tables() -> None:
    assert sum(weight for _name, weight in audit_score.WEIGHTS) == 100
    published = [(name, weight) for name, weight in audit_score.WEIGHTS]
    assert published == _published_weights(
        REPO_ROOT / "skills" / "seo" / "SKILL.md",
        "### SEO Health Score",
    )
    assert published == _published_weights(
        REPO_ROOT / "skills" / "seo-audit" / "SKILL.md",
        "## Scoring Weights",
    )


def test_audit_skill_delegates_the_score_to_the_script() -> None:
    text = (REPO_ROOT / "skills" / "seo-audit" / "SKILL.md").read_text(encoding="utf-8")
    process = text[text.index("## Process"):text.index("## Crawl Configuration")]
    assert "aggregate into SEO Health Score" not in process
    assert "Scoring the health score" in process
    assert "Do not weight, round, or fill" in process
    command = text[text.index("## Scoring the health score"):text.index("## Report Structure")]
    assert "run audit_score.py --data {domain}-audit/audit-data.json --write --json" in command
    assert "claude-seo" in command
    assert "Do not substitute 0" in command
    assert "python audit_score.py" not in command
    assert "python3" not in command
    hub = (REPO_ROOT / "skills" / "seo" / "SKILL.md").read_text(encoding="utf-8")
    steps = [
        line for line in hub.splitlines()
        if line.split(". ", 1)[0].isdigit()
    ]
    score_steps = [line for line in steps if "audit_score.py" in line]
    assert score_steps == [
        "14. Collect results, write `{domain}-audit/audit-data.json`, then "
        "score it with `audit_score.py` (see seo-audit's \"Scoring the health "
        "score\"). Do not compute the weighted score yourself."
    ]
    assert not any("SEO Health Score (0-100)" in line for line in steps)


def test_uniform_scores_stay_put_and_zero_is_a_real_score() -> None:
    perfect = audit_score.score_audit(_full(100))
    assert perfect["status"] == "complete"
    assert perfect["health_score"] == 100
    assert perfect["coverage_percent"] == 100
    assert perfect["omitted"] == []
    assert "full-audit" not in perfect["presentation"]

    zero = audit_score.score_audit(_full(0))
    assert zero["health_score"] == 0
    assert zero["status"] == "complete"

    images_zero = {name: Decimal(100) for name, _weight in audit_score.WEIGHTS}
    images_zero["Images"] = Decimal(0)
    result = audit_score.score_audit({
        "categories": _categories({name: int(score) for name, score in images_zero.items()})
    })
    display, exact, weight = _expected(images_zero)
    assert weight == 100
    assert result["health_score"] == display == 95
    assert result["health_score_exact"] == exact


def test_missing_performance_is_rescaled_not_treated_as_zero() -> None:
    """The rate-limited PageSpeed case: Performance is null, not a score of 0."""
    scores = {
        "Technical SEO": 80,
        "Content Quality": 90,
        "On-Page SEO": 70,
        "Schema / Structured Data": 60,
        "Performance (CWV)": None,
        "AI Search Readiness": 100,
        "Images": 40,
    }
    result = audit_score.score_audit({"categories": _categories(scores)})
    measured = {name: Decimal(score) for name, score in scores.items() if score is not None}
    display, exact, weight = _expected(measured)
    assert weight == 90
    assert display == 78
    assert exact == "78.1111"
    assert result["health_score"] == 78
    assert result["health_score_exact"] == "78.1111"
    assert result["status"] == "partial"
    assert result["coverage_percent"] == 90
    assert result["measured_weight"] == 90
    assert result["omitted"] == [
        {"name": "Performance (CWV)", "weight": 10, "reason": "not measured"}
    ]
    assert "Performance (CWV)" in result["presentation"]
    assert "Do not present it as a full-audit score." in result["presentation"]
    # Treating the null as 0 would be 7030/100 = 70.3, which must not win.
    assert result["health_score"] != 70


def test_absent_category_is_named_separately_from_a_null_score() -> None:
    result = audit_score.score_audit({
        "categories": [
            {"name": "Images", "score": "n/a"},
            {"name": "technical", "score": "80"},
        ]
    })
    reasons = {item["name"]: item["reason"] for item in result["omitted"]}
    assert reasons["Images"] == "not measured"
    assert reasons["Content Quality"] == "not in the audit"
    assert result["status"] == "partial"
    assert result["coverage_percent"] == 22
    assert result["health_score"] == 80
    technical = next(item for item in result["categories"] if item["name"] == "Technical SEO")
    assert technical["score"] == "80"
    assert technical["input_name"] == "technical"


def test_aliases_resolve_and_unknown_names_do_not_enter_the_score() -> None:
    result = audit_score.score_audit({
        "categories": [
            {"name": "Schema & Structured Data", "score": 40},
            {"name": "Performance (CWV)", "score": 60},
            {"name": "on-page", "score": 50},
            {"name": "core web vitals", "score": 10},
        ]
    })
    assert result["status"] == "error"
    assert {item["code"] for item in result["problems"]} == {"duplicate_category"}
    assert "health_score" not in result

    unknown = audit_score.score_audit({
        "categories": [
            {"name": "Technical SEO", "score": 90},
            {"name": "SXO Gap Score", "score": 10},
        ]
    })
    assert unknown["status"] == "error"
    assert unknown["problems"][0]["code"] == "unknown_category"
    assert "Technical SEO" in unknown["problems"][0]["message"]
    assert "health_score" not in unknown


def test_invalid_scores_are_rejected_together_and_bools_are_not_numbers() -> None:
    result = audit_score.score_audit({
        "categories": [
            {"name": "Images", "score": True},
            {"name": "Technical SEO", "score": 150},
            {"name": "Technical SEO", "score": 10},
            {"name": "Content Quality", "score": "eighty"},
            {"name": "On-Page SEO", "score": float("nan")},
            {"name": "Schema", "score": float("inf")},
            "not-an-object",
            {"score": 10},
        ]
    })
    codes = [item["code"] for item in result["problems"]]
    assert "invalid_score" in codes
    assert "duplicate_category" in codes
    assert "invalid_category" in codes
    assert result["status"] == "error"
    assert "health_score" not in result


@pytest.mark.parametrize(
    "raw",
    ["sNaN", "NaN", "Infinity", "1e2", "1e1000000", "1e999999", "1e-999999"],
)
def test_hostile_score_strings_stay_short_errors(raw: str) -> None:
    result = audit_score.score_audit({"categories": [{"name": "Images", "score": raw}]})
    assert result["status"] == "error"
    assert result["problems"][0]["code"] == "invalid_score"
    assert len(result["error"]) < 200
    assert "health_score" not in result


def test_boundaries_round_half_up_and_stay_inside_0_to_100() -> None:
    half = audit_score.score_audit({"categories": [{"name": "Images", "score": "0.5"}]})
    assert half["health_score"] == 1
    assert half["health_score_exact"] == "0.5000"
    just_under = audit_score.score_audit({"categories": [{"name": "Images", "score": "0.49"}]})
    assert just_under["health_score"] == 0
    assert just_under["health_score_exact"] == "0.4900"
    assert audit_score.score_audit(_full("100"))["health_score"] == 100
    assert audit_score.score_audit(_full("0"))["health_score"] == 0
    over = audit_score.score_audit({"categories": [{"name": "Images", "score": "100.0001"}]})
    assert over["status"] == "error"
    negative = audit_score.score_audit({"categories": [{"name": "Images", "score": -0.01}]})
    assert negative["status"] == "error"


def test_no_measured_category_is_insufficient_and_not_zero() -> None:
    documents = (
        {},
        {"categories": None},
        {"categories": []},
        {"summary": {"health_score": 82}, "categories": [{"name": "Images", "score": None}]},
    )
    for document in documents:
        result = audit_score.score_audit(document)
        assert result["status"] == "insufficient"
        assert result["health_score"] is None
        assert result["coverage_percent"] == 0
        assert sum(item["weight"] for item in result["omitted"]) == 100
        assert "Do not print a numeric" in result["presentation"]


def test_formula_holds_for_an_independent_mix() -> None:
    raw = {
        "Technical SEO": Decimal("81.25"),
        "Content Quality": Decimal("64"),
        "On-Page SEO": Decimal("70.5"),
        "Schema / Structured Data": Decimal("100"),
        "Performance (CWV)": Decimal("33.33"),
        "AI Search Readiness": Decimal("0"),
        "Images": Decimal("12.5"),
    }
    result = audit_score.score_audit({
        "categories": _categories({name: str(score) for name, score in raw.items()})
    })
    display, exact, weight = _expected(raw)
    assert weight == 100
    assert result["status"] == "complete"
    assert result["health_score"] == display
    assert result["health_score_exact"] == exact
    numerator = sum(
        (raw[name] * category_weight for name, category_weight in audit_score.WEIGHTS),
        Decimal(0),
    )
    assert Decimal(result["numerator"]) / Decimal(result["denominator"]) == numerator / 100


def test_envelope_shape_errors() -> None:
    assert audit_score.score_audit([])["status"] == "error"
    assert audit_score.score_audit({"categories": {"Technical SEO": 80}})["status"] == "error"
    assert audit_score.score_audit({"categories": [{"name": "   ", "score": 1}]})["status"] == "error"


def test_write_stores_the_score_and_leaves_the_rest_of_the_file(tmp_path: Path) -> None:
    path = tmp_path / "audit-data.json"
    original = {
        "summary": {
            "health_score": 12,
            "business_type": "SaaS",
            "top_findings": ["Keep me"],
        },
        "categories": _categories({
            "Technical SEO": 80,
            "Content Quality": 80,
            "On-Page SEO": 80,
            "Schema / Structured Data": 80,
            "Performance (CWV)": None,
            "AI Search Readiness": 80,
            "Images": 80,
        }),
        "action_plan": {"phases": [{"name": "Phase 1", "items": ["Keep me"]}]},
    }
    path.write_text(json.dumps(original), encoding="utf-8")

    assert audit_score.main(["--data", str(path), "--write", "--json"]) == 0
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["summary"]["business_type"] == "SaaS"
    assert written["summary"]["top_findings"] == ["Keep me"]
    assert written["action_plan"] == original["action_plan"]
    assert written["categories"] == original["categories"]
    assert written["summary"]["health_score"] == 80
    assert written["summary"]["health_score_status"] == "partial"
    assert written["summary"]["health_score_coverage"] == 90
    assert written["summary"]["health_score_omitted"] == ["Performance (CWV)"]
    assert list(tmp_path.glob("*.tmp")) == []

    assert audit_score.main(["--data", str(path), "--write", "--json"]) == 0
    again = json.loads(path.read_text(encoding="utf-8"))
    assert again["summary"]["health_score"] == 80


def test_write_clears_a_hallucinated_score_when_nothing_was_measured(tmp_path: Path) -> None:
    path = tmp_path / "audit-data.json"
    path.write_text(
        json.dumps({"summary": {"health_score": 82}, "categories": []}),
        encoding="utf-8",
    )
    assert audit_score.main(["--data", str(path), "--json"]) == 0
    untouched = json.loads(path.read_text(encoding="utf-8"))
    assert untouched["summary"]["health_score"] == 82

    assert audit_score.main(["--data", str(path), "--write"]) == 0
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["summary"]["health_score"] is None
    assert written["summary"]["health_score_status"] == "insufficient"
    assert written["summary"]["health_score_coverage"] == 0
    assert len(written["summary"]["health_score_omitted"]) == 7


def test_invalid_input_does_not_write_and_cli_errors_are_json(tmp_path: Path, capsys) -> None:
    path = tmp_path / "audit-data.json"
    payload = {
        "categories": [{"name": "Images", "score": True}],
        "summary": {"health_score": 50},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert audit_score.main(["--data", str(path), "--write", "--json"]) == 2
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    error = json.loads(capsys.readouterr().out)
    assert error["status"] == "error"
    assert error["problems"][0]["code"] == "invalid_score"

    missing = tmp_path / "missing.json"
    assert audit_score.main(["--data", str(missing)]) == 1
    assert json.loads(capsys.readouterr().out)["problems"][0]["code"] == "io_error"

    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    assert audit_score.main(["--data", str(broken), "--write"]) == 2
    assert broken.read_text(encoding="utf-8") == "{"
    assert json.loads(capsys.readouterr().out)["problems"][0]["code"] == "invalid_json"

    bom = tmp_path / "bom.json"
    bom.write_bytes(b"\xef\xbb\xbf" + json.dumps(_full(70)).encode("utf-8"))
    assert audit_score.main(["--data", str(bom)]) == 0
    assert json.loads(capsys.readouterr().out)["health_score"] == 70

    assert audit_score.main([]) == 2
    assert "required" in json.loads(capsys.readouterr().out)["error"]

    summary = tmp_path / "bad-summary.json"
    summary.write_text(
        json.dumps({"summary": ["nope"], "categories": _full(10)["categories"]}),
        encoding="utf-8",
    )
    before = summary.read_text(encoding="utf-8")
    assert audit_score.main(["--data", str(summary), "--write"]) == 2
    assert summary.read_text(encoding="utf-8") == before


def test_report_labels_a_partial_score_and_leaves_old_reports_alone(tmp_path: Path) -> None:
    partial = google_report.generate_report(
        "full",
        {
            "summary": {
                "health_score": 78,
                "health_score_status": "partial",
                "health_score_coverage": 90,
                "health_score_omitted": ["Performance (CWV)", "<script>alert(1)</script>"],
            }
        },
        "example.com",
        tmp_path / "partial",
        output_format="html",
    )
    html = Path(partial["files"][0]).read_text(encoding="utf-8")
    assert html.count("SEO Health Score (partial, 90% of weight)") >= 2
    assert "Not measured: Performance (CWV), &lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "It is not a full-audit score." in html

    plain = google_report.generate_report(
        "full",
        {"summary": {"health_score": 82, "business_type": "SaaS"}},
        "example.com",
        tmp_path / "plain",
        output_format="html",
    )
    plain_html = Path(plain["files"][0]).read_text(encoding="utf-8")
    assert ">SEO Health Score<" in plain_html or "SEO Health Score<" in plain_html
    assert "SEO Health Score (partial" not in plain_html
    assert "not a full-audit score" not in plain_html

    empty = google_report.generate_report(
        "full",
        {"summary": {"health_score": None, "health_score_status": "insufficient"}},
        "example.com",
        tmp_path / "empty",
        output_format="html",
    )
    empty_html = Path(empty["files"][0]).read_text(encoding="utf-8")
    assert "No SEO Health Score was calculated" in empty_html
    assert "SEO Health Score (partial" not in empty_html

    leftover = google_report.generate_report(
        "full",
        {"summary": {"health_score": 82, "health_score_status": "insufficient"}},
        "example.com",
        tmp_path / "leftover",
        output_format="html",
    )
    leftover_html = Path(leftover["files"][0]).read_text(encoding="utf-8")
    assert "No SEO Health Score was calculated" in leftover_html
    assert "82/100" not in leftover_html


@pytest.mark.parametrize(
    ("coverage", "label"),
    [
        ("lots", "SEO Health Score (partial)"),
        (True, "SEO Health Score (partial)"),
        (90, "SEO Health Score (partial, 90% of weight)"),
    ],
)
def test_partial_label_survives_a_bad_coverage_value(coverage, label) -> None:
    summary = {"health_score_status": "partial", "health_score_coverage": coverage}
    assert google_report._health_score_label(summary) == label
