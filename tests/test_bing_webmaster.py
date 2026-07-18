"""Bing Webmaster API link discovery regressions (issue #153).

GetLinkDetails does not exist in the Bing Webmaster API (confirmed against
Microsoft's IWebmasterApi reference) and 404s. GetUrlTrafficInfo 400s when
used the way the old get_link_counts() called it. These tests pin the
replacement behavior: link discovery via GetLinkCounts, expanded into real
referring links via GetUrlLinks, with response shapes matching Microsoft's
documented JSON samples exactly.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch


_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import bing_webmaster  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = "{}"

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


# Matches Microsoft's documented GetLinkCounts JSON response sample exactly.
LINK_COUNTS_RESPONSE = {
    "d": {
        "__type": "LinkCounts:#Microsoft.Bing.Webmaster.Api",
        "Links": [
            {"__type": "LinkCount:#Microsoft.Bing.Webmaster.Api", "Count": 14, "Url": "http://example.com/page1.html"},
            {"__type": "LinkCount:#Microsoft.Bing.Webmaster.Api", "Count": 2, "Url": "http://example.com/page2.html"},
        ],
        "TotalPages": 1,
    }
}

# Matches Microsoft's documented GetUrlLinks JSON response sample exactly.
URL_LINKS_RESPONSE = {
    "d": {
        "__type": "LinkDetails:#Microsoft.Bing.Webmaster.Api",
        "Details": [
            {"__type": "LinkDetail:#Microsoft.Bing.Webmaster.Api", "AnchorText": "great tool", "Url": "http://referrer-a.com/post"},
        ],
        "TotalPages": 1,
    }
}


def test_get_link_counts_sums_sampled_page_and_drops_traffic_info() -> None:
    with patch.object(bing_webmaster, "_rate_limit"), \
         patch.object(bing_webmaster.requests, "get", return_value=FakeResponse(LINK_COUNTS_RESPONSE)) as mocked_get:
        result = bing_webmaster.get_link_counts("https://example.com/", "fake-key")

    assert result["status"] == "success"
    assert result["data"]["pages_with_links_sample"] == 2
    assert result["data"]["sampled_inbound_link_count"] == 16
    assert "traffic_info" not in result["data"]
    called_url = mocked_get.call_args.args[0]
    assert "GetLinkCounts" in called_url
    assert "GetUrlTrafficInfo" not in called_url


def test_get_link_details_expands_top_pages_via_get_url_links() -> None:
    def fake_get(url, params=None, **kwargs):
        if "GetLinkCounts" in url:
            return FakeResponse(LINK_COUNTS_RESPONSE)
        return FakeResponse(URL_LINKS_RESPONSE)

    with patch.object(bing_webmaster, "_rate_limit"), \
         patch.object(bing_webmaster.requests, "get", side_effect=fake_get):
        result = bing_webmaster.get_link_details("https://example.com/", "fake-key", max_pages_to_expand=2)

    assert result["status"] == "success"
    links = result["data"]["links"]
    assert len(links) == 2  # one GetUrlLinks result per expanded page
    assert links[0] == {
        "source_url": "http://referrer-a.com/post",
        "target_url": "http://example.com/page1.html",
        "anchor_text": "great tool",
    }


def test_get_link_details_never_calls_removed_or_broken_endpoints() -> None:
    with patch.object(bing_webmaster, "_rate_limit"), \
         patch.object(bing_webmaster.requests, "get", return_value=FakeResponse(LINK_COUNTS_RESPONSE)) as mocked_get:
        bing_webmaster.get_link_details("https://example.com/", "fake-key", max_pages_to_expand=0)

    for call in mocked_get.call_args_list:
        called_url = call.args[0]
        assert "GetLinkDetails" not in called_url
        assert "GetUrlTrafficInfo" not in called_url


def test_compare_links_computes_real_domain_gap_from_expanded_links() -> None:
    def fake_get(url, params=None, **kwargs):
        if "GetLinkCounts" in url:
            return FakeResponse(LINK_COUNTS_RESPONSE)
        site_url = (params or {}).get("siteUrl", "")
        if "competitor" in site_url:
            return FakeResponse({"d": {"Details": [{"AnchorText": "x", "Url": "http://only-competitor.com/a"}]}})
        return FakeResponse({"d": {"Details": [{"AnchorText": "y", "Url": "http://only-you.com/b"}]}})

    with patch.object(bing_webmaster, "_rate_limit"), \
         patch.object(bing_webmaster.requests, "get", side_effect=fake_get):
        result = bing_webmaster.compare_links("https://example.com/", "https://competitor.com/", "fake-key")

    assert result["status"] == "success"
    data = result["data"]
    # Pre-fix: get_link_details() returned entries with no source_url, so
    # both domain sets were always empty and this comparison was hollow.
    assert data["your_linking_domains"] == 1
    assert data["competitor_linking_domains"] == 1
    assert data["gap_domains"] == ["only-competitor.com"]
    assert data["unique_to_you"] == ["only-you.com"]
