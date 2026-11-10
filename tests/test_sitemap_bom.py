"""Encoding signatures must not prevent otherwise valid sitemap XML parsing."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sitemap_discovery import _sitemap_kind  # noqa: E402


@pytest.mark.parametrize("root", ["urlset", "sitemapindex", "rss", "feed"])
def test_utf8_bom_xml_has_the_same_kind(root):
    xml = f'<?xml version="1.0" encoding="UTF-8"?><{root}/>'.encode()
    args = ("application/xml", "https://example.com/sitemap.xml")
    assert _sitemap_kind(xml, *args) == (root, None)
    assert _sitemap_kind(b"\xef\xbb\xbf" + xml, *args) == (root, None)


def test_bom_does_not_bypass_xml_safety_checks():
    xml = b'\xef\xbb\xbf<!DOCTYPE urlset [<!ENTITY x "unsafe">]><urlset>&x;</urlset>'
    assert _sitemap_kind(xml, "application/xml", "https://example.com/sitemap.xml")[0] is None
