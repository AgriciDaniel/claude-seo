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
    def fake_pin(hostname: str, pinned_ip: str, port: int):
        captured["pin"] = (hostname, pinned_ip, port)
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

    validate.assert_called_once_with("https://safe.example/path")
    request_head.assert_called_once_with(
        "https://safe.example/path",
        timeout=7,
        allow_redirects=True,
    )
    assert captured["pin"] == ("safe.example", "1.1.1.1", 443)
    assert result is response


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

    monkeypatch.setattr(google_auth.os, "fchmod", unsupported_fchmod)
    google_auth._save_oauth_token({"access_token": "portable"})
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "access_token": "portable"
    }


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
