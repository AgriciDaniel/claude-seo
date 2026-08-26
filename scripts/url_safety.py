#!/usr/bin/env python3
"""
Canonical URL safety module for claude-seo.

Centralizes SSRF protection, DNS rebinding mitigation, and DNS-pinned HTTP
fetching. Every script in this repository that accepts a user-supplied URL
MUST validate it through this module before issuing any network request.

Public API
==========

validate_url(url) -> bool
    Back-compat boolean check. Rejects non-http(s) schemes, missing
    hostnames, hard-blocked hostnames (localhost, cloud metadata
    endpoints), and IP literals that fall inside private/loopback/reserved
    ranges. Does NOT resolve DNS. Preserves the v1.9.9 contract used by
    google_auth.py.

validate_url_strict(url) -> tuple[str, str]
    Resolves the hostname via socket.getaddrinfo, validates every returned
    A record against the safety predicate, and returns
    ``(normalized_url, pinned_ipv4)``. Raises ``URLSafetyError`` if any
    resolved IP is non-public. Use this whenever the caller is about to
    open a network connection so DNS rebinding cannot swap a public IP
    for a private one between checks.

safe_requests_get(url, *, timeout=30, **kwargs) -> requests.Response
    ``requests.get(...)`` wrapped in a DNS-pinning context manager so the
    OS-level resolver only ever sees the pre-validated IP for the duration
    of the call. The original hostname is preserved in the HTTP Host
    header and TLS SNI; only the connect() target is forced to the pinned
    address.

safe_requests_head(url, *, timeout=30, **kwargs) -> requests.Response
    Same protection as ``safe_requests_get`` for callers that only need a
    HEAD preflight.

safe_requests_session(url) -> context manager yielding requests.Session
    Same protection as ``safe_requests_get`` for callers that need a
    session (cookies, redirect chains, multiple requests to one host).

is_safe_ip(ip_str) -> bool
    True iff the address parses as IPv4/IPv6 and is none of:
    private, loopback, reserved, link-local, multicast, unspecified.

URLSafetyError
    ValueError subclass raised by the strict validator and pinning helpers.

Threading
=========
The DNS pinning helper is a critical section guarded by a non-blocking
``threading.Lock``. Two concurrent pinned fetches on the same process will
raise rather than corrupt the global ``socket.getaddrinfo`` reference.
claude-seo scripts are intentionally single-threaded; parallelism is
delegated to the agent-process layer.

Limitations
===========
Playwright/Chromium-based fetches (``render_page.py``,
``capture_screenshot.py``) perform their own DNS resolution inside
Chromium and therefore cannot be DNS-pinned at the Python layer. Those
scripts must:

  1. Call ``validate_url_strict()`` as a pre-flight check, AND
  2. Attach a Playwright ``route()`` handler that re-validates each
     resolved request IP and aborts subresource fetches to private
     ranges.

The residual DNS-rebinding risk for browser-based fetches is documented
in SECURITY.md.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import threading
from contextlib import contextmanager
from typing import Iterator, Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError as exc:  # pragma: no cover - hard dependency
    raise RuntimeError(
        "scripts/url_safety.py requires the 'requests' package. "
        "Install with: pip install -r requirements.txt"
    ) from exc


__all__ = [
    "URLSafetyError",
    "is_safe_ip",
    "normalize_hostname",
    "validate_url",
    "validate_url_strict",
    "safe_requests_get",
    "safe_requests_head",
    "safe_requests_session",
    "make_safe_playwright_route_handler",
]


# Regex matching any glibc / inet_aton-friendly IPv4 obfuscation. This is the
# allowlist of "looks like a numeric address" forms we want to canonicalize
# before SSRF policy is applied. Matches:
#   - dotted-quad (127.0.0.1)
#   - dotted with leading zeros (127.0.0.001)
#   - dotted octal (0177.0.0.1)
#   - dotted hex (0x7f.0.0.1)
#   - three-part (a.b.c -> a.b.(c & 0xffff))
#   - two-part (a.b -> a.(b & 0xffffff))
#   - single integer (decimal/hex/octal: 2130706433, 0x7f000001, 017700000001)
# Any string matching this regex is normalized through socket.inet_aton, which
# produces the canonical dotted form (or raises OSError if invalid). Strings
# that don't match the regex are treated as DNS hostnames.
_IPV4_OBFUSCATED_RE = re.compile(
    r"^(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+)){0,3}$",
    re.IGNORECASE,
)


# Hard-blocked hostnames. Anything here is refused even before DNS resolution.
# Cloud metadata endpoints are the most common SSRF target; we list every
# documented address across AWS, Azure, GCP, Oracle, and Alibaba so a single
# typo (e.g., metadata.google.internal vs metadata.googleapis.internal)
# cannot slip through.
_BLOCKED_HOSTNAMES: frozenset[str] = frozenset(
    {
        "localhost",
        "ip6-localhost",
        "ip6-loopback",
        "metadata.google.internal",
        "metadata.goog",
        "metadata",
        "metadata.azure.com",
        "metadata.ec2.internal",
        "metadata.oraclecloud.com",
        # Numeric metadata endpoints (also caught by IP literal check, listed
        # explicitly for defence-in-depth and clearer error messages).
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "169.254.169.254",  # AWS, Azure, GCP, Oracle, Alibaba metadata IPv4
        "fd00:ec2::254",    # AWS IMDS IPv6
    }
)


class URLSafetyError(ValueError):
    """Raised when a URL fails SSRF safety checks."""


def _raw_authority(url: str) -> str:
    """Return the undecoded authority substring between scheme and path."""
    match = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://([^/?#]*)", url)
    return match.group(1) if match else ""


def _reject_authority_confusion(url: str, parsed) -> None:
    """Reject forms where URL parsers or HTTP stacks can disagree.

    Backslashes, userinfo, and fragment/userinfo ambiguity have all been
    used to make one parser see a public host while another connects to a
    private host. claude-seo never needs credentials in audit URLs, so
    userinfo is refused outright.
    """
    authority = _raw_authority(url)
    authority_lower = authority.lower()
    url_lower = url.lower()

    if "\\" in authority or "%5c" in authority_lower:
        raise URLSafetyError("URL authority contains a backslash")
    if "%" in authority:
        raise URLSafetyError("URL authority contains percent-encoding")
    if parsed.username is not None or parsed.password is not None or "@" in authority:
        raise URLSafetyError("URL userinfo is not allowed")
    if "#@" in url or "%23@" in url_lower:
        raise URLSafetyError("URL fragment/userinfo confusion refused")


def is_safe_ip(ip_str: str) -> bool:
    """Return True iff ``ip_str`` is a public unicast address.

    Handles IPv4-mapped IPv6 (``::ffff:127.0.0.1`` correctly returns False
    because Python 3.9+'s ``ipaddress`` propagates ``is_loopback`` /
    ``is_private`` through IPv4-mapped form). IPv6 unique-local
    (``fc00::/7``) and link-local (``fe80::/10``) are also rejected.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_reserved
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
    )


def normalize_hostname(hostname: str) -> str:
    """
    Canonicalize a hostname so that obfuscated forms cannot bypass the
    SSRF policy. Performs three normalizations:

      1. Lowercase (DNS is case-insensitive).
      2. Strip a single trailing dot (RFC 1034 FQDN form). Without this,
         ``metadata.google.internal.`` would bypass the hostname
         blocklist (which holds exact strings).
      3. If the result matches an IPv4 obfuscation pattern
         (decimal integer, hex, octal, leading zeros, short forms),
         canonicalize via ``socket.inet_aton`` to dotted-quad. This
         closes the classic SSRF bypass where ``http://2130706433/``
         (decimal 127.0.0.1), ``http://0x7f000001/``, or
         ``http://0177.0.0.1/`` would parse as a hostname rather than
         an IP literal and skip the IP-range check.

    Raises:
        URLSafetyError if the hostname is empty after normalization, or
        if an obfuscated form cannot be canonicalized (malformed input).
    """
    if not hostname:
        raise URLSafetyError("Empty hostname")

    h = hostname.lower().strip()
    # Strip a single trailing dot — FQDN form is semantically identical to
    # the bare form for the purposes of resolution and policy.
    if h.endswith(".") and not h.endswith(".."):
        h = h[:-1]

    if _IPV4_OBFUSCATED_RE.match(h):
        # inet_aton accepts the same obfuscated forms the glibc resolver
        # accepts, so canonicalization here matches what getaddrinfo
        # would produce at connect time.
        try:
            packed = socket.inet_aton(h)
        except OSError as exc:
            raise URLSafetyError(
                f"Malformed IPv4 obfuscation refused: {hostname!r} ({exc})"
            ) from exc
        h = socket.inet_ntoa(packed)
    return h


def validate_url(url: str) -> bool:
    """
    Back-compat boolean validator. Does not resolve DNS.

    Returns False when:
        - Scheme is not http or https
        - Hostname is missing
        - Hostname normalizes to a hard-block list entry
          (including FQDN-form metadata endpoints like
          ``metadata.google.internal.`` and obfuscated IPv4 like
          ``2130706433`` -> ``127.0.0.1``)
        - Normalized hostname is an IP literal that fails ``is_safe_ip``
        - Normalization itself fails (malformed obfuscated input)
    Returns True for any other well-formed http(s) URL with a
    public-looking hostname. Use ``validate_url_strict`` whenever the
    caller will open a socket — only the strict form catches a DNS
    record that resolves to a non-public IP at connect time.
    """
    try:
        parsed = urlparse(url)
        _reject_authority_confusion(url, parsed)
        if parsed.scheme not in ("http", "https"):
            return False
        if not parsed.hostname:
            return False
        hostname = normalize_hostname(parsed.hostname)
    except URLSafetyError:
        return False
    if hostname in _BLOCKED_HOSTNAMES:
        return False
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return True  # Hostname is a name, not a literal — OK at parse time.
    return is_safe_ip(hostname)


def validate_url_strict(url: str) -> tuple[str, str]:
    """
    Resolve and validate the URL's hostname.

    Returns ``(url, pinned_ipv4)`` on success. Raises ``URLSafetyError`` if:
        - Scheme is invalid or hostname is missing.
        - Hostname is hard-blocked.
        - DNS resolution fails.
        - Any A record resolves to a non-public IP (DNS rebinding refused).

    Multi-A-record handling: every returned record must be public. A
    hostname with one public and one private A record is refused so an
    attacker cannot race the resolver between validate and connect.
    """
    parsed = urlparse(url)
    _reject_authority_confusion(url, parsed)
    if parsed.scheme not in ("http", "https"):
        raise URLSafetyError(f"Invalid URL scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise URLSafetyError("URL has no hostname")

    hostname = normalize_hostname(parsed.hostname)
    if hostname in _BLOCKED_HOSTNAMES:
        raise URLSafetyError(f"Blocked hostname: {hostname}")

    # If the hostname is an IP literal, validate it directly without DNS.
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None

    if literal is not None:
        if not is_safe_ip(hostname):
            raise URLSafetyError(f"Blocked IP literal: {hostname}")
        return url, str(literal)

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addrinfo = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    except (socket.gaierror, UnicodeError) as exc:
        raise URLSafetyError(f"DNS resolution failed for {hostname}: {exc}") from exc

    resolved_ips = sorted({info[4][0] for info in addrinfo})
    if not resolved_ips:
        raise URLSafetyError(f"No A records for {hostname}")

    for ip_str in resolved_ips:
        if not is_safe_ip(ip_str):
            raise URLSafetyError(
                f"DNS rebinding refused: {hostname} resolves to "
                f"non-public IP {ip_str}"
            )

    pinned = resolved_ips[0]
    return url, pinned


# A single non-blocking lock guards the global getaddrinfo monkey-patch.
# This is a deliberate choice: claude-seo scripts run one URL fetch at a
# time, and we'd rather raise loudly than silently corrupt resolver state
# if a caller ever introduces threading.
_dns_patch_lock = threading.Lock()


@contextmanager
def _pin_dns(hostname: str, pinned_ip: str, port: int) -> Iterator[None]:
    """
    Temporarily override ``socket.getaddrinfo`` so the named host resolves
    only to ``pinned_ip``, AND every other hostname looked up during the
    pinned scope has its resolved IPs validated against
    :func:`is_safe_ip`. Non-public resolutions raise ``socket.gaierror``,
    which ``requests`` surfaces as ``ConnectionError`` — the caller's
    existing error path.

    The fall-through validation is the v2 fix for redirect-target DNS
    rebinding: ``requests.Session.get(allow_redirects=True)`` may follow
    30x redirects to a *different* hostname; without this guard, the
    redirect target was resolved by the unpatched resolver and could
    land on a private IP.

    Restores the original function on exit, even on exception.
    """
    if not _dns_patch_lock.acquire(blocking=False):
        raise URLSafetyError(
            "DNS-pinned fetch already in progress on another thread; "
            "claude-seo url_safety is not thread-safe by design."
        )

    original_getaddrinfo = socket.getaddrinfo
    target = hostname.lower()

    def patched(host, requested_port, *args, **kwargs):
        # Branch 1: the originally-pinned host returns the validated IP
        # without any further resolver call.
        if host and host.lower() == target:
            family = kwargs.get("family", args[0] if args else 0)
            if family in (0, socket.AF_UNSPEC, socket.AF_INET):
                return [(
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    (pinned_ip, requested_port or port),
                )]
            raise socket.gaierror(
                socket.EAI_FAIL,
                f"url_safety: address family {family} refused for pinned "
                f"IPv4 host {host}",
            )

        # Branch 2: every OTHER hostname (redirect target, embedded
        # subresource, library bookkeeping) gets resolved by the real
        # resolver, then each returned record is checked. A single
        # non-public record fails the entire lookup.
        result = original_getaddrinfo(host, requested_port, *args, **kwargs)
        for info in result:
            sockaddr = info[4]
            if not sockaddr:
                continue
            ip_str = sockaddr[0]
            if not is_safe_ip(ip_str):
                raise socket.gaierror(
                    socket.EAI_FAIL,
                    f"url_safety: refused to resolve {host!r} to "
                    f"non-public IP {ip_str}",
                )
        return result

    socket.getaddrinfo = patched  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo  # type: ignore[assignment]
        _dns_patch_lock.release()


# Default request headers, mirroring the browser-like defaults fetch_page.py
# has used since v1.2.1 (issue #9). Without them ``requests`` announces itself
# as ``User-Agent: python-requests/x.y.z`` with no Accept-Language, which many
# managed WAFs and CDNs answer with 403/406, and which SSR frameworks answer
# with the empty client-side shell. Callers do not see an exception in that
# case, they analyse the error page or the shell as if it were the real
# document. Any header here can be overridden by passing ``headers=``.
DEFAULT_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.7871.115 Safari/537.36 ClaudeSEO/2.0"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _with_default_headers(kwargs: dict) -> dict:
    """Fill in DEFAULT_REQUEST_HEADERS for header keys the caller did not set."""
    headers = dict(DEFAULT_REQUEST_HEADERS)
    headers.update(kwargs.get("headers") or {})
    kwargs["headers"] = headers
    return kwargs


def safe_requests_get(
    url: str,
    *,
    timeout: int = 30,
    **kwargs,
) -> requests.Response:
    """
    ``requests.get`` with DNS-rebinding protection.

    The request's hostname is pinned to a pre-validated IP for the
    duration of the call. Standard ``requests`` semantics otherwise,
    except that browser-like default headers are supplied for any header
    the caller did not set (see ``DEFAULT_REQUEST_HEADERS``).
    """
    norm_url, pinned_ip = validate_url_strict(url)
    parsed = urlparse(norm_url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    assert parsed.hostname is not None  # validate_url_strict guarantees this
    kwargs = _with_default_headers(kwargs)
    with _pin_dns(parsed.hostname, pinned_ip, port):
        return requests.get(norm_url, timeout=timeout, **kwargs)


def safe_requests_head(
    url: str,
    *,
    timeout: int = 30,
    **kwargs,
) -> requests.Response:
    """
    ``requests.head`` with DNS-rebinding protection.

    The request's hostname is pinned to a pre-validated IP for the
    duration of the call. Standard ``requests`` semantics otherwise,
    except that browser-like default headers are supplied for any header
    the caller did not set (see ``DEFAULT_REQUEST_HEADERS``).
    """
    norm_url, pinned_ip = validate_url_strict(url)
    parsed = urlparse(norm_url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    assert parsed.hostname is not None
    kwargs = _with_default_headers(kwargs)
    with _pin_dns(parsed.hostname, pinned_ip, port):
        return requests.head(norm_url, timeout=timeout, **kwargs)


@contextmanager
def safe_requests_session(url: str) -> Iterator[requests.Session]:
    """
    Yield a ``requests.Session`` whose connections to ``url``'s hostname
    are DNS-pinned. Callers may make multiple requests to that host
    within the ``with`` block without re-resolving.
    """
    norm_url, pinned_ip = validate_url_strict(url)
    parsed = urlparse(norm_url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    assert parsed.hostname is not None
    session = requests.Session()
    with _pin_dns(parsed.hostname, pinned_ip, port):
        try:
            yield session
        finally:
            session.close()


def make_safe_playwright_route_handler(
    blocked_resource_types: Optional[set] = None,
):
    """
    Build a Playwright ``page.route()`` callback that aborts subresource
    requests whose hostname resolves to a non-public IP.

    This is defence in depth for browser-based fetches: Chromium does its
    own DNS resolution inside the renderer process, so a Python-layer
    pin on ``socket.getaddrinfo`` cannot reach it. The route handler
    re-validates every request URL using the same predicate as
    :func:`validate_url_strict`.

    Args:
        blocked_resource_types: optional set of Playwright resource type
            strings (``image``, ``media``, ``font``, ``stylesheet``,
            ``script``, ``xhr``, ``fetch``, ``websocket``, ``manifest``,
            ``other``) to abort regardless of IP. Used for fast
            "skip images and fonts" renders.

    Returns:
        Callable ``(route, request) -> None`` suitable for
        ``page.route("**/*", handler)``.
    """
    blocked = set(blocked_resource_types or ())

    def handler(route, request):  # type: ignore[no-untyped-def]
        try:
            if blocked and request.resource_type in blocked:
                route.abort()
                return

            parsed = urlparse(request.url)
            if parsed.scheme not in ("http", "https"):
                # data:, blob:, chrome-extension:, etc. — no DNS involved.
                route.continue_()
                return
            host = parsed.hostname
            if not host:
                route.abort()
                return

            try:
                normalized = normalize_hostname(host)
            except URLSafetyError:
                route.abort()
                return

            # Hostname-level blocks short-circuit DNS resolution entirely
            # (e.g. attacker.example/redirect -> metadata.google.internal).
            if normalized in _BLOCKED_HOSTNAMES:
                route.abort()
                return

            # Dual-stack resolution: Chromium may use IPv6 even when a
            # host has IPv4 records. AF_UNSPEC returns both families;
            # any single non-public record aborts the request.
            try:
                addrinfo = socket.getaddrinfo(
                    normalized,
                    None,
                    family=socket.AF_UNSPEC,
                    type=socket.SOCK_STREAM,
                )
            except socket.gaierror:
                route.abort()
                return
            ips = {info[4][0] for info in addrinfo}
            if not ips or any(not is_safe_ip(ip) for ip in ips):
                route.abort()
                return
            route.continue_()
        except Exception:  # pragma: no cover - fail-closed
            try:
                route.abort()
            except Exception:
                pass

    return handler


def _cli() -> None:
    """Tiny CLI for manual SSRF-policy checks. Not used by other scripts."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="Validate a URL against claude-seo's SSRF policy."
    )
    parser.add_argument("url", help="URL to validate")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Run DNS resolution and refuse on any non-public A record.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON object instead of a one-line summary.",
    )
    args = parser.parse_args()

    result: dict[str, Optional[str]] = {
        "url": args.url,
        "mode": "strict" if args.strict else "parse",
        "ok": None,
        "pinned_ip": None,
        "error": None,
    }

    try:
        if args.strict:
            _, ip = validate_url_strict(args.url)
            result["ok"] = "true"
            result["pinned_ip"] = ip
        else:
            result["ok"] = "true" if validate_url(args.url) else "false"
    except URLSafetyError as exc:
        result["ok"] = "false"
        result["error"] = str(exc)

    if args.json:
        print(json.dumps(result, indent=2))
        if result["ok"] != "true":
            sys.exit(2)
    else:
        if result["ok"] == "true":
            extra = f" -> {result['pinned_ip']}" if result["pinned_ip"] else ""
            print(f"OK: {args.url}{extra}")
        else:
            print(f"BLOCKED: {args.url} ({result['error'] or 'parse-time reject'})")
            sys.exit(2)


if __name__ == "__main__":
    _cli()
