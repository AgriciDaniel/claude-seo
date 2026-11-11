"""Grade effective framing restrictions instead of header presence."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import transport_check as transport  # noqa: E402


@pytest.mark.parametrize("sources", [
    "*", "https:", "http:", "'self' *", "'none' *", "https://*", "http://*:*", "*:443",
])
@pytest.mark.parametrize("xfo", [None, "DENY", "SAMEORIGIN"])
def test_broad_frame_ancestors_is_not_protection_even_with_xfo(sources, xfo):
    headers = {"Content-Security-Policy": f"frame-ancestors {sources}"}
    if xfo:
        headers["X-Frame-Options"] = xfo
    result = transport.analyze_headers(headers)
    assert result["framing"]["frame_ancestors"] is True
    assert result["framing"]["ok"] is False
    assert "clickjacking-protection-missing" in {
        finding["id"] for finding in transport._header_findings(result)
    }


@pytest.mark.parametrize("sources", ["'none'", "'self'", "https://partner.example", ""])
def test_restrictive_or_empty_ancestor_list_is_protection(sources):
    result = transport.analyze_headers({"Content-Security-Policy": f"frame-ancestors {sources}"})
    assert result["framing"]["ok"] is True


@pytest.mark.parametrize("policy", [
    "frame-ancestors *, frame-ancestors 'self'",
    "frame-ancestors 'self', frame-ancestors *",
    "default-src 'none', frame-ancestors 'self'",
])
def test_any_enforced_policy_can_restrict_framing(policy):
    result = transport.analyze_headers({"Content-Security-Policy": policy})
    assert result["framing"] == {"x_frame_options": None, "frame_ancestors": True, "ok": True}


def test_report_only_policy_does_not_override_xfo():
    result = transport.analyze_headers({
        "Content-Security-Policy-Report-Only": "frame-ancestors *",
        "X-Frame-Options": "DENY",
    })
    assert result["framing"] == {"x_frame_options": "DENY", "frame_ancestors": False, "ok": True}


def test_default_src_does_not_supply_an_ancestor_policy():
    result = transport.analyze_headers({"Content-Security-Policy": "default-src 'none'"})
    assert result["framing"]["ok"] is False
