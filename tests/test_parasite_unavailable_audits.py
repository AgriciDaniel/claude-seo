"""A failed crawl cannot establish a low-risk content assessment."""

import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import parasite_risk  # noqa: E402


@pytest.mark.parametrize("status", [404, 429, 500])
def test_http_error_page_does_not_count_as_audited_content(monkeypatch, status):
    class Response:
        status_code = status
        url = "https://example.com/page"

        def raise_for_status(self):
            raise requests.HTTPError(f"HTTP {status}")

    monkeypatch.setattr(parasite_risk, "safe_requests_get", lambda *a, **k: Response())
    monkeypatch.setattr(parasite_risk, "decode_response_text", lambda response: "Not available")
    result = parasite_risk.scan(["https://example.com/page"])
    assert result["pages_audited"] == 0
    assert result["overall_risk"] == "unknown"
    assert len(result["errors"]) == 1


def test_all_transport_failures_produce_unknown_risk(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(parasite_risk, "safe_requests_get", fail)
    result = parasite_risk.scan(["https://example.com/page"])
    assert result["overall_risk"] == "unknown"


def test_json_cli_fails_when_no_page_was_audited(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["parasite_risk.py", "https://example.com", "--json"])
    monkeypatch.setattr(parasite_risk, "scan", lambda urls: {
        "pages_audited": 0, "errors": [{"error": "timeout"}], "overall_risk": "unknown",
    })
    assert parasite_risk.main() == 1
    assert json.loads(capsys.readouterr().out)["overall_risk"] == "unknown"
