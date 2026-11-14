"""Browser egress regression: redirects must not connect to local services."""

from __future__ import annotations

import http.server
import socket
import sys
import threading
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

pytest.importorskip("requests")
pytest.importorskip("playwright.sync_api")
import analyze_visual  # noqa: E402
import browser_proxy  # noqa: E402
import capture_screenshot  # noqa: E402
import render_page  # noqa: E402
import url_safety  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def test_browser_proxy_refuses_local_allowlist(monkeypatch):
    monkeypatch.setattr(browser_proxy, "validate_url_strict", lambda url: (url, "127.0.0.1"))
    with pytest.raises(url_safety.URLSafetyError, match="not public"):
        browser_proxy._destination("http://localhost:8000/")


@pytest.mark.parametrize(
    "request_bytes",
    [
        b"CONNECT 127.0.0.1:9000 HTTP/1.1\r\nHost: 127.0.0.1:9000\r\n\r\n",
        b"GET http://127.0.0.1:9000/ HTTP/1.1\r\nHost: 127.0.0.1:9000\r\n\r\n",
    ],
)
def test_proxy_refuses_direct_internal_connections(request_bytes):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), browser_proxy._ProxyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with socket.create_connection(("127.0.0.1", server.server_port), timeout=3) as client:
            client.sendall(request_bytes)
            assert b" 403 " in client.recv(1024)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_redirect_cannot_reach_internal_server(monkeypatch, tmp_path):
    with sync_playwright() as pw:
        if not Path(pw.chromium.executable_path).exists():
            pytest.skip("Playwright Chromium is not installed")

    hits = {"raw": 0, "browser": 0, "internal": 0}
    marker = "INTERNAL-SECURITY-TEST-MARKER"

    class Internal(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits["internal"] += 1
            body = marker.encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    internal = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Internal)

    class Public(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if "Chrome/" in self.headers.get("User-Agent", ""):
                hits["browser"] += 1
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{internal.server_port}/")
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                hits["raw"] += 1
                body = b"<html><body>Safe raw page</body></html>"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, *_args):
            pass

    public = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Public)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (internal, public)]
    for thread in threads:
        thread.start()

    public_host = "browser-egress.example"
    target = f"http://{public_host}:{public.server_port}/"
    original_dns = socket.getaddrinfo

    def public_dns(host, port, *args, **kwargs):
        if host == public_host:
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port or 80))]
        return original_dns(host, port, *args, **kwargs)

    real_destination = browser_proxy._destination

    def test_destination(url):
        if url.startswith(f"http://{public_host}:"):
            return "127.0.0.1", public_host, public.server_port
        return real_destination(url)

    import requests

    monkeypatch.setattr(url_safety.socket, "getaddrinfo", public_dns)
    monkeypatch.setattr(browser_proxy, "_destination", test_destination)
    monkeypatch.setattr(render_page, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(capture_screenshot, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(analyze_visual, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(
        render_page,
        "safe_requests_get",
        lambda *args, **kwargs: requests.get(f"http://127.0.0.1:{public.server_port}/", stream=True, timeout=5),
    )

    try:
        rendered = render_page.render_page(target, mode="always", timeout_ms=10000, extract_content=False)
        screenshot = capture_screenshot.capture_screenshot(target, str(tmp_path / "blocked.png"), timeout=10000)
        visual = analyze_visual.analyze_visual(target, timeout=10000)
        assert hits["raw"] == 1
        assert hits["browser"] >= 3
        assert hits["internal"] == 0
        assert rendered["error"] and marker not in (rendered["content"] or "")
        assert not screenshot["success"] and screenshot["error"]
        assert not (tmp_path / "blocked.png").exists()
        assert visual["error"]
    finally:
        for server in (public, internal):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)
