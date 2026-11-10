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


def _site(domain: str, ga4: str = "properties/200", prop: str | None = None) -> dict:
    return {"gsc_property": prop or f"sc-domain:{domain}", "ga4_property_id": ga4}


def test_www_is_the_same_site_on_either_side_of_the_mapping() -> None:
    bare_key = {"sites": {"example.com": _site("example.com")}}
    www_key = {"sites": {"www.example.com": _site("example.com", prop="https://www.example.com/")}}

    assert resolve_site_property(bare_key, "gsc", "https://www.example.com") == "sc-domain:example.com"
    assert resolve_site_property(bare_key, "ga4", "www.example.com") == "properties/200"
    assert resolve_site_property(www_key, "gsc", "example.com") == "https://www.example.com/"


def test_exact_key_beats_its_www_twin() -> None:
    config = {
        "sites": {
            "example.com": _site("example.com", prop="https://example.com/"),
            "www.example.com": _site("example.com", prop="https://www.example.com/"),
        }
    }

    assert resolve_site_property(config, "gsc", "example.com") == "https://example.com/"
    assert resolve_site_property(config, "gsc", "www.example.com") == "https://www.example.com/"


def test_domain_property_entry_covers_subdomains_by_dot_suffix_only() -> None:
    config = {
        "default_property": "sc-domain:primary.example",
        "ga4_property_id": "properties/100",
        "sites": {"example.com": _site("example.com")},
    }

    assert resolve_site_property(config, "gsc", "shop.example.com") == "sc-domain:example.com"
    assert resolve_site_property(config, "ga4", "https://a.b.example.com/x") == "properties/200"
    for lookalike in ("notexample.com", "example.com.evil.test", "example.co"):
        with pytest.raises(ValueError, match="refusing to use a different site's default"):
            resolve_site_property(config, "gsc", lookalike)


def test_url_prefix_entry_does_not_cover_subdomains() -> None:
    config = {"sites": {"example.com": _site("example.com", prop="https://example.com/")}}

    with pytest.raises(ValueError, match="refusing to use a different site's default"):
        resolve_site_property(config, "gsc", "shop.example.com")


def test_most_specific_covering_entry_wins() -> None:
    config = {
        "sites": {
            "example.com": _site("example.com", ga4="properties/1"),
            "blog.example.com": _site("blog.example.com", ga4="properties/2"),
        }
    }

    assert resolve_site_property(config, "ga4", "a.blog.example.com") == "properties/2"
    assert resolve_site_property(config, "ga4", "shop.example.com") == "properties/1"


def test_entries_sharing_a_domain_property_prefer_the_domains_own_entry() -> None:
    shared = {
        "example.com": _site("example.com", ga4="properties/1"),
        "blog.example.com": _site("example.com", ga4="properties/2"),
    }

    assert resolve_site_property({"sites": shared}, "ga4", "shop.example.com") == "properties/1"
    assert resolve_site_property({"sites": shared}, "ga4", "blog.example.com") == "properties/2"

    ambiguous = {
        "blog.example.com": _site("example.com", ga4="properties/2"),
        "docs.example.com": _site("example.com", ga4="properties/3"),
    }
    with pytest.raises(ValueError, match="Multiple sites entries cover"):
        resolve_site_property({"sites": ambiguous}, "ga4", "shop.example.com")


def test_legacy_url_prefix_default_treats_www_as_the_same_site() -> None:
    config = {"default_property": "https://www.example.com/", "ga4_property_id": "properties/123"}

    assert resolve_site_property(config, "gsc", "example.com") == "https://www.example.com/"
    with pytest.raises(ValueError, match="refusing to use a different site's default"):
        resolve_site_property(config, "gsc", "shop.example.com")
