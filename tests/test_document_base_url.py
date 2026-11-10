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
        ("", "https://example.com/blog/", "internal"),
    ],
)
def test_resource_urls_follow_document_base(head, prefix, kind):
    html = f'<html><head>{head}</head><body><a href="guide">Guide</a><img src="cover.png"></body></html>'
    result = parse_html(html, "https://example.com/blog/post")
    assert result["links"][kind][0]["href"] == prefix + "guide"
    assert result["links"]["internal" if kind == "external" else "external"] == []
    assert result["images"][0]["src"] == prefix + "cover.png"
