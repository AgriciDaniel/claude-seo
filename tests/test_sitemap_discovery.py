"""Executable sitemap discovery regressions for issue #142."""

from __future__ import annotations

import gzip
import sys
import tracemalloc
import zlib
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


def test_sitemap_directive_keeps_its_url_when_a_comment_follows():
    """Google's robots.txt syntax ignores everything after #. The URL stays."""
    declared = "https://example.com/products.xml"
    robots = (
        f"User-agent: *\nSitemap: {declared} # primary catalog\n"
        f"# Sitemap: https://example.com/secret.xml\n"
    ).encode()
    assert discovery._robots_sitemaps(robots) == [declared]


def test_sitemap_directive_on_the_first_line_survives_a_utf8_bom():
    declared = "https://example.com/products.xml"
    robots = b"\xef\xbb\xbf" + f"Sitemap: {declared}\n".encode()
    assert discovery._robots_sitemaps(robots) == [declared]


def test_commented_sitemap_directive_is_the_url_that_gets_fetched():
    declared = "https://example.com/products.xml"
    fetched = []

    def fake_fetch(url, _limit):
        fetched.append(url)
        if url.endswith("robots.txt"):
            return response(
                content=f"User-agent: *\nSitemap: {declared} # primary catalog\n".encode(),
                content_type="text/plain",
            )
        if url == declared:
            return response(content=URLSET, url=url)
        return response(status=404, url=url)

    with patch.object(discovery, "_bounded_fetch", side_effect=fake_fetch):
        result = discovery.discover_sitemaps("https://example.com")
    assert declared in fetched
    assert [item["url"] for item in result["found"] if item["url"] == declared] == [declared]


def test_paths_that_redirect_to_one_sitemap_are_listed_once():
    """Rank Math sends /sitemap.xml to /sitemap_index.xml: one file, one listing."""
    final = "https://example.com/sitemap_index.xml"

    def fake_fetch(url, _limit):
        if url.endswith("robots.txt"):
            return response(content=b"User-agent: *\n")
        if url.endswith(("/sitemap.xml", "/sitemap_index.xml")):
            return response(content=INDEX, url=final)
        return response(status=404, url=url)

    with patch.object(discovery, "_bounded_fetch", side_effect=fake_fetch):
        result = discovery.discover_sitemaps("https://example.com")
    assert [item["url"] for item in result["found"]] == [final]
    # Both paths were checked and both answered with a valid sitemap.
    assert [item["valid"] for item in result["checked"]] == [True, True, False, False]
    assert "expanded" not in result


def discover_one(body, url="https://example.com/sitemap.xml.gz", content_type="application/gzip"):
    """Plain discovery of a site whose robots.txt declares one sitemap."""

    def fake_fetch(fetch_url, _limit):
        if fetch_url.endswith("robots.txt"):
            return response(content=f"Sitemap: {url}\n".encode())
        if fetch_url == url:
            return response(content=body, url=url, content_type=content_type)
        return response(status=404, url=fetch_url)

    with patch.object(discovery, "_bounded_fetch", side_effect=fake_fetch):
        result = discovery.discover_sitemaps("https://example.com")
    return result, result["checked"][0]


@pytest.mark.parametrize(
    ("plain", "kind"),
    [(URLSET, "urlset"), (INDEX, "sitemapindex"), (b"https://example.com/one\nhttps://example.com/two\n", None)],
)
def test_gzip_sitemap_is_classified_by_its_decompressed_content(plain, kind):
    result, entry = discover_one(gzip.compress(plain))
    assert entry["gzip"] is True
    assert (entry["kind"], entry["valid"]) == (kind, kind is not None)
    assert [item["url"] for item in result["found"]] == (["https://example.com/sitemap.xml.gz"] if kind else [])
    assert set(result) == {"target", "robots_url", "declared", "found", "checked", "warnings", "error"}


def test_gzip_is_detected_by_content_and_plain_entries_carry_no_marker():
    # No .gz in the name and a generic content type: the magic bytes decide.
    result, entry = discover_one(gzip.compress(URLSET), "https://example.com/map", "application/octet-stream")
    assert (entry["kind"], entry["gzip"]) == ("urlset", True)
    # A .gz name whose transfer encoding was already undone is plain XML.
    result, entry = discover_one(URLSET)
    assert entry["kind"] == "urlset"
    assert "gzip" not in entry and "gzip" not in result["found"][0]


def test_gzip_text_sitemap_is_classified_by_its_inner_name():
    body = gzip.compress(b"https://example.com/one\nhttps://example.com/two\n")
    _, entry = discover_one(body, "https://example.com/urls.txt.gz")
    assert (entry["kind"], entry["valid"], entry["gzip"]) == ("text", True, True)


def test_gzip_bomb_in_plain_discovery_is_cut_off_at_the_cap():
    packer = zlib.compressobj(9, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
    piece = b" " * (1024 * 1024)
    bomb = b"".join(packer.compress(piece) for _ in range(64)) + packer.flush()
    assert len(bomb) < 200 * 1024
    tracemalloc.start()
    try:
        with patch.object(discovery, "MAX_SITEMAP_BYTES", 1024 * 1024):
            result, entry = discover_one(bomb)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert (entry["valid"], entry["kind"], entry["gzip"]) == (False, None, True)
    assert "50 MiB" in entry["error"]
    assert result["found"] == []
    # Inflating all of it would take 64 MiB; the capped read stays near 2 MiB.
    assert peak < 8 * 1024 * 1024


def test_corrupt_or_truncated_gzip_is_reported_not_found():
    packed = gzip.compress(URLSET * 50, mtime=0)
    for damaged in (packed[:-12], packed[:20] + b"\xff" * 20 + packed[40:], b"\x1f\x8b not gzip at all"):
        result, entry = discover_one(damaged)
        assert (entry["valid"], entry["error"], entry["gzip"]) == (False, "invalid gzip data", True)
        assert result["found"] == []


def test_doctype_inside_gzip_is_refused():
    hostile = b'<!DOCTYPE urlset [<!ENTITY x SYSTEM "file:///etc/passwd">]><urlset><url><loc>&x;</loc></url></urlset>'
    result, entry = discover_one(gzip.compress(hostile))
    assert (entry["valid"], entry["error"]) == (False, "DOCTYPE is not allowed in sitemap XML")
    assert result["found"] == []
