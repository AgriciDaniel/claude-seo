#!/usr/bin/env python3
"""
TLS certificate, security header and HTTPS redirect check for one site.

Reads the certificate a site presents, grades the security and transport
headers on its response, and follows the http to https and www / non-www
redirects. Output is one JSON object on stdout.

What this means for SEO
=======================
Security headers are a security and trust matter. They are not a confirmed
Google ranking signal, and this script does not claim otherwise. HTTPS itself
is a lightweight ranking signal, per Google's page experience documentation.
The findings that matter most for search are the ones that stop a browser or
a crawler from reaching the page at all: an expired or mismatched certificate,
http that never reaches https, and www / non-www hosts that both answer.

Usage::

    python transport_check.py https://example.com
    python transport_check.py https://example.com/pricing --timeout 15

Result JSON::

    {
      "url": "<requested URL>",
      "host": "<normalized host>",
      "tls": {
        "host", "port", "connected_ip",
        "verified": <bool>,            # system trust store and hostname
        "verify_error": <str|null>,    # OpenSSL text when verified is false
        "verify_code": <int|null>,
        "certificate_read": <bool>,
        "subject": {"common_name", "organization"},
        "issuer":  {"common_name", "organization"},
        "not_before", "not_after",     # ISO 8601, UTC
        "days_until_expiry": <int>, "expired": <bool>, "not_yet_valid": <bool>,
        "san": ["<name>", ...], "san_count": <int>,
        "covers_host": <bool>, "sibling_host": <str|null>,
        "covers_sibling": <bool|null>,
        "protocol": "TLSv1.3", "cipher": "<name>", "cipher_bits": <int>,
        "error": "<only when the handshake did not complete>",
        "certificate_error": "<only when an unverified certificate was unreadable>"
      },                               # or {"skipped": "<reason>"}
      "headers": {
        "url", "status", "https",
        "hsts": {"present", "value", "max_age", "include_subdomains",
                 "preload", "meets_preload_requirements", "preload_gaps",
                 "preload_scope_note", "issues"},
        "csp": {"present", "report_only", "policies", "issues"},
        "x_content_type_options": {"present", "value", "ok"},
        "framing": {"x_frame_options", "frame_ancestors", "ok"},
        "referrer_policy": {"present", "value", "ok"},
        "permissions_policy": {"present", "feature_policy_present"},
        "cookies": [{"name", "secure", "http_only", "same_site", "issues"}]
      },                               # or {"error": "<reason>"}
      "redirects": {
        "http_to_https": {"checked_url", "redirects_to_https", "one_hop",
                          "first_hop_status", "first_hop_target",
                          "first_hop_same_host", "permanent", "hops",
                          "final_url", "error"},
        "www": {"host", "sibling_host", "host_final_url",
                "sibling_final_url", "sibling_resolves",
                "sibling_tls_error",   # true: the counterpart's own HTTPS
                                       # request failed on its certificate
                                       # or TLS; null: it was not fetched
                "same_final_url", "error"}
      },
      "findings": [{"id", "severity", "message", "evidence"}],
      "summary": {"Critical", "High", "Medium", "Low", "Info", "total"}
    }

A refused or malformed target prints ``{"url": ..., "error": ...}`` instead.
Cookies are reported by NAME only. A cookie value never enters the output.

``covers_sibling: false`` alone is not a finding: the www and the bare host
often serve one certificate each. ``tls-sibling-not-covered`` is reported
only when the counterpart's own HTTPS request also failed with a certificate
or TLS error (``sibling_tls_error``). A counterpart that does not resolve,
times out or refuses the connection is ``www-sibling-unreachable`` (Info)
with the reason, never a certificate finding.

Safety
======
The target is validated with ``url_safety.validate_url_strict`` before any
connection. The TLS socket connects to the IP address that call returned,
never to the hostname, so a DNS answer cannot change between the check and
the connection. The hostname is used only for SNI and for certificate
matching. Nothing is written to or read from the socket beyond the handshake,
and it is closed in a ``finally`` block. When the certificate does not verify,
one more handshake without verification reads the certificate so the report
can say why (expired, wrong host); no data is sent on it either. Header and
redirect checks go through ``url_safety.safe_requests_get`` only. When a proxy
environment variable is set, the raw socket would bypass the proxy, so the
TLS section is skipped.

Exit status::

    0  report printed (whatever the findings)
    2  the URL was refused or could not be parsed
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import ssl
import sys
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from requests.exceptions import SSLError as RequestsSSLError

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from url_safety import (  # noqa: E402
    URLSafetyError,
    normalize_hostname,
    safe_requests_get,
    validate_url_strict,
)

EXPIRY_WARN_DAYS = 14
ONE_YEAR = 31536000  # hstspreload.org minimum max-age, in seconds
OLD_PROTOCOLS = ("SSLv3", "TLSv1", "TLSv1.1")
PROXY_ENV_VARS = ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")
SEVERITIES = ("Critical", "High", "Medium", "Low", "Info")
MAX_SAN_REPORTED = 100
MAX_COOKIES = 40

# OpenSSL X509_V_ERR_* codes carried by ssl.SSLCertVerificationError.
_ERR_NOT_YET_VALID = 9
_ERR_EXPIRED = 10
_ERR_HOST_MISMATCH = (62, 64)  # hostname, IP address

PRELOAD_SCOPE_NOTE = (
    "Covers the header directives, the certificate and the same-host HTTP "
    "redirect when those sections ran. Not checked: that every subdomain "
    "serves HTTPS, and that this host is the registrable domain the preload "
    "list requires."
)


def _clip(value, limit: int = 200) -> Optional[str]:
    return None if value is None else str(value)[:limit]


def _iso(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    stamp = datetime.fromtimestamp(seconds, timezone.utc)
    return stamp.isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Certificate parsing
# ---------------------------------------------------------------------------
#
# ``SSLSocket.getpeercert()`` returns a parsed dict only for a certificate
# that verified. For one that did not, the standard library hands back DER
# bytes and offers no public decoder, so the few fields this report needs
# (names, validity, subjectAltName) are read with the small bounds-checked
# walker below. The input is whatever the remote server sent: every length is
# checked against the buffer and any surprise raises ValueError.

_OID_COMMON_NAME = b"\x55\x04\x03"
_OID_ORGANIZATION = b"\x55\x04\x0a"
_OID_SUBJECT_ALT_NAME = b"\x55\x1d\x11"
_MAX_DER_BYTES = 256 * 1024


def _tlv(data: bytes, pos: int) -> tuple[int, int, int]:
    """Return ``(tag, value_start, value_end)`` for the DER element at ``pos``."""
    if pos + 2 > len(data):
        raise ValueError("DER element is truncated")
    tag, first = data[pos], data[pos + 1]
    if tag & 0x1F == 0x1F:
        raise ValueError("multi-byte DER tags are not supported")
    start = pos + 2
    if first & 0x80:
        count = first & 0x7F
        if count == 0 or count > 4 or start + count > len(data):
            raise ValueError("bad DER length")
        length = int.from_bytes(data[start:start + count], "big")
        start += count
    else:
        length = first
    end = start + length
    if end > len(data):
        raise ValueError("DER element runs past the buffer")
    return tag, start, end


def _children(data: bytes, start: int, end: int) -> list[tuple[int, int, int]]:
    out, pos = [], start
    while pos < end:
        tag, value_start, value_end = _tlv(data, pos)
        if value_end > end:
            raise ValueError("DER child runs past its parent")
        out.append((tag, value_start, value_end))
        pos = value_end
    return out


def _der_text(tag: int, raw: bytes) -> str:
    if tag == 0x1E:  # BMPString
        return raw.decode("utf-16-be", errors="replace")
    if tag == 0x1C:  # UniversalString
        return raw.decode("utf-32-be", errors="replace")
    if tag == 0x14:  # TeletexString
        return raw.decode("latin-1")
    return raw.decode("utf-8", errors="replace")


def _der_time(tag: int, raw: bytes) -> float:
    text = raw.decode("ascii")
    digits = text[:-1]
    if not text.endswith("Z") or not digits.isdigit():
        raise ValueError("unsupported certificate time format")
    if tag == 0x17 and len(digits) == 12:  # UTCTime, two-digit year (RFC 5280)
        year = int(digits[:2])
        year += 2000 if year < 50 else 1900
        rest = digits[2:]
    elif tag == 0x18 and len(digits) == 14:  # GeneralizedTime
        year, rest = int(digits[:4]), digits[4:]
    else:
        raise ValueError("unsupported certificate time format")
    month, day, hour, minute, second = (int(rest[i:i + 2]) for i in range(0, 10, 2))
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc).timestamp()


def _der_name(data: bytes, start: int, end: int) -> dict:
    name = {"common_name": None, "organization": None}
    for _set_tag, set_start, set_end in _children(data, start, end):
        for _seq_tag, seq_start, seq_end in _children(data, set_start, set_end):
            parts = _children(data, seq_start, seq_end)
            if len(parts) < 2:
                continue
            oid = data[parts[0][1]:parts[0][2]]
            key = {_OID_COMMON_NAME: "common_name", _OID_ORGANIZATION: "organization"}.get(oid)
            if key and name[key] is None:
                name[key] = _clip(_der_text(parts[1][0], data[parts[1][1]:parts[1][2]]))
    return name


def _der_san(data: bytes, start: int, end: int) -> list[str]:
    """dNSName and iPAddress entries from the extensions block, if any."""
    names: list[str] = []
    wrapper = _children(data, start, end)
    if not wrapper:
        return names
    for _tag, ext_start, ext_end in _children(data, wrapper[0][1], wrapper[0][2]):
        parts = _children(data, ext_start, ext_end)
        if len(parts) < 2 or data[parts[0][1]:parts[0][2]] != _OID_SUBJECT_ALT_NAME:
            continue
        general_names = _children(data, parts[-1][1], parts[-1][2])
        if not general_names:
            continue
        for tag, name_start, name_end in _children(data, general_names[0][1], general_names[0][2]):
            raw = data[name_start:name_end]
            if tag == 0x82:
                names.append(raw.decode("ascii", errors="replace"))
            elif tag == 0x87 and len(raw) in (4, 16):
                names.append(str(ipaddress.ip_address(raw)))
    return names


def parse_der_certificate(der: bytes) -> dict:
    """Read names, validity and subjectAltName from a DER X.509 certificate.

    Returns ``{"subject", "issuer", "not_before", "not_after", "san"}`` with
    times as epoch seconds. Raises ``ValueError`` for anything malformed.
    """
    if not der or len(der) > _MAX_DER_BYTES:
        raise ValueError("no certificate, or certificate too large")
    try:
        _tag, start, end = _tlv(der, 0)
        tbs = _children(der, start, end)[0]
        fields = _children(der, tbs[1], tbs[2])
        if fields and fields[0][0] == 0xA0:  # explicit version
            fields = fields[1:]
        _serial, _algorithm, issuer, validity, subject = fields[:5]
        times = _children(der, validity[1], validity[2])
        san: list[str] = []
        for tag, field_start, field_end in fields[6:]:
            if tag == 0xA3:  # extensions
                san = _der_san(der, field_start, field_end)
        return {
            "subject": _der_name(der, subject[1], subject[2]),
            "issuer": _der_name(der, issuer[1], issuer[2]),
            "not_before": _der_time(times[0][0], der[times[0][1]:times[0][2]]),
            "not_after": _der_time(times[1][0], der[times[1][1]:times[1][2]]),
            "san": san,
        }
    except (IndexError, UnicodeError, OverflowError) as exc:
        raise ValueError(f"malformed certificate: {exc}") from exc


def _from_peercert(cert: dict) -> dict:
    """Normalize a ``getpeercert()`` dict to the ``parse_der_certificate`` shape."""
    def name(dn) -> dict:
        out = {"common_name": None, "organization": None}
        for rdn in dn or ():
            for key, value in rdn:
                slot = {"commonName": "common_name", "organizationName": "organization"}.get(key)
                if slot and out[slot] is None:
                    out[slot] = _clip(value)
        return out

    def seconds(key: str) -> Optional[float]:
        try:
            return float(ssl.cert_time_to_seconds(cert[key]))
        except (KeyError, ValueError):
            return None

    return {
        "subject": name(cert.get("subject")),
        "issuer": name(cert.get("issuer")),
        "not_before": seconds("notBefore"),
        "not_after": seconds("notAfter"),
        "san": [str(value) for kind, value in cert.get("subjectAltName", ())
                if kind in ("DNS", "IP Address")],
    }


def _name_matches(pattern: str, host: str) -> bool:
    """SAN match as browsers do it: a wildcard covers exactly one label."""
    pattern, host = pattern.lower().rstrip("."), host.lower().rstrip(".")
    try:
        return ipaddress.ip_address(pattern) == ipaddress.ip_address(host)
    except ValueError:
        pass
    if pattern.startswith("*."):
        return host.endswith(pattern[1:]) and host.count(".") == pattern.count(".")
    return pattern == host


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def sibling_host(host: str) -> Optional[str]:
    """The www / non-www counterpart of ``host``; None for IPs and bare labels."""
    if _is_ip(host) or "." not in host:
        return None
    return host[4:] if host.startswith("www.") and host.count(".") >= 2 else f"www.{host}"


# ---------------------------------------------------------------------------
# TLS handshake
# ---------------------------------------------------------------------------

def proxy_configured() -> bool:
    return any(os.environ.get(name, "").strip() for name in PROXY_ENV_VARS)


def _pinned_address(value) -> str:
    """Return the validated address as a bare IP literal, or raise ValueError.

    ``validate_url_strict`` returns an IPv4 or IPv6 literal. Insisting on one
    here means a hostname can never reach ``connect()``, whatever a future
    change to the validator returns.
    """
    return str(ipaddress.ip_address(str(value).strip().strip("[]")))


def _handshake(ip: str, port: int, server_hostname: str, timeout: float, *, verify: bool) -> dict:
    """One TLS handshake to ``ip``. Sends and reads nothing after it.

    ``timeout`` bounds the TCP connect and the handshake together. With
    ``verify=False`` the certificate is not checked: that mode exists only to
    read the certificate of a site whose verified handshake already failed.

    Both modes refuse anything older than TLS 1.2. That is already Python's
    default; stating it keeps the probe from following a system OpenSSL
    configuration that lowers the floor. A server that speaks only TLS 1.0 or
    1.1 therefore fails the handshake and is reported as
    ``tls-handshake-failed``.
    """
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    if verify:
        if getattr(ssl, "HAS_NEVER_CHECK_COMMON_NAME", False):
            # Browsers match subjectAltName only; do the same.
            context.hostname_checks_common_name = False
    else:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    deadline = time.monotonic() + timeout
    raw = socket.create_connection((ip, port), timeout=timeout)
    tls = None
    try:
        raw.settimeout(max(0.1, deadline - time.monotonic()))
        tls = context.wrap_socket(raw, server_hostname=server_hostname)
        cipher = tls.cipher() or (None, None, None)
        return {
            "cert": tls.getpeercert() if verify else None,
            "der": None if verify else tls.getpeercert(binary_form=True),
            "protocol": tls.version(),
            "cipher": cipher[0],
            "cipher_bits": cipher[2],
        }
    finally:
        if tls is not None:
            tls.close()
        raw.close()  # a no-op once wrap_socket has taken the descriptor


def check_tls(url: str, timeout: float = 10.0, *, now: Optional[float] = None) -> dict:
    """Read and judge the certificate ``url``'s host presents.

    Raises ``URLSafetyError`` when the target is not a permitted public
    address; no socket is opened in that case. Every other failure is
    reported inside the returned dict.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return {"skipped": "not an https URL, so there is no certificate to read; "
                           "pass the https:// address to check TLS"}
    if proxy_configured():
        return {"skipped": "proxy configured"}

    _validated_url, pinned = validate_url_strict(url)
    host = normalize_hostname(parsed.hostname or "")
    port = parsed.port or 443
    sibling = sibling_host(host)
    result: dict = {
        "host": host, "port": port, "connected_ip": None,
        "verified": False, "verify_error": None, "verify_code": None,
        "certificate_read": False,
        "subject": None, "issuer": None, "not_before": None, "not_after": None,
        "days_until_expiry": None, "expired": None, "not_yet_valid": None,
        "san": [], "san_count": 0,
        "covers_host": None, "sibling_host": sibling, "covers_sibling": None,
        "protocol": None, "cipher": None, "cipher_bits": None,
    }
    try:
        ip = _pinned_address(pinned)
    except ValueError:
        result["error"] = "the validated address is not an IP literal, so no connection was made"
        return result
    result["connected_ip"] = ip

    cert: Optional[dict] = None
    shake: Optional[dict] = None
    try:
        shake = _handshake(ip, port, host, timeout, verify=True)
        result["verified"] = True
        cert = _from_peercert(shake["cert"] or {})
    except ssl.SSLCertVerificationError as exc:
        result["verify_error"] = _clip(getattr(exc, "verify_message", "") or str(exc), 300)
        result["verify_code"] = getattr(exc, "verify_code", None)
        try:
            shake = _handshake(ip, port, host, timeout, verify=False)
            cert = parse_der_certificate(shake["der"] or b"")
        except (ssl.SSLError, OSError, ValueError) as inner:
            result["certificate_error"] = _clip(f"{type(inner).__name__}: {inner}", 300)
    except (ssl.SSLError, OSError, ValueError) as exc:
        result["error"] = _clip(f"{type(exc).__name__}: {exc}", 300)
        return result

    if shake:
        result.update(protocol=shake["protocol"], cipher=shake["cipher"],
                      cipher_bits=shake["cipher_bits"])
    if cert is None:
        return result

    current = time.time() if now is None else now
    names = cert["san"]
    result.update(
        certificate_read=True,
        subject=cert["subject"], issuer=cert["issuer"],
        not_before=_iso(cert["not_before"]), not_after=_iso(cert["not_after"]),
        san=[_clip(name) for name in names[:MAX_SAN_REPORTED]], san_count=len(names),
        # A verified handshake already matched the host; OpenSSL is the judge.
        covers_host=True if result["verified"] else any(_name_matches(n, host) for n in names),
    )
    if sibling:
        result["covers_sibling"] = any(_name_matches(n, sibling) for n in names)
    if cert["not_after"] is not None:
        result["days_until_expiry"] = int((cert["not_after"] - current) // 86400)
        result["expired"] = cert["not_after"] < current
    if cert["not_before"] is not None:
        result["not_yet_valid"] = cert["not_before"] > current
    return result


# ---------------------------------------------------------------------------
# Header grading (pure parsing, no requests)
# ---------------------------------------------------------------------------

def split_set_cookie(value: str) -> list[str]:
    """Split a comma-folded Set-Cookie header without breaking Expires dates."""
    if not value:
        return []
    parts = re.split(r",\s*(?=[^;,=\s]+=[^;,]*)", value)
    return [part.strip() for part in parts if part.strip()]


def set_cookie_values(response) -> list[str]:
    """Raw Set-Cookie lines from a requests Response, one per cookie."""
    raw_headers = getattr(getattr(response, "raw", None), "headers", None)
    getlist = getattr(raw_headers, "getlist", None)
    if callable(getlist):
        try:
            values = [str(v) for v in getlist("Set-Cookie")]
        except Exception:
            values = []
        if values:
            return values
    for key, value in (getattr(response, "headers", None) or {}).items():
        if str(key).lower() == "set-cookie":
            return split_set_cookie(str(value))
    return []


def _parse_cookie(raw: str, https: bool) -> dict:
    """Flags for one cookie. Only the NAME is kept; the value is dropped here."""
    pieces = [piece.strip() for piece in raw.split(";")]
    # "abc" with no "=" is a nameless cookie whose VALUE is "abc": report no name.
    name = pieces[0].split("=", 1)[0].strip() if "=" in pieces[0] else ""
    attrs = {}
    for piece in pieces[1:]:
        key, _sep, value = piece.partition("=")
        attrs[key.strip().lower()] = value.strip()
    same_site = attrs.get("samesite")
    cookie = {
        "name": name[:80] or "(unnamed)",
        "secure": "secure" in attrs,
        "http_only": "httponly" in attrs,
        "same_site": same_site.capitalize()[:10] if same_site else None,
        "issues": [],
    }
    if https and not cookie["secure"]:
        cookie["issues"].append("Missing Secure on an HTTPS site.")
    if not cookie["http_only"]:
        cookie["issues"].append("Missing HttpOnly; fine only if scripts must read this cookie.")
    if same_site is None:
        cookie["issues"].append("No SameSite attribute; browsers default to Lax.")
    elif same_site.lower() == "none" and not cookie["secure"]:
        cookie["issues"].append("SameSite=None without Secure is rejected by browsers.")
    return cookie


def _grade_hsts(raw: Optional[str], https: bool) -> dict:
    hsts = {"present": raw is not None, "value": _clip(raw), "max_age": None,
            "include_subdomains": False, "preload": False,
            "meets_preload_requirements": False, "preload_gaps": [],
            "preload_scope_note": PRELOAD_SCOPE_NOTE, "issues": []}
    if raw is None:
        hsts["preload_gaps"].append("No Strict-Transport-Security header.")
        if https:
            hsts["issues"].append("Strict-Transport-Security was not sent.")
        return hsts
    directives: dict[str, str] = {}
    # Browsers act on the first header only (RFC 6797); requests joins repeats with commas.
    for part in raw.split(",")[0].split(";"):
        key, _sep, value = part.strip().partition("=")
        key = key.strip().lower()
        if key in directives:
            message = "Duplicate HSTS directives invalidate the header, so browsers ignore it."
            hsts["issues"].append(message)
            hsts["preload_gaps"].append(message)
            return hsts
        if key:
            directives[key] = value.strip().strip('"')
    max_age = directives.get("max-age", "")
    hsts["max_age"] = int(max_age) if max_age.isascii() and max_age.isdigit() else None
    hsts["include_subdomains"] = "includesubdomains" in directives
    hsts["preload"] = "preload" in directives
    if hsts["max_age"] is None:
        hsts["issues"].append("max-age is missing, so browsers ignore the header.")
    elif hsts["max_age"] == 0:
        hsts["issues"].append("max-age=0 switches HSTS off.")
    elif hsts["max_age"] < ONE_YEAR:
        hsts["issues"].append("max-age is below one year.")
    if not hsts["include_subdomains"]:
        hsts["issues"].append("includeSubDomains is not set.")
    if (hsts["max_age"] or 0) < ONE_YEAR:
        hsts["preload_gaps"].append("max-age is below 31536000 seconds (one year).")
    if not hsts["include_subdomains"]:
        hsts["preload_gaps"].append("includeSubDomains is missing.")
    if not hsts["preload"]:
        hsts["preload_gaps"].append("The preload directive is missing.")
    hsts["meets_preload_requirements"] = not hsts["preload_gaps"]
    return hsts


def _parse_csp(value: str) -> dict[str, list[str]]:
    directives: dict[str, list[str]] = {}
    for chunk in value.split(";"):
        tokens = chunk.strip().split()
        if tokens:
            directives.setdefault(tokens[0].lower(), [t.lower() for t in tokens[1:]])
    return directives


def _csp_issues(directives: dict[str, list[str]]) -> list[str]:
    issues = []
    script_name = next((n for n in ("script-src", "default-src") if n in directives), None)
    if script_name is None:
        issues.append("No script-src or default-src, so scripts are unrestricted.")
    else:
        sources = directives[script_name]
        strict = any(s.startswith(("'nonce-", "'sha256-", "'sha384-", "'sha512-")) for s in sources)
        if "'unsafe-inline'" in sources and not strict:
            issues.append(f"'unsafe-inline' in {script_name}.")
        if "'unsafe-eval'" in sources:
            issues.append(f"'unsafe-eval' in {script_name}.")
        for loose in ("*", "https:", "http:", "data:"):
            if loose in sources:
                issues.append(f"{loose} in {script_name} allows scripts from almost anywhere.")
    if "object-src" not in directives and directives.get("default-src") != ["'none'"]:
        issues.append("No object-src restriction.")
    if "base-uri" not in directives:
        issues.append("No base-uri restriction.")
    return issues


_REFERRER_POLICIES = frozenset({
    "no-referrer", "no-referrer-when-downgrade", "origin", "origin-when-cross-origin",
    "same-origin", "strict-origin", "strict-origin-when-cross-origin", "unsafe-url",
})


def analyze_headers(headers: Optional[dict], set_cookies: Optional[list[str]] = None,
                    *, https: bool = True) -> dict:
    """Grade the security headers of one response. Makes no requests.

    ``headers`` is a plain mapping; ``set_cookies`` is one raw Set-Cookie line
    per cookie. Cookie values are read here and never returned.
    """
    low = {str(k).lower(): str(v) for k, v in (headers or {}).items()}

    enforced = low.get("content-security-policy")
    report_only = low.get("content-security-policy-report-only")
    policy = enforced if enforced is not None else report_only
    csp = {"present": enforced is not None,
           "report_only": enforced is None and report_only is not None,
           "policies": 0, "issues": []}
    directives: dict[str, list[str]] = {}
    if policy is None:
        csp["issues"].append("Content-Security-Policy was not sent.")
    else:
        policies = [p for p in policy.split(",") if p.strip()]
        csp["policies"] = len(policies)
        directives = _parse_csp(policies[0]) if policies else {}
        csp["issues"].extend(_csp_issues(directives))
        if len(policies) > 1:
            csp["issues"].append("More than one policy was sent; only the first is graded.")
        if csp["report_only"]:
            csp["issues"].insert(0, "Only a report-only policy was sent, so nothing is enforced.")

    nosniff = low.get("x-content-type-options")
    xfo = low.get("x-frame-options")
    xfo_ok = xfo is not None and xfo.strip().upper() in ("DENY", "SAMEORIGIN")
    frame_ancestors = enforced is not None and "frame-ancestors" in directives

    referrer = low.get("referrer-policy")
    known = [t.strip().lower() for t in (referrer or "").split(",")
             if t.strip().lower() in _REFERRER_POLICIES]
    effective = known[-1] if known else None  # browsers use the last value they recognise

    return {
        "hsts": _grade_hsts(low.get("strict-transport-security"), https),
        "csp": csp,
        "x_content_type_options": {
            "present": nosniff is not None, "value": _clip(nosniff, 60),
            "ok": nosniff is not None and nosniff.strip().lower() == "nosniff"},
        "framing": {"x_frame_options": _clip(xfo, 60), "frame_ancestors": frame_ancestors,
                    "ok": xfo_ok or frame_ancestors},
        "referrer_policy": {"present": referrer is not None, "value": _clip(referrer, 120),
                            "ok": effective is not None and effective != "unsafe-url"},
        "permissions_policy": {"present": "permissions-policy" in low,
                               "feature_policy_present": "feature-policy" in low},
        "cookies": [_parse_cookie(line, https)
                    for line in (set_cookies or [])[:MAX_COOKIES] if line.strip()],
    }


# ---------------------------------------------------------------------------
# Fetching (url_safety helpers only) and redirect checks
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: float) -> dict:
    """GET ``url`` through ``safe_requests_get`` and keep headers and hops only.

    The body is never read (``stream=True``). The Set-Cookie header is kept
    apart from ``headers`` so a cookie value cannot ride along into output.
    """
    record: dict = {"url": url, "final_url": None, "status": None, "hops": [],
                    "headers": {}, "set_cookies": [], "error": None,
                    "tls_error_url": None}
    response = None
    try:
        response = safe_requests_get(url, timeout=timeout, allow_redirects=True, stream=True)
        chain = [*response.history, response]
        record["hops"] = [
            {"url": _clip(hop.url, 500), "status": hop.status_code,
             "target": _clip(chain[index + 1].url, 500),
             "hsts": any(str(k).lower() == "strict-transport-security" for k in hop.headers)}
            for index, hop in enumerate(response.history)
        ]
        record["final_url"] = _clip(response.url, 500)
        record["status"] = response.status_code
        record["headers"] = {str(k).lower(): str(v) for k, v in response.headers.items()
                             if str(k).lower() != "set-cookie"}
        record["set_cookies"] = set_cookie_values(response)
    except URLSafetyError as exc:
        record["error"] = _clip(f"url_safety: {exc}", 300)
    except Exception as exc:  # requests / urllib3 errors: report, never raise
        record["error"] = _clip(f"{type(exc).__name__}: {exc}", 300)
        # Judged by exception type, never by the error text. requests names
        # the hop that failed; without it the failure is on ``url`` itself.
        if isinstance(exc, (ssl.SSLError, RequestsSSLError)):
            failed = getattr(getattr(exc, "request", None), "url", None)
            record["tls_error_url"] = _clip(failed or url, 500)
    finally:
        if response is not None:
            response.close()
    return record


def _url_host(host: str) -> str:
    return f"[{host}]" if ":" in host else host


def _tls_failed_on(record: dict, host: str) -> bool:
    """True when ``record``'s fetch failed on TLS at an https URL of ``host``.

    A TLS failure on another host later in the redirect chain says nothing
    about the certificate ``host`` serves, so it does not count.
    """
    failed = record.get("tls_error_url")
    if not failed:
        return False
    try:
        parsed = urlparse(failed)
        return parsed.scheme == "https" and normalize_hostname(parsed.hostname or "") == host
    except ValueError:  # includes URLSafetyError: an unusable URL is no evidence
        return False


def _same_url(left: Optional[str], right: Optional[str]) -> Optional[bool]:
    if not left or not right:
        return None
    a, b = urlparse(left), urlparse(right)
    return ((a.scheme, a.netloc.lower(), a.path or "/", a.query)
            == (b.scheme, b.netloc.lower(), b.path or "/", b.query))


def check_redirects(url: str, timeout: float = 10.0, primary: Optional[dict] = None) -> dict:
    """http to https, and www / non-www consolidation, for ``url``'s host.

    ``primary`` is an earlier ``_fetch`` record of ``url``; it is reused when
    it already covers one of the URLs checked here.
    """
    parsed = urlparse(url)
    host = normalize_hostname(parsed.hostname or "")
    port = parsed.port
    port_part = f":{port}" if port else ""

    seen: dict[str, dict] = {}

    def fetch(target: str) -> dict:
        if primary is not None and _same_url(primary.get("url"), target):
            return primary
        if target not in seen:
            seen[target] = _fetch(target, timeout)
        return seen[target]

    # http to https
    if parsed.scheme == "https" and port not in (None, 443):
        http_check: dict = {"skipped": "https on a non-default port has no http counterpart"}
    else:
        http_url = f"http://{_url_host(host)}{port_part if parsed.scheme == 'http' else ''}/"
        record = fetch(http_url)
        hops = record["hops"]
        first = hops[0] if hops else None
        first_target = urlparse(first["target"]) if first else None
        http_check = {
            "checked_url": http_url,
            "redirects_to_https": bool(record["final_url"]
                                       and record["final_url"].startswith("https://")),
            "one_hop": bool(first_target and first_target.scheme == "https"),
            "first_hop_status": first["status"] if first else None,
            "first_hop_target": first["target"] if first else None,
            "first_hop_same_host": (first_target.hostname or "").lower() == host
            if first_target else None,
            "permanent": first["status"] in (301, 308) if first else None,
            "hops": len(hops),
            "final_url": record["final_url"],
            "error": record["error"],
        }

    # www / non-www
    sibling = sibling_host(host)
    if sibling is None:
        www_check: dict = {"skipped": "no www counterpart for an IP address or a bare label"}
    else:
        host_record = fetch(f"{parsed.scheme}://{_url_host(host)}{port_part}/")
        sibling_url = f"{parsed.scheme}://{sibling}{port_part}/"
        www_check = {"host": host, "sibling_host": sibling,
                     "host_final_url": host_record["final_url"],
                     "sibling_final_url": None, "sibling_resolves": False,
                     "sibling_tls_error": None,
                     "same_final_url": None, "error": host_record["error"]}
        try:
            validate_url_strict(sibling_url)
        except URLSafetyError as exc:
            www_check["error"] = www_check["error"] or _clip(f"url_safety: {exc}", 300)
        else:
            www_check["sibling_resolves"] = True
            sibling_record = _fetch(sibling_url, timeout)
            www_check["sibling_final_url"] = sibling_record["final_url"]
            www_check["sibling_tls_error"] = _tls_failed_on(sibling_record, sibling)
            www_check["error"] = www_check["error"] or sibling_record["error"]
            www_check["same_final_url"] = _same_url(host_record["final_url"],
                                                    sibling_record["final_url"])
    return {"http_to_https": http_check, "www": www_check}


def _apply_preload_context(headers: dict, tls: dict, redirects: dict, hops: list[dict]) -> None:
    """Add the non-header hstspreload.org requirements this run could observe."""
    hsts = headers.get("hsts")
    if not hsts or not hsts["present"]:
        return
    gaps = hsts["preload_gaps"]
    if tls.get("verified") is False and "skipped" not in tls:
        gaps.append("The certificate did not verify.")
    http_check = redirects.get("http_to_https", {})
    if http_check.get("final_url") and not (http_check.get("one_hop")
                                            and http_check.get("first_hop_same_host")):
        gaps.append("HTTP does not redirect to HTTPS on the same host first.")
    if any(hop["url"].startswith("https://") and not hop["hsts"] for hop in hops):
        gaps.append("An HTTPS redirect on the way to the page does not send the HSTS header.")
    hsts["meets_preload_requirements"] = not gaps


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def _finding(fid: str, severity: str, message: str, evidence: Optional[dict] = None) -> dict:
    return {"id": fid, "severity": severity, "message": message, "evidence": evidence or {}}


def _tls_findings(tls: dict, redirects: dict) -> list[dict]:
    if not tls or "skipped" in tls:
        return []
    if tls.get("error"):
        return [_finding("tls-handshake-failed", "High",
                         "The TLS handshake with the site did not complete.",
                         {"error": tls["error"]})]
    out = []
    code = tls.get("verify_code")
    verify = {"verify_error": tls.get("verify_error")}
    expired = bool(tls.get("expired")) or code == _ERR_EXPIRED
    not_yet = bool(tls.get("not_yet_valid")) or code == _ERR_NOT_YET_VALID
    mismatch = not tls["verified"] and (tls.get("covers_host") is False
                                        or code in _ERR_HOST_MISMATCH)
    if expired:
        message = ("The TLS certificate has expired." if tls.get("expired")
                   else "A certificate in the site's chain has expired.")
        out.append(_finding("tls-cert-expired", "Critical", message,
                            {"not_after": tls.get("not_after"),
                             "days_until_expiry": tls.get("days_until_expiry"), **verify}))
    if not_yet:
        out.append(_finding("tls-cert-not-yet-valid", "Critical",
                            "The TLS certificate is not valid yet.",
                            {"not_before": tls.get("not_before"), **verify}))
    if mismatch:
        out.append(_finding("tls-cert-hostname-mismatch", "Critical",
                            "The TLS certificate does not cover the requested host.",
                            {"host": tls["host"], "san": tls.get("san", [])[:10], **verify}))
    if not tls["verified"] and not (expired or not_yet or mismatch):
        out.append(_finding("tls-cert-not-trusted", "High",
                            "The certificate chain did not verify against the system trust store.",
                            verify))
    days = tls.get("days_until_expiry")
    if not expired and days is not None and 0 <= days <= EXPIRY_WARN_DAYS:
        out.append(_finding("tls-cert-expiring-soon", "High",
                            f"The TLS certificate expires within {EXPIRY_WARN_DAYS} days.",
                            {"days_until_expiry": days, "not_after": tls.get("not_after")}))
    if tls.get("protocol") in OLD_PROTOCOLS:
        out.append(_finding("tls-old-protocol", "Medium",
                            "The server negotiated a TLS version older than 1.2.",
                            {"protocol": tls["protocol"]}))
    # A certificate that does not name the counterpart is normal when the
    # counterpart serves its own. It is a finding only with evidence that the
    # counterpart is broken over TLS: its own HTTPS request failed that way.
    www = redirects.get("www", {})
    if tls.get("covers_sibling") is False and www.get("sibling_tls_error") is True:
        out.append(_finding("tls-sibling-not-covered", "Medium",
                            "The www or non-www counterpart fails its HTTPS request with a "
                            "certificate or TLS error, and this host's certificate does not "
                            "cover it.",
                            {"sibling_host": tls.get("sibling_host"),
                             "error": www.get("error")}))
    return out


def _header_findings(headers: dict) -> list[dict]:
    if headers.get("error"):
        return [_finding("headers-not-checked", "Info",
                         "The page could not be fetched, so its response headers were not graded.",
                         {"error": headers["error"]})]
    out = []
    https = headers.get("https", True)
    hsts = headers["hsts"]
    if https and not hsts["present"]:
        out.append(_finding("hsts-missing", "Medium",
                            "The HTTPS response does not send a Strict-Transport-Security header."))
    elif https and not hsts["max_age"]:
        out.append(_finding("hsts-disabled", "Medium",
                            "The Strict-Transport-Security header has no effect because max-age "
                            "is missing, invalid or zero, or the header is invalid.",
                            {"value": hsts["value"], "issues": hsts["issues"]}))
    elif https and hsts["issues"]:
        out.append(_finding("hsts-weak", "Low", "The Strict-Transport-Security header is weak.",
                            {"value": hsts["value"], "issues": hsts["issues"]}))
    csp = headers["csp"]
    if not csp["present"] and not csp["report_only"]:
        out.append(_finding("csp-missing", "Low", "No Content-Security-Policy header is sent."))
    elif csp["report_only"]:
        out.append(_finding("csp-report-only", "Low",
                            "The Content-Security-Policy is report-only, so nothing is enforced.",
                            {"issues": csp["issues"]}))
    elif csp["issues"]:
        out.append(_finding("csp-weak", "Low", "The Content-Security-Policy has obvious gaps.",
                            {"issues": csp["issues"]}))
    nosniff = headers["x_content_type_options"]
    if not nosniff["ok"]:
        out.append(_finding("nosniff-missing", "Low",
                            "X-Content-Type-Options is not set to nosniff.",
                            {"value": nosniff["value"]}))
    framing = headers["framing"]
    if not framing["ok"]:
        out.append(_finding("clickjacking-protection-missing", "Low",
                            "Neither X-Frame-Options nor a CSP frame-ancestors directive limits "
                            "framing of the page.",
                            {"x_frame_options": framing["x_frame_options"]}))
    referrer = headers["referrer_policy"]
    if not referrer["present"]:
        out.append(_finding("referrer-policy-missing", "Info",
                            "No Referrer-Policy header is sent, so the browser default applies."))
    elif not referrer["ok"]:
        out.append(_finding("referrer-policy-unsafe", "Low",
                            "The Referrer-Policy is unsafe-url or not a recognised value.",
                            {"value": referrer["value"]}))
    if not headers["permissions_policy"]["present"]:
        out.append(_finding("permissions-policy-missing", "Info",
                            "No Permissions-Policy header is sent."))

    def names(text: str) -> list[str]:
        return [c["name"] for c in headers["cookies"] if any(text in i for i in c["issues"])]

    insecure = sorted(set(names("Missing Secure") + names("SameSite=None")))
    if insecure:
        out.append(_finding("cookie-missing-secure", "Low",
                            "One or more cookies are set without the Secure flag.",
                            {"cookies": insecure}))
    if names("HttpOnly"):
        out.append(_finding("cookie-missing-httponly", "Info",
                            "One or more cookies are readable by scripts because HttpOnly is "
                            "not set.", {"cookies": names("HttpOnly")}))
    if names("No SameSite"):
        out.append(_finding("cookie-missing-samesite", "Info",
                            "One or more cookies set no SameSite attribute.",
                            {"cookies": names("No SameSite")}))
    return out


def _redirect_findings(redirects: dict) -> list[dict]:
    out = []
    http_check = redirects.get("http_to_https", {})
    if http_check.get("final_url"):
        evidence = {key: http_check[key] for key in
                    ("checked_url", "first_hop_status", "first_hop_target", "hops", "final_url")}
        if not http_check["redirects_to_https"]:
            out.append(_finding("http-no-https-redirect", "High",
                                "The http:// address does not redirect to https://.", evidence))
        elif not http_check["one_hop"]:
            out.append(_finding("http-https-redirect-chain", "Low",
                                "The http:// address reaches https:// only after more than "
                                "one redirect.", evidence))
        elif not http_check["permanent"]:
            out.append(_finding("http-https-redirect-temporary", "Low",
                                "The http to https redirect is temporary, not a 301 or 308.",
                                evidence))
    www = redirects.get("www", {})
    if www.get("same_final_url") is False:
        out.append(_finding("www-not-consolidated", "Medium",
                            "The www and non-www hosts end on different URLs.",
                            {key: www[key] for key in ("host", "sibling_host", "host_final_url",
                                                       "sibling_final_url")}))
    elif "sibling_host" in www and www.get("host_final_url") and not www.get("sibling_final_url"):
        out.append(_finding("www-sibling-unreachable", "Info",
                            "The www or non-www counterpart of the host did not answer.",
                            {"sibling_host": www["sibling_host"], "error": www.get("error")}))
    return out


def build_findings(tls: dict, headers: dict, redirects: dict) -> list[dict]:
    findings = (_tls_findings(tls, redirects) + _redirect_findings(redirects)
                + _header_findings(headers))
    return sorted(findings, key=lambda f: SEVERITIES.index(f["severity"]))


def summarize(findings: list[dict]) -> dict:
    """Count per severity, keyed by the severity as findings spell it (as page_checks.py does)."""
    counts = {level: sum(1 for f in findings if f["severity"] == level) for level in SEVERITIES}
    counts["total"] = len(findings)
    return counts


# ---------------------------------------------------------------------------
# Orchestration and CLI
# ---------------------------------------------------------------------------

def run(url: str, timeout: float = 10.0, *, now: Optional[float] = None) -> dict:
    """Run every check for ``url`` and return the JSON-serializable report."""
    url = (url or "").strip()
    if "://" not in url:
        url = f"https://{url}"
    # Validate first: a refused target stops here, before any socket or request.
    try:
        validate_url_strict(url)
        parsed = urlparse(url)
        host = normalize_hostname(parsed.hostname or "")
        tls = check_tls(url, timeout, now=now)
    except URLSafetyError as exc:
        return {"url": url, "error": f"url_safety: {exc}"}
    except ValueError as exc:
        return {"url": url, "error": f"invalid URL: {exc}"}

    primary = _fetch(url, timeout)
    redirects = check_redirects(url, timeout, primary)
    if primary["error"]:
        headers: dict = {"url": url, "error": primary["error"]}
    else:
        https = (primary["final_url"] or "").startswith("https://")
        headers = {"url": primary["final_url"], "status": primary["status"], "https": https,
                   **analyze_headers(primary["headers"], primary["set_cookies"], https=https)}
        _apply_preload_context(headers, tls, redirects, primary["hops"])

    findings = build_findings(tls, headers, redirects)
    return {"url": url, "host": host, "tls": tls, "headers": headers, "redirects": redirects,
            "findings": findings, "summary": summarize(findings)}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read a site's TLS certificate, grade its security and transport "
                    "headers, and check its http to https and www redirects. JSON on stdout."
    )
    parser.add_argument("url", help="Site or page URL, for example https://example.com")
    parser.add_argument("--timeout", type=float, default=10.0, metavar="N",
                        help="Seconds allowed per connection or request (1 to 60, default 10)")
    parser.add_argument("--json", action="store_true",
                        help="Accepted for consistency with the other scripts; "
                             "output is always JSON")
    args = parser.parse_args(argv)

    report = run(args.url, timeout=min(max(args.timeout, 1.0), 60.0))
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 2 if "error" in report else 0


if __name__ == "__main__":
    sys.exit(main())
