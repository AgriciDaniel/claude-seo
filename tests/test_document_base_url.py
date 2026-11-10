"""Resolve relative resources against the document's first base href."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from parse_html import parse_html  # noqa: E402


@pytest.mark.parametrize(
    ("head", "prefix", "kind"),
    [
        ('<base href="https://cdn.example.net/docs/">', "https://cdn.example.net/docs/", "external"),
        ('<base href="/docs/">', "https://example.com/docs/", "internal"),
        ('<base href="//cdn.example.net/docs/">', "https://cdn.example.net/docs/", "external"),
        ('<base target="_blank"><base href="/docs/">', "https://example.com/docs/", "internal"),
        ('<base href="/first/"><base href="/second/">', "https://example.com/first/", "internal"),
        ('<base href="">', "https://example.com/blog/", "internal"),
        ('<base href="javascript:alert(1)"><base href="/ignored/">', "https://example.com/blog/", "internal"),
        ('<base href="http://[invalid">', "https://example.com/blog/", "internal"),
        ('<base href="file:///etc/">', "https://example.com/blog/", "internal"),
        ('<base href="mailto:x">', "https://example.com/blog/", "internal"),
        ('<base href="ftp://files.example.net/pub/">', "https://example.com/blog/", "internal"),
        ('<base href="HTTPS://cdn.example.net/docs/">', "https://cdn.example.net/docs/", "external"),
        ("", "https://example.com/blog/", "internal"),
    ],
)
def test_resource_urls_follow_document_base(head, prefix, kind):
    html = f'<html><head>{head}</head><body><a href="guide">Guide</a><img src="cover.png"></body></html>'
    result = parse_html(html, "https://example.com/blog/post")
    assert result["links"][kind][0]["href"] == prefix + "guide"
    assert result["links"]["internal" if kind == "external" else "external"] == []
    assert result["images"][0]["src"] == prefix + "cover.png"


def _hrefs(result, kind):
    return [link["href"] for link in result["links"][kind]]


@pytest.mark.parametrize("head", ["", '<base href="">', '<base href="/blog/post">', '<base href="file:///etc/">'])
def test_fragment_only_link_is_skipped_while_the_base_is_the_page(head):
    html = f'<html><head>{head}</head><body><a href="#top">Top</a></body></html>'
    result = parse_html(html, "https://example.com/blog/post")
    assert result["links"] == {"internal": [], "external": []}


def test_fragment_only_link_follows_a_base_that_points_elsewhere():
    """HTML resolves #frag against the document base URL, so it leaves the page."""
    html = (
        '<html><head><base href="https://other.example/page"></head>'
        '<body><a href="#frag">Jump</a></body></html>'
    )
    result = parse_html(html, "https://example.com/blog/post")
    assert _hrefs(result, "external") == ["https://other.example/page#frag"]
    assert _hrefs(result, "internal") == []


def test_fragment_only_link_follows_a_same_site_base():
    html = '<html><head><base href="/"></head><body><a href="#pricing">Pricing</a></body></html>'
    result = parse_html(html, "https://example.com/blog/post")
    assert _hrefs(result, "internal") == ["https://example.com/#pricing"]


def test_relative_base_without_a_page_url_still_prefixes_images():
    result = parse_html('<base href="/docs/"><img src="cover.png">')
    assert result["images"][0]["src"] == "/docs/cover.png"


def test_non_web_base_without_a_page_url_is_ignored():
    result = parse_html('<base href="file:///etc/"><img src="cover.png">')
    assert result["images"][0]["src"] == "cover.png"
