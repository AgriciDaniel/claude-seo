"""Executable sitemap discovery regressions for issue #142."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# sitemap_discovery imports lxml at module scope. Without it the collection
# error interrupts the whole pytest session, so skip this module instead.
pytest.importorskip("lxml")

import sitemap_discovery as discovery  # noqa: E402

URLSET = b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
INDEX = b'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></sitemapindex>'


def response(status=200, content=b"", url="https://example.com/", error=None, too_large=False, content_type="application/xml"):
    return {
        "status_code": status,
        "content": content,
        "content_type": content_type,
        "final_url": url,
        "too_large": too_large,
        "error": error,
    }


def test_wordpress_index_is_found_after_default_path_fails():
    def fake_fetch(url, _limit):
        if url.endswith("robots.txt"):
            return response(content=b"User-agent: *\n")
        if url.endswith("sitemap_index.xml"):
            return response(content=INDEX, url=url)
        return response(status=404, url=url)

    with patch.object(discovery, "_bounded_fetch", side_effect=fake_fetch):
        result = discovery.discover_sitemaps("https://example.com/page")
    assert [item["url"] for item in result["found"]] == ["https://example.com/sitemap_index.xml"]


def test_stale_declared_sitemap_does_not_suppress_working_fallback():
    stale = "https://example.com/old.xml"

    def fake_fetch(url, _limit):
        if url.endswith("robots.txt"):
            return response(content=f"Sitemap: {stale}\n".encode())
        if url == stale:
            return response(status=404, url=url)
        if url.endswith("wp-sitemap.xml"):
            return response(content=URLSET, url=url)
        return response(status=404, url=url)

    with patch.object(discovery, "_bounded_fetch", side_effect=fake_fetch):
        result = discovery.discover_sitemaps("https://example.com")
    assert any(item["source"] == "robots.txt" and not item["valid"] for item in result["checked"])
    assert result["found"][0]["url"].endswith("/wp-sitemap.xml")


def test_multiple_directives_are_deduplicated_and_cross_host_is_recorded():
    robots = (
        b"sItEmAp: https://cdn.example.net/a.xml\n"
        b"Sitemap: https://cdn.example.net/a.xml\n"
        b"Sitemap: https://example.com/b.xml\n"
    )

    def fake_fetch(url, _limit):
        if url.endswith("robots.txt"):
            return response(content=robots)
        if url.endswith(("a.xml", "b.xml")):
            return response(content=URLSET, url=url)
        return response(status=404, url=url)

    with patch.object(discovery, "_bounded_fetch", side_effect=fake_fetch):
        result = discovery.discover_sitemaps("https://example.com")
    assert len(result["declared"]) == 2
    assert len(result["found"]) == 2
    assert result["found"][0]["cross_host"] is True


def test_unsafe_declared_target_is_not_treated_as_found():
    unsafe = "http://127.0.0.1/private.xml"

    def fake_fetch(url, _limit):
        if url.endswith("robots.txt"):
            return response(content=f"Sitemap: {unsafe}\n".encode())
        if url == unsafe:
            return response(error="URL safety validation failed", url=url)
        return response(status=404, url=url)

    with patch.object(discovery, "_bounded_fetch", side_effect=fake_fetch):
        result = discovery.discover_sitemaps("https://example.com")
    unsafe_entry = next(item for item in result["checked"] if item["url"] == unsafe)
    assert unsafe_entry["valid"] is False
    assert unsafe_entry["error"] == "URL safety validation failed"


def test_invalid_xml_and_html_200_are_rejected():
    assert discovery._sitemap_kind(b"<urlset>", "application/xml", "https://example.com/sitemap.xml")[0] is None
    assert discovery._sitemap_kind(b"<html></html>", "text/html", "https://example.com/sitemap.xml")[0] is None


def test_text_sitemap_entries_are_syntax_checked_without_dns_resolution():
    content = b"https://example.com/one\nhttps://example.com/two\n"
    with patch.object(discovery, "validate_url", side_effect=AssertionError("unexpected DNS validation")):
        kind, error = discovery._sitemap_kind(
            content, "text/plain", "https://example.com/sitemap.txt"
        )
    assert kind == "text"
    assert error is None
    assert discovery._valid_sitemap_url_syntax("http://user@example.com/private") is False


def test_doctype_and_oversized_sitemap_are_rejected():
    assert discovery._sitemap_kind(b"<!DOCTYPE x><urlset/>", "application/xml", "https://example.com/sitemap.xml")[0] is None

    def fake_fetch(url, _limit):
        if url.endswith("robots.txt"):
            return response(content=b"Sitemap: https://example.com/huge.xml\n")
        if url.endswith("huge.xml"):
            return response(url=url, too_large=True)
        return response(status=404, url=url)

    with patch.object(discovery, "_bounded_fetch", side_effect=fake_fetch):
        result = discovery.discover_sitemaps("https://example.com")
    huge = next(item for item in result["checked"] if item["url"].endswith("huge.xml"))
    assert "50 MiB" in huge["error"]


def test_query_values_are_never_returned_in_discovery_output():
    declared = "https://example.com/private.xml?token=not-for-output"

    def fake_fetch(url, _limit):
        if url.endswith("robots.txt"):
            return response(content=f"Sitemap: {declared}\n".encode())
        if url == declared:
            return response(content=URLSET, url=url)
        return response(status=404, url=url)

    with patch.object(discovery, "_bounded_fetch", side_effect=fake_fetch):
        result = discovery.discover_sitemaps("https://example.com")
    dumped = str(result)
    assert "not-for-output" not in dumped
    assert result["declared"][0]["query_redacted"] is True


def test_private_literal_is_refused_before_network_request():
    result = discovery._bounded_fetch("http://127.0.0.1/sitemap.xml", 100)
    assert result["error"] == "URL safety validation failed"


def test_invalid_port_is_reported_without_crashing():
    result = discovery.discover_sitemaps("https://example.com:invalid/")
    assert result["error"] == "Target URL contains an invalid port"
