"""Shopify crawler: sitemap walk, origin binding of the signature, bounded reads, HTML signals, summary."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
pytest.importorskip("lxml")
pytest.importorskip("requests")

SPEC = importlib.util.spec_from_file_location("shopify_crawl", SCRIPTS / "shopify_crawl.py")
assert SPEC and SPEC.loader
crawl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(crawl)

SIG = {"Signature-Agent": '"https://shopify.com"', "Signature-Input": "sig1=(...)", "Signature": "sig1=:x:"}
ORIGIN = crawl.Origin("https", "shop.example")


class _Response:
    def __init__(self, status: int, content: bytes = b"", headers: dict | None = None):
        self.status_code = status
        self._content = content
        self.headers = headers or {}
        self.encoding = "utf-8"
        self.closed = False

    def iter_content(self, chunk_size=65536):
        for start in range(0, len(self._content), chunk_size):
            yield self._content[start:start + chunk_size]

    def close(self):
        self.closed = True


class _Session:
    """Serves canned responses and records which headers each URL received."""

    def __init__(self, routes: dict[str, _Response] | None = None, factory=None):
        self.routes = routes or {}
        self.factory = factory
        self.calls: list[tuple[str, dict]] = []
        self.headers: dict = {}

    def get(self, url, headers=None, **kwargs):
        self.calls.append((url, dict(headers or {})))
        if self.factory:
            return self.factory(url)
        return self.routes.get(url, _Response(404))


SITEMAP_INDEX = b"""<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://shop.example/sitemap_products_1.xml</loc></sitemap>
  <sitemap><loc>https://cdn.other.example/sitemap_evil.xml</loc></sitemap>
  <sitemap><loc>http://shop.example/sitemap_plain.xml</loc></sitemap>
</sitemapindex>"""

SITEMAP_PRODUCTS = b"""<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
  <url>
    <loc>https://shop.example/products/a</loc>
    <image:image><image:loc>https://cdn.shopify.com/a.jpg</image:loc></image:image>
  </url>
  <url><loc>https://shop.example/products/b</loc></url>
  <url><loc>https://shop.example/products/a</loc></url>
  <url><loc>https://elsewhere.example/products/c</loc></url>
  <url><loc>http://shop.example/products/plain</loc></url>
</urlset>"""


def test_sitemap_walk_stays_on_the_signed_origin_and_ignores_image_locs() -> None:
    session = _Session({
        "https://shop.example/sitemap.xml": _Response(200, SITEMAP_INDEX),
        "https://shop.example/sitemap_products_1.xml": _Response(200, SITEMAP_PRODUCTS),
        "https://cdn.other.example/sitemap_evil.xml": _Response(200, SITEMAP_PRODUCTS),
        "http://shop.example/sitemap_plain.xml": _Response(200, SITEMAP_PRODUCTS),
    })
    log: list[str] = []
    urls, stats = crawl.fetch_sitemap_urls(session, ORIGIN, crawl.RateLimitGovernor(0), sig_headers=SIG,
                                           robots_text="Sitemap: https://shop.example/sitemap.xml\n",
                                           log=log.append)
    assert urls == ["https://shop.example/products/a", "https://shop.example/products/b"]
    fetched = [url for url, _ in session.calls]
    assert fetched == ["https://shop.example/sitemap.xml", "https://shop.example/sitemap_products_1.xml"]
    assert all(headers.get("Signature") == "sig1=:x:" for url, headers in session.calls)
    assert stats["skipped_foreign"] == 4
    assert stats["discovery_capped"] is None


def test_sitemap_walk_stops_on_a_deep_index_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    def chain(url: str) -> _Response:
        level = int(url.rsplit("-", 1)[-1]) if "-" in url else 0
        body = (f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f'<sitemap><loc>https://shop.example/index-{level + 1}</loc></sitemap></sitemapindex>')
        return _Response(200, body.encode())

    session = _Session(factory=chain)
    urls, stats = crawl.fetch_sitemap_urls(session, ORIGIN, crawl.RateLimitGovernor(0), log=lambda _m: None)
    assert urls == []
    assert stats["discovery_capped"].startswith("sitemap index nested deeper than")
    assert stats["sitemaps_fetched"] == crawl.MAX_SITEMAP_DEPTH


def test_sitemap_walk_stops_at_the_sitemap_count_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crawl, "MAX_SITEMAPS", 3)
    many = "".join(f"<sitemap><loc>https://shop.example/child-{i}</loc></sitemap>" for i in range(10))

    def fan_out(url: str) -> _Response:
        if url.endswith("sitemap.xml"):
            return _Response(200, f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{many}</sitemapindex>'.encode())
        return _Response(200, f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{url}/p</loc></url></urlset>'.encode())

    session = _Session(factory=fan_out)
    urls, stats = crawl.fetch_sitemap_urls(session, ORIGIN, crawl.RateLimitGovernor(0), log=lambda _m: None)
    assert stats["sitemaps_fetched"] == 3
    assert stats["discovery_capped"] == "more than 3 sitemaps"
    assert len(urls) == 2


def test_oversized_sitemap_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crawl, "MAX_SITEMAP_BYTES", 100)
    big = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + b"<url><loc>https://shop.example/p</loc></url>" * 20 + b"</urlset>"
    session = _Session({"https://shop.example/sitemap.xml": _Response(200, big)})
    log: list[str] = []
    urls, _ = crawl.fetch_sitemap_urls(session, ORIGIN, crawl.RateLimitGovernor(0), log=log.append)
    assert urls == []
    assert any("larger than 100 bytes" in line for line in log)


def test_sitemap_with_doctype_is_rejected() -> None:
    with pytest.raises(ValueError):
        crawl.sitemap_locs(b'<!DOCTYPE x [<!ENTITY e "x">]><urlset><url><loc>&e;</loc></url></urlset>')


def test_signature_is_only_attached_to_the_issuing_origin() -> None:
    signed = crawl.headers_for("https://shop.example/products/a", ORIGIN, SIG)
    other_host = crawl.headers_for("https://www.shop.example/products/a", ORIGIN, SIG)
    cleartext = crawl.headers_for("http://shop.example/products/a", ORIGIN, SIG)
    assert signed["Signature-Input"] == "sig1=(...)"
    assert "Signature" not in other_host
    assert "Signature" not in cleartext
    assert other_host["User-Agent"] == crawl.USER_AGENT


def test_crawl_one_records_redirects_without_following() -> None:
    session = _Session({
        "https://shop.example/products/old": _Response(301, headers={"Location": "https://evil.example/"}),
    })
    record = crawl.crawl_one(lambda: session, "https://shop.example/products/old", ORIGIN, None,
                             crawl.RateLimitGovernor(0), timeout=5, save_html_dir=None)
    assert record["status"] == 301
    assert record["redirect_to"] == "https://evil.example/"
    assert record["html"] is False
    assert [url for url, _ in session.calls] == ["https://shop.example/products/old"]


def test_crawl_one_bounds_the_page_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crawl, "MAX_PAGE_BYTES", 1000)
    response = _Response(200, b"<html><title>big</title>" + b"x" * 5000, headers={"Content-Type": "text/html"})
    session = _Session({"https://shop.example/products/big": response})
    record = crawl.crawl_one(lambda: session, "https://shop.example/products/big", ORIGIN, None,
                             crawl.RateLimitGovernor(0), timeout=5, save_html_dir=None)
    assert record["too_large"] is True
    assert record["html"] is False
    assert "title" not in record
    assert response.closed


def test_crawl_one_uses_the_worker_session_and_analyzes_html() -> None:
    response = _Response(200, b"<html><title>Bottle</title><h1>x</h1></html>", headers={"Content-Type": "text/html; charset=utf-8"})
    session = _Session({"https://shop.example/products/a": response})
    calls = []

    def session_for():
        calls.append(1)
        return session

    record = crawl.crawl_one(session_for, "https://shop.example/products/a", ORIGIN, SIG,
                             crawl.RateLimitGovernor(0), timeout=5, save_html_dir=None)
    assert calls == [1]
    assert record["title"] == "Bottle"
    assert record["signed"] is True
    assert response.closed


def test_rate_limit_on_signed_request_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crawl.time, "sleep", lambda _seconds: None)
    session = _Session({"https://shop.example/products/a": _Response(430)})
    governor = crawl.RateLimitGovernor(0)
    record = crawl.crawl_one(lambda: session, "https://shop.example/products/a", ORIGIN, SIG,
                             governor, timeout=5, save_html_dir=None)
    assert record["rate_limited"] is True
    assert record["failed"] is True
    assert governor.hits == 4


def test_thread_sessions_are_per_thread() -> None:
    import threading

    sessions = crawl.ThreadSessions()
    seen = []

    def worker():
        seen.append(id(sessions.get()))
        seen.append(id(sessions.get()))

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(seen) == 6
    assert len(set(seen)) == 3
    sessions.close()


def test_classify_templates() -> None:
    assert crawl.classify("https://s.example/") == "home"
    assert crawl.classify("https://s.example/products/x") == "product"
    assert crawl.classify("https://s.example/collections/all") == "collection"
    assert crawl.classify("https://s.example/collections/all?filter=1") == "collection_filtered"
    assert crawl.classify("https://s.example/blogs/news/post") == "blog_article"
    assert crawl.classify("https://s.example/blogs/news") == "blog_index"
    assert crawl.classify("https://s.example/policies/refund-policy") == "policy"
    assert crawl.classify("https://s.example/pages/about") == "page"


def test_analyze_html_extracts_signals_from_visible_markup() -> None:
    html = """
    <html><head><title> Blue   Bottle </title>
    <meta name="description" content="A bottle.">
    <link rel="canonical" href="https://s.example/products/bottle">
    <link rel="alternate" hreflang="de" href="https://s.example/de/products/bottle">
    <script type="application/ld+json">{"@type": "Product", "offers": {"@type": "Offer"}}</script>
    </head><body><h1>Bottle</h1>
    <img src="a.jpg" alt="bottle"><img src="b.jpg">
    <script type="text/template"><img src="hidden.jpg"></script>
    <noscript><img src="ns.jpg"></noscript>
    <p>word word word</p></body></html>
    """
    signals = crawl.analyze_html(html)
    assert signals["title"] == "Blue Bottle"
    assert signals["meta_description_length"] == 9
    assert signals["canonical"] == "https://s.example/products/bottle"
    assert signals["hreflang"] == ["de"]
    assert signals["schema_types"] == ["Offer", "Product"]
    assert signals["h1_count"] == 1
    assert signals["image_count"] == 2
    assert signals["images_without_alt"] == 1


def test_summary_counts_only_html_documents_and_flags_duplicates() -> None:
    page = {"status": 200, "html": True, "template": "product", "elapsed_ms": 100,
            "content_type": "text/html", "title": "Same", "title_length": 4,
            "meta_description": None, "canonical": None, "h1_count": 0, "word_count": 10}
    records = [
        dict(page, url="https://s.example/products/a"),
        dict(page, url="https://s.example/products/b"),
        {"url": "https://s.example/agents.md", "status": 200, "html": False, "template": "page",
         "elapsed_ms": 50, "content_type": "text/markdown"},
        {"url": "https://s.example/products/gone", "status": 404, "template": "product"},
        {"url": "https://s.example/products/moved", "status": 301, "template": "product",
         "redirect_to": "https://s.example/products/a"},
        {"url": "https://s.example/products/huge", "status": 200, "html": False, "template": "product",
         "elapsed_ms": 900, "content_type": "text/html", "too_large": True},
    ]
    summary = crawl.summarize(records)
    assert summary["pages_crawled"] == 6
    assert summary["html_documents"] == 2
    assert summary["non_html_resources"] == 2
    assert summary["redirects"] == 1
    assert summary["too_large"] == 1
    assert summary["issues"]["missing_title"] == 0
    assert summary["issues"]["duplicate_titles"] == 2
    assert summary["issues"]["missing_meta_description"] == 2
    assert summary["issues"]["h1_missing"] == 2
    assert summary["duplicate_title_examples"] == ["Same"]
    assert summary["status_distribution"] == {"200": 4, "404": 1, "301": 1}


def test_settings_precedence_cli_over_block_over_global_over_builtin() -> None:
    args = SimpleNamespace(max_pages=None, concurrency=4, delay=None, timeout=None,
                           sample_per_template=None, include=None, exclude=None,
                           save_html=None, ignore_robots=None)
    env = {"crawl": {"max_pages": 100, "concurrency": 8, "delay": 0.5}}
    entry = {"crawl": {"max_pages": 200}}
    crawl.resolve_settings(args, env, entry, signed=True)
    assert args.concurrency == 4
    assert args.max_pages == 200
    assert args.delay == 0.5
    assert args.timeout == 30

    unsigned = SimpleNamespace(max_pages=None, concurrency=None, delay=None, timeout=None,
                               sample_per_template=None, include=None, exclude=None,
                               save_html=None, ignore_robots=None)
    crawl.resolve_settings(unsigned, {"crawl": {}}, None, signed=False)
    assert (unsigned.concurrency, unsigned.delay, unsigned.max_pages) == (2, 1.0, 0)


def test_main_refuses_unsafe_roots(capsys: pytest.CaptureFixture[str]) -> None:
    assert crawl.main(["http://127.0.0.1/", "--out", "unused"]) == 1
    assert "Error:" in capsys.readouterr().err
