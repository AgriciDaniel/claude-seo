"""Site-specific Google property selection must never cross domains."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from google_properties import resolve_site_property  # noqa: E402


def test_resolves_properties_from_exact_site_mapping() -> None:
    config = {
        "default_property": "sc-domain:primary.example",
        "ga4_property_id": "properties/100",
        "sites": {
            "client.example": {
                "gsc_property": "sc-domain:client.example",
                "ga4_property_id": "properties/200",
            }
        },
    }

    assert resolve_site_property(config, "gsc", "https://CLIENT.example/report") == "sc-domain:client.example"
    assert resolve_site_property(config, "ga4", "client.example") == "properties/200"


def test_does_not_fall_back_to_another_sites_global_properties() -> None:
    config = {
        "default_property": "sc-domain:primary.example",
        "ga4_property_id": "properties/100",
    }

    with pytest.raises(ValueError, match="refusing to use a different site's default"):
        resolve_site_property(config, "gsc", "client.example")
    with pytest.raises(ValueError, match="refusing to use a different site's default"):
        resolve_site_property(config, "ga4", "client.example")


def test_legacy_single_site_properties_are_usable_only_for_matching_domain() -> None:
    config = {
        "default_property": "sc-domain:example.com",
        "ga4_property_id": "properties/123",
    }

    assert resolve_site_property(config, "gsc", "https://example.com/page") == "sc-domain:example.com"
    assert resolve_site_property(config, "gsc", "https://www.example.com/page") == "sc-domain:example.com"
    assert resolve_site_property(config, "ga4", "example.com") == "properties/123"


def test_incomplete_site_mapping_does_not_fall_back_to_global_value() -> None:
    config = {
        "default_property": "sc-domain:example.com",
        "ga4_property_id": "properties/123",
        "sites": {"example.com": {"gsc_property": "sc-domain:example.com"}},
    }

    with pytest.raises(ValueError, match="No ga4_property_id configured"):
        resolve_site_property(config, "ga4", "example.com")


def test_duplicate_normalized_site_keys_are_rejected() -> None:
    config = {
        "sites": {
            "example.com": {"gsc_property": "sc-domain:example.com"},
            "EXAMPLE.COM.": {"gsc_property": "https://example.com/"},
        }
    }

    with pytest.raises(ValueError, match="Multiple sites entries"):
        resolve_site_property(config, "gsc", "example.com")
