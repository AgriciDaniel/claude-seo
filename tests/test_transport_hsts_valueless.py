"""A value on the valueless HSTS includeSubDomains directive invalidates it."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import transport_check as transport  # noqa: E402


@pytest.mark.parametrize("value", ["true", "false", '""', "''", '"true"', '"false"', ""])
@pytest.mark.parametrize("first", [False, True])
def test_include_subdomains_value_does_not_establish_hsts(value, first):
    directive = f"iNcLuDeSuBdOmAiNs={value}"
    policy = (
        f"{directive}; max-age=31536000; preload" if first
        else f"max-age=31536000; {directive}; preload"
    )
    headers = transport.analyze_headers({"Strict-Transport-Security": policy})
    hsts = headers["hsts"]
    assert hsts["max_age"] is None
    assert not hsts["include_subdomains"]
    assert not hsts["meets_preload_requirements"]
    assert hsts["issues"]
    assert any(
        item["id"] == "hsts-disabled" for item in transport._header_findings(headers)
    )


@pytest.mark.parametrize("policy", [
    "max-age=31536000; includeSubDomains; preload",
    'max-age="31536000"; includeSubDomains; preload',
    "includeSubDomains; max-age=31536000; extension=value; preload",
])
def test_valueless_directive_and_unknown_extension_still_work(policy):
    hsts = transport.analyze_headers({"Strict-Transport-Security": policy})["hsts"]
    assert hsts["max_age"] == 31536000
    assert hsts["include_subdomains"]
    assert hsts["meets_preload_requirements"]
