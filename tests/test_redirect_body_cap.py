"""Bodies are read under a cap on every safe-fetch path, redirects included.

requests reads the whole body of each 3xx it follows (``resp.content`` in
``resolve_redirects``), decompressed and unbounded, before the caller sees
anything. url_safety caps that body with a response hook. render_page's raw
fetch reads the final body under MAX_PAGE_BYTES the way fetch_page does.

A real local server is used; it is reached through the narrow
CLAUDE_SEO_LOCAL_TARGETS allowlist, which covers the top-level URL only, and
the redirect stays on that host.
"""

from __future__ import annotations

import gzip
import http.server
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_page  # noqa: E402
import render_page  # noqa: E402
import url_safety  # noqa: E402

# 64 MiB of zeros compresses to about 64 KB: a small decompression bomb.
BOMB_SIZE = 64 * 1024 * 1024
BOMB = gzip.compress(b"\0" * BOMB_SIZE, compresslevel=9)
FINAL_HTML = b"<html><head><title>Final</title></head><body><p>Landed.</p></body></html>"
BIG_PAGE = b"<html><body>" + b"x" * (3 * 1024 * 1024) + b"</body></html>"


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (http.server API)
        if self.path == "/bomb-redirect":
            self.send_response(302)
            self.send_header("Location", "/final")
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(BOMB)))
            self.end_headers()
            self.wfile.write(BOMB)
        elif self.path == "/final":
            self._send(200, FINAL_HTML)
        elif self.path == "/big":
            self._send(200, BIG_PAGE)
        else:
            self._send(404, b"not found")

    def _send(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server(monkeypatch):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", f"127.0.0.1:{port}")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_safe_get_caps_the_body_of_a_redirect(server):
    resp = url_safety.safe_requests_get(f"{server}/bomb-redirect", timeout=10)
    assert resp.status_code == 200
    assert resp.content == FINAL_HTML
    assert [r.status_code for r in resp.history] == [302]
    assert resp.history[0].headers["Location"] == "/final"
    assert len(resp.history[0].content) <= url_safety.MAX_REDIRECT_BODY_BYTES


def test_safe_session_caps_the_body_of_a_redirect(server):
    with url_safety.safe_requests_session(f"{server}/bomb-redirect") as session:
        resp = session.get(f"{server}/bomb-redirect", timeout=10)
    assert resp.content == FINAL_HTML
    assert len(resp.history[0].content) <= url_safety.MAX_REDIRECT_BODY_BYTES


def test_fetch_page_follows_a_bomb_redirect_with_history_intact(server):
    result = fetch_page.fetch_page(f"{server}/bomb-redirect", timeout=10)
    assert result["error"] is None
    assert result["status_code"] == 200
    assert result["url"] == f"{server}/final"
    assert result["content"] == FINAL_HTML.decode()
    assert result["redirect_details"] == [{"url": f"{server}/bomb-redirect", "status_code": 302}]
    assert result["too_large"] is False


def test_redirect_cap_leaves_other_responses_and_caller_hooks_alone(server):
    seen = []
    resp = url_safety.safe_requests_get(
        f"{server}/final", timeout=10, hooks={"response": lambda r, *a, **k: seen.append(r.status_code)}
    )
    assert resp.content == FINAL_HTML
    assert seen == [200]


def test_render_page_raw_fetch_is_capped(server, monkeypatch):
    monkeypatch.setattr(render_page, "MAX_PAGE_BYTES", 1024 * 1024)
    result = render_page.render_page(f"{server}/big", mode="never")
    assert result["error"] is None
    assert result["mode_used"] == "raw"
    assert result["too_large"] is True
    assert 0 < len(result["raw_content"]) <= 1024 * 1024
    assert any("size cap" in d for d in result["render_diagnostics"])


def test_render_page_raw_fetch_reads_a_normal_page_whole(server):
    result = render_page.render_page(f"{server}/final", mode="never")
    assert result["error"] is None
    assert result["too_large"] is False
    assert result["raw_content"] == FINAL_HTML.decode()
