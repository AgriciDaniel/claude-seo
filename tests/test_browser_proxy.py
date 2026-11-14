"""Browser egress regression: redirects must not connect to local services."""

from __future__ import annotations

import http.server
import re
import socket
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

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

PUBLIC_HOST = "public.example"


def _exchange(proxy_url: str, request: bytes, *, timeout: float = 5) -> bytes:
    """Send raw bytes to the guard and return everything it answers."""
    port = int(proxy_url.rsplit(":", 1)[1])
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as client:
        client.sendall(request)
        chunks = []
        while chunk := client.recv(65536):
            chunks.append(chunk)
        return b"".join(chunks)


class _Origin:
    """A loopback server standing in for a public site or an upstream proxy.

    ``respond(handler)`` writes the answer. Each request is recorded as
    ``(request_line, headers, body)``.
    """

    def __init__(self, respond=None):
        self.requests: list[tuple[str, dict, bytes]] = []
        origin = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _handle(self):
                size = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(size) if size else b""
                headers = {}
                for key, value in self.headers.items():
                    headers.setdefault(key.lower(), []).append(value)
                origin.requests.append((self.requestline, headers, body))
                (respond or _plain_ok)(self)

            do_GET = do_POST = do_HEAD = do_PUT = do_CONNECT = _handle

            def log_message(self, *_args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def _plain_ok(handler):
    body = b"origin body"
    handler.send_response_only(200, "OK")
    handler.send_header("Server", "origin-server")
    handler.send_header("Set-Cookie", "a=1")
    handler.send_header("Set-Cookie", "b=2")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


@pytest.fixture
def origin():
    server = _Origin()
    yield server
    server.close()


def _map_public_host(monkeypatch, port: int) -> None:
    """Treat ``public.example`` as a public site that lives on loopback."""
    real = browser_proxy._destination

    def mapped(url):
        if urlsplit(url).hostname == PUBLIC_HOST:
            return "127.0.0.1", PUBLIC_HOST, urlsplit(url).port or port
        return real(url)

    monkeypatch.setattr(browser_proxy, "_destination", mapped)


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch):
    """No test inherits the developer's proxy, allowlist or sandbox opt-out."""
    monkeypatch.setattr(url_safety.requests.utils, "getproxies", lambda: {})
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)
    monkeypatch.setattr(browser_proxy.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.delenv(browser_proxy.NO_SANDBOX_ENV, raising=False)


def test_browser_proxy_refuses_local_allowlist(monkeypatch):
    monkeypatch.setattr(
        browser_proxy, "validate_public_url_strict", lambda url: (url, "127.0.0.1")
    )
    with pytest.raises(url_safety.URLSafetyError, match="not public"):
        browser_proxy._destination("http://localhost:8000/")


@pytest.mark.parametrize(
    "url",
    ["http://localhost:3000/", "http://127.0.0.1:8080/", "http://100.101.102.103/"],
)
def test_browser_proxy_never_reads_the_operator_allowlist(monkeypatch, url):
    """Rendering an allowlisted local target was refused before the guard
    existed (the route handler never read the allowlist) and still is."""
    monkeypatch.setenv(
        "CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000,127.0.0.1:8080,100.101.102.103"
    )
    loopback = lambda host, port, *a, **k: [  # noqa: E731
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port or 0))
    ]
    monkeypatch.setattr(url_safety.socket, "getaddrinfo", loopback)
    # The raw-HTTP validator admits it; the browser guard does not.
    assert url_safety.validate_url_strict(url)[0] == url
    with pytest.raises(url_safety.URLSafetyError):
        browser_proxy._destination(url)


@pytest.mark.parametrize(
    "request_bytes",
    [
        b"CONNECT 127.0.0.1:9000 HTTP/1.1\r\nHost: 127.0.0.1:9000\r\n\r\n",
        b"GET http://127.0.0.1:9000/ HTTP/1.1\r\nHost: 127.0.0.1:9000\r\n\r\n",
    ],
)
def test_proxy_refuses_direct_internal_connections(request_bytes):
    with browser_proxy.guarded_proxy() as proxy:
        assert b" 403 " in _exchange(proxy, request_bytes)


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


# ---------------------------------------------------------------------------
# The proxy itself: what it refuses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "request_bytes",
    [
        # Origin-form: the Host header never chooses the destination.
        b"GET / HTTP/1.1\r\nHost: 127.0.0.1:9000\r\n\r\n",
        b"GET /latest/meta-data/ HTTP/1.1\r\nHost: 169.254.169.254\r\n\r\n",
        # Loopback, private, link-local and metadata destinations.
        b"GET http://localhost:9000/ HTTP/1.1\r\nHost: x\r\n\r\n",
        b"GET http://10.0.0.5/ HTTP/1.1\r\nHost: x\r\n\r\n",
        b"GET http://169.254.169.254/latest/meta-data/ HTTP/1.1\r\nHost: x\r\n\r\n",
        b"GET http://[::1]:9000/ HTTP/1.1\r\nHost: x\r\n\r\n",
        b"GET http://[::ffff:127.0.0.1]/ HTTP/1.1\r\nHost: x\r\n\r\n",
        b"GET http://2130706433/ HTTP/1.1\r\nHost: x\r\n\r\n",
        b"GET http://0x7f.0.0.1/ HTTP/1.1\r\nHost: x\r\n\r\n",
        # Credentials and parser-confusion forms.
        b"GET http://user:pw@127.0.0.1/ HTTP/1.1\r\nHost: x\r\n\r\n",
        b"GET http://public.example@127.0.0.1/ HTTP/1.1\r\nHost: x\r\n\r\n",
        b"GET http://public.example\\@127.0.0.1/ HTTP/1.1\r\nHost: x\r\n\r\n",
        # Only plain HTTP is forwarded; other schemes never open a socket.
        b"GET https://127.0.0.1/ HTTP/1.1\r\nHost: x\r\n\r\n",
        b"GET file:///etc/passwd HTTP/1.1\r\nHost: x\r\n\r\n",
        b"GET ftp://127.0.0.1/ HTTP/1.1\r\nHost: x\r\n\r\n",
        b"GET gopher://127.0.0.1:6379/_INFO HTTP/1.1\r\nHost: x\r\n\r\n",
        # CONNECT: any port, IPv6, and malformed authority forms.
        b"CONNECT localhost:22 HTTP/1.1\r\nHost: x\r\n\r\n",
        b"CONNECT 169.254.169.254:80 HTTP/1.1\r\nHost: x\r\n\r\n",
        b"CONNECT [::1]:443 HTTP/1.1\r\nHost: x\r\n\r\n",
        b"CONNECT [fd00:ec2::254]:80 HTTP/1.1\r\nHost: x\r\n\r\n",
        b"CONNECT 127.0.0.1:80@public.example:443 HTTP/1.1\r\nHost: x\r\n\r\n",
        b"CONNECT public.example:443/path HTTP/1.1\r\nHost: x\r\n\r\n",
        b"CONNECT public.example HTTP/1.1\r\nHost: x\r\n\r\n",
        b"CONNECT http://127.0.0.1:80/ HTTP/1.1\r\nHost: x\r\n\r\n",
        b"CONNECT 127.0.0.1:99999 HTTP/1.1\r\nHost: x\r\n\r\n",
    ],
)
def test_proxy_refuses_unsafe_or_malformed_targets(monkeypatch, origin, request_bytes):
    """``public.example`` itself is reachable here, so a refusal below is
    about the request's form or its real destination, not about DNS."""
    _map_public_host(monkeypatch, origin.port)
    with browser_proxy.guarded_proxy() as proxy:
        assert b" 403 " in _exchange(proxy, request_bytes).split(b"\r\n", 1)[0] + b" "
    assert origin.requests == []


def test_proxy_refuses_before_reading_the_environment_allowlist(monkeypatch):
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "127.0.0.1:9000,localhost:9000")
    with browser_proxy.guarded_proxy() as proxy:
        for line in (b"GET http://127.0.0.1:9000/", b"CONNECT localhost:9000"):
            answer = _exchange(proxy, line + b" HTTP/1.1\r\nHost: x\r\n\r\n")
            assert answer.startswith(b"HTTP/1.0 403 ")


# ---------------------------------------------------------------------------
# The proxy itself: plain-HTTP forwarding
# ---------------------------------------------------------------------------


def test_forwarding_rebuilds_host_and_drops_hop_headers(monkeypatch, origin):
    _map_public_host(monkeypatch, origin.port)
    request = (
        f"GET http://{PUBLIC_HOST}:{origin.port}/a/b?x=1&y=2 HTTP/1.1\r\n"
        "Host: 127.0.0.1:1\r\n"
        "Proxy-Authorization: Basic c2VjcmV0\r\n"
        "Proxy-Connection: keep-alive\r\n"
        "Connection: keep-alive, X-Per-Hop\r\n"
        "X-Per-Hop: drop-me\r\n"
        "Accept-Encoding: gzip\r\n"
        "Cookie: a=1\r\n"
        "X-Keep: yes\r\n\r\n"
    ).encode()
    with browser_proxy.guarded_proxy() as proxy:
        answer = _exchange(proxy, request)

    (request_line, headers, body), = origin.requests
    assert request_line == "GET /a/b?x=1&y=2 HTTP/1.1"
    assert headers["host"] == [f"{PUBLIC_HOST}:{origin.port}"]
    assert headers["x-keep"] == ["yes"] and headers["cookie"] == ["a=1"]
    assert headers["accept-encoding"] == ["gzip"]
    assert headers["connection"] == ["close"]
    for dropped in ("proxy-authorization", "proxy-connection", "x-per-hop"):
        assert dropped not in headers
    assert body == b""

    head, _, payload = answer.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.0 200 OK")
    assert payload == b"origin body"
    # The page's own headers reach the audit: nothing of the proxy is added
    # and repeated headers are kept.
    lines = head.decode().split("\r\n")[1:]
    assert [line for line in lines if line.lower().startswith("server:")] == [
        "Server: origin-server"
    ]
    assert not [line for line in lines if line.lower().startswith("date:")]
    assert [line for line in lines if line.startswith("Set-Cookie:")] == [
        "Set-Cookie: a=1",
        "Set-Cookie: b=2",
    ]


def test_forwarding_sends_the_request_body(monkeypatch, origin):
    _map_public_host(monkeypatch, origin.port)
    request = (
        f"POST http://{PUBLIC_HOST}:{origin.port}/submit HTTP/1.1\r\n"
        "Host: x\r\nContent-Type: text/plain\r\nContent-Length: 5\r\n\r\nhello"
    ).encode()
    with browser_proxy.guarded_proxy() as proxy:
        assert _exchange(proxy, request).startswith(b"HTTP/1.0 200 ")
    (request_line, headers, body), = origin.requests
    assert request_line.startswith("POST /submit ")
    assert headers["content-length"] == ["5"] and body == b"hello"


@pytest.mark.parametrize(
    "extra_headers,status",
    [
        ("Content-Length: 5\r\nContent-Length: 0\r\n", b"400"),
        ("Content-Length: 5_0\r\n", b"400"),
        ("Content-Length: -1\r\n", b"400"),
        ("Content-Length: +5\r\n", b"400"),
        ("Transfer-Encoding: chunked\r\n", b"501"),
        ("Content-Length: 5\r\nTransfer-Encoding: chunked\r\n", b"501"),
        (f"Content-Length: {11 * 1024 * 1024}\r\n", b"413"),
    ],
)
def test_ambiguous_request_framing_is_never_forwarded(
    monkeypatch, origin, extra_headers, status
):
    """Request smuggling needs two parsers to disagree about where a body
    ends. The proxy forwards one unambiguous length or nothing."""
    _map_public_host(monkeypatch, origin.port)
    request = (
        f"POST http://{PUBLIC_HOST}:{origin.port}/ HTTP/1.1\r\nHost: x\r\n"
        f"{extra_headers}\r\nhello"
    ).encode()
    with browser_proxy.guarded_proxy() as proxy:
        assert _exchange(proxy, request).split(b" ")[1] == status
    assert origin.requests == []


def test_unreachable_destination_gets_no_response(monkeypatch):
    """A proxy error page would be rendered, and reported, as the site's own
    answer. Dropping the connection makes the browser report a failed load."""
    with socket.socket() as placeholder:
        placeholder.bind(("127.0.0.1", 0))
        closed_port = placeholder.getsockname()[1]
    _map_public_host(monkeypatch, closed_port)
    request = f"GET http://{PUBLIC_HOST}:{closed_port}/ HTTP/1.1\r\nHost: x\r\n\r\n".encode()
    with browser_proxy.guarded_proxy() as proxy:
        assert _exchange(proxy, request) == b""
        connect = f"CONNECT {PUBLIC_HOST}:{closed_port} HTTP/1.1\r\nHost: x\r\n\r\n".encode()
        assert _exchange(proxy, connect).startswith(b"HTTP/1.0 502 ")


def test_a_response_cut_short_gets_no_error_page_appended(monkeypatch):
    def truncated(handler):
        handler.send_response_only(200, "OK")
        handler.send_header("Content-Length", "100")
        handler.end_headers()
        handler.wfile.write(b"0123456789")

    server = _Origin(truncated)
    try:
        _map_public_host(monkeypatch, server.port)
        request = f"GET http://{PUBLIC_HOST}:{server.port}/ HTTP/1.1\r\nHost: x\r\n\r\n".encode()
        with browser_proxy.guarded_proxy() as proxy:
            answer = _exchange(proxy, request)
    finally:
        server.close()
    assert answer.count(b"HTTP/1.0 ") == 1
    assert b"Destination refused" not in answer and b"Error response" not in answer


# ---------------------------------------------------------------------------
# The proxy itself: CONNECT tunnels and shutdown
# ---------------------------------------------------------------------------


class _EchoServer:
    """Accepts TCP connections and echoes what it reads, upper-cased."""

    def __init__(self):
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.connections = 0
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            self.connections += 1
            threading.Thread(target=self._echo, args=(conn,), daemon=True).start()

    @staticmethod
    def _echo(conn):
        with conn:
            while data := conn.recv(4096):
                conn.sendall(data.upper())

    def close(self):
        self.listener.close()


def _open_tunnel(proxy_url: str, target: str) -> tuple[socket.socket, bytes]:
    port = int(proxy_url.rsplit(":", 1)[1])
    client = socket.create_connection(("127.0.0.1", port), timeout=5)
    client.sendall(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = client.recv(4096)
        if not chunk:
            break
        head += chunk
    return client, head


def test_connect_tunnel_relays_both_directions(monkeypatch):
    echo = _EchoServer()
    try:
        _map_public_host(monkeypatch, echo.port)
        with browser_proxy.guarded_proxy() as proxy:
            client, head = _open_tunnel(proxy, f"{PUBLIC_HOST}:{echo.port}")
            with client:
                assert head.startswith(b"HTTP/1.0 200 ")
                client.sendall(b"ping")
                assert client.recv(4096) == b"PING"
                client.sendall(b"again")
                assert client.recv(4096) == b"AGAIN"
    finally:
        echo.close()


def test_shutdown_does_not_wait_for_an_open_tunnel(monkeypatch):
    echo = _EchoServer()
    try:
        _map_public_host(monkeypatch, echo.port)
        started = time.monotonic()
        with browser_proxy.guarded_proxy() as proxy:
            client, head = _open_tunnel(proxy, f"{PUBLIC_HOST}:{echo.port}")
            assert head.startswith(b"HTTP/1.0 200 ")
        # The tunnel is idle and still open; leaving the block must not hang
        # for the idle timeout.
        assert time.monotonic() - started < 5
        client.close()
        port = int(proxy.rsplit(":", 1)[1])
        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=2).close()
    finally:
        echo.close()


# ---------------------------------------------------------------------------
# Chaining to the operator's HTTP proxy (HTTPS_PROXY and friends)
# ---------------------------------------------------------------------------


def test_plain_http_is_chained_in_absolute_form(monkeypatch):
    upstream = _Origin()
    try:
        _map_public_host(monkeypatch, 8080)
        monkeypatch.setattr(
            browser_proxy,
            "upstream_http_proxy",
            lambda url: ("127.0.0.1", upstream.port, "Basic dTpw"),
        )
        request = (
            f"GET http://{PUBLIC_HOST}:8080/p?q=1 HTTP/1.1\r\n"
            "Host: x\r\nProxy-Authorization: Basic from-the-page\r\n\r\n"
        ).encode()
        with browser_proxy.guarded_proxy() as proxy:
            assert _exchange(proxy, request).startswith(b"HTTP/1.0 200 ")
    finally:
        upstream.close()
    (request_line, headers, _body), = upstream.requests
    assert request_line == f"GET http://{PUBLIC_HOST}:8080/p?q=1 HTTP/1.1"
    assert headers["host"] == [f"{PUBLIC_HOST}:8080"]
    # The operator's credential, never one the page supplied.
    assert headers["proxy-authorization"] == ["Basic dTpw"]


def test_connect_is_chained_through_the_upstream_proxy(monkeypatch):
    seen = {}

    def upstream_proxy(listener):
        conn, _ = listener.accept()
        with conn:
            head = b""
            while b"\r\n\r\n" not in head:
                head += conn.recv(4096)
            seen["head"] = head
            # Bytes sent right behind the response head must not be lost.
            conn.sendall(b"HTTP/1.1 200 Connection established\r\n\r\nEARLY")
            while data := conn.recv(4096):
                conn.sendall(data.upper())

    listener = socket.create_server(("127.0.0.1", 0))
    threading.Thread(target=upstream_proxy, args=(listener,), daemon=True).start()
    try:
        _map_public_host(monkeypatch, 443)
        monkeypatch.setattr(
            browser_proxy,
            "upstream_http_proxy",
            lambda url: ("127.0.0.1", listener.getsockname()[1], "Basic dTpw"),
        )
        with browser_proxy.guarded_proxy() as proxy:
            client, head = _open_tunnel(proxy, f"{PUBLIC_HOST}:443")
            with client:
                assert head.startswith(b"HTTP/1.0 200 ")
                early = head.partition(b"\r\n\r\n")[2]
                while len(early) < 5:
                    early += client.recv(4096)
                assert early == b"EARLY"
                client.sendall(b"hello")
                assert client.recv(4096) == b"HELLO"
    finally:
        listener.close()
    lines = seen["head"].decode().split("\r\n")
    assert lines[0] == f"CONNECT {PUBLIC_HOST}:443 HTTP/1.1"
    assert f"Host: {PUBLIC_HOST}:443" in lines
    assert "Proxy-Authorization: Basic dTpw" in lines


def test_upstream_proxy_refusal_is_a_502(monkeypatch):
    def deny(handler):
        handler.send_response_only(407, "Proxy Authentication Required")
        handler.end_headers()

    upstream = _Origin(deny)
    try:
        _map_public_host(monkeypatch, 443)
        monkeypatch.setattr(
            browser_proxy, "upstream_http_proxy", lambda url: ("127.0.0.1", upstream.port, None)
        )
        with browser_proxy.guarded_proxy() as proxy:
            _client, head = _open_tunnel(proxy, f"{PUBLIC_HOST}:443")
            _client.close()
    finally:
        upstream.close()
    assert head.startswith(b"HTTP/1.0 502 ")


def test_destination_is_validated_before_the_upstream_proxy_is_contacted(monkeypatch):
    upstream = _Origin()
    try:
        monkeypatch.setattr(
            browser_proxy, "upstream_http_proxy", lambda url: ("127.0.0.1", upstream.port, None)
        )
        with browser_proxy.guarded_proxy() as proxy:
            for line in (
                b"GET http://127.0.0.1:9000/",
                b"GET http://169.254.169.254/",
                b"CONNECT 10.0.0.5:443",
                b"CONNECT localhost:8080",
            ):
                answer = _exchange(proxy, line + b" HTTP/1.1\r\nHost: x\r\n\r\n")
                assert answer.startswith(b"HTTP/1.0 403 ")
    finally:
        upstream.close()
    assert upstream.requests == []


def test_an_unusable_upstream_proxy_refuses_instead_of_going_direct(monkeypatch, origin):
    _map_public_host(monkeypatch, origin.port)

    def refused(url):
        raise url_safety.URLSafetyError("Refusing configured HTTP proxy")

    monkeypatch.setattr(browser_proxy, "upstream_http_proxy", refused)
    with browser_proxy.guarded_proxy() as proxy:
        for line in (
            f"GET http://{PUBLIC_HOST}:{origin.port}/".encode(),
            f"CONNECT {PUBLIC_HOST}:{origin.port}".encode(),
        ):
            answer = _exchange(proxy, line + b" HTTP/1.1\r\nHost: x\r\n\r\n")
            assert answer.startswith(b"HTTP/1.0 403 ")
    assert origin.requests == []


# ---------------------------------------------------------------------------
# require_public_page: what a finished navigation may be reported as
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", ["about:blank", "", "chrome-error://chromewebdata/"])
def test_blank_and_error_pages_are_a_failed_load_not_a_safety_error(url):
    with pytest.raises(browser_proxy.PageNotLoadedError):
        browser_proxy.require_public_page(SimpleNamespace(url=url))


@pytest.mark.parametrize(
    "url",
    [
        "data:text/html,<h1>x</h1>",
        "file:///etc/passwd",
        "blob:https://public.example/1",
        "chrome://settings/",
        "http://127.0.0.1:9000/",
        "http://169.254.169.254/latest/meta-data/",
        "https://localhost/",
    ],
)
def test_non_public_or_non_http_documents_are_a_safety_error(url):
    with pytest.raises(url_safety.URLSafetyError):
        browser_proxy.require_public_page(SimpleNamespace(url=url))


def test_public_page_passes(monkeypatch):
    _map_public_host(monkeypatch, 443)
    page = SimpleNamespace(url=f"https://{PUBLIC_HOST}/landing?x=1#top")
    assert browser_proxy.require_public_page(page) is None


# ---------------------------------------------------------------------------
# Chromium launch: sandbox on by default, explicit opt-out
# ---------------------------------------------------------------------------


class _FakeBrowserType:
    def __init__(self, error=None):
        self.error = error
        self.calls: list[dict] = []
        self.browser = SimpleNamespace(closed=0)
        self.browser.close = lambda: setattr(self.browser, "closed", self.browser.closed + 1)

    def launch(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.browser


@pytest.fixture
def regular_user(monkeypatch):
    monkeypatch.setattr(browser_proxy.os, "geteuid", lambda: 1000, raising=False)


def test_chromium_launches_sandboxed_and_proxied_by_default(regular_user):
    browser_type = _FakeBrowserType()
    with browser_proxy.guarded_chromium(browser_type) as browser:
        assert browser is browser_type.browser
    (kwargs,) = browser_type.calls
    assert kwargs["chromium_sandbox"] is True
    assert kwargs["headless"] is True
    assert re.fullmatch(r"http://127\.0\.0\.1:\d+", kwargs["proxy"]["server"])
    assert kwargs["proxy"]["bypass"] == ""
    assert "--proxy-bypass-list=<-loopback>" in kwargs["args"]
    assert "--disable-quic" in kwargs["args"]
    assert "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" in kwargs["args"]
    assert "--no-sandbox" not in kwargs["args"]
    assert browser_type.browser.closed == 1


@pytest.mark.parametrize("value", ["1", "true", " YES "])
def test_no_sandbox_opt_out_is_explicit(monkeypatch, regular_user, value):
    monkeypatch.setenv("CLAUDE_SEO_CHROMIUM_NO_SANDBOX", value)
    browser_type = _FakeBrowserType()
    with browser_proxy.guarded_chromium(browser_type):
        pass
    assert browser_type.calls[0]["chromium_sandbox"] is False


@pytest.mark.parametrize("value", ["", "0", "false", "no"])
def test_other_values_keep_the_sandbox(monkeypatch, regular_user, value):
    monkeypatch.setenv("CLAUDE_SEO_CHROMIUM_NO_SANDBOX", value)
    browser_type = _FakeBrowserType()
    with browser_proxy.guarded_chromium(browser_type):
        pass
    assert browser_type.calls[0]["chromium_sandbox"] is True


def test_root_gets_a_clear_error_before_launch(monkeypatch):
    monkeypatch.setattr(browser_proxy.os, "geteuid", lambda: 0, raising=False)
    browser_type = _FakeBrowserType()
    with pytest.raises(browser_proxy.ChromiumSandboxError) as excinfo:
        with browser_proxy.guarded_chromium(browser_type):
            pass
    assert "CLAUDE_SEO_CHROMIUM_NO_SANDBOX=1" in str(excinfo.value)
    assert "root" in str(excinfo.value)
    assert browser_type.calls == []

    monkeypatch.setenv("CLAUDE_SEO_CHROMIUM_NO_SANDBOX", "1")
    with browser_proxy.guarded_chromium(browser_type):
        pass
    assert browser_type.calls[0]["chromium_sandbox"] is False


@pytest.mark.parametrize(
    "log",
    [
        "BrowserType.launch: Target page, context or browser has been closed\n"
        "Browser logs:\nChromium sandboxing failed!\n====",
        "[pid] zygote_host_impl_linux.cc(128)] No usable sandbox! If you are running on Ubuntu",
        "Running as root without --no-sandbox is not supported. See https://crbug.com/638180.",
        "Failed to move to new namespace: PID namespaces supported, Network namespace "
        "supported, but failed: errno = Operation not permitted",
    ],
)
def test_sandbox_launch_failure_names_the_opt_out(regular_user, log):
    browser_type = _FakeBrowserType(error=RuntimeError(log))
    with pytest.raises(browser_proxy.ChromiumSandboxError) as excinfo:
        with browser_proxy.guarded_chromium(browser_type):
            pass
    assert "CLAUDE_SEO_CHROMIUM_NO_SANDBOX=1" in str(excinfo.value)
    assert excinfo.value.__cause__ is browser_type.error


def test_other_launch_failures_are_not_blamed_on_the_sandbox(monkeypatch, regular_user):
    error = RuntimeError("BrowserType.launch: Executable doesn't exist at /x/chrome")
    browser_type = _FakeBrowserType(error=error)
    with pytest.raises(RuntimeError) as excinfo:
        with browser_proxy.guarded_chromium(browser_type):
            pass
    assert excinfo.value is error

    # With the opt-out set, a sandbox message is not ours to rewrite either.
    monkeypatch.setenv("CLAUDE_SEO_CHROMIUM_NO_SANDBOX", "1")
    error = RuntimeError("No usable sandbox!")
    browser_type = _FakeBrowserType(error=error)
    with pytest.raises(RuntimeError) as excinfo:
        with browser_proxy.guarded_chromium(browser_type):
            pass
    assert excinfo.value is error


def test_guard_proxy_stops_when_the_browser_block_ends(regular_user):
    browser_type = _FakeBrowserType()
    with browser_proxy.guarded_chromium(browser_type):
        port = int(browser_type.calls[0]["proxy"]["server"].rsplit(":", 1)[1])
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=2).close()


def test_a_failing_browser_close_does_not_mask_the_real_error(regular_user):
    browser_type = _FakeBrowserType()

    def broken_close():
        raise RuntimeError("browser already crashed")

    browser_type.browser.close = broken_close
    with pytest.raises(ValueError, match="the real error"):
        with browser_proxy.guarded_chromium(browser_type):
            raise ValueError("the real error")


def test_unusable_configured_proxy_is_reported_before_launch(monkeypatch, regular_user):
    """HTTPS_PROXY on loopback is refused on the raw-HTTP path. The browser
    path says so up front instead of failing every request with a 403."""
    monkeypatch.setattr(
        url_safety.requests.utils, "getproxies", lambda: {"https": "http://127.0.0.1:3128"}
    )
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    browser_type = _FakeBrowserType()
    with pytest.raises(url_safety.URLSafetyError, match="Refusing configured HTTP proxy"):
        with browser_proxy.guarded_chromium(browser_type, "https://example.com/"):
            pass
    assert browser_type.calls == []


def test_no_script_launches_chromium_outside_the_guard():
    """Every browser launch goes through guarded_chromium: sandboxed and
    behind the egress guard. A direct launch elsewhere would have neither."""
    root = SCRIPTS.parent
    pattern = re.compile(
        r"(chromium|firefox|webkit)\s*\.\s*launch|launch_persistent_context|connect_over_cdp"
    )
    offenders = []
    for folder in ("scripts", "extensions", "skills", "agents", "hooks"):
        for path in (root / folder).rglob("*"):
            if path.suffix not in (".py", ".js", ".cjs", ".mjs", ".ts", ".sh"):
                continue
            if path.name == "browser_proxy.py":
                continue
            if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append(str(path.relative_to(root)))
    assert offenders == []
    for name in ("render_page.py", "capture_screenshot.py", "analyze_visual.py"):
        assert "guarded_chromium(p.chromium" in (SCRIPTS / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# analyze_visual: the same page check, on its normal error path
# ---------------------------------------------------------------------------


class _VisualManager:
    """A Playwright stand-in whose page lands on ``final_url``."""

    def __init__(self, final_url):
        self.page = SimpleNamespace(
            url=final_url,
            route=lambda *_a: None,
            goto=lambda *_a, **_k: None,
            query_selector=lambda *_a: None,
            evaluate=lambda *_a: 16,
        )
        context = SimpleNamespace(
            new_page=lambda: self.page,
            route=lambda *_a: None,
            route_web_socket=lambda *_a: None,
            close=lambda: None,
        )
        browser = SimpleNamespace(new_context=lambda **_k: context, close=lambda: None)
        self.playwright = SimpleNamespace(chromium=SimpleNamespace(launch=lambda **_k: browser))

    def __enter__(self):
        return self.playwright

    def __exit__(self, *_args):
        return False


@pytest.mark.parametrize(
    "final_url,prefix",
    [
        ("about:blank", "Page did not load: "),
        ("chrome-error://chromewebdata/", "Page did not load: "),
        ("http://127.0.0.1:9000/", "url_safety: "),
        ("data:text/html,x", "url_safety: "),
    ],
)
def test_analyze_visual_reports_a_page_that_is_not_the_site(
    monkeypatch, regular_user, final_url, prefix
):
    monkeypatch.setattr(analyze_visual, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(analyze_visual, "sync_playwright", lambda: _VisualManager(final_url))
    result = analyze_visual.analyze_visual("https://site.example/")
    assert result["error"].startswith(prefix)
    assert "Invalid URL scheme" not in result["error"]
    assert result["mobile"]["viewport_meta"] is False


def test_analyze_visual_runs_on_a_public_page(monkeypatch, regular_user):
    _map_public_host(monkeypatch, 443)
    url = f"https://{PUBLIC_HOST}/"
    monkeypatch.setattr(analyze_visual, "validate_url_strict", lambda u: (u, "93.184.216.34"))
    monkeypatch.setattr(analyze_visual, "sync_playwright", lambda: _VisualManager(url))
    result = analyze_visual.analyze_visual(url)
    assert result["error"] is None
    assert result["fonts"]["base_size"] == 16
