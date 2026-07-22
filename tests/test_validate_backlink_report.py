"""Backlink report validation regressions."""

from __future__ import annotations

import os
import sys


_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import validate_backlink_report as vbr  # noqa: E402


def test_unflattened_graph_schema_is_flagged_as_error() -> None:
    issues = vbr.validate_schema_claims({"schema": [{"@graph": [{"@type": "Product"}]}]})

    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert "@graph" in issues[0]["message"]


def test_deprecated_howto_schema_is_flagged_as_error() -> None:
    issues = vbr.validate_schema_claims({"schema": [{"@type": "HowTo"}]})

    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert "HowTo" in issues[0]["message"]


def test_schema_type_array_is_not_flagged() -> None:
    issues = vbr.validate_schema_claims({"schema": [{"@type": ["Product", "ItemPage"]}]})

    assert issues == []


def test_verification_summary_mismatch_is_flagged_as_error() -> None:
    verify_data = {
        "data": {
            "results": [{"status": "verified"}, {"status": "verified"}],
            "summary": {"verified": 1},
        }
    }

    issues = vbr.validate_verification_results(verify_data)

    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert "verified=1" in issues[0]["message"]


def test_social_media_link_removed_with_200_is_flagged_as_error() -> None:
    verify_data = {
        "data": {
            "results": [{
                "source_url": "https://www.instagram.com/somepage",
                "status": "link_removed",
                "http_status": 200,
            }],
            "summary": {"link_removed": 1},
        }
    }

    issues = vbr.validate_verification_results(verify_data)

    assert any(i["severity"] == "error" and "unverifiable_js" in i["message"] for i in issues)


def test_health_score_with_insufficient_data_is_flagged_as_error() -> None:
    issues = vbr.validate_health_score({"total_factors": 7, "factors_with_data": 2, "score": 82})

    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert "INSUFFICIENT DATA" in issues[0]["message"]


def test_health_score_with_sufficient_data_is_not_flagged() -> None:
    issues = vbr.validate_health_score({"total_factors": 7, "factors_with_data": 6, "score": 82})

    assert issues == []


def test_validate_report_status_is_fail_when_errors_present() -> None:
    result = vbr.validate_report({"parsed_data": {"schema": [{"@type": "HowTo"}]}})

    assert result["status"] == "FAIL"
    assert result["data"]["errors"] == 1


def test_validate_report_status_is_pass_when_no_issues() -> None:
    result = vbr.validate_report({"parsed_data": {"schema": [{"@type": "Organization"}]}})

    assert result["status"] == "PASS"
    assert result["data"]["total_issues"] == 0
