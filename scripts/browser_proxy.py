"""Per-browser HTTP proxy that validates and pins every outbound connection.

Playwright route handlers see only the first URL of a redirect chain. This
proxy checks the destination at the socket boundary, including every redirect
hop and every Chromium DNS lookup. It is intentionally local to one browser
run and is not a general-purpose proxy.
"""

from __future__ import annotations

import http.client
import select
import socket
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from url_safety import URLSafetyError, is_safe_ip, validate_url_strict

_CONNECT_TIMEOUT = 10
_HTTP_IO_TIMEOUT = 30
_TUNNEL_IDLE_TIMEOUT = 60
_HOP_HEADERS = {"connection", "proxy-connection", "proxy-authorization", "keep-alive", "te", "trailer", "upgrade"}


def _destination(url: str) -> tuple[str, str, int]:
    normalized, ip = validate_url_strict(url)
    # The operator's local-target allowlist applies to raw HTTP only.
    if not is_safe_ip(ip):
        raise URLSafetyError("Browser destination is not public")
    parsed = urlsplit(normalized)
    assert parsed.hostname is not None
    return ip, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)


def require_public_page(page) -> None:  # type: ignore[no-untyped-def]
    """Refuse to return a browser result after a blocked top-level redirect."""
    _url, ip = validate_url_strict(page.url)
    if not is_safe_ip(ip):
        raise URLSafetyError("Browser navigated to a non-public destination")


class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *_args) -> None:
        pass

    def do_CONNECT(self) -> None:
        try:
            # urlsplit validates IPv6 brackets and rejects malformed ports.
            ip, _host, port = _destination(f"https://{self.path}/")
            upstream = socket.create_connection((ip, port), timeout=_CONNECT_TIMEOUT)
        except (URLSafetyError, ValueError, OSError):
            self.send_error(403, "Destination refused")
            return

        try:
            self.send_response(200, "Connection established")
            self.end_headers()
            self.connection.settimeout(_TUNNEL_IDLE_TIMEOUT)
            upstream.settimeout(_TUNNEL_IDLE_TIMEOUT)
            sockets = (self.connection, upstream)
            while True:
                readable, _, _ = select.select(sockets, (), (), _TUNNEL_IDLE_TIMEOUT)
                if not readable:
                    break
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    (upstream if source is self.connection else self.connection).sendall(data)
        except OSError:
            pass
        finally:
            upstream.close()

    def do_GET(self) -> None:
        self._forward_http()

    def do_HEAD(self) -> None:
        self._forward_http()

    def do_POST(self) -> None:
        self._forward_http()

    def do_PUT(self) -> None:
        self._forward_http()

    def do_OPTIONS(self) -> None:
        self._forward_http()

    def do_DELETE(self) -> None:
        self._forward_http()

    def do_PATCH(self) -> None:
        self._forward_http()

    def _forward_http(self) -> None:
        try:
            ip, host, port = _destination(self.path)
            parsed = urlsplit(self.path)
            if parsed.scheme != "http":
                raise URLSafetyError("Only HTTP requests use direct proxy forwarding")
            if self.headers.get("Transfer-Encoding"):
                raise URLSafetyError("Chunked proxy requests are unsupported")
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > 10 * 1024 * 1024:
                raise URLSafetyError("Request body too large")
            body = self.rfile.read(size) if size else None
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP_HEADERS and k.lower() != "host"}
            host_header = f"[{host}]" if ":" in host else host
            headers["Host"] = host_header if port == 80 else f"{host_header}:{port}"
            connection = http.client.HTTPConnection(ip, port, timeout=_HTTP_IO_TIMEOUT)
            try:
                connection.request(self.command, path, body=body, headers=headers)
                response = connection.getresponse()
                self.send_response(response.status, response.reason)
                for key, value in response.getheaders():
                    if key.lower() not in _HOP_HEADERS and key.lower() != "transfer-encoding":
                        self.send_header(key, value)
                self.send_header("Connection", "close")
                self.end_headers()
                while chunk := response.read(65536):
                    self.wfile.write(chunk)
            finally:
                connection.close()
        except (URLSafetyError, ValueError, OSError, http.client.HTTPException):
            if not self.wfile.closed:
                try:
                    self.send_error(403, "Destination refused")
                except OSError:
                    pass


@contextmanager
def guarded_chromium(browser_type):  # type: ignore[no-untyped-def]
    """Launch Chromium with all HTTP(S) traffic forced through the local guard."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ProxyHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    browser = None
    try:
        browser = browser_type.launch(
            headless=True,
            proxy={"server": f"http://127.0.0.1:{server.server_port}", "bypass": ""},
            args=[
                "--proxy-bypass-list=<-loopback>",
                "--disable-quic",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            ],
        )
        yield browser
    finally:
        try:
            if browser is not None:
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
