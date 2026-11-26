"""PSI can return HTTP 200 even when Lighthouse itself failed."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pagespeed_check as pagespeed  # noqa: E402


def payload(runtime_error=None):
    lighthouse = {
        "lighthouseVersion": "13.5.0",
        "categories": {"performance": {"score": None}, "seo": {"score": 0.91}},
        "audits": {},
    }
    if runtime_error is not None:
        lighthouse["runtimeError"] = runtime_error
    return {
        "analysisUTCTimestamp": "2026-11-15T00:00:00.000Z",
        "lighthouseResult": lighthouse,
        "loadingExperience": {
            "metrics": {"FIRST_CONTENTFUL_PAINT_MS": {"percentile": 1200, "category": "FAST"}}
        },
    }


def mock_response(monkeypatch, data):
    monkeypatch.setattr(pagespeed, "validate_url", lambda url: True)
    monkeypatch.setattr(pagespeed.requests, "get", lambda *args, **kwargs: SimpleNamespace(
        status_code=200, raise_for_status=lambda: None, json=lambda: data,
    ))


@pytest.mark.parametrize("code", ["NO_FCP", "FAILED_DOCUMENT_REQUEST", "PROTOCOL_TIMEOUT"])
def test_runtime_failure_is_reported_without_losing_partial_metrics(monkeypatch, code):
    mock_response(monkeypatch, payload({"code": code, "message": "Lighthouse could not load the page."}))
    result = pagespeed.run_pagespeed("https://example.com/")
    assert result["error"] and code in result["error"]
    assert "could not load" in result["error"]
    assert result["lighthouse_scores"] == {"seo": 91}
    assert result["field_metrics"]["url_first_contentful_paint"]["p75"] == 1200
    assert result["lighthouse_version"] == "13.5.0"
    assert result["analysis_timestamp"] == "2026-11-15T00:00:00.000Z"


@pytest.mark.parametrize("runtime_error", [None, {}, {"code": "NO_ERROR"}])
def test_absent_or_no_error_runtime_state_preserves_success(monkeypatch, runtime_error):
    mock_response(monkeypatch, payload(runtime_error))
    result = pagespeed.run_pagespeed("https://example.com/")
    assert result["error"] is None
    assert result["lighthouse_scores"]["seo"] == 91


def test_code_without_message_still_reports_the_failure(monkeypatch):
    mock_response(monkeypatch, payload({"code": "NO_FCP"}))
    result = pagespeed.run_pagespeed("https://example.com/")
    assert result["error"] and "NO_FCP" in result["error"]


def test_runtime_error_message_redacts_credentials(monkeypatch):
    secret = "AI" + "zaSyDUMMYSECRET"
    mock_response(monkeypatch, payload({
        "code": "FAILED_DOCUMENT_REQUEST",
        "message": "Failed https://example.com/?key=" + secret,
    }))
    result = pagespeed.run_pagespeed("https://example.com/")
    assert result["error"]
    assert secret not in result["error"]


def test_psi_only_cli_exits_with_reported_runtime_failure(monkeypatch, capsys):
    mock_response(monkeypatch, payload({"code": "NO_FCP", "message": "No paint."}))
    monkeypatch.setattr(pagespeed, "get_api_key", lambda: None)
    monkeypatch.setattr(sys, "argv", [
        "pagespeed_check.py", "https://example.com/", "--psi-only",
        "--strategy", "mobile", "--json",
    ])
    with pytest.raises(SystemExit) as exc:
        pagespeed.main()
    assert exc.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert "NO_FCP" in result["error"]
    assert result["psi"]["mobile"]["error"] == result["error"]


def test_combined_report_propagates_runtime_failure(monkeypatch):
    mock_response(monkeypatch, payload({"code": "NO_FCP", "message": "No paint."}))
    result = pagespeed.combined_check("https://example.com/", strategy="mobile")
    assert result["error"] and "NO_FCP" in result["error"]
