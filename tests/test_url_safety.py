"""
Tests for scripts/url_safety.py.

These tests exercise the SSRF policy, DNS-rebinding mitigation, and the
Playwright route-handler factory. They intentionally include a proof case
for the redirect-rebinding scenario that was discovered during the v2
self-audit (`safe_requests_session` did not validate redirect-target
hostname resolutions). The fix validates every host the patched resolver
is asked about, not only the originally-pinned host.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

pytest.importorskip("requests")
import url_safety  # noqa: E402

# ---------------------------------------------------------------------------
# normalize_hostname (v2 self-audit: closes obfuscated-IPv4 + FQDN bypasses)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Trailing dot (FQDN form) collapses to bare form so blocklists match
        ("metadata.google.internal.", "metadata.google.internal"),
        ("example.com.", "example.com"),
        # Casing
        ("Example.COM", "example.com"),
        # Obfuscated IPv4 — every glibc-accepted form canonicalises
        ("2130706433", "127.0.0.1"),       # decimal integer
        ("0x7f000001", "127.0.0.1"),       # hex integer
        ("017700000001", "127.0.0.1"),     # octal integer
        ("127.0.0.001", "127.0.0.1"),      # leading zeros
        ("0177.0.0.1", "127.0.0.1"),       # octal dotted
        ("0x7f.0.0.1", "127.0.0.1"),       # hex dotted
        ("127.1", "127.0.0.1"),            # two-part form
        ("127.0.1", "127.0.0.1"),          # three-part form
        # Public addresses pass through (verifies normalisation doesn't
        # accidentally rewrite legitimate IPs)
        ("1.1.1.1", "1.1.1.1"),
        ("8.8.8.8", "8.8.8.8"),
    ],
)
def test_normalize_hostname(raw: str, expected: str) -> None:
    assert url_safety.normalize_hostname(raw) == expected


def test_normalize_hostname_rejects_empty() -> None:
    with pytest.raises(url_safety.URLSafetyError, match="Empty hostname"):
        url_safety.normalize_hostname("")


def test_normalize_hostname_passes_through_dns_names() -> None:
    assert url_safety.normalize_hostname("example.com") == "example.com"
    assert url_safety.normalize_hostname("sub.deep.example.org") == "sub.deep.example.org"


# ---------------------------------------------------------------------------
# Obfuscated IPv4 bypass regression — validate_url MUST reject these.
# Before the v2 self-audit, validate_url returned True for these forms;
# only validate_url_strict caught them at DNS time. Anyone using the
# parse-only function as a pre-flight gate would have been vulnerable.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://2130706433/",          # decimal 127.0.0.1
        "http://0x7f000001/",          # hex 127.0.0.1
        "http://017700000001/",        # octal 127.0.0.1
        "http://127.0.0.001/",         # leading zeros
        "http://0177.0.0.1/",          # octal dotted
        "http://0x7f.0.0.1/",          # hex dotted
        "https://metadata.google.internal./",  # FQDN trailing dot
        "https://METADATA.GOOGLE.INTERNAL/",   # case bypass
        "http://Metadata.Google.Internal./",   # case + FQDN combined
    ],
)
def test_validate_url_blocks_obfuscated_bypasses(url: str) -> None:
    """Each of these would have bypassed v1.x parse-mode validation."""
    assert url_safety.validate_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:6666\\@1.1.1.1/",
        "https://169.254.169.254\\@example.com/latest/meta-data/",
        "https://user:pass@example.com/",
        "https://127.0.0.1#@example.com/",
        "https://example.com%5c@1.1.1.1/",
        "https://metadata.google.internal%2e/",
        "http://127.0.0.1%2e/",
    ],
)
def test_validate_url_blocks_authority_confusion(url: str) -> None:
    """Reject URL forms where urllib and the eventual HTTP stack can
    disagree about the connection target."""
    assert url_safety.validate_url(url) is False
    with pytest.raises(url_safety.URLSafetyError):
        url_safety.validate_url_strict(url)


# ---------------------------------------------------------------------------
# is_safe_ip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ip,expected",
    [
        ("1.1.1.1", True),
        ("8.8.8.8", True),
        ("104.20.23.154", True),
        ("2606:4700:4700::1111", True),
        ("192.168.1.1", False),
        ("10.0.0.1", False),
        ("172.16.0.1", False),
        ("127.0.0.1", False),
        ("169.254.169.254", False),  # AWS/GCP/Azure metadata
        ("100.100.100.200", False),  # Alibaba Cloud metadata (RFC 6598 shared space)
        ("100.64.0.0", False),  # RFC 6598 lower bound
        ("100.127.255.255", False),  # RFC 6598 upper bound
        ("100.128.0.1", True),  # first address past the /10 is public
        ("::ffff:100.100.100.200", False),  # IPv4-mapped form of the above
        ("::ffff:127.0.0.1", False),
        ("::ffff:8.8.8.8", True),
        ("0.0.0.0", False),
        ("::1", False),
        ("fe80::1", False),  # IPv6 link-local
        ("fd00::1", False),  # IPv6 unique-local
        ("224.0.0.1", False),  # multicast
        ("not-an-ip", False),
        ("", False),
    ],
)
def test_is_safe_ip(ip: str, expected: bool) -> None:
    assert url_safety.is_safe_ip(ip) is expected


# ---------------------------------------------------------------------------
# validate_url (parse-only, no DNS)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://example.com/path?q=1",
        "https://example.com:8443/api",
        "http://1.1.1.1",
        "https://subdomain.example.com",
    ],
)
def test_validate_url_accepts_public(url: str) -> None:
    assert url_safety.validate_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://localhost",
        "https://127.0.0.1",
        "https://10.0.0.1",
        "https://192.168.1.1",
        "https://169.254.169.254",
        "https://metadata.google.internal",
        "https://metadata.azure.com",
        "not a url",
        "https://",
    ],
)
def test_validate_url_rejects(url: str) -> None:
    assert url_safety.validate_url(url) is False


# ---------------------------------------------------------------------------
# validate_url_strict (resolves DNS; private resolutions raise)
# ---------------------------------------------------------------------------


def test_validate_url_strict_accepts_ip_literal_public() -> None:
    url, ip = url_safety.validate_url_strict("https://1.1.1.1/")
    assert ip == "1.1.1.1"
    assert url == "https://1.1.1.1/"


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/",
        "https://10.0.0.1/",
        "https://192.168.1.1/",
        "https://169.254.169.254/",
        "http://100.100.100.200/latest/meta-data/",
        "http://[::ffff:100.100.100.200]/latest/meta-data/",
        "https://0.0.0.0/",
    ],
)
def test_validate_url_strict_rejects_private_ip_literal(url: str) -> None:
    with pytest.raises(url_safety.URLSafetyError):
        url_safety.validate_url_strict(url)


def test_validate_url_strict_refuses_when_dns_resolves_to_private() -> None:
    """A hostname whose A record points at a private IP must be refused."""
    fake_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.0.0.7", 443))
    ]
    with patch.object(url_safety.socket, "getaddrinfo", return_value=fake_addrinfo):
        with pytest.raises(url_safety.URLSafetyError, match="non-public IP"):
            url_safety.validate_url_strict("https://attacker.example/")


def test_validate_url_strict_refuses_mixed_public_and_private() -> None:
    """If any A record is private, refuse the whole hostname (mitigates
    multi-record race conditions)."""
    fake_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("1.2.3.4", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.0.0.7", 443)),
    ]
    with patch.object(url_safety.socket, "getaddrinfo", return_value=fake_addrinfo):
        with pytest.raises(url_safety.URLSafetyError, match="non-public IP"):
            url_safety.validate_url_strict("https://attacker.example/")


def test_validate_url_strict_dns_failure_raises_safety_error() -> None:
    """DNS failures surface as URLSafetyError, not gaierror, so callers
    have a uniform exception type."""
    with patch.object(
        url_safety.socket,
        "getaddrinfo",
        side_effect=socket.gaierror("nodename nor servname provided"),
    ):
        with pytest.raises(url_safety.URLSafetyError, match="DNS resolution failed"):
            url_safety.validate_url_strict("https://does-not-exist.example/")


# ---------------------------------------------------------------------------
# _pin_dns: redirect-target validation (regression test for v2 self-audit)
# ---------------------------------------------------------------------------


def test_pin_dns_validates_non_pinned_host_resolutions() -> None:
    """
    The v2 self-audit found that ``_pin_dns`` only intercepted lookups for
    the originally-pinned host. Redirect targets (which are different
    hostnames) fell through to the unprotected resolver, allowing
    DNS-rebinding via 30x redirects: an attacker-controlled public host
    could redirect to e.g. http://169.254.169.254/ and the request would
    be followed.

    This test asserts that *any* host whose resolution lands on a private
    IP raises ``socket.gaierror`` from inside the pinned context, which
    ``requests`` surfaces as a ``ConnectionError`` (caught and reported
    by ``fetch_page.fetch_page``).
    """
    original_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        # Original pinned host: this branch is never reached during the
        # test because we never look it up after _pin_dns intercepts.
        if host == "pinned.example":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port or 443))]
        # Redirect target: resolves to AWS metadata endpoint.
        if host == "redirected.example":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", port or 443))]
        return original_getaddrinfo(host, port, *args, **kwargs)

    with patch.object(url_safety.socket, "getaddrinfo", side_effect=fake_getaddrinfo):
        with url_safety._pin_dns("pinned.example", "8.8.8.8", 443):
            # Lookup for the redirect target must fail-closed, even though
            # _pin_dns was set up for "pinned.example".
            with pytest.raises(socket.gaierror, match="non-public IP"):
                socket.getaddrinfo("redirected.example", 443)


def test_pin_dns_refuses_same_host_redirect_to_another_port() -> None:
    """A host:port exemption must not become all ports through a redirect."""
    with url_safety._pin_dns("demo.test", "127.0.0.1", 8443):
        with pytest.raises(socket.gaierror, match="port 9443 refused"):
            socket.getaddrinfo("demo.test", 9443)
        result = socket.getaddrinfo("demo.test", 8443)
        assert result[0][4] == ("127.0.0.1", 8443)


def test_pin_dns_passes_through_public_redirect_targets() -> None:
    """Public redirect targets keep working normally."""
    original_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host == "elsewhere.example":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", port or 443))]
        return original_getaddrinfo(host, port, *args, **kwargs)

    with patch.object(url_safety.socket, "getaddrinfo", side_effect=fake_getaddrinfo):
        with url_safety._pin_dns("pinned.example", "8.8.8.8", 443):
            result = socket.getaddrinfo("elsewhere.example", 443)
            assert result[0][4][0] == "1.1.1.1"


def test_pin_dns_restores_getaddrinfo_on_normal_exit() -> None:
    before = socket.getaddrinfo
    with url_safety._pin_dns("pinned.example", "8.8.8.8", 443):
        assert socket.getaddrinfo is not before
    assert socket.getaddrinfo is before


def test_safe_requests_head_uses_strict_validation_and_dns_pin() -> None:
    captured: dict = {}
    response = SimpleNamespace(status_code=200)

    @contextmanager
    def fake_pin(hostname: str, pinned_ip: str, port: int, exempt_hosts=frozenset()):
        captured["pin"] = (hostname, pinned_ip, port)
        captured["exempt"] = exempt_hosts
        yield

    with patch.object(
        url_safety,
        "validate_url_strict",
        return_value=("https://safe.example/path", "1.1.1.1"),
    ) as validate, patch.object(
        url_safety,
        "_pin_dns",
        side_effect=fake_pin,
    ), patch.object(
        url_safety.requests,
        "head",
        return_value=response,
    ) as request_head:
        result = url_safety.safe_requests_head(
            "https://safe.example/path",
            timeout=7,
            allow_redirects=True,
        )

    validate.assert_called_once_with(
        "https://safe.example/path", allow_local_target=True
    )
    request_head.assert_called_once_with(
        "https://safe.example/path",
        timeout=7,
        allow_redirects=True,
        headers=url_safety.DEFAULT_REQUEST_HEADERS,
    )
    assert captured["pin"] == ("safe.example", "1.1.1.1", 443)
    assert result is response


def test_default_headers_are_browser_like() -> None:
    headers = url_safety.DEFAULT_REQUEST_HEADERS
    assert "python-requests" not in headers["User-Agent"]
    assert headers["User-Agent"].startswith("Mozilla/5.0")
    assert "Accept" in headers


def test_default_headers_are_the_same_object_fetch_page_uses() -> None:
    """One source of truth: fetch_page.py's raw-HTTP defaults are url_safety's,
    so the two fetch paths cannot drift into announcing different clients."""
    import fetch_page  # noqa: WPS433

    assert fetch_page.DEFAULT_HEADERS == url_safety.DEFAULT_REQUEST_HEADERS
    assert fetch_page.DEFAULT_USER_AGENT == url_safety.DEFAULT_USER_AGENT
    assert (
        url_safety.DEFAULT_REQUEST_HEADERS["User-Agent"]
        == url_safety.DEFAULT_USER_AGENT
    )


def test_default_headers_do_not_announce_a_language() -> None:
    """Announcing en-US makes a multi-locale site serve its English variant,
    which silently corrupts every hreflang and international audit."""
    assert "Accept-Language" not in url_safety.DEFAULT_REQUEST_HEADERS
    assert "Accept-Language" not in url_safety._with_default_headers({})["headers"]


def test_with_default_headers_fills_unset_headers() -> None:
    assert url_safety._with_default_headers({})["headers"] == (
        url_safety.DEFAULT_REQUEST_HEADERS
    )
    assert url_safety._with_default_headers({"headers": None})["headers"] == (
        url_safety.DEFAULT_REQUEST_HEADERS
    )


def test_with_default_headers_lets_caller_override() -> None:
    # fetch_page.py --user-agent (Googlebot cloaking checks) must still win.
    merged = url_safety._with_default_headers(
        {"headers": {"User-Agent": "Googlebot/2.1"}}
    )["headers"]
    assert merged["User-Agent"] == "Googlebot/2.1"
    # Headers the caller did not set are still filled in.
    assert merged["Accept"] == url_safety.DEFAULT_REQUEST_HEADERS["Accept"]


def _capture_safe_get_headers(**kwargs) -> dict:
    """Run safe_requests_get with validation and pinning stubbed out, and
    return the headers mapping that reached requests.get."""
    @contextmanager
    def fake_pin(hostname: str, pinned_ip: str, port: int, exempt_hosts=frozenset()):
        yield

    with patch.object(
        url_safety,
        "validate_url_strict",
        return_value=("https://safe.example/", "1.1.1.1"),
    ), patch.object(
        url_safety, "_pin_dns", side_effect=fake_pin
    ), patch.object(
        url_safety, "_validated_proxy_hosts", return_value=frozenset()
    ), patch.object(
        url_safety.requests, "get", return_value=SimpleNamespace(status_code=200)
    ) as request_get:
        url_safety.safe_requests_get("https://safe.example/", **kwargs)
    return request_get.call_args.kwargs["headers"]


def test_safe_requests_get_sends_no_accept_language_by_default() -> None:
    headers = _capture_safe_get_headers()
    assert "Accept-Language" not in headers
    assert headers["User-Agent"] == url_safety.DEFAULT_USER_AGENT


def test_safe_requests_get_preserves_a_caller_supplied_accept_language() -> None:
    headers = _capture_safe_get_headers(headers={"Accept-Language": "de-DE,de;q=0.9"})
    assert headers["Accept-Language"] == "de-DE,de;q=0.9"
    # The rest of the defaults are still filled in.
    assert headers["Accept"] == url_safety.DEFAULT_REQUEST_HEADERS["Accept"]


def test_with_default_headers_preserves_other_kwargs_and_constant() -> None:
    before = dict(url_safety.DEFAULT_REQUEST_HEADERS)
    kwargs = url_safety._with_default_headers({"stream": True, "allow_redirects": False})
    assert kwargs["stream"] is True
    assert kwargs["allow_redirects"] is False
    url_safety._with_default_headers({"headers": {"User-Agent": "mutating/1.0"}})
    assert url_safety.DEFAULT_REQUEST_HEADERS == before


def test_pin_dns_restores_getaddrinfo_on_exception() -> None:
    before = socket.getaddrinfo
    with pytest.raises(RuntimeError):
        with url_safety._pin_dns("pinned.example", "8.8.8.8", 443):
            raise RuntimeError("boom")
    assert socket.getaddrinfo is before


def test_pin_dns_lock_refuses_concurrent_entry() -> None:
    """The non-blocking lock raises rather than corrupts state."""
    entered = threading.Event()
    proceed = threading.Event()
    second_exc: list[Exception] = []

    def first_thread():
        with url_safety._pin_dns("a.example", "1.1.1.1", 443):
            entered.set()
            proceed.wait()

    def second_thread():
        entered.wait()
        try:
            with url_safety._pin_dns("b.example", "2.2.2.2", 443):
                pass
        except url_safety.URLSafetyError as exc:
            second_exc.append(exc)

    t1 = threading.Thread(target=first_thread)
    t2 = threading.Thread(target=second_thread)
    t1.start()
    t2.start()
    t2.join(timeout=5)
    proceed.set()
    t1.join(timeout=5)
    assert len(second_exc) == 1, "concurrent _pin_dns must raise URLSafetyError"


# ---------------------------------------------------------------------------
# Playwright route handler factory
# ---------------------------------------------------------------------------


class _FakeRoute:
    def __init__(self) -> None:
        self.action: str | None = None

    def abort(self) -> None:
        self.action = "abort"

    def continue_(self) -> None:
        self.action = "continue"


class _FakeRequest:
    def __init__(self, url: str, resource_type: str = "document") -> None:
        self.url = url
        self.resource_type = resource_type


def test_route_handler_continues_public_host() -> None:
    handler = url_safety.make_safe_playwright_route_handler()
    fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443))]
    with patch.object(url_safety.socket, "getaddrinfo", return_value=fake_addrinfo):
        route = _FakeRoute()
        handler(route, _FakeRequest("https://safe.example/style.css"))
        assert route.action == "continue"


def test_route_handler_aborts_private_resolution() -> None:
    handler = url_safety.make_safe_playwright_route_handler()
    fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))]
    with patch.object(url_safety.socket, "getaddrinfo", return_value=fake_addrinfo):
        route = _FakeRoute()
        handler(route, _FakeRequest("http://attacker.example/exfil"))
        assert route.action == "abort"


def test_route_handler_allows_data_urls() -> None:
    """data:, blob:, chrome-extension: schemes are not DNS-bound."""
    handler = url_safety.make_safe_playwright_route_handler()
    route = _FakeRoute()
    handler(route, _FakeRequest("data:image/png;base64,iVBOR..."))
    assert route.action == "continue"


def test_route_handler_blocks_specified_resource_types() -> None:
    handler = url_safety.make_safe_playwright_route_handler(
        blocked_resource_types={"image", "font"}
    )
    route = _FakeRoute()
    # Even a public-IP image gets aborted when type is blocked.
    fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443))]
    with patch.object(url_safety.socket, "getaddrinfo", return_value=fake_addrinfo):
        handler(route, _FakeRequest("https://cdn.example/logo.png", "image"))
    assert route.action == "abort"


def test_route_handler_aborts_on_dns_failure() -> None:
    handler = url_safety.make_safe_playwright_route_handler()
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=socket.gaierror("nx")):
        route = _FakeRoute()
        handler(route, _FakeRequest("https://nx.example/"))
        assert route.action == "abort"


def test_route_handler_blocks_metadata_via_fqdn_form() -> None:
    """A redirect or subresource targeting metadata.google.internal. (with
    trailing dot) is short-circuited before DNS resolution."""
    handler = url_safety.make_safe_playwright_route_handler()
    route = _FakeRoute()
    handler(route, _FakeRequest("http://metadata.google.internal./latest"))
    assert route.action == "abort"


def test_route_handler_blocks_obfuscated_ipv4_in_subresource() -> None:
    """Chromium might be tricked into fetching http://2130706433/... via a
    crafted script tag. The route handler normalises the host before
    resolution."""
    handler = url_safety.make_safe_playwright_route_handler()
    route = _FakeRoute()
    # 2130706433 normalises to 127.0.0.1 which is in the hard-block set.
    handler(route, _FakeRequest("http://2130706433/exfil"))
    assert route.action == "abort"


def test_route_handler_blocks_when_ipv6_resolution_is_private() -> None:
    """Dual-stack regression: AF_UNSPEC returns both IPv4 and IPv6. If any
    record (including an IPv6 ULA) is non-public, abort.
    """
    handler = url_safety.make_safe_playwright_route_handler()
    fake = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 0)),
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00::1", 0, 0, 0)),
    ]
    with patch.object(url_safety.socket, "getaddrinfo", return_value=fake):
        route = _FakeRoute()
        handler(route, _FakeRequest("https://dualstack.example/"))
        assert route.action == "abort"


def test_route_handler_continues_when_both_ipv4_and_ipv6_public() -> None:
    handler = url_safety.make_safe_playwright_route_handler()
    fake = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 0)),
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", 0, 0, 0)),
    ]
    with patch.object(url_safety.socket, "getaddrinfo", return_value=fake):
        route = _FakeRoute()
        handler(route, _FakeRequest("https://safe-dualstack.example/"))
        assert route.action == "continue"


# ---------------------------------------------------------------------------
# OAuth token file permission hardening (Phase H)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.name != "posix", reason="asserts POSIX mode bits, which Windows does not represent"
)
def test_save_oauth_token_writes_0o600(tmp_path, monkeypatch) -> None:
    """_save_oauth_token must produce a 0o600 file regardless of whether
    the path existed beforehand or what the umask is."""
    import google_auth  # noqa: WPS433

    target = tmp_path / "config" / "oauth-token.json"
    monkeypatch.setattr(google_auth, "TOKEN_PATH", str(target))
    # Permissive umask: 0o022 would yield 0o644 without our explicit chmod.
    old_umask = os.umask(0o022)
    try:
        google_auth._save_oauth_token({"access_token": "abc"})
        mode = target.stat().st_mode & 0o777
        assert mode == 0o600, f"expected 0o600, got {oct(mode)}"
    finally:
        os.umask(old_umask)


@pytest.mark.skipif(
    os.name != "posix", reason="asserts POSIX mode bits, which Windows does not represent"
)
def test_save_oauth_token_remediates_legacy_0o644(tmp_path, monkeypatch) -> None:
    """A pre-existing 0o644 token (v1.9.x default) is locked down on save."""
    import google_auth  # noqa: WPS433

    target = tmp_path / "config" / "oauth-token.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"legacy": true}')
    os.chmod(target, 0o644)
    assert target.stat().st_mode & 0o777 == 0o644

    monkeypatch.setattr(google_auth, "TOKEN_PATH", str(target))
    google_auth._save_oauth_token({"access_token": "new"})
    assert target.stat().st_mode & 0o777 == 0o600


def test_save_oauth_token_without_fchmod_closes_descriptor(tmp_path, monkeypatch) -> None:
    """Windows has no os.fchmod; persistence must still succeed and close fd."""
    import json

    import google_auth  # noqa: WPS433

    target = tmp_path / "config" / "oauth-token.json"
    monkeypatch.setattr(google_auth, "TOKEN_PATH", str(target))
    monkeypatch.delattr(google_auth.os, "fchmod", raising=False)

    real_open = os.open
    opened_fds = []

    def recording_open(*args, **kwargs):
        fd = real_open(*args, **kwargs)
        opened_fds.append(fd)
        return fd

    monkeypatch.setattr(google_auth.os, "open", recording_open)
    google_auth._save_oauth_token({"access_token": "windows"})

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "access_token": "windows"
    }
    assert len(opened_fds) == 1
    with pytest.raises(OSError):
        os.fstat(opened_fds[0])


def test_save_oauth_token_ignores_fchmod_oserror(tmp_path, monkeypatch) -> None:
    """Filesystems without descriptor chmod support must still persist tokens."""
    import json

    import google_auth  # noqa: WPS433

    target = tmp_path / "config" / "oauth-token.json"
    monkeypatch.setattr(google_auth, "TOKEN_PATH", str(target))

    def unsupported_fchmod(_fd, _mode):
        raise OSError("unsupported")

    # os.fchmod only exists on Windows from Python 3.13; install the stub
    # either way so the OSError path is exercised on every platform.
    monkeypatch.setattr(google_auth.os, "fchmod", unsupported_fchmod, raising=False)
    google_auth._save_oauth_token({"access_token": "portable"})
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "access_token": "portable"
    }


@pytest.mark.skipif(
    os.name != "posix", reason="asserts POSIX mode bits, which Windows does not represent"
)
def test_load_oauth_token_remediates_legacy_0o644(tmp_path, monkeypatch) -> None:
    """_load_oauth_token chmods the file before reading, so the next read
    by any other process sees 0o600 even without a re-save."""
    import google_auth  # noqa: WPS433

    target = tmp_path / "config" / "oauth-token.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"access_token": "x"}')
    os.chmod(target, 0o644)

    monkeypatch.setattr(google_auth, "TOKEN_PATH", str(target))
    data = google_auth._load_oauth_token()
    assert data == {"access_token": "x"}
    assert target.stat().st_mode & 0o777 == 0o600


# ---------------------------------------------------------------------------
# Configured HTTP proxy (issue #280): the proxy host must resolve
# ---------------------------------------------------------------------------


def _addrinfo(ip: str, port: int) -> list:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]


def _system_proxies(monkeypatch, mapping: dict) -> None:
    """Pin what ``requests`` sees as the environment's proxies. Going through
    the real ``getproxies`` would pick up the developer's own HTTPS_PROXY, or
    the Windows registry proxy, and make these tests machine-dependent."""
    monkeypatch.setattr(url_safety.requests.utils, "getproxies", lambda: dict(mapping))


def test_proxy_hosts_reads_environment_and_honours_no_proxy(monkeypatch) -> None:
    _system_proxies(monkeypatch, {"https": "http://127.0.0.1:3128"})
    monkeypatch.setenv("NO_PROXY", "direct.example")
    assert url_safety._proxy_hosts("https://example.com/") == frozenset({"127.0.0.1"})
    assert url_safety._proxy_hosts("https://direct.example/") == frozenset()
    assert url_safety._proxy_hosts("http://example.com/") == frozenset()


def test_proxy_hosts_prefers_explicit_proxies_mapping(monkeypatch) -> None:
    _system_proxies(monkeypatch, {"https": "http://127.0.0.1:3128"})
    explicit = {"https": "proxy.corp.example:8080"}
    assert url_safety._proxy_hosts("https://example.com/", explicit) == frozenset(
        {"proxy.corp.example"}
    )


def test_proxy_hosts_is_empty_without_a_proxy(monkeypatch) -> None:
    _system_proxies(monkeypatch, {})
    assert url_safety._proxy_hosts("https://example.com/") == frozenset()


def test_pin_dns_lets_the_exempt_proxy_host_resolve_to_loopback() -> None:
    """The primitive honours whatever exempt set it is handed. Callers reach it
    through _validated_proxy_hosts, which refuses a loopback proxy before it can
    ever land in that set; this test pins the low-level contract only."""
    original_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host == "127.0.0.1":
            return _addrinfo("127.0.0.1", port or 3128)
        return original_getaddrinfo(host, port, *args, **kwargs)

    with patch.object(url_safety.socket, "getaddrinfo", side_effect=fake_getaddrinfo):
        # Without the exemption the loopback proxy is refused (the #280 symptom).
        with url_safety._pin_dns("pinned.example", "8.8.8.8", 443):
            with pytest.raises(socket.gaierror, match="non-public IP"):
                socket.getaddrinfo("127.0.0.1", 3128)
        with url_safety._pin_dns(
            "pinned.example", "8.8.8.8", 443, exempt_hosts=frozenset({"127.0.0.1"})
        ):
            assert socket.getaddrinfo("127.0.0.1", 3128)[0][4][0] == "127.0.0.1"


def test_pin_dns_exemption_does_not_leak_to_other_hosts() -> None:
    """Only the proxy host is exempt; a redirect target on loopback still fails."""
    original_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host == "redirected.example":
            return _addrinfo("127.0.0.1", port or 80)
        return original_getaddrinfo(host, port, *args, **kwargs)

    with patch.object(url_safety.socket, "getaddrinfo", side_effect=fake_getaddrinfo):
        with url_safety._pin_dns(
            "pinned.example", "8.8.8.8", 443, exempt_hosts=frozenset({"127.0.0.1"})
        ):
            with pytest.raises(socket.gaierror, match="non-public IP"):
                socket.getaddrinfo("redirected.example", 80)


def _fake_resolver(mapping: dict):
    """getaddrinfo stand-in resolving only the named hosts, refusing the rest.

    Refusing everything else keeps these tests from touching the developer's
    real resolver, which would make them slow and network-dependent.
    """
    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host in mapping:
            return _addrinfo(mapping[host], port or 0)
        raise socket.gaierror(socket.EAI_NONAME, f"unmocked host {host!r}")

    return fake_getaddrinfo


def test_assert_proxy_host_is_public_accepts_a_public_proxy() -> None:
    resolver = _fake_resolver({"proxy.corp.example": "8.8.4.4"})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        assert (
            url_safety._assert_proxy_host_is_public("Proxy.Corp.Example")
            == "proxy.corp.example"
        )


@pytest.mark.parametrize(
    "proxy_host",
    [
        "127.0.0.1",          # loopback
        "10.0.0.5",           # RFC 1918
        "192.168.1.10",       # RFC 1918
        "169.254.169.254",    # cloud metadata / link-local
        "100.100.100.200",    # RFC 6598, Alibaba metadata
        "metadata.google.internal",
        "localhost",
    ],
)
def test_assert_proxy_host_is_public_refuses_non_public_proxies(proxy_host) -> None:
    """A proxy is exempt from the pinned scope, so it gets the same policy as
    an audit target. Anything the environment can point at the local network
    or a metadata endpoint must be refused, not exempted."""
    with pytest.raises(url_safety.URLSafetyError, match="Refusing configured HTTP proxy"):
        url_safety._assert_proxy_host_is_public(proxy_host)


def test_assert_proxy_host_is_public_refuses_a_proxy_that_resolves_private() -> None:
    """The literal is public-looking; only resolution reveals the private IP."""
    resolver = _fake_resolver({"proxy.evil.example": "10.1.2.3"})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with pytest.raises(url_safety.URLSafetyError, match="non-public IP 10.1.2.3"):
            url_safety._assert_proxy_host_is_public("proxy.evil.example")


def test_validated_proxy_hosts_is_empty_without_a_proxy(monkeypatch) -> None:
    _system_proxies(monkeypatch, {})
    assert url_safety._validated_proxy_hosts("https://example.com/") == frozenset()


def _run_safe_get_with_proxy(monkeypatch, proxy_url: str, resolves: dict):
    """Drive safe_requests_get with a pinned environment proxy, capturing the
    exempt set handed to _pin_dns. Returns that captured dict."""
    captured: dict = {}
    _system_proxies(monkeypatch, {"https": proxy_url})
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    @contextmanager
    def fake_pin(hostname: str, pinned_ip: str, port: int, exempt_hosts=frozenset()):
        captured["exempt"] = exempt_hosts
        yield

    with patch.object(
        url_safety.socket, "getaddrinfo", side_effect=_fake_resolver(resolves)
    ), patch.object(
        url_safety, "_pin_dns", side_effect=fake_pin
    ), patch.object(
        url_safety.requests, "get", return_value=SimpleNamespace(status_code=200)
    ):
        captured["response"] = url_safety.safe_requests_get(
            "https://example.com/", timeout=5
        )
    return captured


def test_safe_requests_get_exempts_a_public_proxy(monkeypatch) -> None:
    """Positive control: a proxy on a public address is still exempted, so the
    #280 fix keeps working for a real corporate proxy."""
    captured = _run_safe_get_with_proxy(
        monkeypatch,
        "http://proxy.corp.example:8080",
        {"example.com": "93.184.216.34", "proxy.corp.example": "8.8.4.4"},
    )
    assert captured["exempt"] == frozenset({"proxy.corp.example"})
    assert captured["response"].status_code == 200


@pytest.mark.parametrize(
    "proxy_url",
    ["http://169.254.169.254:3128", "http://127.0.0.1:8080"],
)
def test_safe_requests_get_refuses_a_non_public_proxy(monkeypatch, proxy_url) -> None:
    """Negative control: the exemption must never be granted to a proxy on
    loopback or at a metadata address. Before this check, setting HTTPS_PROXY
    was enough to read cloud metadata through every audit."""
    _system_proxies(monkeypatch, {"https": proxy_url})
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    resolver = _fake_resolver({"example.com": "93.184.216.34"})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with pytest.raises(
            url_safety.URLSafetyError, match="Refusing configured HTTP proxy"
        ):
            url_safety.safe_requests_get("https://example.com/", timeout=5)


def test_safe_requests_session_refuses_a_non_public_proxy(monkeypatch) -> None:
    _system_proxies(monkeypatch, {"https": "http://127.0.0.1:8080"})
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    resolver = _fake_resolver({"example.com": "93.184.216.34"})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with pytest.raises(
            url_safety.URLSafetyError, match="Refusing configured HTTP proxy"
        ):
            with url_safety.safe_requests_session("https://example.com/"):
                pass


# ---------------------------------------------------------------------------
# CLAUDE_SEO_LOCAL_TARGETS: explicit, top-level-only local allowlist
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_local_targets(monkeypatch):
    """No test in this module inherits the developer's own allowlist."""
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)


def _loopback_resolver(host_ips: dict):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host in host_ips:
            return _addrinfo(host_ips[host], port or 0)
        raise socket.gaierror(socket.EAI_NONAME, f"unmocked host {host!r}")

    return fake_getaddrinfo


def test_local_targets_unset_leaves_behaviour_unchanged(monkeypatch) -> None:
    """The default policy must be byte-for-byte what it was before the flag."""
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)
    assert url_safety.validate_url("http://localhost:3000/") is False
    assert url_safety.validate_url("http://127.0.0.1:8080/") is False
    assert url_safety.validate_url("http://192.168.1.10/") is False
    assert url_safety.validate_url("http://100.101.102.103/") is False
    with pytest.raises(url_safety.URLSafetyError, match="Blocked hostname"):
        url_safety.validate_url_strict("http://localhost:3000/")
    with pytest.raises(url_safety.URLSafetyError, match="Blocked hostname"):
        url_safety.validate_url_strict("http://127.0.0.1:8080/")
    with pytest.raises(url_safety.URLSafetyError, match="Blocked IP literal"):
        url_safety.validate_url_strict("http://192.168.1.10/")


def test_empty_local_targets_is_the_same_as_unset(monkeypatch) -> None:
    for value in ("", "   ", ",", " , "):
        monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", value)
        assert url_safety.validate_url("http://localhost:3000/") is False


def test_allowlisted_hostname_passes_at_top_level(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000,127.0.0.1:8080")
    assert url_safety.validate_url("http://localhost:3000/nl") is True

    resolver = _loopback_resolver({"localhost": "127.0.0.1"})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        norm, pinned = url_safety.validate_url_strict("http://localhost:3000/nl")
    assert norm == "http://localhost:3000/nl"
    assert pinned == "127.0.0.1"


def test_allowlisted_ip_literal_passes_at_top_level(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "127.0.0.1:8080")
    assert url_safety.validate_url("http://127.0.0.1:8080/") is True
    assert url_safety.validate_url_strict("http://127.0.0.1:8080/") == (
        "http://127.0.0.1:8080/",
        "127.0.0.1",
    )


def test_bare_host_entry_matches_any_port_and_covers_tailscale(monkeypatch) -> None:
    """RFC 6598 is the Tailscale range; a bare entry names the host only."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "100.101.102.103")
    assert url_safety.validate_url("http://100.101.102.103/") is True
    assert url_safety.validate_url("https://100.101.102.103:8443/staging") is True
    assert url_safety.validate_url_strict("http://100.101.102.103/")[1] == (
        "100.101.102.103"
    )


def test_port_mismatch_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000")
    assert url_safety.validate_url("http://localhost:3001/") is False
    assert url_safety.validate_url("http://localhost/") is False  # implicit :80
    with pytest.raises(url_safety.URLSafetyError, match="Blocked hostname"):
        url_safety.validate_url_strict("http://localhost:3001/")


def test_unlisted_host_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000")
    assert url_safety.validate_url("http://127.0.0.1:3000/") is False
    assert url_safety.validate_url("http://192.168.1.10:3000/") is False
    with pytest.raises(url_safety.URLSafetyError, match="Blocked IP literal"):
        url_safety.validate_url_strict("http://192.168.1.10:3000/")


@pytest.mark.parametrize(
    "target",
    [
        "169.254.169.254",
        "metadata.google.internal",
        "[fd00:ec2::254]",
        "100.100.100.200",
        "metadata.goog",
        "metadata.azure.com",
    ],
)
def test_metadata_endpoints_are_never_allowlistable(monkeypatch, target) -> None:
    """Listing a metadata endpoint must not unblock it. This is the trapdoor
    a naive 'allow loopback and private' carve-out falls through."""
    host = target.strip("[]")
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", f"{host},{host}:80,{host}:3128")
    assert url_safety.validate_url(f"http://{target}/latest/meta-data/") is False
    with pytest.raises(url_safety.URLSafetyError):
        url_safety.validate_url_strict(f"http://{target}/latest/meta-data/")


def test_allowlist_does_not_unblock_link_local_resolution(monkeypatch) -> None:
    """A listed name that resolves into 169.254/16 is still refused: the
    allowlist forgives loopback, RFC 1918 and RFC 6598, never link-local."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "sneaky.local:80")
    resolver = _loopback_resolver({"sneaky.local": "169.254.169.254"})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with pytest.raises(url_safety.URLSafetyError, match="DNS rebinding refused"):
            url_safety.validate_url_strict("http://sneaky.local/")


def test_allowlist_does_not_change_is_safe_ip(monkeypatch) -> None:
    """is_safe_ip stays a pure predicate. Every fail-closed path downstream
    (redirects, subresources) depends on it not reading the environment."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000,127.0.0.1:8080")
    assert url_safety.is_safe_ip("127.0.0.1") is False
    assert url_safety.is_safe_ip("192.168.1.10") is False
    assert url_safety.is_safe_ip("100.101.102.103") is False


def test_allowlisted_host_is_refused_as_a_redirect_target(monkeypatch) -> None:
    """The allowlist is consulted once, for the top-level URL. Inside the
    pinned scope a 30x to the same host resolves through the fall-through
    check, which does not read it."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000")
    resolver = _loopback_resolver({"localhost": "127.0.0.1"})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with url_safety._pin_dns("audited.example", "93.184.216.34", 443):
            with pytest.raises(socket.gaierror, match="non-public IP"):
                socket.getaddrinfo("localhost", 3000)


def test_allowlisted_host_is_refused_as_a_browser_subresource(monkeypatch) -> None:
    """The Playwright route handler never reads the allowlist, so a rendered
    page cannot pull a subresource off the allowlisted dev server."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000,127.0.0.1:8080")
    handler = url_safety.make_safe_playwright_route_handler()
    resolver = _loopback_resolver({"localhost": "127.0.0.1"})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        route = _FakeRoute()
        handler(route, _FakeRequest("http://localhost:3000/app.js", "script"))
        assert route.action == "abort"
        route = _FakeRoute()
        handler(route, _FakeRequest("http://127.0.0.1:8080/app.js", "script"))
        assert route.action == "abort"


def test_local_target_entries_are_normalized(monkeypatch) -> None:
    """Entries go through normalize_hostname, so case, a trailing dot, and
    obfuscated IPv4 cannot be used to smuggle a second spelling past a
    reviewer reading the environment variable."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", " LocalHost.:3000 , 2130706433:8080 ")
    assert url_safety._local_targets() == (("localhost", 3000), ("127.0.0.1", 8080))
    assert url_safety.validate_url("http://localhost:3000/") is True
    assert url_safety.validate_url("http://127.0.0.1:8080/") is True


def test_test_suffix_wildcard_allows_reserved_test_hosts_at_top_level(
    monkeypatch,
) -> None:
    """*.test covers all RFC-reserved local-development names, including
    nested names, while retaining the existing top-level-only boundary."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "*.test")
    resolver = _loopback_resolver(
        {
            "klarc.test": "127.0.0.1",
            "preview.klarc.test": "127.0.0.1",
        }
    )
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        assert url_safety.validate_url_strict("https://klarc.test/")[1] == (
            "127.0.0.1"
        )
        assert url_safety.validate_url_strict("https://preview.klarc.test/")[1] == (
            "127.0.0.1"
        )


def test_test_suffix_wildcard_respects_ports_and_label_boundaries(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "*.test:8443")
    resolver = _loopback_resolver(
        {
            "klarc.test": "127.0.0.1",
            "test": "127.0.0.1",
            "eviltest": "127.0.0.1",
            "klarc.test.evil": "127.0.0.1",
        }
    )
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        assert url_safety.validate_url_strict("https://klarc.test:8443/")[1] == (
            "127.0.0.1"
        )
        for url in (
            "https://klarc.test/",
            "https://test:8443/",
            "https://eviltest:8443/",
            "https://klarc.test.evil:8443/",
        ):
            with pytest.raises(
                url_safety.URLSafetyError, match="DNS rebinding refused"
            ):
                url_safety.validate_url_strict(url)


def test_only_test_suffix_wildcard_is_accepted(monkeypatch) -> None:
    """Broad or malformed patterns are dropped rather than widening access."""
    monkeypatch.setenv(
        "CLAUDE_SEO_LOCAL_TARGETS",
        ",".join(
            (
                "*",
                "*.*",
                "*.com",
                "*.internal",
                "*.evil@test",
                "*.user:pass@test:8443",
                "*.test/ignored",
                "*.test:8443/path",
                "*.test?ignored",
                "*.test#ignored",
                "*.test:",
                "*.teſt",
                "*.teſt:443",
                "*.test:" + "9" * 5000,
                "*.test",
                "*.TEST:8443",
            )
        ),
    )
    assert url_safety._local_targets() == (("*.test", None), ("*.test", 8443))


def test_test_suffix_wildcard_rejects_invalid_dns_boundaries(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "*.test")
    invalid_hosts = (
        ".test",
        "foo..test",
        "-foo.test",
        "foo-.test",
        f"{'x' * 64}.test",
    )
    resolver = _loopback_resolver({host: "127.0.0.1" for host in invalid_hosts})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        for host in invalid_hosts:
            with pytest.raises(
                url_safety.URLSafetyError, match="DNS rebinding refused"
            ):
                url_safety.validate_url_strict(f"https://{host}/")


def test_malformed_entries_are_dropped_not_widened(monkeypatch) -> None:
    monkeypatch.setenv(
        "CLAUDE_SEO_LOCAL_TARGETS",
        ",".join(
            (
                "localhost:notaport",
                "",
                ":8080",
                "localhost:",
                "user@localhost",
                "user:pass@localhost:8443",
                "localhost/path",
                "localhost?query",
                "localhost#fragment",
                "http://localhost:8080",
                "[localhost]",
                "[127.0.0.1]",
                "[example.com]:443",
                "localhost:3000",
            )
        ),
    )
    assert url_safety._local_targets() == (("localhost", 3000),)
    assert url_safety.validate_url("http://localhost:3000/") is True
    assert url_safety.validate_url("http://localhost:8080/") is False
    assert url_safety.validate_url("http://localhost:54321/") is False


def test_ipv6_entries_parse_in_both_spellings(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "[::1]:3000,fd00::1")
    assert url_safety._local_targets() == (("::1", 3000), ("fd00::1", None))
    assert url_safety.validate_url("http://[::1]:3000/") is True
    assert url_safety.validate_url("http://[::1]:3001/") is False


def test_allowlist_does_not_bypass_authority_confusion_checks(monkeypatch) -> None:
    """The allowlist relaxes the address policy, nothing else."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000")
    assert url_safety.validate_url("http://user@localhost:3000/") is False
    assert url_safety.validate_url("http://localhost:3000\\@evil.example/") is False
    assert url_safety.validate_url("ftp://localhost:3000/") is False


def test_pin_dns_rechecks_a_dns_named_exempt_proxy_at_resolve_time() -> None:
    """A proxy validated as public must not be trusted if it later resolves to a
    private or metadata address (DNS rebinding between validation and use)."""
    original_getaddrinfo = socket.getaddrinfo

    def rebinding_getaddrinfo(host, port, *args, **kwargs):
        if host == "proxy.example":
            return _addrinfo("169.254.169.254", port or 3128)
        return original_getaddrinfo(host, port, *args, **kwargs)

    with patch.object(url_safety.socket, "getaddrinfo", side_effect=rebinding_getaddrinfo):
        with url_safety._pin_dns(
            "pinned.example", "8.8.8.8", 443, exempt_hosts=frozenset({"proxy.example"})
        ):
            with pytest.raises(socket.gaierror, match="non-public IP"):
                socket.getaddrinfo("proxy.example", 3128)


def test_pin_dns_lets_a_dns_named_exempt_proxy_resolve_to_public() -> None:
    original_getaddrinfo = socket.getaddrinfo

    def public_getaddrinfo(host, port, *args, **kwargs):
        if host == "proxy.example":
            return _addrinfo("93.184.216.34", port or 3128)
        return original_getaddrinfo(host, port, *args, **kwargs)

    with patch.object(url_safety.socket, "getaddrinfo", side_effect=public_getaddrinfo):
        with url_safety._pin_dns(
            "pinned.example", "8.8.8.8", 443, exempt_hosts=frozenset({"proxy.example"})
        ):
            assert socket.getaddrinfo("proxy.example", 3128)[0][4][0] == "93.184.216.34"
