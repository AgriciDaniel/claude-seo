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
* A direct connection dials a validated address, not the name, so a DNS
  answer cannot change between the check and the connect. When a host has
  several addresses, each one that passed validation is tried in turn under
  one connect budget; the name is never resolved a second time.
* Behind the operator's own HTTP proxy (``HTTPS_PROXY`` and friends) the
  guard chains to it after validating the destination. That proxy must pass
  the same policy as in ``url_safety`` and it resolves the destination
  itself, so the pin degrades to the validation, as on the raw HTTP path.
* ``guarded_chromium`` gives its guard a random per-run credential and hands
  it to Chromium, so another local process cannot use the listener. A guard
  started with plain ``guarded_proxy()`` (Unlighthouse, whose Chrome takes
  the proxy from a command-line flag that cannot carry one) has none.
* A plain-HTTP response is relayed with the origin's own framing and the
  client connection is reset when the origin fails mid-response, so a
  truncated transfer is never passed off as a complete one.
* A plain-HTTP response head has one overall deadline, and a request whose
  client has gone away is dropped at once, so a slow origin cannot pile up
  guard threads and sockets behind requests the page already abandoned.

Chromium
========
``guarded_chromium`` is the one place that launches a browser. It launches
with the Chromium sandbox on. ``CLAUDE_SEO_CHROMIUM_NO_SANDBOX=1`` turns the
sandbox off for root and container environments where it cannot start.
"""

from __future__ import annotations

import base64
import hmac
import http.client
import os
import re
import secrets
import select
import socket
import struct
import threading
import time
from contextlib import contextmanager, suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlsplit

from url_safety import (
    URLSafetyError,
    is_safe_ip,
    upstream_http_proxy,
    validate_public_url_addresses,
)

# One budget for reaching a destination, shared by all of its addresses.
_CONNECT_TIMEOUT = 10
# The least an address that does not answer is given before the next is tried.
_MIN_CONNECT_SHARE = 1.0
_HTTP_IO_TIMEOUT = 30
# One budget for a whole plain-HTTP response head, informational responses
# included. The idle timeout alone would let an origin hold a guard thread
# and two sockets for hours by sending one header line every few seconds.
_RESPONSE_HEAD_TIMEOUT = 30
_TUNNEL_IDLE_TIMEOUT = 60
_MAX_REQUEST_BODY = 10 * 1024 * 1024
_MAX_CONNECT_RESPONSE = 64 * 1024
# A plain-HTTP response head, all lines together. Chromium's own limit is
# 256 KiB; the line count only bounds the work spent on a hostile head.
_MAX_RESPONSE_HEAD = 256 * 1024
_MAX_RESPONSE_HEADERS = 1000
# Informational (1xx) responses skipped before the final one.
_MAX_INTERIM_RESPONSES = 10
_RELAY_CHUNK = 65536
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
_STATUS_LINE_RE = re.compile(rb"^HTTP/1\.[01] ([0-9]{3})(?: [^\x00-\x08\x0a-\x1f\x7f]*)?$")
_HEADER_NAME_RE = re.compile(rb"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
_HEADER_VALUE_BAD_RE = re.compile(rb"[\x00\r\n]")
# SO_LINGER with a zero timeout: closing the socket sends a reset, not a FIN.
_LINGER_RESET = struct.pack("HH" if os.name == "nt" else "ii", 1, 0)
_PROXY_AUTH_REALM = "claude-seo egress guard"
_PROXY_USERNAME = "claude-seo"

NO_SANDBOX_ENV = "CLAUDE_SEO_CHROMIUM_NO_SANDBOX"
# Messages that mean the sandbox itself could not start: Chromium's own
# wording (zygote_host_impl_linux.cc, the setuid sandbox host) and the banner
# Playwright prints in their place. Whole phrases only. A bare word such as
# "sandbox" also matches install paths and the launch command line, and
# would blame an unrelated failure (a missing shared library) on the sandbox.
_SANDBOX_FAILURE_MARKERS = (
    "chromium sandboxing failed!",
    "no usable sandbox",
    "running as root without --no-sandbox is not supported",
    "failed to move to new namespace",
    "zygote_host_impl_linux.cc",
    "the suid sandbox helper binary was found, but is not configured correctly",
    "the setuid sandbox is not running as root",
    "the setuid sandbox provides api version",
    "crbug.com/638180",
    "crbug.com/357670",
)


class ChromiumSandboxError(RuntimeError):
    """Chromium could not start with its sandbox enabled."""


class PageNotLoadedError(RuntimeError):
    """The browser holds no loaded document (blank or an error page)."""


def _destination(url: str) -> tuple[tuple[str, ...], str, int]:
    """Validate ``url`` and return ``(addresses, hostname, port)``.

    ``addresses`` holds every address of the host that passed validation,
    the pinned one first. They come from the one lookup the validator made;
    nothing resolves the name again before the connect.
    """
    normalized, addresses = validate_public_url_addresses(url)
    # Belt and braces: the validator above never reads the operator's
    # local-target allowlist, which applies to raw HTTP only.
    if not addresses or not all(is_safe_ip(ip) for ip in addresses):
        raise URLSafetyError("Browser destination is not public")
    parsed = urlsplit(normalized)
    assert parsed.hostname is not None
    if not _HOST_RE.match(parsed.hostname):
        raise URLSafetyError("Browser destination has an invalid hostname")
    return (
        tuple(addresses),
        parsed.hostname,
        parsed.port or (443 if parsed.scheme == "https" else 80),
    )


def _as_addresses(value) -> tuple[str, ...]:  # type: ignore[no-untyped-def]
    """The address list of a ``_destination`` result (one address is fine)."""
    return (value,) if isinstance(value, str) else tuple(value)


def _connect(addresses: tuple[str, ...], port: int) -> socket.socket:
    """Connect to the first of ``addresses`` that answers.

    Every address was validated by the caller. They are tried in order under
    one ``_CONNECT_TIMEOUT`` budget: an address that does not answer gets an
    even share of what is left (at least ``_MIN_CONNECT_SHARE``), and one
    that fails at once (refused, no route, no IPv4 or IPv6 on this network)
    leaves its share to the rest. Raises the last ``OSError``.
    """
    deadline = time.monotonic() + _CONNECT_TIMEOUT
    error: OSError = OSError("no address to connect to")
    for index, address in enumerate(addresses):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        share = max(remaining / (len(addresses) - index), _MIN_CONNECT_SHARE)
        try:
            return socket.create_connection(
                (address, port), timeout=min(share, remaining)
            )
        except OSError as exc:
            error = exc
    raise error


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


class _ResponseHeadTooLarge(Exception):
    """The origin's response head is over this proxy's size limits."""


class _OriginReader:
    """Reads a plain-HTTP response from the origin while watching the client.

    Every wait ends on the first of: origin bytes, the idle timeout
    (``_HTTP_IO_TIMEOUT`` per read), ``deadline`` (a ``time.monotonic()``
    value, or None for no overall limit) and the client hanging up. The last
    three raise ``OSError``, so the caller drops the request and both sockets.

    The request was read in full and the connection serves no second one, so
    anything the client still sends is discarded; the end of its stream means
    it has gone away.
    """

    def __init__(self, origin: socket.socket, client: socket.socket) -> None:
        self._origin = origin
        self._client = client
        self._buffer = bytearray()
        self._ended = False
        self.deadline: Optional[float] = None

    def _fill(self) -> None:
        """Wait for the origin and buffer what it sent (nothing at its end)."""
        idle_until = time.monotonic() + _HTTP_IO_TIMEOUT
        while not self._ended:
            until = idle_until if self.deadline is None else min(idle_until, self.deadline)
            wait = until - time.monotonic()
            if wait <= 0:
                raise socket.timeout("timed out waiting for the origin")
            readable, _, _ = select.select((self._origin, self._client), (), (), wait)
            if self._client in readable and not self._client.recv(_RELAY_CHUNK):
                raise OSError("client disconnected")
            if self._origin in readable:
                data = self._origin.recv(_RELAY_CHUNK)
                self._ended = not data
                self._buffer += data
                return

    def readline(self, limit: int) -> bytes:
        """One line with its newline, at most ``limit`` bytes; short at the end."""
        scanned = 0
        while (end := self._buffer.find(b"\n", scanned, limit) + 1) == 0:
            scanned = len(self._buffer)
            if scanned >= limit or self._ended:
                end = limit
                break
            self._fill()
        line = bytes(self._buffer[:end])
        del self._buffer[:end]
        return line

    def read1(self, size: int) -> bytes:
        """Up to ``size`` bytes after at most one wait; empty at the end."""
        if not self._buffer:
            self._fill()
        chunk = bytes(self._buffer[:size])
        del self._buffer[:size]
        return chunk


def _read_response_head(reader) -> tuple[bytes, int, list[tuple[bytes, bytes]]]:  # type: ignore[no-untyped-def]
    """Read one response head: ``(status_line, status, headers)``.

    ``status_line`` is the origin's own, checked to be ``HTTP/1.x``, three
    digits and a reason without control characters. Headers come back as
    ``(name, value)`` in the order sent, repeats kept. A line that is not a
    well-formed header is left out, as Chromium does, along with any folded
    lines that continue it; a folded line continues the header before it.

    Raises:
        _ResponseHeadTooLarge: over ``_MAX_RESPONSE_HEAD`` bytes or
            ``_MAX_RESPONSE_HEADERS`` lines.
        ValueError: the status line is not HTTP/1.x.
        OSError: the connection ended or failed inside the head, the
            reader's deadline passed, or the client went away.
    """
    budget = _MAX_RESPONSE_HEAD

    def read_line() -> bytes:
        nonlocal budget
        line = reader.readline(budget + 1)
        if not line:
            raise OSError("connection closed inside the response head")
        if len(line) > budget:
            raise _ResponseHeadTooLarge()
        if not line.endswith(b"\n"):
            raise OSError("connection closed inside the response head")
        budget -= len(line)
        return line.rstrip(b"\r\n")

    status_line = read_line()
    matched = _STATUS_LINE_RE.match(status_line)
    if matched is None:
        raise ValueError("malformed status line")
    headers: list[tuple[bytes, bytes]] = []
    lines = 0
    kept = False  # whether the header a folded line would continue was kept
    while line := read_line():
        lines += 1
        if lines > _MAX_RESPONSE_HEADERS:
            raise _ResponseHeadTooLarge()
        folded = line[:1] in (b" ", b"\t")
        if _HEADER_VALUE_BAD_RE.search(line):
            kept = kept and folded
            if folded and kept:
                headers.pop()
                kept = False
            continue
        if folded:
            if kept:
                name, value = headers[-1]
                headers[-1] = (name, (value + b" " + line.strip(b" \t")).strip(b" "))
            continue
        name, colon, value = line.partition(b":")
        kept = bool(colon and _HEADER_NAME_RE.match(name))
        if kept:
            headers.append((name, value.strip(b" \t")))
    return status_line, int(matched.group(1)), headers


def _read_final_response_head(reader) -> tuple[bytes, int, list[tuple[bytes, bytes]]]:  # type: ignore[no-untyped-def]
    """Like ``_read_response_head``, past any informational responses.

    ``100 Continue``, ``103 Early Hints`` and other 1xx responses come before
    the final response on the same connection and are dropped. ``101`` would
    switch a request this proxy never asked to upgrade (it strips
    ``Upgrade``) to another protocol, so it is an error.
    """
    for _ in range(_MAX_INTERIM_RESPONSES + 1):
        status_line, status, headers = _read_response_head(reader)
        if status == 101:
            raise ValueError("unrequested protocol switch")
        if not 100 <= status < 200:
            return status_line, status, headers
    raise ValueError("too many informational responses")


def _body_length(method: str, status: int, headers: list[tuple[bytes, bytes]]) -> Optional[int]:
    """Bytes of body that follow the head, or None when only the origin's
    framing (chunked, or the close of the connection) marks the end."""
    if method == "HEAD" or status in (204, 304):
        return 0
    lengths = [value for name, value in headers if name.lower() == b"content-length"]
    chunked = any(name.lower() == b"transfer-encoding" for name, _ in headers)
    if chunked or len(lengths) != 1 or not lengths[0].isdigit():
        return None
    return int(lengths[0])


def _open_tunnel(addresses: tuple[str, ...], host: str, port: int) -> tuple[socket.socket, bytes]:
    """Open the TCP stream for a CONNECT to an already validated destination.

    Direct: connect to one of the validated addresses. Behind the operator's
    proxy: connect to that proxy and ask it for the tunnel. Returns the
    socket and any bytes the far side sent after the proxy's response head.
    """
    proxy = upstream_http_proxy(f"https://{_authority(host, port)}/")
    if proxy is None:
        return _connect(addresses, port), b""

    address, proxy_port, authorization = proxy
    authority = _authority(host, port)
    head = f"CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n"
    if authorization:
        head += f"Proxy-Authorization: {authorization}\r\n"
    upstream = _connect((address,), proxy_port)
    try:
        upstream.settimeout(_CONNECT_TIMEOUT)
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

    def _authorized(self) -> bool:
        """Check the per-run credential; answer 407 when it is missing or wrong.

        A guard started without a credential accepts every local client.
        """
        expected = getattr(self.server, "proxy_authorization", None)
        if expected is None:
            return True
        scheme, _, token = (self.headers.get("Proxy-Authorization") or "").strip().partition(" ")
        supplied = token.strip().encode("latin-1", "replace")
        if scheme.lower() == "basic" and hmac.compare_digest(supplied, expected):
            return True
        self.close_connection = True
        with suppress(OSError):
            self.send_response_only(407, "Proxy Authentication Required")
            self.send_header("Proxy-Authenticate", f'Basic realm="{_PROXY_AUTH_REALM}"')
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
        return False

    def _abort_client(self) -> None:
        """Reset the client connection instead of closing it cleanly.

        Used once a response is in flight and the origin failed: a clean
        close would let a body with no declared length pass as complete.
        """
        with suppress(OSError):
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, _LINGER_RESET)
        # Closing here, before the server's own shutdown() can send a FIN,
        # is what turns the close into a reset. The descriptor is released
        # when the handler's read buffer is closed in finish().
        with suppress(OSError):
            self.connection.close()

    def do_CONNECT(self) -> None:
        if not self._authorized():
            return
        try:
            if not _CONNECT_TARGET_RE.match(self.path):
                raise URLSafetyError("Malformed CONNECT target")
            # urlsplit validates IPv6 brackets and rejects malformed ports.
            pinned, host, port = _destination(f"https://{self.path}/")
            upstream, early = _open_tunnel(_as_addresses(pinned), host, port)
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
            upstream.settimeout(_TUNNEL_IDLE_TIMEOUT)
            # Bytes the client sent right behind the CONNECT head were read
            # into the handler's buffer with it; the relay below reads the
            # socket, so they are passed on first.
            client.setblocking(False)
            sent_early = b""
            with suppress(OSError):
                sent_early = self.rfile.read1(_RELAY_CHUNK) or b""
            client.settimeout(_TUNNEL_IDLE_TIMEOUT)
            if sent_early:
                upstream.sendall(sent_early)
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

        The response is relayed, not re-framed: status line, headers
        (hop-by-hop ones aside) and body bytes go to the client as the origin
        sent them, after any informational 1xx responses. The client
        therefore sees the origin's own ``Content-Length`` or chunked framing
        and detects a short body itself, and when the origin fails after the
        head was passed on, the client connection is reset.
        """
        self.close_connection = True
        if not self._authorized():
            return
        try:
            pinned, host, port = _destination(self.path)
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
            peers, peer_port = _as_addresses(pinned), port
        else:
            # The operator's proxy takes the absolute form and resolves the
            # (already validated) host itself.
            peers, peer_port = (proxy[0],), proxy[1]
            target = f"http://{host_header}{target}"

        # Headers the client marked as hop-by-hop are not forwarded either.
        listed = ",".join(self.headers.get_all("Connection") or [])
        dropped = _HOP_HEADERS | {"host", "content-length"} | {
            token.strip().lower() for token in listed.split(",") if token.strip()
        }
        # http.client writes the request (it refuses control characters in
        # the target and in header values) on a socket this proxy connected
        # itself, so it never dials. The response is read from that socket
        # directly, below.
        connection = http.client.HTTPConnection(peers[0], peer_port, timeout=_HTTP_IO_TIMEOUT)
        connection.auto_open = 0
        in_flight = False
        try:
            connection.sock = _connect(peers, peer_port)
            connection.sock.settimeout(_HTTP_IO_TIMEOUT)
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

            reader = _OriginReader(connection.sock, self.connection)
            # The whole head, informational responses included, under one
            # deadline. The body after it may take as long as it likes while
            # bytes keep coming (downloads, streams) and the client stays.
            reader.deadline = time.monotonic() + _RESPONSE_HEAD_TIMEOUT
            status_line, status, headers = _read_final_response_head(reader)
            reader.deadline = None
            # The page's own status line and headers reach the audit as sent:
            # no Server or Date header of this proxy is added. The origin's
            # framing headers go through too, because the body is relayed as
            # received and the client decides whether it is complete.
            head = [status_line]
            for name, value in headers:
                if name.decode("ascii").lower() not in _HOP_HEADERS:
                    head.append(name + b": " + value)
            head.append(b"Connection: close")
            in_flight = True
            self.wfile.write(b"\r\n".join(head) + b"\r\n\r\n")

            remaining = _body_length(self.command, status, headers)
            while remaining is None or remaining > 0:
                chunk = reader.read1(
                    _RELAY_CHUNK if remaining is None else min(_RELAY_CHUNK, remaining)
                )
                if not chunk:
                    if remaining is not None:
                        raise OSError("origin closed before the declared length")
                    break
                self.wfile.write(chunk)
                if remaining is not None:
                    remaining -= len(chunk)
        except _ResponseHeadTooLarge:
            # Not silence: the operator should see why the page did not load.
            self._reject(502, "Upstream response headers too large")
        except (OSError, ValueError, http.client.HTTPException):
            # Unreachable, reset, timed out (the head deadline included),
            # malformed, or the client went away. Before the head was passed
            # on the client gets no response at all. After it, nothing is
            # appended to the response in flight; the connection is reset so
            # the client cannot take a cut-off body for a complete one.
            if in_flight:
                self._abort_client()
        finally:
            connection.close()


class _GuardServer(ThreadingHTTPServer):
    daemon_threads = True
    # Handler threads are daemons and are not joined on close, so a tunnel
    # that is still open cannot hold up shutdown.
    block_on_close = False
    # Chromium opens many connections at once; the default backlog is 5.
    request_queue_size = 128
    # ``base64(user:password)`` every request must present, or None.
    proxy_authorization: Optional[bytes] = None

    def handle_error(self, request, client_address) -> None:  # type: ignore[no-untyped-def]
        # A client that went away mid-request is routine; keep stderr clean.
        pass


@contextmanager
def guarded_proxy(credentials: Optional[tuple[str, str]] = None):
    """Run a local proxy that refuses non-public destinations at each hop.

    ``credentials`` is a ``(username, password)`` pair every request must
    then present as ``Proxy-Authorization: Basic``; anything else gets a 407.
    Without it any local process can use the proxy while it runs. That is
    the mode for a client that cannot authenticate to a proxy (Chrome under
    Unlighthouse, which takes the proxy from ``--proxy-server``).
    """
    server = _GuardServer(("127.0.0.1", 0), _ProxyHandler)
    if credentials is not None:
        server.proxy_authorization = base64.b64encode(
            ":".join(credentials).encode("utf-8")
        )
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


def _reports_sandbox_failure(error: BaseException) -> bool:
    """True when a launch error carries one of Chromium's sandbox messages.

    The launch command line that Playwright echoes into the error is left
    out, and only whole phrases count, so a path or a flag never matches.
    """
    text = "\n".join(
        line for line in str(error).splitlines() if "<launching>" not in line
    ).lower()
    return any(marker in text for marker in _SANDBOX_FAILURE_MARKERS)


def _launch(browser_type, proxy_url: str, credentials: tuple[str, str]):  # type: ignore[no-untyped-def]
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
            # The credential goes to Chromium through Playwright, which
            # answers the guard's 407. It is not on the command line.
            proxy={
                "server": proxy_url,
                "bypass": "",
                "username": credentials[0],
                "password": credentials[1],
            },
            args=[
                # Chromium skips the proxy for loopback and link-local
                # addresses unless those implicit rules are subtracted.
                "--proxy-bypass-list=<-loopback>",
                "--disable-quic",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            ],
        )
    except Exception as exc:
        if sandbox and _reports_sandbox_failure(exc):
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
    # A fresh secret per run: only this browser can use this guard.
    credentials = (_PROXY_USERNAME, secrets.token_urlsafe(32))
    with guarded_proxy(credentials) as proxy_url:
        browser = _launch(browser_type, proxy_url, credentials)
        try:
            yield browser
        finally:
            # A browser that already crashed must not mask the real error.
            with suppress(Exception):
                browser.close()
