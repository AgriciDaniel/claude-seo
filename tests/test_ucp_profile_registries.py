"""Required UCP registries may be empty; capabilities are optional."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ucp_check as ucp  # noqa: E402


def minimal_profile():
    return {"ucp": {"version": "2026-08-25", "services": {}, "payment_handlers": {}}}


@pytest.mark.parametrize("capabilities", ["absent", {}])
def test_minimal_spec_profile_is_not_reported_as_missing_registries(capabilities):
    profile = minimal_profile()
    if capabilities != "absent":
        profile["ucp"]["capabilities"] = capabilities
    report = ucp.parse_profile(json.dumps(profile))
    assert report["issues"] == []
    assert report["services"] == report["capabilities"] == []


def test_payment_handler_registry_is_required():
    profile = minimal_profile()
    profile["ucp"].pop("payment_handlers")
    report = ucp.parse_profile(json.dumps(profile))
    assert "missing-payment-handlers" in report["issues"]


@pytest.mark.parametrize("value", [None, [], "handlers", 1])
def test_payment_handler_registry_must_be_an_object(value):
    profile = minimal_profile()
    profile["ucp"]["payment_handlers"] = value
    report = ucp.parse_profile(json.dumps(profile))
    assert "payment-handlers-not-an-object" in report["issues"]


@pytest.mark.parametrize("value", [None, [], "capabilities", 1])
def test_present_capabilities_must_be_an_object(value):
    profile = minimal_profile()
    profile["ucp"]["capabilities"] = value
    report = ucp.parse_profile(json.dumps(profile))
    assert "capabilities-not-an-object" in report["issues"]


def test_services_are_still_required():
    profile = minimal_profile()
    profile["ucp"].pop("services")
    assert "missing-services" in ucp.parse_profile(json.dumps(profile))["issues"]


def test_site_audit_reports_zero_structural_issues_for_minimal_profile(monkeypatch):
    payload = json.dumps(minimal_profile()).encode()
    response = SimpleNamespace(status_code=200, content=payload,
                               headers={"Content-Type": "application/json"})
    monkeypatch.setattr(ucp, "validate_url_strict", lambda url: None)
    monkeypatch.setattr(ucp, "safe_requests_get", lambda *args, **kwargs: response)
    report = ucp.audit_site("https://example.com/")
    assert report["profile_present"] is True
    assert report["parse"]["issues"] == []
    assert "0 structural issues" in report["summary"]
