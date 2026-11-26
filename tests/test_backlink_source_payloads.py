"""A successful API envelope is not itself backlink measurement data."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_backlink_report as validator  # noqa: E402


def _scored_report(source: str, payload) -> dict:
    return {
        source: payload,
        "scoring_factors": {"score": 68, "factors_with_data": 5},
    }


@pytest.mark.parametrize("source", ["moz_data", "bing_data", "dataforseo_data"])
@pytest.mark.parametrize("data", [None, {}, []])
def test_empty_api_payload_cannot_unlock_scoring(source, data):
    response = {
        "status": "success", "data": data, "error": None,
        "metadata": {"source": source, "timestamp": "2026-11-26T00:00:00Z"},
    }
    result = validator.validate_report(_scored_report(source, response))

    assert result["status"] == "FAIL"
    assert any(
        issue["field"] == "health_score" and "no backlink data source" in issue["message"]
        for issue in result["data"]["issues"]
    )


@pytest.mark.parametrize("source", ["moz_data", "bing_data", "dataforseo_data"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_measured_zero_remains_available(source, wrapped):
    data = {"total_returned": 0, "links": []}
    response = {"status": "success", "data": data, "error": None} if wrapped else data

    result = validator.validate_report(_scored_report(source, response))

    assert result["status"] == "PASS"


def test_partial_response_with_collected_data_remains_available():
    response = {
        "status": "partial",
        "data": {"sampled_inbound_link_count": 17, "complete": False},
        "error": None,
    }

    result = validator.validate_report(_scored_report("bing_data", response))

    assert result["status"] == "PASS"


def test_another_measured_source_can_support_the_score():
    report = _scored_report("moz_data", {"status": "success", "data": None, "error": None})
    report["bing_data"] = {"data": {"sampled_inbound_link_count": 17}, "error": None}

    assert validator.validate_report(report)["status"] == "PASS"


def test_errored_response_with_data_still_does_not_unlock_scoring():
    response = {"data": {"domain_authority": 41}, "error": "request failed"}

    assert validator.validate_report(_scored_report("moz_data", response))["status"] == "FAIL"


def test_empty_moz_metrics_response_through_the_production_client(monkeypatch):
    import moz_api

    class EmptyMetricsResponse:
        status_code = 200

        def json(self):
            return {}

    monkeypatch.setattr(moz_api, "_rate_limit", lambda: None)
    monkeypatch.setattr(moz_api.requests, "post", lambda *args, **kwargs: EmptyMetricsResponse())
    response = moz_api.get_url_metrics("https://www.python.org/", "test-key")

    assert response["status"] == "success"
    assert response["data"] == {}
    assert validator.validate_report(_scored_report("moz_data", response))["status"] == "FAIL"


def test_cli_rejects_empty_source_payload():
    report = _scored_report("moz_data", {"status": "success", "data": None, "error": None})
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_backlink_report.py"),
         "--report", "-", "--json"],
        input=json.dumps(report), text=True, capture_output=True, check=True,
    )

    result = json.loads(process.stdout)
    assert result["status"] == "FAIL"
    assert result["data"]["errors"] == 1
    assert not process.stderr
