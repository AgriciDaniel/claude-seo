"""Only crawlable HTTP(S) URLs belong in the internal/external link inventory."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from parse_html import parse_html  # noqa: E402


@pytest.mark.parametrize("href", [
    "mailto:hello@example.com", "tel:+123456789", "sms:+123456789",
    "JAVASCRIPT:void(0)", " javascript:void(0)", "data:text/plain,Hello",
    "ftp://files.example.com/manual", "blob:https://example.com/object",
])
def test_nonweb_links_are_not_classified_as_external_pages(href):
    parsed = parse_html(f'<a href="{href}">Contact</a>', "https://example.com/")
    assert parsed["links"] == {"internal": [], "external": []}


def test_relative_and_protocol_relative_web_links_still_work():
    parsed = parse_html('<a href="/page">Page</a><a href="//other.test/x">Other</a>', "https://example.com/")
    assert parsed["links"]["internal"][0]["href"] == "https://example.com/page"
    assert parsed["links"]["external"][0]["href"] == "https://other.test/x"
