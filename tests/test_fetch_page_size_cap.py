"""fetch_page.py stops reading a body past its size cap (after decompression).

A tiny gzip body can inflate without bound; the cap counts decompressed
bytes, so it holds. The server is a local stub reached through a fake
session, so no network is used.
"""

from __future__ import annotations

import gzip
import io
import sys
from contextlib import contextmanager
from pathlib import Path

import requests
from urllib3.response import HTTPResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_page  # noqa: E402
import url_safety  # noqa: E402


def _streamed_response(body: bytes, *, gzipped: bool = False) -> requests.Response:
    """A streamed requests.Response built the way the HTTP adapter builds one."""
    headers = {"Content-Type": "text/html; charset=utf-8"}
    payload = body
    if gzipped:
        payload = gzip.compress(body)
        headers["Content-Encoding"] = "gzip"
    raw = HTTPResponse(body=io.BytesIO(payload), headers=headers, status=200, preload_content=False)
    resp = requests.Response()
    resp.status_code = 200
    resp.headers.update(headers)
    resp.raw = raw
    resp.url = "https://example.com/"
    return resp


def _patched_fetch(monkeypatch, response: requests.Response, **kwargs) -> dict:
    seen = {}

    class _Session:
        max_redirects = 5

        def get(self, url, **kw):
            seen.update(kw)
            return response

    @contextmanager
    def fake_session(_url):
        yield _Session()

    monkeypatch.setattr(fetch_page, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(fetch_page, "safe_requests_session", fake_session)
    result = fetch_page.fetch_page("https://example.com/", **kwargs)
    result["_stream"] = seen.get("stream")
    return result


def test_gzip_bomb_is_cut_at_the_cap(monkeypatch):
    bomb = _streamed_response(b"A" * (8 * 1024 * 1024), gzipped=True)  # ~8 KB on the wire
    result = _patched_fetch(monkeypatch, bomb, max_bytes=1024 * 1024)
    assert result["_stream"] is True
    assert result["error"] is None
    assert result["too_large"] is True
    assert 0 < len(result["content"]) <= 1024 * 1024


def test_normal_page_is_read_whole_and_decoded(monkeypatch):
    page = _streamed_response("<html><title>Café</title></html>".encode())
    result = _patched_fetch(monkeypatch, page)
    assert result["too_large"] is False
    assert result["content"] == "<html><title>Café</title></html>"


def test_cap_is_reported_in_the_json_contract():
    rendered = fetch_page._as_render_result({"too_large": True, "content": "x"}, mode_used="raw")
    assert rendered["render_diagnostics"] and "size cap" in rendered["render_diagnostics"][0]
    assert fetch_page._as_render_result({"content": "x"}, mode_used="raw")["render_diagnostics"] == []


def test_read_bounded_counts_decompressed_bytes():
    raw, too_large = url_safety.read_bounded(_streamed_response(b"B" * 300_000, gzipped=True), 100_000)
    assert too_large is True and len(raw) <= 100_000
    raw, too_large = url_safety.read_bounded(_streamed_response(b"B" * 50_000), 100_000)
    assert too_large is False and raw == b"B" * 50_000
