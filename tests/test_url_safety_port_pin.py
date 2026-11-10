"""
Port-bound DNS pin for CLAUDE_SEO_LOCAL_TARGETS (scripts/url_safety.py).

A ``host:port`` allowlist entry admits that port only. These tests drive the
real ``requests`` and ``urllib3`` stack through ``safe_requests_get`` with
the resolver and ``socket.socket`` replaced, so a redirect is followed the
way it is in production and every connection attempt is recorded. No test
here touches the network.
"""

from __future__ import annotations

import io
import os
import socket
import sys
from unittest.mock import patch

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

requests = pytest.importorskip("requests")
import url_safety  # noqa: E402

PUBLIC_IP = "93.184.216.34"


def _redirect(location: str) -> bytes:
    return (
        f"HTTP/1.1 302 Found\r\nLocation: {location}\r\n"
        "Content-Length: 0\r\nConnection: close\r\n\r\n"
    ).encode("ascii")


def _ok(body: str) -> bytes:
    return (
        f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}"
    ).encode("ascii")


class _FakeNet:
    """Canned HTTP servers keyed by ``(ip, port)``, plus a connection log."""

    def __init__(self, hosts: dict, servers: dict) -> None:
        self.hosts = hosts
        self.servers = servers
        self.connections: list = []

    def getaddrinfo(self, host, port, *args, **kwargs):
        if host in self.hosts:
            ip = self.hosts[host]
        else:
            try:
                socket.inet_aton(host)
            except (OSError, TypeError):
                raise socket.gaierror(socket.EAI_NONAME, f"unmocked host {host!r}") from None
            ip = host
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))]

    def socket(self, *args, **kwargs):
        return _FakeSocket(self)


class _FakeSocket:
    """The slice of ``socket.socket`` that urllib3 and http.client use."""

    def __init__(self, net: _FakeNet) -> None:
        self._net = net
        self._address = None

    def connect(self, address) -> None:
        self._net.connections.append(address)
        if address not in self._net.servers:
            raise ConnectionRefusedError(111, "no fake server on this port")
        self._address = address

    def makefile(self, *args, **kwargs):
        return io.BytesIO(self._net.servers[self._address])

    def sendall(self, data) -> None:
        pass

    def setsockopt(self, *args) -> None:
        pass

    def settimeout(self, value) -> None:
        pass

    def shutdown(self, how) -> None:
        pass

    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    """No developer allowlist, no developer proxy."""
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)
    monkeypatch.setattr(url_safety.requests.utils, "getproxies", lambda: {})


def _get(url: str, net: _FakeNet):
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=net.getaddrinfo), \
            patch.object(url_safety.socket, "socket", side_effect=net.socket):
        return url_safety.safe_requests_get(url, timeout=5)


# ---------------------------------------------------------------------------
# Local targets admitted through a host:port entry
# ---------------------------------------------------------------------------


def test_allowed_local_target_still_fetches(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000")
    net = _FakeNet({"localhost": "127.0.0.1"}, {("127.0.0.1", 3000): _ok("dev server")})

    response = _get("http://localhost:3000/", net)

    assert response.status_code == 200
    assert response.content == b"dev server"
    assert net.connections == [("127.0.0.1", 3000)]


@pytest.mark.parametrize("requested_port", [3000, "3000", None, 0])
def test_pin_on_a_non_public_address_answers_for_the_validated_port(
    monkeypatch, requested_port
) -> None:
    """A lookup that names no port gets the validated one, as before."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000")
    with url_safety._pin_dns("localhost", "127.0.0.1", 3000):
        sockaddr = socket.getaddrinfo("localhost", requested_port)[0][4]
    assert sockaddr == ("127.0.0.1", requested_port or 3000)


@pytest.mark.parametrize(
    "allowlist,start,hosts,first,location",
    [
        (
            "localhost:3000",
            "http://localhost:3000/",
            {"localhost": "127.0.0.1"},
            ("127.0.0.1", 3000),
            "http://localhost:6379/",
        ),
        (
            "localhost:3000",
            "http://localhost:3000/",
            {"localhost": "127.0.0.1"},
            ("127.0.0.1", 3000),
            "http://localhost/",
        ),
        (
            "127.0.0.1:8080",
            "http://127.0.0.1:8080/",
            {},
            ("127.0.0.1", 8080),
            "http://127.0.0.1:6379/",
        ),
        (
            "staging.internal:8080",
            "http://staging.internal:8080/",
            {"staging.internal": "10.0.0.5"},
            ("10.0.0.5", 8080),
            "http://staging.internal:9200/",
        ),
    ],
)
def test_redirect_to_another_port_on_an_allowed_local_host_is_refused(
    monkeypatch, allowlist, start, hosts, first, location
) -> None:
    """``host:port`` allows that port only, on every hop."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", allowlist)
    servers = {first: _redirect(location)}
    # Every other port on the address answers, so only the pin can stop it.
    for port in (80, 6379, 9200):
        servers[(first[0], port)] = _ok("internal service")
    net = _FakeNet(hosts, servers)

    with pytest.raises(requests.exceptions.ConnectionError, match="validated port"):
        _get(start, net)

    assert net.connections == [first]


def test_session_cannot_reach_another_port_on_an_allowed_local_host(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000")
    net = _FakeNet(
        {"localhost": "127.0.0.1"},
        {("127.0.0.1", 3000): _ok("dev server"), ("127.0.0.1", 6379): _ok("internal service")},
    )
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=net.getaddrinfo), \
            patch.object(url_safety.socket, "socket", side_effect=net.socket):
        with url_safety.safe_requests_session("http://localhost:3000/") as session:
            assert session.get("http://localhost:3000/", timeout=5).content == b"dev server"
            with pytest.raises(requests.exceptions.ConnectionError, match="validated port"):
                session.get("http://localhost:6379/", timeout=5)

    assert net.connections == [("127.0.0.1", 3000)]


def test_redirect_to_a_port_the_allowlist_also_names_is_followed(monkeypatch) -> None:
    """The other port is checked as a new target, and the operator named it."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000,localhost:3001")
    net = _FakeNet(
        {"localhost": "127.0.0.1"},
        {
            ("127.0.0.1", 3000): _redirect("http://localhost:3001/"),
            ("127.0.0.1", 3001): _ok("second dev server"),
            ("127.0.0.1", 6379): _ok("internal service"),
        },
    )

    assert _get("http://localhost:3000/", net).content == b"second dev server"
    assert net.connections == [("127.0.0.1", 3000), ("127.0.0.1", 3001)]

    net.servers[("127.0.0.1", 3001)] = _redirect("http://localhost:6379/")
    net.connections.clear()
    with pytest.raises(requests.exceptions.ConnectionError, match="validated port"):
        _get("http://localhost:3000/", net)
    assert net.connections == [("127.0.0.1", 3000), ("127.0.0.1", 3001)]


def test_bare_host_entry_still_matches_any_port_on_redirect(monkeypatch) -> None:
    """A bare ``host`` entry matches any port, so its redirects keep working."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "100.101.102.103")
    net = _FakeNet(
        {},
        {
            ("100.101.102.103", 80): _redirect("http://100.101.102.103:8080/"),
            ("100.101.102.103", 8080): _ok("staging"),
        },
    )

    assert _get("http://100.101.102.103/", net).content == b"staging"
    assert net.connections == [("100.101.102.103", 80), ("100.101.102.103", 8080)]


@pytest.mark.parametrize("requested_port", [6379, "6379", "redis", 80, 443, 3001])
def test_pin_on_a_non_public_address_answers_for_the_validated_port_only(
    monkeypatch, requested_port
) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000")
    with url_safety._pin_dns("localhost", "127.0.0.1", 3000):
        with pytest.raises(socket.gaierror, match="validated port is 3000"):
            socket.getaddrinfo("localhost", requested_port)
        with pytest.raises(socket.gaierror, match="validated port is 3000"):
            socket.getaddrinfo("LOCALHOST", requested_port)


def test_pin_on_a_non_public_address_is_port_bound_without_an_allowlist() -> None:
    """Fail closed: the binding follows the pinned address, not the environment."""
    with url_safety._pin_dns("internal.example", "10.0.0.5", 8080):
        assert socket.getaddrinfo("internal.example", 8080)[0][4] == ("10.0.0.5", 8080)
        with pytest.raises(socket.gaierror, match="validated port is 8080"):
            socket.getaddrinfo("internal.example", 9200)


# ---------------------------------------------------------------------------
# Public hosts and the default policy are unchanged
# ---------------------------------------------------------------------------


def test_public_host_redirecting_http_to_https_still_connects() -> None:
    """The most common redirect on the web. TLS itself is out of scope here:
    the fake server refuses the connection, after the pin has answered for
    port 443 with the validated address."""
    net = _FakeNet(
        {"example.com": PUBLIC_IP},
        {(PUBLIC_IP, 80): _redirect("https://example.com/")},
    )

    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        _get("http://example.com/", net)

    assert "url_safety" not in str(excinfo.value)
    assert net.connections == [(PUBLIC_IP, 80), (PUBLIC_IP, 443)]


def test_public_host_redirect_to_another_port_is_followed() -> None:
    net = _FakeNet(
        {"example.com": PUBLIC_IP},
        {
            (PUBLIC_IP, 80): _redirect("http://example.com:8080/app"),
            (PUBLIC_IP, 8080): _ok("public app"),
        },
    )

    assert _get("http://example.com/", net).content == b"public app"
    assert net.connections == [(PUBLIC_IP, 80), (PUBLIC_IP, 8080)]


@pytest.mark.parametrize("requested_port", [80, 443, 8080, "8443", None, 0])
def test_pin_on_a_public_address_answers_for_any_port(requested_port) -> None:
    with url_safety._pin_dns("example.com", PUBLIC_IP, 80):
        sockaddr = socket.getaddrinfo("example.com", requested_port)[0][4]
    assert sockaddr == (PUBLIC_IP, requested_port or 80)


def test_public_pin_never_consults_the_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "example.com:80")
    with patch.object(
        url_safety, "_is_allowlisted_local_target", side_effect=AssertionError("consulted")
    ):
        with url_safety._pin_dns("example.com", PUBLIC_IP, 80):
            assert socket.getaddrinfo("example.com", 443)[0][4] == (PUBLIC_IP, 443)


def test_without_local_targets_local_hosts_are_refused_before_any_connection() -> None:
    net = _FakeNet({"localhost": "127.0.0.1"}, {("127.0.0.1", 3000): _ok("dev server")})

    with pytest.raises(url_safety.URLSafetyError, match="Blocked hostname"):
        _get("http://localhost:3000/", net)
    with pytest.raises(url_safety.URLSafetyError, match="Blocked hostname"):
        _get("http://127.0.0.1:3000/", net)

    assert net.connections == []


@pytest.mark.parametrize("allowlist", [None, "localhost:3000"])
def test_public_host_redirecting_to_a_local_port_is_refused(monkeypatch, allowlist) -> None:
    """The allowlist never applies to a redirect target on another host."""
    if allowlist:
        monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", allowlist)
    net = _FakeNet(
        {"example.com": PUBLIC_IP, "localhost": "127.0.0.1"},
        {
            (PUBLIC_IP, 80): _redirect("http://localhost:3000/"),
            ("127.0.0.1", 3000): _ok("dev server"),
        },
    )

    with pytest.raises(requests.exceptions.ConnectionError, match="non-public IP"):
        _get("http://example.com/", net)

    assert net.connections == [(PUBLIC_IP, 80)]
