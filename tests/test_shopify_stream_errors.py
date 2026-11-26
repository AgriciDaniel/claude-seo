"""Stream failures must remain per-request failures, not abort the whole crawl."""

from __future__ import annotations

import io
import json

import pytest
from test_shopify_main import (
    HOST,
    PAGE,
    SECRET,
    _env,
    _Response,
    _signature_input,
    _Store,
    crawl,
    requests,
)
from test_shopify_main import (
    run as run,
)
from urllib3.response import HTTPResponse

ERRORS = (
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ConnectionError,
    requests.exceptions.ContentDecodingError,
)


class BrokenBody(_Response):
    def __init__(self, error_type=ERRORS[0]):
        super().__init__(200, headers={"Content-Type": "text/html"})
        self.error_type = error_type
        self.closed = False

    def iter_content(self, chunk_size=65536):
        yield b"<html><title>Incomplete page</title>"
        raise self.error_type(f"stream interrupted: sig1=:{SECRET}:")

    def close(self):
        self.closed = True


@pytest.mark.parametrize("error_type", ERRORS)
def test_stream_failure_retries_then_keeps_only_complete_html(run, tmp_path, error_type):
    broken = BrokenBody(error_type)
    attempts = []

    def page(url):
        attempts.append(url)
        return broken if len(attempts) == 1 else _Response(
            200, PAGE, {"Content-Type": "text/html"}
        )

    code, summary, _ = run(
        _Store(products=1, page=page), argv=["--save-html"],
        env_body=_env(_signature_input()),
    )
    assert code == 0 and len(attempts) == 2 and broken.closed
    assert summary["pages_ok"] == summary["html_documents"] == 1
    record = json.loads((tmp_path / "crawl/pages.jsonl").read_text())
    assert record["title"] == "Product"
    assert "error" not in record and "failed" not in record
    saved = list((tmp_path / "crawl/html").glob("*.html"))
    assert len(saved) == 1 and saved[0].read_bytes() == PAGE


@pytest.mark.parametrize("error_type", ERRORS)
def test_exhausted_stream_retries_are_failed_not_successful_html(run, tmp_path, error_type):
    responses = []

    def page(_url):
        response = BrokenBody(error_type)
        responses.append(response)
        return response

    code, summary, _ = run(
        _Store(products=1, page=page), argv=["--save-html"],
        env_body=_env(_signature_input()),
    )
    assert code == 0 and len(responses) == 4
    assert all(response.closed for response in responses)
    assert summary["pages_crawled"] == 1
    assert summary["pages_ok"] == summary["html_documents"] == 0
    assert summary["non_html_resources"] == 0
    record = json.loads((tmp_path / "crawl/pages.jsonl").read_text())
    assert record["status"] == 200 and record["failed"] is True
    assert record["html"] is False and "title" not in record
    assert "[signature removed]" in record["error"]
    assert list((tmp_path / "crawl/html").iterdir()) == []


@pytest.mark.parametrize("error_type", ERRORS)
def test_sitemap_stream_failure_does_not_discard_healthy_siblings(error_type):
    broken = BrokenBody(error_type)
    root = f"""<sitemapindex>
    <sitemap><loc>{HOST}/broken.xml</loc></sitemap>
    <sitemap><loc>{HOST}/healthy.xml</loc></sitemap></sitemapindex>"""
    healthy = f"<urlset><url><loc>{HOST}/products/good</loc></url></urlset>"
    store = _Store(
        sitemap=_Response(200, root.encode()),
        page=lambda url: broken if url.endswith("broken.xml") else _Response(200, healthy.encode()),
    )
    logs = []
    urls, stats = crawl.fetch_sitemap_urls(
        store, crawl.Origin("https", "shop.example"), crawl.RateLimitGovernor(0),
        sig_headers={"Signature": f"sig1=:{SECRET}:"}, log=logs.append,
    )
    assert urls == [f"{HOST}/products/good"]
    assert stats["sitemaps_fetched"] == 3 and broken.closed
    assert any("sitemap failed" in message and "broken.xml" in message for message in logs)
    assert SECRET not in "".join(logs)


def test_failed_page_is_recorded_without_losing_other_pages_and_can_resume(run, tmp_path):
    store = _Store(products=2, page=lambda url: BrokenBody() if url.endswith("/p0")
                   else _Response(200, PAGE, {"Content-Type": "text/html"}))
    code, summary, _ = run(store, env_body=_env(_signature_input()))
    assert code == 0 and summary["pages_crawled"] == 2 and summary["pages_ok"] == 1
    records = [json.loads(line) for line in (tmp_path / "crawl/pages.jsonl").read_text().splitlines()]
    assert sum(bool(record.get("failed")) for record in records) == 1
    assert len(store.page_urls()) == 5

    healthy = _Store(products=2)
    code, summary, _ = run(healthy, argv=["--resume"])
    assert code == 0 and summary["pages_crawled"] == summary["pages_ok"] == 2
    assert healthy.page_urls() == [f"{HOST}/products/p0"]


def test_failed_root_sitemap_returns_the_normal_discovery_error(run):
    broken = BrokenBody()
    store = _Store(sitemap=broken)
    code, summary, stderr = run(store, env_body=_env(_signature_input()))
    assert code == 1 and summary is None and broken.closed
    assert "sitemap failed" in stderr and "no sitemap URLs found" in stderr
    assert store.page_urls() == []


@pytest.mark.parametrize("error_type", ERRORS)
def test_broken_robots_body_keeps_the_existing_fail_closed_behavior(run, error_type):
    broken = BrokenBody(error_type)
    store = _Store(robots=broken)
    code, summary, stderr = run(store)
    assert code == 1 and summary is None and broken.closed
    assert "rules are unknown" in stderr
    assert [url for url, _ in store.calls] == [f"{HOST}/robots.txt"]


def test_real_requests_truncated_body_is_retried(run):
    # Exercise Requests/urllib3's actual incomplete-body exception conversion.
    response = requests.Response()
    response.status_code = 200
    response.headers["Content-Type"] = "text/html"
    response.encoding = "utf-8"
    response.raw = HTTPResponse(
        body=io.BytesIO(PAGE), headers={"Content-Length": str(len(PAGE) + 10)},
        preload_content=False, enforce_content_length=True,
    )
    attempts = []

    def page(url):
        attempts.append(url)
        return response if len(attempts) == 1 else _Response(
            200, PAGE, {"Content-Type": "text/html"}
        )

    code, summary, _ = run(_Store(products=1, page=page))
    assert code == 0 and len(attempts) == 2
    assert response.raw.closed and summary["html_documents"] == 1


def test_connect_failure_after_a_broken_stream_does_not_reuse_html_state(run, tmp_path):
    attempts = []

    def page(url):
        attempts.append(url)
        if len(attempts) == 1:
            return BrokenBody()
        raise requests.exceptions.ConnectionError("connection failed")

    code, summary, _ = run(_Store(products=1, page=page))
    assert code == 0 and len(attempts) == 4 and summary["pages_ok"] == 0
    record = json.loads((tmp_path / "crawl/pages.jsonl").read_text())
    assert record["failed"] is True and record["html"] is False
    assert record["error"] == "connection failed"
