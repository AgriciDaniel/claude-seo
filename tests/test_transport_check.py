"""
Tests for scripts/transport_check.py: TLS certificate, security header and
redirect checks.

Nothing here touches the network. ``socket.create_connection``,
``ssl.SSLContext.wrap_socket`` and the ``url_safety`` fetch helper are
replaced by recorders, so each test can also assert what the script would
have connected to. The fake sockets raise on any use beyond the handshake
surface, which is how "no data is sent or read" is enforced.
"""

from __future__ import annotations

import base64
import json
import os
import re
import socket
import ssl
import sys
from datetime import datetime, timezone

import pytest
import requests

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import transport_check as tc  # noqa: E402
from url_safety import URLSafetyError  # noqa: E402

PUBLIC_IP = "93.184.216.34"
NOW = datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()
DAY = 86400

# Self-signed throwaway certificate (the private key was discarded), DER, base64.
# Subject and issuer: CN=fixture.example.test, O=Fixture Org
# Valid 2020-01-01 to 2021-01-01 UTC.
# subjectAltName: fixture.example.test, www.fixture.example.test,
#                 *.wild.example.test, 192.0.2.7, 2001:db8::7
FIXTURE_DER = base64.b64decode(
    "MIICKDCCAc+gAwIBAgIUDJc2dXhK+lixzsOhiwZXgcIFpqMwCgYIKoZIzj0EAwIwNTEdMBsGA1UE"
    "AwwUZml4dHVyZS5leGFtcGxlLnRlc3QxFDASBgNVBAoMC0ZpeHR1cmUgT3JnMB4XDTIwMDEwMTAw"
    "MDAwMFoXDTIxMDEwMTAwMDAwMFowNTEdMBsGA1UEAwwUZml4dHVyZS5leGFtcGxlLnRlc3QxFDAS"
    "BgNVBAoMC0ZpeHR1cmUgT3JnMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6ZxflPBKM8/NBTya"
    "2fsWODv9DdBIXHNVANGSzZKG23GUmA6+GnEwrRFRP9BE6icWbhr2LECOe5eHkrH2CAEl0qOBvDCB"
    "uTAdBgNVHQ4EFgQUSiGbxgVgxLfdPiMYm1lSjOj48mEwHwYDVR0jBBgwFoAUSiGbxgVgxLfdPiMY"
    "m1lSjOj48mEwDwYDVR0TAQH/BAUwAwEB/zBmBgNVHREEXzBdghRmaXh0dXJlLmV4YW1wbGUudGVz"
    "dIIYd3d3LmZpeHR1cmUuZXhhbXBsZS50ZXN0ghMqLndpbGQuZXhhbXBsZS50ZXN0hwTAAAIHhxAg"
    "AQ24AAAAAAAAAAAAAAAHMAoGCCqGSM49BAMCA0cAMEQCIGzAsWjlsio52r/hXabfJ6MZTx0i0H6X"
    "ZyCm4a9cjCWjAiBBJ5sapBLddkeZNfMR24mvcxiAoFZF29Hs0pDdCvj7qw=="
)
FIXTURE_MID_VALIDITY = datetime(2020, 6, 1, tzinfo=timezone.utc).timestamp()

GOOD_HSTS = "max-age=63072000; includeSubDomains; preload"
GOOD_HEADERS = {
    "Strict-Transport-Security": GOOD_HSTS,
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'nonce-r4nd'; "
                               "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=()",
}


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeSock:
    """A raw TCP socket that only tolerates settimeout() and close()."""

    def __init__(self) -> None:
        self.closed = False
        self.timeouts: list[float] = []

    def settimeout(self, value: float) -> None:
        self.timeouts.append(value)

    def close(self) -> None:
        self.closed = True

    def __getattr__(self, name: str):
        raise AssertionError(f"raw socket .{name} must not be used")


class FakeTLS:
    """A wrapped socket that only tolerates the read-the-handshake surface."""

    def __init__(self, cert=None, der=None, protocol="TLSv1.3",
                 cipher=("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)) -> None:
        self._cert, self._der, self._protocol, self._cipher = cert, der, protocol, cipher
        self.closed = False

    def getpeercert(self, binary_form: bool = False):
        return self._der if binary_form else self._cert

    def version(self):
        return self._protocol

    def cipher(self):
        return self._cipher

    def close(self) -> None:
        self.closed = True

    def __getattr__(self, name: str):
        raise AssertionError(f"TLS socket .{name} must not be used (no data may be sent or read)")


class Net:
    """What the script connected to, and what each handshake should answer."""

    def __init__(self) -> None:
        self.connects: list[tuple] = []
        self.socks: list[FakeSock] = []
        self.wraps: list[dict] = []
        self.verified = None    # FakeTLS or an exception, for the verifying handshake
        self.unverified = None  # the same, for the certificate-reading handshake


@pytest.fixture
def net(monkeypatch) -> Net:
    for name in (*tc.PROXY_ENV_VARS, "CLAUDE_SEO_LOCAL_TARGETS"):
        monkeypatch.delenv(name, raising=False)
    state = Net()

    def create_connection(address, timeout=None, **_kwargs):
        state.connects.append((address, timeout))
        sock = FakeSock()
        state.socks.append(sock)
        return sock

    def wrap_socket(self, sock, server_hostname=None, **_kwargs):
        verify = self.verify_mode != ssl.CERT_NONE
        state.wraps.append({"verify": verify, "server_hostname": server_hostname, "sock": sock})
        outcome = state.verified if verify else state.unverified
        if isinstance(outcome, BaseException):
            raise outcome
        assert outcome is not None, "unexpected handshake"
        return outcome

    monkeypatch.setattr(socket, "create_connection", create_connection)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap_socket)
    return state


@pytest.fixture
def public(monkeypatch):
    """Make the validator answer PUBLIC_IP for every name, with no DNS."""
    unresolvable: set[str] = set()

    def fake_validate(url: str):
        host = tc.urlparse(url).hostname
        if host in unresolvable:
            raise URLSafetyError(f"DNS resolution failed for {host}")
        return url, PUBLIC_IP

    monkeypatch.setattr(tc, "validate_url_strict", fake_validate)
    return unresolvable


class FakeRawHeaders:
    def __init__(self, cookies) -> None:
        self._cookies = list(cookies)

    def getlist(self, name: str):
        return list(self._cookies) if name.lower() == "set-cookie" else []


class FakeRaw:
    def __init__(self, cookies) -> None:
        self.headers = FakeRawHeaders(cookies)


class FakeResponse:
    """A requests.Response stand-in with no body attributes at all."""

    def __init__(self, url, status=200, headers=None, cookies=(), history=(), raw=True) -> None:
        self.url, self.status_code = url, status
        self.headers = dict(headers or {})
        self.history = list(history)
        self.closed = False
        if raw:
            self.raw = FakeRaw(cookies)

    def close(self) -> None:
        self.closed = True


def redirect(url, target, status=301, headers=None):
    return FakeResponse(url, status, {"Location": target, **(headers or {})})


def site(host="example.com", headers=None, cookies=()):
    """Routes for a tidy site: http and www both go to https://host/ in one hop."""
    headers = GOOD_HEADERS if headers is None else headers
    home = f"https://{host}/"
    return {
        home: FakeResponse(home, 200, headers, cookies),
        f"http://{host}/": FakeResponse(
            home, 200, headers, cookies, history=[redirect(f"http://{host}/", home)]),
        f"https://www.{host}/": FakeResponse(
            home, 200, headers, cookies,
            history=[redirect(f"https://www.{host}/", home,
                              headers={"Strict-Transport-Security": GOOD_HSTS})]),
    }


@pytest.fixture
def web(monkeypatch):
    """Install URL routes for safe_requests_get; returns (install, calls)."""
    calls: list[str] = []
    routes: dict = {}

    def fake_get(url, **kwargs):
        calls.append(url)
        assert kwargs.get("stream") is True, "the body must not be downloaded"
        outcome = routes.get(url)
        if outcome is None:
            raise OSError(f"no route to {url}")
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(tc, "safe_requests_get", fake_get)

    def install(new_routes: dict) -> list[str]:
        routes.clear()
        routes.update(new_routes)
        return calls

    return install


def peercert(*names, not_before=NOW - 30 * DAY, not_after=NOW + 60 * DAY) -> dict:
    def stamp(seconds: float) -> str:
        return datetime.fromtimestamp(seconds, timezone.utc).strftime("%b %d %H:%M:%S %Y GMT")

    return {
        "subject": ((("commonName", names[0]),),),
        "issuer": ((("countryName", "US"),), (("organizationName", "Example Trust"),),
                   (("commonName", "Example CA 1"),)),
        "notBefore": stamp(not_before),
        "notAfter": stamp(not_after),
        "subjectAltName": tuple(("DNS", name) for name in names),
    }


def verify_error(code: int, message: str) -> ssl.SSLCertVerificationError:
    exc = ssl.SSLCertVerificationError(
        1, f"[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: {message}")
    exc.verify_code, exc.verify_message = code, message
    return exc


def ids(report_or_findings) -> list[str]:
    findings = (report_or_findings["findings"] if isinstance(report_or_findings, dict)
                else report_or_findings)
    return [finding["id"] for finding in findings]


def by_id(report: dict) -> dict:
    return {finding["id"]: finding for finding in report["findings"]}


# ---------------------------------------------------------------------------
# Refusals: nothing is opened for a blocked target
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://127.0.0.1/",
    "https://localhost/",
    "https://10.0.0.5/",
    "https://192.168.1.10:8443/admin",
    "https://169.254.169.254/latest/meta-data/",
    "https://[::1]/",
    "https://100.100.100.200/",
    "http://127.0.0.1/",
    "http://localhost:8080/",
    "ftp://example.com/",
    "https://user:pw@127.0.0.1/",
])
def test_blocked_target_is_refused_before_any_socket_or_request(url, net, web) -> None:
    calls = web({})
    report = tc.run(url, now=NOW)
    assert set(report) == {"url", "error"}
    assert report["error"].startswith("url_safety:")
    assert net.connects == [] and net.wraps == []
    assert calls == []


def test_check_tls_refuses_a_private_target_on_its_own(net) -> None:
    with pytest.raises(URLSafetyError):
        tc.check_tls("https://10.0.0.5/", now=NOW)
    assert net.connects == []


def test_cli_prints_error_json_and_exits_2_for_a_refused_target(net, web, capsys) -> None:
    web({})
    assert tc.main(["https://127.0.0.1/"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert "error" in out and out["url"] == "https://127.0.0.1/"
    assert net.connects == []


# ---------------------------------------------------------------------------
# The socket goes to the validated IP, never to the hostname
# ---------------------------------------------------------------------------

def test_socket_connects_to_validated_ip_and_hostname_is_sni_only(net, public, monkeypatch) -> None:
    def no_dns(*_args, **_kwargs):
        raise AssertionError("check_tls must not resolve the hostname itself")

    monkeypatch.setattr(socket, "getaddrinfo", no_dns)
    net.verified = FakeTLS(cert=peercert("example.com", "www.example.com"))
    tls = tc.check_tls("https://Example.COM./pricing", timeout=7, now=NOW)

    assert net.connects == [((PUBLIC_IP, 443), 7)]
    assert all("example" not in str(address) for address, _timeout in net.connects)
    assert [w["server_hostname"] for w in net.wraps] == ["example.com"]
    assert tls["connected_ip"] == PUBLIC_IP and tls["verified"] is True
    assert net.socks[0].timeouts and 0 < net.socks[0].timeouts[0] <= 7
    assert net.verified.closed and net.socks[0].closed


def test_ipv6_validated_address_and_explicit_port_are_used(net, monkeypatch) -> None:
    monkeypatch.setattr(tc, "validate_url_strict", lambda url: (url, "2606:2800:220:1::1946"))
    net.verified = FakeTLS(cert=peercert("example.com"))
    tls = tc.check_tls("https://example.com:8443/", now=NOW)
    assert net.connects[0][0] == ("2606:2800:220:1::1946", 8443)
    assert tls["port"] == 8443 and tls["connected_ip"] == "2606:2800:220:1::1946"


def test_a_validator_answer_that_is_not_an_ip_literal_is_never_dialled(net, monkeypatch) -> None:
    monkeypatch.setattr(tc, "validate_url_strict", lambda url: (url, "evil.example.net"))
    tls = tc.check_tls("https://example.com/", now=NOW)
    assert net.connects == []
    assert "not an IP literal" in tls["error"]


def test_certificate_reading_handshake_reuses_the_same_validated_ip(net, public) -> None:
    net.verified = verify_error(10, "certificate has expired")
    net.unverified = FakeTLS(der=FIXTURE_DER)
    tc.check_tls("https://fixture.example.test/", now=NOW)
    assert [address for address, _timeout in net.connects] == [(PUBLIC_IP, 443), (PUBLIC_IP, 443)]
    assert [w["verify"] for w in net.wraps] == [True, False]
    assert all(w["server_hostname"] == "fixture.example.test" for w in net.wraps)
    assert all(sock.closed for sock in net.socks) and net.unverified.closed


# ---------------------------------------------------------------------------
# Certificate verdicts
# ---------------------------------------------------------------------------

def test_valid_certificate_is_reported_in_full(net, public) -> None:
    net.verified = FakeTLS(cert=peercert("example.com", "www.example.com"))
    tls = tc.check_tls("https://example.com/", now=NOW)
    assert tls["verified"] is True and tls["verify_error"] is None
    assert tls["subject"] == {"common_name": "example.com", "organization": None}
    assert tls["issuer"] == {"common_name": "Example CA 1", "organization": "Example Trust"}
    assert tls["not_before"] == "2026-05-02T00:00:00Z"
    assert tls["not_after"] == "2026-07-31T00:00:00Z"
    assert tls["days_until_expiry"] == 60 and tls["expired"] is False
    assert tls["covers_host"] is True
    assert tls["sibling_host"] == "www.example.com" and tls["covers_sibling"] is True
    assert (tls["protocol"], tls["cipher"], tls["cipher_bits"]) == (
        "TLSv1.3", "TLS_AES_256_GCM_SHA384", 256)
    assert tc._tls_findings(tls, {}) == []


def test_expired_certificate_is_critical(net, public) -> None:
    net.verified = verify_error(10, "certificate has expired")
    net.unverified = FakeTLS(der=FIXTURE_DER)
    tls = tc.check_tls("https://fixture.example.test/", now=NOW)
    assert tls["verified"] is False
    assert tls["verify_error"] == "certificate has expired" and tls["verify_code"] == 10
    assert tls["certificate_read"] is True and tls["expired"] is True
    assert tls["not_after"] == "2021-01-01T00:00:00Z" and tls["days_until_expiry"] < 0
    assert tls["covers_host"] is True
    findings = tc._tls_findings(tls, {})
    assert ids(findings) == ["tls-cert-expired"]
    assert findings[0]["severity"] == "Critical"
    assert findings[0]["evidence"]["not_after"] == "2021-01-01T00:00:00Z"


def test_hostname_mismatch_is_critical(net, public) -> None:
    net.verified = verify_error(
        62, "Hostname mismatch, certificate is not valid for 'shop.example.org'.")
    net.unverified = FakeTLS(der=FIXTURE_DER)
    tls = tc.check_tls("https://shop.example.org/", now=FIXTURE_MID_VALIDITY)
    assert tls["verified"] is False and tls["covers_host"] is False
    assert tls["expired"] is False
    findings = tc._tls_findings(tls, {})
    assert ids(findings) == ["tls-cert-hostname-mismatch"]
    assert findings[0]["severity"] == "Critical"
    assert "fixture.example.test" in findings[0]["evidence"]["san"]


@pytest.mark.parametrize("days_left, expected", [
    (0.5, ["tls-cert-expiring-soon"]),
    (7.5, ["tls-cert-expiring-soon"]),
    (14.5, ["tls-cert-expiring-soon"]),
    (15.5, []),
    (90.5, []),
])
def test_expiry_within_14_days_is_high(days_left, expected, net, public) -> None:
    net.verified = FakeTLS(cert=peercert("example.com", "www.example.com",
                                         not_after=NOW + days_left * DAY))
    tls = tc.check_tls("https://example.com/", now=NOW)
    findings = tc._tls_findings(tls, {})
    assert ids(findings) == expected
    assert tls["days_until_expiry"] == int(days_left)
    if findings:
        assert findings[0]["severity"] == "High"


def test_untrusted_chain_is_high_and_the_certificate_is_still_described(net, public) -> None:
    net.verified = verify_error(18, "self-signed certificate")
    net.unverified = FakeTLS(der=FIXTURE_DER)
    tls = tc.check_tls("https://fixture.example.test/", now=FIXTURE_MID_VALIDITY)
    assert tls["issuer"] == {"common_name": "fixture.example.test", "organization": "Fixture Org"}
    findings = tc._tls_findings(tls, {})
    assert [(f["id"], f["severity"]) for f in findings] == [("tls-cert-not-trusted", "High")]
    assert findings[0]["evidence"]["verify_error"] == "self-signed certificate"


def test_verdict_falls_back_to_the_openssl_code_when_the_certificate_cannot_be_read(
        net, public) -> None:
    net.verified = verify_error(10, "certificate has expired")
    net.unverified = ConnectionResetError("reset during handshake")
    tls = tc.check_tls("https://example.com/", now=NOW)
    assert tls["certificate_read"] is False and "ConnectionResetError" in tls["certificate_error"]
    assert ids(tc._tls_findings(tls, {})) == ["tls-cert-expired"]
    assert all(sock.closed for sock in net.socks)


def test_unreadable_certificate_bytes_do_not_raise(net, public) -> None:
    net.verified = verify_error(18, "self-signed certificate")
    net.unverified = FakeTLS(der=b"\x30\x82\xff\xff garbage")
    tls = tc.check_tls("https://example.com/", now=NOW)
    assert tls["certificate_read"] is False
    assert ids(tc._tls_findings(tls, {})) == ["tls-cert-not-trusted"]


@pytest.mark.parametrize("failure", [
    TimeoutError("timed out"),
    ConnectionRefusedError("refused"),
    ssl.SSLError(1, "[SSL: TLSV1_ALERT_PROTOCOL_VERSION] tlsv1 alert protocol version"),
])
def test_failed_handshake_is_reported_and_the_socket_is_closed(failure, net, public) -> None:
    net.verified = failure
    tls = tc.check_tls("https://example.com/", now=NOW)
    assert type(failure).__name__ in tls["error"]
    assert [sock.closed for sock in net.socks] == [True]
    findings = tc._tls_findings(tls, {})
    assert [(f["id"], f["severity"]) for f in findings] == [("tls-handshake-failed", "High")]


def test_old_protocol_is_flagged(net, public) -> None:
    net.verified = FakeTLS(cert=peercert("example.com", "www.example.com"), protocol="TLSv1.1")
    tls = tc.check_tls("https://example.com/", now=NOW)
    assert ids(tc._tls_findings(tls, {})) == ["tls-old-protocol"]


# ---------------------------------------------------------------------------
# http URLs and proxies
# ---------------------------------------------------------------------------

def test_http_url_skips_tls_with_a_clear_message_but_still_checks_redirects(
        net, public, web) -> None:
    calls = web(site())
    report = tc.run("http://example.com/", now=NOW)
    assert set(report["tls"]) == {"skipped"} and "not an https URL" in report["tls"]["skipped"]
    assert net.connects == []
    assert calls.count("http://example.com/") == 1  # one fetch serves all three checks
    assert report["headers"]["https"] is True and report["headers"]["hsts"]["present"] is True
    assert report["redirects"]["http_to_https"]["redirects_to_https"] is True
    assert report["redirects"]["http_to_https"]["one_hop"] is True


@pytest.mark.parametrize("variable", ["HTTPS_PROXY", "https_proxy", "ALL_PROXY"])
def test_proxy_configured_skips_the_raw_socket(variable, net, public, web, monkeypatch) -> None:
    monkeypatch.setenv(variable, "http://proxy.example.net:3128")
    web(site())
    report = tc.run("https://example.com/", now=NOW)
    assert report["tls"] == {"skipped": "proxy configured"}
    assert net.connects == [] and net.wraps == []
    assert report["headers"]["hsts"]["present"] is True  # header checks still run
    assert not [i for i in ids(report) if i.startswith("tls-")]


# ---------------------------------------------------------------------------
# Header grading
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value, max_age, subdomains, preload, meets, finding", [
    (None, None, False, False, False, "hsts-missing"),
    ("max-age=63072000; includeSubDomains; preload", 63072000, True, True, True, None),
    ("MAX-AGE=\"31536000\" ; INCLUDESUBDOMAINS ; PRELOAD", 31536000, True, True, True, None),
    ("max-age=31536000; includeSubDomains", 31536000, True, False, False, None),
    ("max-age=31535999; includeSubDomains; preload", 31535999, True, True, False, "hsts-weak"),
    ("max-age=300", 300, False, False, False, "hsts-weak"),
    ("max-age=63072000; preload", 63072000, False, True, False, "hsts-weak"),
    ("max-age=0; includeSubDomains", 0, True, False, False, "hsts-disabled"),
    ("includeSubDomains; preload", None, True, True, False, "hsts-disabled"),
    ("max-age=abc", None, False, False, False, "hsts-disabled"),
    ("max-age=63072000; includeSubDomains; preload, max-age=1", 63072000, True, True, True, None),
])
def test_hsts_variants(value, max_age, subdomains, preload, meets, finding) -> None:
    headers = {k: v for k, v in GOOD_HEADERS.items() if k != "Strict-Transport-Security"}
    if value is not None:
        headers["strict-transport-security"] = value
    graded = tc.analyze_headers(headers, [])
    hsts = graded["hsts"]
    assert (hsts["max_age"], hsts["include_subdomains"], hsts["preload"]) == (
        max_age, subdomains, preload)
    assert hsts["meets_preload_requirements"] is meets
    assert bool(hsts["preload_gaps"]) is not meets
    found = tc._header_findings({"https": True, **graded})
    assert ids(found) == ([finding] if finding else [])
    if finding:
        severity = {"hsts-missing": "Medium", "hsts-disabled": "Medium", "hsts-weak": "Low"}
        assert found[0]["severity"] == severity[finding]


def test_missing_hsts_is_not_a_finding_on_a_plain_http_response() -> None:
    graded = tc.analyze_headers({}, ["sid=1"], https=False)
    found = ids(tc._header_findings({"https": False, **graded}))
    assert "hsts-missing" not in found and "cookie-missing-secure" not in found


def test_strong_headers_produce_no_findings() -> None:
    graded = tc.analyze_headers(GOOD_HEADERS, ["sid=1; Secure; HttpOnly; SameSite=Lax"])
    assert tc._header_findings({"https": True, **graded}) == []
    assert graded["framing"] == {"x_frame_options": None, "frame_ancestors": True, "ok": True}


def test_csp_gaps() -> None:
    weak = tc.analyze_headers({"Content-Security-Policy": "script-src 'self' 'unsafe-inline' *"})
    joined = " ".join(weak["csp"]["issues"])
    for fragment in ("'unsafe-inline' in script-src", "* in script-src", "object-src", "base-uri"):
        assert fragment in joined
    no_script = tc.analyze_headers({"Content-Security-Policy": "img-src 'self'"})
    assert "No script-src or default-src" in no_script["csp"]["issues"][0]
    nonce = tc.analyze_headers(
        {"Content-Security-Policy": "script-src 'unsafe-inline' 'nonce-x'; object-src 'none'; "
                                    "base-uri 'none'"})
    assert nonce["csp"]["issues"] == []

    def csp_finding(headers):
        return [f for f in ids(tc._header_findings({"https": True, **tc.analyze_headers(headers)}))
                if f.startswith("csp-")]

    assert csp_finding({}) == ["csp-missing"]
    assert csp_finding({"Content-Security-Policy": "img-src 'self'"}) == ["csp-weak"]
    assert csp_finding(
        {"Content-Security-Policy-Report-Only": "default-src 'self'"}) == ["csp-report-only"]


def test_report_only_frame_ancestors_does_not_count_as_framing_protection() -> None:
    graded = tc.analyze_headers(
        {"Content-Security-Policy-Report-Only": "frame-ancestors 'none'"})
    assert graded["framing"]["ok"] is False


def test_hygiene_headers_are_low_or_info() -> None:
    graded = tc.analyze_headers({
        "Strict-Transport-Security": GOOD_HSTS,
        "X-Content-Type-Options": "sniff",
        "X-Frame-Options": "ALLOW-FROM https://x.example",
        "Referrer-Policy": "no-referrer, unsafe-url",
    })
    found = {f["id"]: f["severity"] for f in tc._header_findings({"https": True, **graded})}
    assert found == {
        "csp-missing": "Low",
        "nosniff-missing": "Low",
        "clickjacking-protection-missing": "Low",
        "referrer-policy-unsafe": "Low",
        "permissions-policy-missing": "Info",
    }
    absent = tc.analyze_headers({"X-Frame-Options": "sameorigin"})
    found = {f["id"]: f["severity"] for f in tc._header_findings({"https": True, **absent})}
    assert found["referrer-policy-missing"] == "Info"
    assert "clickjacking-protection-missing" not in found


# ---------------------------------------------------------------------------
# Cookies: flags per name, values never leave the parser
# ---------------------------------------------------------------------------

def test_cookie_without_secure_is_reported_by_name() -> None:
    graded = tc.analyze_headers(GOOD_HEADERS, [
        "session_id=abc123; Path=/; HttpOnly; SameSite=Lax",
        "prefs=dark; Secure; HttpOnly; SameSite=Strict",
        "track=1; SameSite=None",
    ])
    assert [(c["name"], c["secure"], c["http_only"], c["same_site"]) for c in graded["cookies"]] == [
        ("session_id", False, True, "Lax"),
        ("prefs", True, True, "Strict"),
        ("track", False, False, "None"),
    ]
    found = {f["id"]: f for f in tc._header_findings({"https": True, **graded})}
    assert found["cookie-missing-secure"]["severity"] == "Low"
    assert found["cookie-missing-secure"]["evidence"] == {"cookies": ["session_id", "track"]}
    assert found["cookie-missing-httponly"]["evidence"] == {"cookies": ["track"]}


def test_cookie_values_never_appear_in_the_output(net, public, web, capsys) -> None:
    secrets = ["S3CRET-SESSION-VALUE", "TOPSECRET456", "NAMELESSSECRET789", "eyJhbGciOiJIUzI1NiJ9"]
    cookies = [
        f"session_id={secrets[0]}; Path=/; HttpOnly",
        f"prefs={secrets[1]}; Secure",
        secrets[2],  # no "=": a nameless cookie whose whole text is the value
        f"jwt={secrets[3]}; Expires=Wed, 21 Oct 2026 07:28:00 GMT; SameSite=None",
    ]
    net.verified = FakeTLS(cert=peercert("example.com", "www.example.com"))
    web(site(cookies=cookies))
    assert tc.main(["https://example.com/"]) == 0
    printed = capsys.readouterr().out
    report = json.loads(printed)
    assert [c["name"] for c in report["headers"]["cookies"]] == [
        "session_id", "prefs", "(unnamed)", "jwt"]
    for secret in secrets:
        assert secret not in printed
    assert "cookie-missing-secure" in ids(report)


def test_folded_set_cookie_header_is_split_and_values_stay_out(net, public, web) -> None:
    folded = ("a=FOLDEDSECRET1; Expires=Wed, 21 Oct 2026 07:28:00 GMT; Secure, "
              "b=FOLDEDSECRET2; Path=/")
    routes = site()
    home = "https://example.com/"
    # No urllib3 raw headers: only the comma-folded mapping value is available.
    routes[home] = FakeResponse(home, 200, {**GOOD_HEADERS, "Set-Cookie": folded}, raw=False)
    net.verified = FakeTLS(cert=peercert("example.com", "www.example.com"))
    web(routes)
    report = tc.run(home, now=NOW)
    assert [(c["name"], c["secure"]) for c in report["headers"]["cookies"]] == [
        ("a", True), ("b", False)]
    assert "FOLDEDSECRET" not in json.dumps(report)


# ---------------------------------------------------------------------------
# Redirects
# ---------------------------------------------------------------------------

def good_tls(net) -> None:
    net.verified = FakeTLS(cert=peercert("example.com", "www.example.com"))


def test_tidy_site_has_no_findings_and_fetches_each_url_once(net, public, web) -> None:
    good_tls(net)
    routes = site()
    routes["https://example.com"] = routes["https://example.com/"]  # as typed, no slash
    calls = web(routes)
    report = tc.run("https://example.com", now=NOW)
    assert report["findings"] == []
    assert report["summary"] == {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0, "total": 0}
    assert sorted(calls) == ["http://example.com/", "https://example.com",
                             "https://www.example.com/"]
    http = report["redirects"]["http_to_https"]
    assert (http["redirects_to_https"], http["one_hop"], http["permanent"], http["hops"]) == (
        True, True, True, 1)
    assert http["first_hop_same_host"] is True
    www = report["redirects"]["www"]
    assert www["same_final_url"] is True and www["sibling_resolves"] is True
    assert report["headers"]["hsts"]["meets_preload_requirements"] is True


def test_http_that_stays_on_http_is_high(net, public, web) -> None:
    good_tls(net)
    routes = site()
    routes["http://example.com/"] = FakeResponse("http://example.com/", 200, {})
    web(routes)
    report = tc.run("https://example.com/", now=NOW)
    assert by_id(report)["http-no-https-redirect"]["severity"] == "High"
    assert report["redirects"]["http_to_https"]["one_hop"] is False
    hsts = report["headers"]["hsts"]
    assert hsts["meets_preload_requirements"] is False
    assert "HTTP does not redirect to HTTPS on the same host first." in hsts["preload_gaps"]


def test_http_reaching_https_after_two_hops_is_a_chain(net, public, web) -> None:
    good_tls(net)
    routes = site()
    home = "https://example.com/"
    routes["http://example.com/"] = FakeResponse(home, 200, GOOD_HEADERS, history=[
        redirect("http://example.com/", "http://www.example.com/"),
        redirect("http://www.example.com/", home),
    ])
    web(routes)
    report = tc.run(home, now=NOW)
    http = report["redirects"]["http_to_https"]
    assert (http["redirects_to_https"], http["one_hop"], http["hops"]) == (True, False, 2)
    assert by_id(report)["http-https-redirect-chain"]["severity"] == "Low"


def test_temporary_http_to_https_redirect_is_low(net, public, web) -> None:
    good_tls(net)
    routes = site()
    home = "https://example.com/"
    routes["http://example.com/"] = FakeResponse(home, 200, GOOD_HEADERS, history=[
        redirect("http://example.com/", home, status=302)])
    web(routes)
    report = tc.run(home, now=NOW)
    assert by_id(report)["http-https-redirect-temporary"]["severity"] == "Low"


def test_closed_port_80_is_not_a_finding(net, public, web) -> None:
    good_tls(net)
    routes = site()
    routes["http://example.com/"] = ConnectionRefusedError("refused")
    web(routes)
    report = tc.run("https://example.com/", now=NOW)
    assert "ConnectionRefusedError" in report["redirects"]["http_to_https"]["error"]
    assert not [i for i in ids(report) if i.startswith("http-")]


def test_www_and_bare_host_on_different_final_urls_is_medium(net, public, web) -> None:
    good_tls(net)
    routes = site()
    routes["https://www.example.com/"] = FakeResponse("https://www.example.com/", 200, GOOD_HEADERS)
    web(routes)
    report = tc.run("https://example.com/", now=NOW)
    finding = by_id(report)["www-not-consolidated"]
    assert finding["severity"] == "Medium"
    assert finding["evidence"]["sibling_final_url"] == "https://www.example.com/"
    assert report["redirects"]["www"]["same_final_url"] is False


def test_sibling_that_does_not_resolve_is_info_and_no_certificate_finding(
        net, public, web) -> None:
    public.add("www.blog.example.com")
    net.verified = FakeTLS(cert=peercert("blog.example.com"))
    calls = web(site("blog.example.com"))
    report = tc.run("https://blog.example.com/", now=NOW)
    assert report["tls"]["covers_sibling"] is False
    assert report["redirects"]["www"]["sibling_resolves"] is False
    assert "https://www.blog.example.com/" not in calls
    assert ids(report) == ["www-sibling-unreachable"]
    assert report["findings"][0]["severity"] == "Info"


def test_sibling_that_resolves_but_is_not_on_the_certificate_is_medium(net, public, web) -> None:
    net.verified = FakeTLS(cert=peercert("example.com"))
    routes = site()
    routes["https://www.example.com/"] = ssl.SSLError(1, "certificate verify failed")
    web(routes)
    report = tc.run("https://example.com/", now=NOW)
    assert by_id(report)["tls-sibling-not-covered"]["severity"] == "Medium"
    assert report["redirects"]["www"]["sibling_resolves"] is True


def test_sibling_with_its_own_valid_certificate_is_not_a_finding(net, public, web) -> None:
    # One certificate per host is a normal setup. This certificate does not name
    # www, but www answered over HTTPS, so the certificate it serves verified.
    net.verified = FakeTLS(cert=peercert("example.com"))
    web(site())
    report = tc.run("https://example.com/", now=NOW)
    assert report["tls"]["covers_sibling"] is False
    www = report["redirects"]["www"]
    assert www["sibling_resolves"] is True
    assert www["sibling_final_url"] == "https://example.com/"
    assert www["sibling_tls_error"] is False
    assert report["findings"] == []


def test_sibling_finding_needs_evidence_of_a_tls_failure_not_just_dns() -> None:
    # The shape the independent review probed: covered host, uncovered sibling
    # that resolves and whose HTTPS fetch succeeded.
    tls = {"host": "example.com", "verified": True, "verify_code": None, "verify_error": None,
           "expired": False, "not_yet_valid": False, "covers_host": True,
           "sibling_host": "www.example.com", "covers_sibling": False,
           "days_until_expiry": 60, "protocol": "TLSv1.3", "san": ["example.com"]}
    www = {"host": "example.com", "sibling_host": "www.example.com",
           "host_final_url": "https://example.com/",
           "sibling_final_url": "https://example.com/", "sibling_resolves": True,
           "same_final_url": True, "error": None}
    assert tc._tls_findings(tls, {"www": www}) == []
    # No verdict on the sibling's TLS (not checked) is not evidence either.
    assert tc._tls_findings(tls, {"www": {**www, "sibling_tls_error": None}}) == []
    assert tc._tls_findings(tls, {}) == []
    assert ids(tc._tls_findings(tls, {"www": {**www, "sibling_tls_error": True}})) == [
        "tls-sibling-not-covered"]


@pytest.mark.parametrize("failure", [
    ConnectionRefusedError("refused"),
    TimeoutError("timed out"),
    requests.exceptions.ConnectTimeout("connect timed out"),
    requests.exceptions.ConnectionError("Name or service not known"),
])
def test_sibling_that_fails_for_a_non_tls_reason_is_info_with_the_reason(
        failure, net, public, web) -> None:
    net.verified = FakeTLS(cert=peercert("example.com"))
    routes = site()
    routes["https://www.example.com/"] = failure
    web(routes)
    report = tc.run("https://example.com/", now=NOW)
    assert report["tls"]["covers_sibling"] is False
    assert report["redirects"]["www"]["sibling_tls_error"] is False
    assert ids(report) == ["www-sibling-unreachable"]
    finding = report["findings"][0]
    assert finding["severity"] == "Info"
    assert finding["evidence"]["error"].startswith(type(failure).__name__)
    assert "certificate" not in finding["message"].lower()


def test_requests_ssl_error_on_the_sibling_is_the_certificate_finding(net, public, web) -> None:
    net.verified = FakeTLS(cert=peercert("example.com"))
    routes = site()
    routes["https://www.example.com/"] = requests.exceptions.SSLError(
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch")
    web(routes)
    report = tc.run("https://example.com/", now=NOW)
    assert report["redirects"]["www"]["sibling_tls_error"] is True
    finding = by_id(report)["tls-sibling-not-covered"]
    assert finding["severity"] == "Medium"
    assert finding["evidence"]["sibling_host"] == "www.example.com"
    assert finding["evidence"]["error"].startswith("SSLError")
    assert "resolves in DNS" not in finding["message"]
    assert finding["message"].endswith(".") and finding["message"].count(". ") == 0


def test_tls_failure_on_another_host_in_the_sibling_redirects_is_not_blamed_on_the_sibling(
        net, public, web) -> None:
    # www redirects to a third host whose certificate is broken. That says
    # nothing about the certificate www itself serves.
    net.verified = FakeTLS(cert=peercert("example.com"))
    failing_hop = requests.Request("GET", "https://cdn.elsewhere.example/").prepare()
    routes = site()
    routes["https://www.example.com/"] = requests.exceptions.SSLError(
        "certificate verify failed", request=failing_hop)
    web(routes)
    report = tc.run("https://example.com/", now=NOW)
    assert report["redirects"]["www"]["sibling_tls_error"] is False
    assert ids(report) == ["www-sibling-unreachable"]
    assert report["findings"][0]["severity"] == "Info"


def test_error_text_that_mentions_ssl_is_not_taken_for_a_tls_failure(net, public, web) -> None:
    # The verdict comes from the exception type. Text is page and network data.
    net.verified = FakeTLS(cert=peercert("example.com"))
    routes = site()
    routes["https://www.example.com/"] = OSError("SSLError: certificate verify failed")
    web(routes)
    report = tc.run("https://example.com/", now=NOW)
    assert report["redirects"]["www"]["sibling_tls_error"] is False
    assert "tls-sibling-not-covered" not in ids(report)


def test_sibling_tls_verdict_is_null_when_the_sibling_was_not_fetched(net, public, web) -> None:
    public.add("www.blog.example.com")
    net.verified = FakeTLS(cert=peercert("blog.example.com"))
    web(site("blog.example.com"))
    report = tc.run("https://blog.example.com/", now=NOW)
    assert report["redirects"]["www"]["sibling_tls_error"] is None
    assert "sibling_tls_error" in tc.__doc__


def test_www_input_uses_the_bare_domain_as_sibling() -> None:
    assert tc.sibling_host("www.example.com") == "example.com"
    assert tc.sibling_host("example.com") == "www.example.com"
    assert tc.sibling_host("www.com") == "www.www.com"
    assert tc.sibling_host("93.184.216.34") is None
    assert tc.sibling_host("2606:2800:220:1::1946") is None
    assert tc.sibling_host("intranet") is None


def test_page_fetch_failure_is_reported_not_raised(net, public, web) -> None:
    good_tls(net)
    web({})
    report = tc.run("https://example.com/", now=NOW)
    assert "error" in report["headers"] and "error" not in report
    assert "headers-not-checked" in ids(report)


def test_https_redirect_hop_without_hsts_is_a_preload_gap(net, public, web) -> None:
    good_tls(net)
    routes = site()
    start, home = "https://example.com/old", "https://example.com/"
    routes[start] = FakeResponse(home, 200, GOOD_HEADERS, history=[redirect(start, home)])
    web(routes)
    report = tc.run(start, now=NOW)
    hsts = report["headers"]["hsts"]
    assert hsts["meets_preload_requirements"] is False
    assert any("HTTPS redirect" in gap for gap in hsts["preload_gaps"])


# ---------------------------------------------------------------------------
# DER reader
# ---------------------------------------------------------------------------

def test_der_reader_matches_the_fixture_certificate() -> None:
    cert = tc.parse_der_certificate(FIXTURE_DER)
    assert cert["subject"] == {"common_name": "fixture.example.test", "organization": "Fixture Org"}
    assert cert["issuer"] == cert["subject"]
    assert tc._iso(cert["not_before"]) == "2020-01-01T00:00:00Z"
    assert tc._iso(cert["not_after"]) == "2021-01-01T00:00:00Z"
    assert cert["san"] == ["fixture.example.test", "www.fixture.example.test",
                           "*.wild.example.test", "192.0.2.7", "2001:db8::7"]


def test_der_reader_only_ever_raises_valueerror_on_hostile_bytes() -> None:
    for junk in (b"", b"\x30", b"\x30\x84\xff\xff\xff\xff", b"\x00" * 64, b"\x30\x80\x00\x00",
                 b"\xff" * 300_000):
        with pytest.raises(ValueError):
            tc.parse_der_certificate(junk)
    for cut in range(0, len(FIXTURE_DER) - 1, 7):
        with pytest.raises(ValueError):
            tc.parse_der_certificate(FIXTURE_DER[:cut])
    # Corrupt every byte in turn: a result or a ValueError, never another exception.
    for index in range(len(FIXTURE_DER)):
        for value in (0x00, 0x30, 0x80, 0x84, 0xFF):
            mutated = FIXTURE_DER[:index] + bytes([value]) + FIXTURE_DER[index + 1:]
            try:
                tc.parse_der_certificate(mutated)
            except ValueError:
                pass


def test_san_matching_follows_browser_wildcard_rules() -> None:
    assert tc._name_matches("*.example.com", "www.example.com")
    assert tc._name_matches("EXAMPLE.com.", "example.com")
    assert not tc._name_matches("*.example.com", "example.com")
    assert not tc._name_matches("*.example.com", "a.b.example.com")
    assert tc._name_matches("2001:DB8:0:0:0:0:0:7", "2001:db8::7")
    assert not tc._name_matches("192.0.2.7", "192.0.2.8")


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

def test_findings_shape_order_and_summary(net, public, web) -> None:
    net.verified = verify_error(10, "certificate has expired")
    net.unverified = FakeTLS(der=FIXTURE_DER)
    routes = site("fixture.example.test", headers={}, cookies=["sid=1"])
    routes["http://fixture.example.test/"] = FakeResponse("http://fixture.example.test/", 200, {})
    web(routes)
    report = tc.run("https://fixture.example.test/", now=NOW)

    assert list(report) == ["url", "host", "tls", "headers", "redirects", "findings", "summary"]
    assert report["findings"], "expected findings"
    order = [tc.SEVERITIES.index(f["severity"]) for f in report["findings"]]
    assert order == sorted(order)
    for finding in report["findings"]:
        assert list(finding) == ["id", "severity", "message", "evidence"]
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", finding["id"])
        assert finding["severity"] in tc.SEVERITIES
        assert finding["message"].endswith(".") and finding["message"].count(". ") == 0
        assert isinstance(finding["evidence"], dict)
    assert len(set(ids(report))) == len(report["findings"])
    assert report["summary"]["total"] == len(report["findings"])
    assert sum(v for k, v in report["summary"].items() if k != "total") == len(report["findings"])
    assert report["summary"]["Critical"] == 1
    found = by_id(report)
    assert found["tls-cert-expired"]["severity"] == "Critical"
    assert found["http-no-https-redirect"]["severity"] == "High"
    assert found["hsts-missing"]["severity"] == "Medium"
    json.dumps(report)  # serializable as is


def test_scheme_is_optional_on_the_command_line(net, public, web, capsys) -> None:
    good_tls(net)
    web(site())
    assert tc.main(["example.com", "--timeout", "500", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["url"] == "https://example.com"
    assert net.connects == [((PUBLIC_IP, 443), 60.0)]  # timeout is capped


def test_docstring_does_not_overclaim_ranking_impact() -> None:
    doc = " ".join(tc.__doc__.split())
    assert "not a confirmed Google ranking signal" in doc
    assert "lightweight ranking signal" in doc
