"""Atom links use the fetched document URL and inherited XML Base."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sitemap_discovery as discovery  # noqa: E402


def entries(xml, url="https://example.com/feeds/current.xml"):
    kind, error, root, _ = discovery._classify(xml.encode(), "application/atom+xml", url)
    assert error is None
    return list(discovery._xml_entries(kind, root))


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('<entry><link href="articles/one"/></entry>', "https://example.com/feeds/articles/one"),
        ('<entry><link href="/articles/one"/></entry>', "https://example.com/articles/one"),
        ('<entry><link href="//news.example.net/one"/></entry>', "https://news.example.net/one"),
        (
            '<entry xml:base="../articles/"><link xml:base="2026/" href="one"/></entry>',
            "https://example.com/articles/2026/one",
        ),
        ('<entry><link href="https://other.example/one"/></entry>', "https://other.example/one"),
    ],
)
def test_atom_resolves_relative_links(body, expected):
    xml = f'<feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'
    assert entries(xml) == [(expected, None)]


def test_atom_inherits_base_from_feed():
    xml = (
        '<feed xmlns="http://www.w3.org/2005/Atom" xml:base="https://archive.example/posts/">'
        '<entry xml:base="2026/"><link href="one"/></entry></feed>'
    )
    assert entries(xml) == [("https://archive.example/posts/2026/one", None)]


def test_atom_uses_final_fetch_url():
    fetched = {
        "content": b'<feed><entry><link href="one"/></entry></feed>',
        "content_type": "application/atom+xml",
        "final_url": "https://redirect.example/articles/feed.xml",
        "too_large": False,
    }
    body = discovery._read_body(fetched)
    assert list(discovery._xml_entries(body["kind"], body["root"])) == [
        ("https://redirect.example/articles/one", None)
    ]


@pytest.mark.parametrize("link", ['<link/>', '<link href=""/>', '<link href="   "/>'])
def test_missing_atom_href_does_not_become_feed_url(link):
    assert entries(f"<feed><entry>{link}</entry></feed>") == [(None, None)]


def test_relative_sitemap_loc_still_requires_an_absolute_url():
    assert entries('<urlset><url><loc>articles/one</loc></url></urlset>') == [("articles/one", None)]


def test_malformed_atom_href_does_not_crash_expansion():
    assert entries('<feed><entry><link href="https://[broken"/></entry></feed>') == [("https://[broken", None)]
