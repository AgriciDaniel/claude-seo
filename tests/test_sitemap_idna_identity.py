"""Unicode and ASCII domain spellings identify the same sitemap hosts."""

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sitemap_discovery as discovery  # noqa: E402


@pytest.mark.parametrize(
    "unicode_url, ascii_url",
    [
        ("https://bücher.de/path", "https://xn--bcher-kva.de/path"),
        ("https://BÜCHER.de./path", "https://xn--bcher-kva.de/path"),
        ("https://ｂücher.de/path", "https://xn--bcher-kva.de/path"),
        ("https://straße.de/path", "https://xn--strae-oqa.de/path"),
    ],
)
def test_sitemap_identity_uses_the_ascii_domain(unicode_url, ascii_url):
    assert discovery._host(unicode_url) == discovery._host(ascii_url)
    assert discovery._normalize_url(unicode_url) == discovery._normalize_url(ascii_url)


def test_idna_does_not_conflate_distinct_sharp_s_domains():
    assert discovery._normalize_url("https://straße.de/a") != discovery._normalize_url(
        "https://strasse.de/a"
    )


@pytest.mark.parametrize(
    "url",
    ["https://example.com/a", "https://[2001:4860:4860::8888]/a", "https://bad\u200dlabel.de/a"],
)
def test_host_comparison_remains_total_for_other_hosts(url):
    assert isinstance(discovery._host(url), str)
    assert isinstance(discovery._normalize_url(url), str)


def test_expansion_deduplicates_idn_urls_without_cross_host_warnings(monkeypatch):
    unicode_origin = "https://bücher.de"
    ascii_origin = "https://xn--bcher-kva.de"
    sitemap_url = ascii_origin + "/sitemap.xml"
    body = (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{unicode_origin}/a</loc></url>"
        f"<url><loc>{ascii_origin}/a</loc></url>"
        "</urlset>"
    ).encode()

    def fake_fetch(url, limit):
        path = urlparse(url).path
        content = b""
        final_url = url
        status = 404
        if path == "/robots.txt":
            status = 200
            content = f"Sitemap: {sitemap_url}\n".encode()
        elif path == "/sitemap.xml":
            status = 200
            content = body
            final_url = sitemap_url
        return {
            "status_code": status,
            "content": content,
            "content_type": "application/xml",
            "final_url": final_url,
            "too_large": False,
            "error": None,
        }

    monkeypatch.setattr(discovery, "_bounded_fetch", fake_fetch)
    result = discovery.discover_sitemaps(unicode_origin, expand=True)

    declared = next(item for item in result["checked"] if item["source"] == "robots.txt")
    assert not declared.get("cross_host", False)
    item = next(item for item in result["expanded"]["files"] if item["url"] == sitemap_url)
    assert item["cross_host_url_count"] == 0
    assert item["url_count"] == 2
    assert item["duplicate_count"] == 1
    assert result["expanded"]["totals"]["unique_urls"] == 1
    json.dumps(result)
