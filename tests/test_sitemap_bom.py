"""Encoding signatures must not prevent otherwise valid sitemap XML parsing."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sitemap_discovery import _robots_sitemaps, _sitemap_kind  # noqa: E402


@pytest.mark.parametrize("root", ["urlset", "sitemapindex", "rss", "feed"])
def test_utf8_bom_xml_has_the_same_kind(root):
    xml = f'<?xml version="1.0" encoding="UTF-8"?><{root}/>'.encode()
    args = ("application/xml", "https://example.com/sitemap.xml")
    assert _sitemap_kind(xml, *args) == (root, None)
    assert _sitemap_kind(b"\xef\xbb\xbf" + xml, *args) == (root, None)


def test_bom_does_not_bypass_xml_safety_checks():
    xml = b'\xef\xbb\xbf<!DOCTYPE urlset [<!ENTITY x "unsafe">]><urlset>&x;</urlset>'
    assert _sitemap_kind(xml, "application/xml", "https://example.com/sitemap.xml")[0] is None


@pytest.mark.parametrize(
    ("content_type", "url"),
    [
        ("text/plain; charset=utf-8", "https://example.com/sitemap.txt"),
        ("application/octet-stream", "https://example.com/sitemap.txt"),
        ("text/plain", "https://example.com/sitemap"),
    ],
)
def test_utf8_bom_text_sitemap_is_valid(content_type, url):
    body = b"https://example.com/one\nhttps://example.com/two\n"
    assert _sitemap_kind(body, content_type, url) == ("text", None)
    assert _sitemap_kind(b"\xef\xbb\xbf" + body, content_type, url) == ("text", None)


def test_bom_does_not_make_an_invalid_text_sitemap_valid():
    body = b"\xef\xbb\xbfhttps://example.com/one\nnot a url\n"
    assert _sitemap_kind(body, "text/plain", "https://example.com/sitemap.txt") == (
        None,
        "invalid text sitemap",
    )


def test_robots_bom_and_trailing_comment_together():
    declared = "https://example.com/products.xml"
    robots = b"\xef\xbb\xbf" + f"Sitemap: {declared} # catalog\nSitemap: {declared}\n".encode()
    assert _robots_sitemaps(robots) == [declared]
