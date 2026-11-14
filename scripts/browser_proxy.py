"""Per-browser HTTP proxy that validates and pins every outbound connection.

Playwright route handlers see only the first URL of a redirect chain. This
proxy checks the destination at the socket boundary, including every redirect
hop and every Chromium DNS lookup. It is intentionally local to one browser
run and is not a general-purpose proxy.

What it enforces
================
* Every destination goes through ``validate_public_url_strict``: the
  ``CLAUDE_SEO_LOCAL_TARGETS`` allowlist is never read here, so rendering a
  local or private host stays unsupported, as it was before this guard.
* A direct connection dials the validated address, not the name, so a DNS
  answer cannot change between the check and the connect.
* Behind the operator's own HTTP proxy (``HTTPS_PROXY`` and friends) the
  guard chains to it after validating the destination. That proxy must pass
  the same policy as in ``url_safety`` and it resolves the destination
  itself, so the pin degrades to the validation, as on the raw HTTP path.

Chromium
========
``guarded_chromium`` is the one place that launches a browser. It launches
with the Chromium sandbox on. ``CLAUDE_SEO_CHROMIUM_NO_SANDBOX=1`` turns the
sandbox off for root and container environments where it cannot start.
"""

from __future__ import annotations

import http.client
import os
import re
import select
import socket
import threading
from contextlib import contextmanager, suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlsplit

from url_safety import (
    URLSafetyError,
    is_safe_ip,
    upstream_http_proxy,
    validate_public_url_strict,
)

_CONNECT_TIMEOUT = 10
_HTTP_IO_TIMEOUT = 30
_TUNNEL_IDLE_TIMEOUT = 60
_MAX_REQUEST_BODY = 10 * 1024 * 1024
_MAX_CONNECT_RESPONSE = 64 * 1024
_HOP_HEADERS = {
    "connection",
    "proxy-connection",
    "proxy-authorization",
    "proxy-authenticate",
    "keep-alive",
    "te",
    "trailer",
    "upgrade",
}
# Characters a host may hold once it is written into a request this proxy
# builds itself (a CONNECT line, a Host header). Chromium sends IDNs as
# punycode, so anything else is malformed or an injection attempt.
_HOST_RE = re.compile(r"^[A-Za-z0-9._\-:]+$")
# Authority-form of CONNECT: ``host:port`` or ``[v6]:port``, nothing else.
_CONNECT_TARGET_RE = re.compile(r"^(?:\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9._\-]+):[0-9]{1,5}$")

NO_SANDBOX_ENV = "CLAUDE_SEO_CHROMIUM_NO_SANDBOX"
# Text Chromium or Playwright prints when the sandbox cannot start.
_SANDBOX_FAILURE_MARKERS = (
    "sandbox",
    "crbug.com/638180",
    "crbug.com/357670",
    "zygote",
    "failed to move to new namespace",
)


class ChromiumSandboxError(RuntimeError):
    """Chromium could not start with its sandbox enabled."""


class PageNotLoadedError(RuntimeError):
    """The browser holds no loaded document (blank or an error page)."""


def _destination(url: str) -> tuple[str, str, int]:
    """Validate ``url`` and return ``(pinned_ip, hostname, port)``."""
    normalized, ip = validate_public_url_strict(url)
    # Belt and braces: the validator above never reads the operator's
    # local-target allowlist, which applies to raw HTTP only.
    if not is_safe_ip(ip):
        raise URLSafetyError("Browser destination is not public")
    parsed = urlsplit(normalized)
    assert parsed.hostname is not None
    if not _HOST_RE.match(parsed.hostname):
        raise URLSafetyError("Browser destination has an invalid hostname")
    return ip, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)


def _authority(host: str, port: int, default_port: Optional[int] = None) -> str:
    """``host:port`` with IPv6 brackets; the port is left off when default."""
    bracketed = f"[{host}]" if ":" in host else host
    return bracketed if port == default_port else f"{bracketed}:{port}"


def require_public_page(page) -> None:  # type: ignore[no-untyped-def]
    """Raise unless ``page`` holds a loaded document from a public address.

    The egress guard answers a refused plain-HTTP hop with its own 403 page,
    so after a blocked top-level redirect the page URL is the refused one.
    Callers must not report such a page as the audited site.

    Raises:
        PageNotLoadedError: the page is still blank (``about:blank``: the
            navigation never committed) or shows Chromium's error page
            (``chrome-error://``: the load failed or was refused). Nothing
            was reached; this is a failed load, not a safety event.
        URLSafetyError: the document came from a non-public address or from
            a scheme other than http(s) (``data:``, ``file:`` and so on).
    """
    url = getattr(page, "url", "") or ""
    scheme = url.split(":", 1)[0].lower() if ":" in url else ""
    if scheme in ("", "about"):
        raise PageNotLoadedError("the page did not load (the browser is still blank)")
    if scheme == "chrome-error":
        raise PageNotLoadedError(
            "the page failed to load, or the egress guard refused its destination"
        )
    if scheme not in ("http", "https"):
        raise URLSafetyError(f"Browser ended on a non-HTTP document ({scheme}:)")
    try:
        _destination(url)
    except URLSafetyError as exc:
        raise URLSafetyError(
            f"Browser navigated to a non-public destination: {exc}"
        ) from exc


class _Rejected(Exception):
    """A request this proxy answers itself, with ``status`` and ``reason``."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


def _open_tunnel(ip: str, host: str, port: int) -> tuple[socket.socket, bytes]:
    """Open the TCP stream for a CONNECT to an already validated destination.

    Direct: connect to the validated address. Behind the operator's proxy:
    connect to that proxy and ask it for the tunnel. Returns the socket and
    any bytes the far side sent after the proxy's response head.
    """
    proxy = upstream_http_proxy(f"https://{_authority(host, port)}/")
    if proxy is None:
        return socket.create_connection((ip, port), timeout=_CONNECT_TIMEOUT), b""

    address, proxy_port, authorization = proxy
    authority = _authority(host, port)
    head = f"CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n"
    if authorization:
        head += f"Proxy-Authorization: {authorization}\r\n"
    upstream = socket.create_connection((address, proxy_port), timeout=_CONNECT_TIMEOUT)
    try:
        upstream.sendall((head + "\r\n").encode("ascii"))
        buffered = b""
        while b"\r\n\r\n" not in buffered:
            chunk = upstream.recv(4096)
            if not chunk or len(buffered) > _MAX_CONNECT_RESPONSE:
                raise OSError("upstream proxy closed or sent an oversized response")
            buffered += chunk
        response_head, _, rest = buffered.partition(b"\r\n\r\n")
        status_line = response_head.split(b"\r\n", 1)[0].split(b" ")
        if (
            len(status_line) < 2
            or not status_line[0].startswith(b"HTTP/1.")
            or len(status_line[1]) != 3
            or not status_line[1].startswith(b"2")
        ):
            raise OSError("upstream proxy refused the tunnel")
        return upstream, rest
    except BaseException:
        upstream.close()
        raise


class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    # Applied to the client socket while the request head and body are read.
    timeout = _HTTP_IO_TIMEOUT

    def log_message(self, *_args) -> None:
        pass

    def _reject(self, status: int, reason: str) -> None:
        self.close_connection = True
        with suppress(OSError):
            self.send_error(status, reason)

    def do_CONNECT(self) -> None:
        try:
            if not _CONNECT_TARGET_RE.match(self.path):
                raise URLSafetyError("Malformed CONNECT target")
            # urlsplit validates IPv6 brackets and rejects malformed ports.
            ip, host, port = _destination(f"https://{self.path}/")
            upstream, early = _open_tunnel(ip, host, port)
        except (URLSafetyError, ValueError):
            self._reject(403, "Destination refused")
            return
        except OSError:
            self._reject(502, "Destination unreachable")
            return

        try:
            self.send_response_only(200, "Connection established")
            self.end_headers()
            self.wfile.flush()
            client = self.connection
            client.settimeout(_TUNNEL_IDLE_TIMEOUT)
            upstream.settimeout(_TUNNEL_IDLE_TIMEOUT)
            if early:
                client.sendall(early)
            sockets = (client, upstream)
            while True:
                readable, _, _ = select.select(sockets, (), (), _TUNNEL_IDLE_TIMEOUT)
                if not readable:
                    break
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    (upstream if source is client else client).sendall(data)
        except (OSError, ValueError):
            pass
        finally:
            self.close_connection = True
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

    def _read_body(self) -> bytes:
        """Read the request body under a strict, unambiguous length."""
        if self.headers.get("Transfer-Encoding"):
            raise _Rejected(501, "Chunked proxy requests are unsupported")
        lengths = self.headers.get_all("Content-Length") or []
        if not lengths:
            return b""
        value = lengths[0].strip()
        if len(lengths) > 1 or not (value.isascii() and value.isdigit()):
            raise _Rejected(400, "Invalid Content-Length")
        size = int(value)
        if size > _MAX_REQUEST_BODY:
            raise _Rejected(413, "Request body too large")
        body = self.rfile.read(size) if size else b""
        if len(body) != size:
            raise _Rejected(400, "Incomplete request body")
        return body

    def _forward_http(self) -> None:
        """Forward one absolute-form plain-HTTP request to its destination.

        The destination comes from the request target alone; the client's
        Host header is discarded and rebuilt. A refusal is answered with this
        proxy's own error page. A destination that cannot be reached gets no
        response at all, so the browser reports a failed load instead of
        rendering a proxy error page as if the site had sent it.
        """
        self.close_connection = True
        try:
            ip, host, port = _destination(self.path)
            parsed = urlsplit(self.path)
            if parsed.scheme != "http":
                raise URLSafetyError("Only HTTP requests use direct proxy forwarding")
            body = self._read_body()
            proxy = upstream_http_proxy(self.path)
        except _Rejected as exc:
            self._reject(exc.status, exc.reason)
            return
        except (URLSafetyError, ValueError, OSError):
            self._reject(403, "Destination refused")
            return

        target = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")
        host_header = _authority(host, port, default_port=80)
        if proxy is None:
            peer = (ip, port)
        else:
            # The operator's proxy takes the absolute form and resolves the
            # (already validated) host itself.
            peer = proxy[:2]
            target = f"http://{host_header}{target}"

        # Headers the client marked as hop-by-hop are not forwarded either.
        listed = ",".join(self.headers.get_all("Connection") or [])
        dropped = _HOP_HEADERS | {"host", "content-length"} | {
            token.strip().lower() for token in listed.split(",") if token.strip()
        }
        connection = http.client.HTTPConnection(peer[0], peer[1], timeout=_HTTP_IO_TIMEOUT)
        try:
            connection.putrequest(
                self.command, target, skip_host=True, skip_accept_encoding=True
            )
            for key, value in self.headers.items():
                if key.lower() not in dropped:
                    connection.putheader(key, value)
            connection.putheader("Host", host_header)
            connection.putheader("Connection", "close")
            if proxy is not None and proxy[2]:
                connection.putheader("Proxy-Authorization", proxy[2])
            if body or self.command in ("POST", "PUT", "PATCH"):
                connection.putheader("Content-Length", str(len(body)))
            connection.endheaders(body or None)
            response = connection.getresponse()

            # send_response_only: no Server or Date header of this proxy is
            # added, so the page's own headers reach the audit unchanged.
            self.send_response_only(response.status, response.reason)
            for key, value in response.getheaders():
                if key.lower() not in _HOP_HEADERS and key.lower() != "transfer-encoding":
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()
            while chunk := response.read(65536):
                self.wfile.write(chunk)
        except (OSError, ValueError, http.client.HTTPException):
            # Unreachable, reset, or malformed in either direction: drop the
            # client connection. Nothing is appended to a response in flight.
            pass
        finally:
            connection.close()


class _GuardServer(ThreadingHTTPServer):
    daemon_threads = True
    # Handler threads are daemons and are not joined on close, so a tunnel
    # that is still open cannot hold up shutdown.
    block_on_close = False
    # Chromium opens many connections at once; the default backlog is 5.
    request_queue_size = 128

    def handle_error(self, request, client_address) -> None:  # type: ignore[no-untyped-def]
        # A client that went away mid-request is routine; keep stderr clean.
        pass


@contextmanager
def guarded_proxy():
    """Run a local proxy that refuses non-public destinations at each hop."""
    server = _GuardServer(("127.0.0.1", 0), _ProxyHandler)
    # A short poll interval keeps shutdown prompt: serve_forever only notices
    # the shutdown request between polls.
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
    )
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def chromium_sandbox_enabled() -> bool:
    """False only when ``CLAUDE_SEO_CHROMIUM_NO_SANDBOX`` opts out."""
    return os.environ.get(NO_SANDBOX_ENV, "").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    )


def _sandbox_error(detail: str) -> ChromiumSandboxError:
    return ChromiumSandboxError(
        f"Chromium could not start with its sandbox enabled ({detail}). "
        "claude-seo renders untrusted pages, so the sandbox is on by default. "
        "Run as a regular user on a system that supports the Chromium "
        f"sandbox, or set {NO_SANDBOX_ENV}=1 to launch without it (for root "
        "and container environments; a browser exploit is then not contained)."
    )


def _launch(browser_type, proxy_url: str):  # type: ignore[no-untyped-def]
    """Launch headless Chromium behind ``proxy_url``, sandboxed by default."""
    sandbox = chromium_sandbox_enabled()
    geteuid = getattr(os, "geteuid", None)
    if sandbox and geteuid is not None and geteuid() == 0:
        # Chromium refuses to run sandboxed as root; say so before it does.
        raise _sandbox_error("running as root")
    try:
        return browser_type.launch(
            headless=True,
            # Playwright passes --no-sandbox unless this is exactly True.
            chromium_sandbox=sandbox,
            # An empty bypass keeps PLAYWRIGHT_PROXY_BYPASS_FOR_TESTING out.
            proxy={"server": proxy_url, "bypass": ""},
            args=[
                # Chromium skips the proxy for loopback and link-local
                # addresses unless those implicit rules are subtracted.
                "--proxy-bypass-list=<-loopback>",
                "--disable-quic",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            ],
        )
    except Exception as exc:
        text = str(exc).lower()
        if sandbox and any(marker in text for marker in _SANDBOX_FAILURE_MARKERS):
            raise _sandbox_error("the browser reported a sandbox failure") from exc
        raise


@contextmanager
def guarded_chromium(browser_type, url: Optional[str] = None):  # type: ignore[no-untyped-def]
    """Launch Chromium with all HTTP(S) traffic forced through the local guard.

    This is the only place claude-seo launches a browser. ``url`` is the page
    about to be loaded: when given, an HTTP proxy configured for it that the
    guard cannot use (non-public, or not ``http://``) raises
    ``URLSafetyError`` here, before the browser starts, instead of failing
    every request later.

    Raises:
        ChromiumSandboxError: Chromium cannot start sandboxed. The message
            names ``CLAUDE_SEO_CHROMIUM_NO_SANDBOX``.
        URLSafetyError: the configured proxy for ``url`` is refused.
    """
    if url is not None:
        upstream_http_proxy(url)
    with guarded_proxy() as proxy_url:
        browser = _launch(browser_type, proxy_url)
        try:
            yield browser
        finally:
            # A browser that already crashed must not mask the real error.
            with suppress(Exception):
                browser.close()
