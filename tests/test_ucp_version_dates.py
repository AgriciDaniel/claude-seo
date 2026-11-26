"""UCP versions are complete calendar dates, including component versions."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ucp_check as ucp  # noqa: E402

PROFILE = {"ucp": {
    "version": "2026-08-25",
    "services": {"dev.ucp.shopping": [{
        "version": "2026-08-25", "transport": "rest", "endpoint": "https://example.com/api",
    }]},
    "capabilities": {"dev.ucp.shopping.checkout": [{
        "version": "2026-08-25", "spec": "https://ucp.dev/spec", "schema": "https://ucp.dev/schema",
    }]},
    "payment_handlers": {},
}}


@pytest.mark.parametrize("version", ["2026-02-30", "2025-02-29", "2026-13-01", "2026-08-25\n"])
def test_root_version_requires_a_complete_calendar_date(version):
    profile = copy.deepcopy(PROFILE)
    profile["ucp"]["version"] = version
    parsed = ucp.parse_profile(json.dumps(profile))
    assert parsed["version"] is None
    assert "version-missing-or-not-a-date" in parsed["issues"]


@pytest.mark.parametrize("registry", ["services", "capabilities"])
@pytest.mark.parametrize("version", [
    "draft", "2026-02-30", "2026-08-25\n", 42, True, ["2026-08-25"], {"date": "2026-08-25"},
])
def test_component_version_must_be_a_date_string(registry, version):
    profile = copy.deepcopy(PROFILE)
    variant = next(iter(profile["ucp"][registry].values()))[0]
    variant["version"] = version
    parsed = ucp.parse_profile(json.dumps(profile))
    assert "version-not-a-date" in parsed[registry][0]["issues"]


def test_invalid_supported_version_date_is_not_advertised():
    profile = copy.deepcopy(PROFILE)
    profile["ucp"]["supported_versions"] = {
        "2026-02-30": "https://example.com/invalid",
        "2026-08-25\n": "https://example.com/newline",
        "2024-02-29": "https://example.com/leap",
    }
    parsed = ucp.parse_profile(json.dumps(profile))
    assert parsed["supported_versions"] == {"2024-02-29": "https://example.com/leap"}
    assert sum(item.startswith("supported-version-key-not-a-date:") for item in parsed["issues"]) == 2


@pytest.mark.parametrize("registry", ["services", "capabilities"])
@pytest.mark.parametrize("version", ["", None])
def test_missing_component_version_keeps_its_existing_issue(registry, version):
    profile = copy.deepcopy(PROFILE)
    next(iter(profile["ucp"][registry].values()))[0]["version"] = version
    parsed = ucp.parse_profile(json.dumps(profile))
    assert "missing-version" in parsed[registry][0]["issues"]
    assert "version-not-a-date" not in parsed[registry][0]["issues"]


def test_valid_independent_component_dates_and_leap_days_are_preserved():
    profile = copy.deepcopy(PROFILE)
    profile["ucp"]["version"] = "2024-02-29"
    next(iter(profile["ucp"]["services"].values()))[0]["version"] = "2026-08-25"
    next(iter(profile["ucp"]["capabilities"].values()))[0]["version"] = "2026-04-08"
    parsed = ucp.parse_profile(json.dumps(profile))
    assert parsed["issues"] == []
    assert parsed["version"] == "2024-02-29"
    assert not parsed["services"][0]["issues"]
    assert not parsed["capabilities"][0]["issues"]
