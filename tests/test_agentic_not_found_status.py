"""Only a missing-page response verifies the unknown-path probe."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import agentic_check as checker  # noqa: E402


def record(status, error=None):
    return {"status": status, "headers": {"content-type": "text/html"}, "error": error}


@pytest.mark.parametrize("status", [401, 403, 429, 500, 502, 503, 504])
def test_unavailable_probe_does_not_pass_missing_page_check(monkeypatch, status):
    monkeypatch.setattr(checker, "fetch", lambda url: record(status))
    checks, data = checker.audit_not_found("https://example.com")
    assert checks[0]["status"] == "info"
    assert data["inconclusive"] is True
    assert str(status) in checks[0]["fix"]


@pytest.mark.parametrize("status", [204, 302])
def test_other_status_is_explicitly_inconclusive(monkeypatch, status):
    monkeypatch.setattr(checker, "fetch", lambda url: record(status))
    checks, data = checker.audit_not_found("https://example.com")
    assert checks[0]["status"] == "info"
    assert data["inconclusive"] is True


def test_network_error_is_preserved(monkeypatch):
    monkeypatch.setattr(checker, "fetch", lambda url: record(None, "Connection timed out"))
    checks, data = checker.audit_not_found("https://example.com")
    assert checks[0]["status"] == "info"
    assert data["error"] == "Connection timed out"
    assert data["inconclusive"] is True
    assert checks[0]["fix"]


@pytest.mark.parametrize("status", [404, 410])
def test_missing_page_response_passes(monkeypatch, status):
    monkeypatch.setattr(checker, "fetch", lambda url: record(status))
    checks, data = checker.audit_not_found("https://example.com")
    assert checks[0]["status"] == "pass"
    assert not data.get("inconclusive")
    assert not data["catch_all_200"]


def test_catch_all_200_still_warns(monkeypatch):
    monkeypatch.setattr(checker, "fetch", lambda url: record(200))
    checks, data = checker.audit_not_found("https://example.com")
    assert checks[0]["status"] == "warn"
    assert data["catch_all_200"] is True
    assert "200" in checks[0]["fix"]
