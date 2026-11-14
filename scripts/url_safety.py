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
    Resolves the hostname via socket.getaddrinfo in both address families,
    validates every returned A and AAAA record against the safety
    predicate, and returns ``(normalized_url, pinned_ip)``. The pinned
    address is IPv4 whenever the host has an A record, and IPv6 only for a
    host that publishes AAAA records alone. Raises ``URLSafetyError`` if any
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
    private, loopback, reserved, link-local, multicast, unspecified,
    an IPv6 transition or special-purpose range (NAT64, 6to4, Teredo,
    site-local, documentation, ORCHID), or an address with a zone
    identifier.

URLSafetyError
    ValueError subclass raised by the strict validator and pinning helpers.

Local targets
=============
``CLAUDE_SEO_LOCAL_TARGETS`` is an opt-in, comma-separated allowlist of
``host`` or ``host:port`` entries (for example
``localhost:3000,127.0.0.1:8080,100.101.102.103``) that lets an operator
audit a dev server, a staging host, or a machine reached over Tailscale.
It is consulted **only** for the first, top-level URL handed to
``validate_url`` / ``validate_url_strict``. Redirect targets, embedded
subresources, and browser-issued requests never consult it, and cloud
metadata endpoints are refused even when listed. The one later read is the
DNS pin's port check: a redirect to another port on the admitted host is
followed only if the allowlist names that port too. Unset, the policy is
exactly what it is without the feature.

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
import os
import re
import socket
import threading
import time
from contextlib import contextmanager
from typing import Iterator, Optional
from urllib.parse import urlparse

try:
    import requests

    # urllib3 is the HTTP layer under requests, so it installs with it.
    from urllib3 import exceptions as _urllib3_exceptions
    from urllib3.response import BaseHTTPResponse as _Urllib3Response
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
    "DEFAULT_USER_AGENT",
    "DEFAULT_REQUEST_HEADERS",
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


# RFC 6598 shared address space (carrier-grade NAT). Not in ``is_private``
# on any supported Python, yet never publicly routable: Alibaba Cloud serves
# its instance metadata at 100.100.100.200, and Tailscale/WireGuard meshes
# hand out 100.64/10 addresses for internal services.
_SHARED_ADDRESS_SPACE = ipaddress.ip_network("100.64.0.0/10")

# IPv6 ranges that are never a public audit target. The ``ipaddress`` flags
# used below already cover most of them, but those tables change between
# Python releases (2001:20::/28 is no longer ``is_private``, 2002::/16 only
# became so recently) and no flag covers site-local, so the policy is spelled
# out here and holds on every interpreter. The ranges that embed an IPv4
# address (NAT64, 6to4, Teredo, IPv4-compatible) are refused whole rather
# than judged by that address. The one place a NAT64 address is passed over
# is the DNS64 case in ``validate_url_strict``, where it is never dialled.
_NAT64_WELL_KNOWN = ipaddress.ip_network("64:ff9b::/96")
_UNSAFE_IPV6_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "::/96",           # IPv4-compatible (deprecated); holds :: and ::1
        "64:ff9b::/96",    # NAT64 well-known prefix (RFC 6052)
        "64:ff9b:1::/48",  # NAT64 local-use prefix (RFC 8215)
        "2001::/32",       # Teredo
        "2001:10::/28",    # ORCHID (deprecated)
        "2001:20::/28",    # ORCHIDv2
        "2001:db8::/32",   # documentation
        "2002::/16",       # 6to4
        "3fff::/20",       # documentation (RFC 9637)
        "fc00::/7",        # unique-local; holds AWS IMDS fd00:ec2::254
        "fe80::/10",       # link-local
        "fec0::/10",       # site-local (deprecated)
        "ff00::/8",        # multicast
    )
)


def is_safe_ip(ip_str: str) -> bool:
    """Return True iff ``ip_str`` is a public unicast address.

    IPv4-mapped IPv6 (``::ffff:127.0.0.1``) is unwrapped and judged as the
    embedded IPv4 address, so every IPv4 rule below applies to it too.
    Every other IPv6 address is checked against ``_UNSAFE_IPV6_NETWORKS``
    as well as the flags below. An address with a zone identifier
    (``fe80::1%eth0``) is refused: a zone only means something on the
    machine that names it.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if ip.version == 6:
        if ip.scope_id is not None:
            return False
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif any(ip in network for network in _UNSAFE_IPV6_NETWORKS):
            return False
    return not (
        ip.is_private
        or (ip.version == 4 and ip in _SHARED_ADDRESS_SPACE)
        or ip.is_loopback
        or ip.is_reserved
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
    )


# ---------------------------------------------------------------------------
# CLAUDE_SEO_LOCAL_TARGETS: an explicit, top-level-only allowlist
# ---------------------------------------------------------------------------
#
# Auditing a site before it is deployed, or a staging host reached over
# Tailscale, means pointing claude-seo at a non-public address. The default
# policy refuses that, correctly: this toolkit follows URLs found on pages it
# crawls, so a blanket "allow private" switch is an SSRF hole with a friendly
# name.
#
# The allowlist is therefore narrow by construction:
#
#   * It is consulted for the FIRST, top-level URL only, in ``validate_url``
#     and ``validate_url_strict``. Redirect targets, embedded subresources,
#     and browser-issued requests never reach it: those go through
#     ``is_safe_ip`` and ``_BLOCKED_HOSTNAMES``, which this module keeps
#     free of any environment dependency.
#   * A host must be named. There is no range, wildcard, or "all private".
#   * ``host:port`` matches that port only. A bare ``host`` matches any port.
#     ``_pin_dns`` holds the admitted host to the same rule for the whole
#     request chain: see ``_local_pin_allows_port``.
#   * Cloud metadata endpoints are refused even when listed. This is the
#     trapdoor every "allow local" flag falls through: 169.254.169.254 is
#     link-local, 100.100.100.200 sits inside the Tailscale range this
#     allowlist exists to permit, and fd00:ec2::254 is unique-local rather
#     than link-local, so no single address predicate catches all three.
_LOCAL_TARGETS_ENV = "CLAUDE_SEO_LOCAL_TARGETS"


# Hostnames and literals no allowlist entry can ever unblock.
_NEVER_ALLOWLISTABLE_HOSTNAMES: frozenset[str] = frozenset(
    {
        "metadata",
        "metadata.goog",
        "metadata.google.internal",
        "metadata.azure.com",
        "metadata.ec2.internal",
        "metadata.oraclecloud.com",
        "169.254.169.254",  # AWS, Azure, GCP, Oracle, Alibaba metadata IPv4
        "100.100.100.200",  # Alibaba metadata, inside RFC 6598
        "fd00:ec2::254",    # AWS IMDS IPv6
        "0.0.0.0",
    }
)


def _is_allowlistable_ip(ip_str: str) -> bool:
    """True when an explicit allowlist entry may reach ``ip_str``.

    Loopback, RFC 1918, and RFC 6598 (Tailscale) are the ranges an operator
    can opt into. Link-local stays refused in both families: that is where
    the IMDS endpoints live, and Python's ``is_private`` reports
    169.254.0.0/16 as private, so a plain "loopback or private" carve-out
    would hand back 169.254.169.254. Multicast, unspecified, and reserved
    are refused for the same reason: nothing an SEO audit legitimately
    targets lives there.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if ip.version == 6 and ip.scope_id is not None:
        return False  # Zone identifier, refused as in is_safe_ip.
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if str(ip) in _NEVER_ALLOWLISTABLE_HOSTNAMES:
        return False
    if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return False
    if ip.is_loopback:
        # Checked before is_reserved: IPv6 ::/8 is reserved and contains ::1.
        return True
    return not ip.is_reserved


def _parse_local_target(entry: str) -> Optional[tuple[str, Optional[int]]]:
    """Parse one ``host`` or ``host:port`` entry into ``(host, port|None)``.

    Returns ``None`` for anything unparseable, so a typo in the environment
    variable widens nothing.
    """
    entry = entry.strip()
    if not entry:
        return None
    # A bare IPv6 literal has more than one colon and no brackets; urlparse
    # would read its last group as a port.
    if entry.count(":") > 1 and "[" not in entry:
        candidate, port = entry, None
    else:
        try:
            parsed = urlparse(f"//{entry}")
            candidate, port = parsed.hostname, parsed.port
        except ValueError:
            return None
        if not candidate:
            return None
    try:
        return normalize_hostname(candidate), port
    except URLSafetyError:
        return None


def _local_targets() -> tuple[tuple[str, Optional[int]], ...]:
    """The parsed contents of ``CLAUDE_SEO_LOCAL_TARGETS``.

    Read on every call rather than cached: the variable is operator
    configuration, and a cached empty tuple from import time would make the
    setting silently inert in a long-lived process.
    """
    raw = os.environ.get(_LOCAL_TARGETS_ENV, "")
    if not raw.strip():
        return ()
    parsed = (_parse_local_target(part) for part in raw.split(","))
    return tuple(entry for entry in parsed if entry is not None)


def _is_allowlisted_local_target(hostname: str, port: Optional[int]) -> bool:
    """True when ``hostname``/``port`` is named in ``CLAUDE_SEO_LOCAL_TARGETS``.

    ``hostname`` must already be normalized. Metadata endpoints are refused
    before the list is even read.
    """
    if hostname in _NEVER_ALLOWLISTABLE_HOSTNAMES:
        return False
    if not _is_allowlistable_ip(hostname) and _looks_like_ip(hostname):
        return False
    for entry_host, entry_port in _local_targets():
        if entry_host != hostname:
            continue
        if entry_port is None or entry_port == port:
            return True
    return False


def _looks_like_ip(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True


def _url_port(parsed) -> Optional[int]:
    """The URL's effective port, or ``None`` if the authority names a bad one."""
    try:
        explicit = parsed.port
    except ValueError:
        return None
    if explicit is not None:
        return explicit
    return 443 if parsed.scheme == "https" else 80


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
    # Strip a single trailing dot: FQDN form is semantically identical to
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
    caller will open a socket; only the strict form catches a DNS
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
    # An unparseable port matches no allowlist entry, but is otherwise left
    # to the caller and to validate_url_strict: this function is a parse-time
    # check and its answer for such URLs is unchanged.
    port = _url_port(parsed)
    allowlisted = port is not None and _is_allowlisted_local_target(hostname, port)
    if hostname in _BLOCKED_HOSTNAMES and not allowlisted:
        return False
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return True  # Hostname is a name, not a literal: OK at parse time.
    if is_safe_ip(hostname):
        return True
    return allowlisted and _is_allowlistable_ip(hostname)


def _is_dns64_synthesized(ip_str: str) -> bool:
    """True for an address in the NAT64 well-known prefix, 64:ff9b::/96.

    The local-use prefix 64:ff9b:1::/48 and anything with a zone identifier
    do not count: neither is what a DNS64 resolver hands out by default.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return ip.version == 6 and ip.scope_id is None and ip in _NAT64_WELL_KNOWN


def validate_url_strict(url: str) -> tuple[str, str]:
    """
    Resolve and validate the URL's hostname.

    Returns ``(url, pinned_ip)`` on success. Raises ``URLSafetyError`` if:
        - Scheme is invalid or hostname is missing.
        - Hostname is hard-blocked.
        - DNS resolution fails.
        - Any A or AAAA record resolves to a non-public IP (DNS rebinding
          refused).

    Multi-record handling: every returned record must be public, in both
    address families. A hostname with one public and one private record
    (two A records, or a public A beside a private AAAA) is refused so an
    attacker cannot race the resolver between validate and connect. The one
    record passed over is a DNS64 AAAA under 64:ff9b::/96 on a host that
    also has an A record: the pin is then IPv4 and that address is unused.

    The pinned address is the host's IPv4 address when it has one, so a
    dual-stack host is reached exactly as before. An IPv6 address is pinned
    only for a host that publishes AAAA records alone, or for an IPv6
    literal, which keeps its brackets in the returned URL.
    """
    parsed = urlparse(url)
    _reject_authority_confusion(url, parsed)
    if parsed.scheme not in ("http", "https"):
        raise URLSafetyError(f"Invalid URL scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise URLSafetyError("URL has no hostname")

    hostname = normalize_hostname(parsed.hostname)
    port = _url_port(parsed)
    if port is None:
        raise URLSafetyError(f"Invalid port in URL authority: {url!r}")

    # The CLAUDE_SEO_LOCAL_TARGETS allowlist is read here, which is what keeps
    # it top-level only. The request chain reaches it again in one place, the
    # pin's port check for this same host (``_local_pin_allows_port``).
    allowlisted = _is_allowlisted_local_target(hostname, port)
    if hostname in _BLOCKED_HOSTNAMES and not allowlisted:
        raise URLSafetyError(f"Blocked hostname: {hostname}")

    # If the hostname is an IP literal, validate it directly without DNS.
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None

    if literal is not None:
        if not is_safe_ip(hostname) and not (
            allowlisted and _is_allowlistable_ip(hostname)
        ):
            raise URLSafetyError(f"Blocked IP literal: {hostname}")
        return url, str(literal)

    try:
        addrinfo = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except (socket.gaierror, UnicodeError) as exc:
        raise URLSafetyError(f"DNS resolution failed for {hostname}: {exc}") from exc

    # IPv4 sorts first, so the pin below is IPv6 only when there is no A
    # record. Every address in the list is still checked, whichever is pinned.
    resolved_ips = sorted(
        {info[4][0] for info in addrinfo}, key=lambda ip: (":" in ip, ip)
    )
    if not resolved_ips:
        raise URLSafetyError(f"No address records for {hostname}")

    # On a DNS64 network the resolver adds, to a name that has an A record
    # and no AAAA, a synthesized AAAA record under 64:ff9b::/96. Judged like any
    # other record it would refuse every IPv4-only site, which resolved fine
    # while this lookup asked for A records alone. With an A record present
    # the pin is IPv4, so that AAAA is never dialled: it is skipped here, not
    # trusted. ``is_safe_ip`` still refuses the prefix everywhere else, and a
    # host with no A record gets no such pass.
    has_a_record = ":" not in resolved_ips[0]

    for ip_str in resolved_ips:
        if is_safe_ip(ip_str):
            continue
        if allowlisted and _is_allowlistable_ip(ip_str):
            continue  # Named in CLAUDE_SEO_LOCAL_TARGETS; see that block.
        if has_a_record and _is_dns64_synthesized(ip_str):
            continue
        raise URLSafetyError(
            f"DNS rebinding refused: {hostname} resolves to "
            f"non-public IP {ip_str}"
        )

    pinned = resolved_ips[0]
    return url, pinned


def _proxy_hosts(url: str, proxies: Optional[dict] = None) -> frozenset:
    """Hostnames ``requests`` will connect to instead of ``url``'s host.

    Mirrors the proxy selection ``requests`` performs for a plain call:
    environment proxies (``HTTPS_PROXY`` and friends, honouring ``NO_PROXY``)
    overridden by an explicit ``proxies`` mapping. Returns the empty set when
    the request goes direct.
    """
    merged = dict(requests.utils.get_environ_proxies(url))
    if proxies:
        merged.update(proxies)
    proxy = requests.utils.select_proxy(url, merged)
    if not proxy:
        return frozenset()
    host = urlparse(requests.utils.prepend_scheme_if_needed(proxy, "http")).hostname
    return frozenset({host.lower()}) if host else frozenset()


def _assert_proxy_host_is_public(host: str) -> str:
    """Resolve one configured proxy host and refuse it unless it is public.

    The exemption in :func:`_pin_dns` removes a proxy host from the
    fall-through validation, so without this check anything the environment
    can set (``HTTPS_PROXY``, ``ALL_PROXY``, a stray ``.bashrc`` export, a
    hostile devcontainer image) would become an unvalidated egress target.
    ``HTTPS_PROXY=http://169.254.169.254:3128`` would turn every audit into a
    cloud-metadata read.

    The proxy therefore goes through exactly the same policy as an audit
    target: the hostname blocklist, then :func:`is_safe_ip` on every resolved
    address across both families. Loopback, RFC 1918, RFC 6598, link-local,
    and the metadata endpoints are refused with a message that names the
    address, rather than being silently exempted.

    Returns the normalized hostname. Raises ``URLSafetyError`` otherwise.
    """
    normalized = normalize_hostname(host)
    hint = (
        "Point the proxy environment variable at a publicly routable "
        "address, or unset it."
    )
    if normalized in _BLOCKED_HOSTNAMES:
        raise URLSafetyError(
            f"Refusing configured HTTP proxy {host!r}: blocked hostname "
            f"{normalized}. {hint}"
        )

    try:
        literal = ipaddress.ip_address(normalized)
    except ValueError:
        literal = None

    if literal is not None:
        if not is_safe_ip(normalized):
            raise URLSafetyError(
                f"Refusing configured HTTP proxy {host!r}: non-public "
                f"address {normalized}. {hint}"
            )
        return normalized

    try:
        addrinfo = socket.getaddrinfo(
            normalized,
            None,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except (socket.gaierror, UnicodeError) as exc:
        raise URLSafetyError(
            f"Refusing configured HTTP proxy {host!r}: DNS resolution "
            f"failed ({exc}). {hint}"
        ) from exc

    resolved_ips = sorted({info[4][0] for info in addrinfo if info[4]})
    if not resolved_ips:
        raise URLSafetyError(
            f"Refusing configured HTTP proxy {host!r}: no address records. "
            f"{hint}"
        )
    for ip_str in resolved_ips:
        if not is_safe_ip(ip_str):
            raise URLSafetyError(
                f"Refusing configured HTTP proxy {host!r}: it resolves to "
                f"non-public IP {ip_str}. {hint}"
            )
    return normalized


def _validated_proxy_hosts(url: str, proxies: Optional[dict] = None) -> frozenset:
    """The proxy hosts to exempt from the pinned scope, each policy-checked.

    Thin wrapper over :func:`_proxy_hosts` and
    :func:`_assert_proxy_host_is_public`. Must be called *before* entering
    :func:`_pin_dns`, so the resolution it performs goes through the real
    resolver rather than the patched one.
    """
    return frozenset(
        _assert_proxy_host_is_public(host) for host in _proxy_hosts(url, proxies)
    )


def _local_pin_allows_port(hostname: str, validated_port: int, requested_port) -> bool:
    """Whether a pin on a non-public address may answer for ``requested_port``.

    The validated port always may. Any other port on the pinned host (a
    redirect hop, a second request on a session) is a new target and goes
    through ``CLAUDE_SEO_LOCAL_TARGETS`` again: a ``host:port`` entry reaches
    that port only, while a bare ``host`` entry keeps matching every port.
    A port that cannot be read as a number is refused.
    """
    if not requested_port:
        return True  # No port named: the caller is handed the validated one.
    try:
        requested = int(requested_port)
    except (TypeError, ValueError):
        return False
    if requested == validated_port:
        return True
    try:
        normalized = normalize_hostname(hostname)
    except URLSafetyError:
        return False
    return _is_allowlisted_local_target(normalized, requested)


# A single non-blocking lock guards the global getaddrinfo monkey-patch.
# This is a deliberate choice: claude-seo scripts run one URL fetch at a
# time, and we'd rather raise loudly than silently corrupt resolver state
# if a caller ever introduces threading.
_dns_patch_lock = threading.Lock()


@contextmanager
def _pin_dns(
    hostname: str,
    pinned_ip: str,
    port: int,
    exempt_hosts: frozenset = frozenset(),
) -> Iterator[None]:
    """
    Temporarily override ``socket.getaddrinfo`` so the named host resolves
    only to ``pinned_ip``, AND every other hostname looked up during the
    pinned scope has its resolved IPs validated against
    :func:`is_safe_ip`. Non-public resolutions raise ``socket.gaierror``,
    which ``requests`` surfaces as ``ConnectionError``: the caller's
    existing error path.

    A public ``pinned_ip`` answers for every port on the named host, so an
    http to https redirect keeps the pin. A non-public ``pinned_ip`` (a
    ``CLAUDE_SEO_LOCAL_TARGETS`` target) answers for ``port`` only, plus any
    other port the allowlist names for that host; see
    :func:`_local_pin_allows_port`.

    The pin answers in the family of ``pinned_ip``: an ``AF_INET`` tuple for
    an IPv4 address, an ``AF_INET6`` tuple with the four-part sockaddr for an
    IPv6 one. A lookup that asks for the other family only is refused, so a
    machine without IPv6 fails closed on an IPv6-only host instead of being
    handed an address it cannot connect to.

    ``exempt_hosts`` are resolved by the real resolver without the
    fall-through check. It carries the configured HTTP proxy, if any: the
    proxy is the process's own egress, and requests must resolve it to open
    the tunnel, which the fall-through check otherwise refused. Callers pass
    :func:`_validated_proxy_hosts`, which has already put that host through
    the hostname blocklist and :func:`is_safe_ip`, so a proxy on loopback or
    at a metadata address never reaches this set. Behind a CONNECT proxy the
    target is resolved by the proxy, and :func:`validate_url_strict`'s
    pre-flight check remains the guard for it.

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
    # A pinned address that is not public was admitted through
    # CLAUDE_SEO_LOCAL_TARGETS, where ``host:port`` allows that port only.
    # Such a pin must not answer for the host's other ports, or a redirect
    # from the allowed dev server reaches every service on that address.
    port_bound = not is_safe_ip(pinned_ip)
    pinned_family = socket.AF_INET6 if ":" in pinned_ip else socket.AF_INET

    def patched(host, requested_port, *args, **kwargs):
        # Branch 1: the originally-pinned host returns the validated IP
        # without any further resolver call.
        if host and host.lower() == target:
            if port_bound and not _local_pin_allows_port(target, port, requested_port):
                raise socket.gaierror(
                    socket.EAI_FAIL,
                    f"url_safety: refused port {requested_port!r} on pinned "
                    f"non-public host {host}; validated port is {port}",
                )
            family = kwargs.get("family", args[0] if args else 0)
            if family in (0, socket.AF_UNSPEC, pinned_family):
                sockaddr = (pinned_ip, requested_port or port)
                if pinned_family == socket.AF_INET6:
                    sockaddr += (0, 0)  # flowinfo, scope_id
                return [(
                    pinned_family,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    sockaddr,
                )]
            pinned_kind = "IPv6" if pinned_family == socket.AF_INET6 else "IPv4"
            raise socket.gaierror(
                socket.EAI_FAIL,
                f"url_safety: address family {family} refused for pinned "
                f"{pinned_kind} host {host}",
            )

        if host and host.lower() in exempt_hosts:
            result = original_getaddrinfo(host, requested_port, *args, **kwargs)
            # An exempt entry that is an IP literal cannot change between the
            # pre-flight validation and this lookup. A DNS name can (rebinding),
            # so its answer is re-checked here; an exempt proxy that now resolves
            # to a non-public address is refused rather than trusted.
            try:
                ipaddress.ip_address(host.strip("[]"))
            except ValueError:
                for info in result:
                    sockaddr = info[4]
                    if sockaddr and not is_safe_ip(sockaddr[0]):
                        raise socket.gaierror(
                            socket.EAI_FAIL,
                            f"url_safety: exempt proxy host {host} resolved to "
                            f"non-public IP {sockaddr[0]} after validation",
                        )
            return result

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


# The browser-like default User-Agent for every raw-HTTP fetch in claude-seo.
# ``fetch_page.py`` has carried these defaults since v1.2.1 (issue #9); they
# live here now because ``url_safety`` is the lower layer, so this module is
# the one place to change them. ``fetch_page.py`` imports them back.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.7871.114 Safari/537.36 ClaudeSEO/2.0"
)

# Without these, ``requests`` announces itself as
# ``User-Agent: python-requests/x.y.z``, which many managed WAFs and CDNs
# answer with 403/406 and SSR frameworks answer with the empty client-side
# shell. Callers do not see an exception in that case, they analyse the error
# page or the shell as if it were the real document.
#
# Accept-Language is deliberately absent. Announcing ``en-US`` makes a
# multi-locale site serve its English variant, which silently corrupts every
# hreflang, international, and localized-content audit. A caller that wants a
# specific locale passes it in ``headers=``; anything else lets the site
# choose, which is what an auditor wants to observe.
#
# Any header here can be overridden by passing ``headers=``.
DEFAULT_REQUEST_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


_CONTENT_TYPE_CHARSET_RE = re.compile(r"charset\s*=\s*['\"]?([^;,'\"\s>]+)", re.IGNORECASE)
# HTML's encoding prescan reads attributes, not the substring "charset=".
_META_TAG_RE = re.compile(r"<meta\b([^>]*)>", re.IGNORECASE)
# An unquoted value runs to whitespace or ">", as in HTML, so
# ``content=text/html;charset=windows-1252`` is one value. The value part is
# optional so a run of name characters with no "=" is consumed in one step
# instead of being rescanned from every offset (quadratic on hostile input).
_META_ATTR_RE = re.compile(
    r"([^\s=/>]+)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+)))?",
    re.IGNORECASE,
)
_BOMS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


def _decode_bytes(raw: bytes, encoding: str) -> str:
    try:
        return raw.decode(encoding, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _extract_charset_from_content_type(content_type: str) -> str | None:
    match = _CONTENT_TYPE_CHARSET_RE.search(content_type or "")
    return match.group(1).strip() if match else None


def _extract_meta_charset(raw: bytes) -> str | None:
    """Return a meta encoding, using HTML's prescan rules.

    A ``charset`` attribute wins. A ``content`` attribute counts only when
    the same tag's ``http-equiv`` is ``content-type``. ``charset=`` inside
    another attribute, such as an og:image URL, is not the document encoding.
    """
    head = raw[:4096].decode("ascii", errors="ignore")
    for match in _META_TAG_RE.finditer(head):
        charset = None
        got_pragma = False
        need_pragma = None
        seen: set[str] = set()
        for attr in _META_ATTR_RE.finditer(match.group(1)):
            name = attr.group(1).lower()
            if name in seen:
                continue
            seen.add(name)
            value = attr.group(2)
            if value is None:
                value = attr.group(3)
            if value is None:
                value = attr.group(4) or ""
            if name == "http-equiv" and value.lower() == "content-type":
                got_pragma = True
            elif name == "content":
                extracted = _extract_charset_from_content_type(value)
                if extracted and charset is None:
                    charset = extracted
                    need_pragma = True
            elif name == "charset":
                charset = value.strip()
                need_pragma = False
        # An unquoted value keeps the "/" of a self-closing tag
        # (``<meta charset=utf-8/>``); no encoding label ends in one.
        charset = (charset or "").strip().rstrip("/")
        if not charset or need_pragma is None:
            continue
        if need_pragma and not got_pragma:
            continue
        return charset
    return None


def decode_response_text(response) -> str:
    """Decode a response body deterministically: BOM, then the Content-Type
    charset, then ``<meta charset>``, then UTF-8.

    Use this instead of ``response.text``. ``requests`` falls back to
    ISO-8859-1 for text/* responses without a charset, which garbles UTF-8
    pages (issue #314). Reading ``response.content`` consumes a streamed body,
    so streamed callers should decode the bytes they already read.
    """
    content_type = response.headers.get("Content-Type", "") if response.headers else ""
    return decode_body(response.content or b"", content_type)


def decode_body(raw: bytes, content_type: str = "") -> str:
    """Decode already-read bytes with the same rules as ``decode_response_text``.

    For streamed responses, whose ``.content`` must not be read again.
    """
    raw = raw or b""
    for marker, encoding in _BOMS:
        if raw.startswith(marker):
            return _decode_bytes(raw[len(marker):], encoding.replace("-sig", ""))

    charset = _extract_charset_from_content_type(content_type)
    if charset:
        return _decode_bytes(raw, charset)

    charset = _extract_meta_charset(raw)
    if charset:
        return _decode_bytes(raw, charset)

    return raw.decode("utf-8", errors="replace")


# Largest page body read, counted after decompression. Real HTML pages are
# far smaller; the cap stops a decompression bomb or an endless stream.
MAX_PAGE_BYTES = 10 * 1024 * 1024

# A redirect's own body is never used, but requests reads it in full before
# it follows Location. This much is read; the rest is dropped unread.
MAX_REDIRECT_BODY_BYTES = 64 * 1024


def read_bounded(response, max_bytes: int) -> tuple[bytes, bool]:
    """Read a ``stream=True`` response body, stopping past ``max_bytes``.

    Counts bytes after decompression, so a small gzip body that inflates
    without bound (a decompression bomb) is cut off. Returns the bytes read
    before the chunk that crossed the cap, and whether the cap was hit.
    Decode the result with :func:`decode_body`, not ``response.content``.
    """
    raw, too_large, _timed_out = _read_capped(
        response.iter_content(chunk_size=65536), max_bytes, None
    )
    return raw, too_large


def read_bounded_until(
    response, max_bytes: int, deadline: float
) -> tuple[bytes, bool, bool]:
    """:func:`read_bounded` with a wall-clock deadline as well.

    ``deadline`` is a ``time.monotonic()`` value. It is checked before the
    first read and after every piece of the body, and the body is taken as
    each socket read delivers it, so a server that drips a byte at a time is
    cut off at the deadline plus at most one socket read timeout. Returns the
    bytes read so far, whether the size cap was hit, and whether the deadline
    passed.
    """
    return _read_capped(_iter_as_received(response), max_bytes, deadline)


def _read_capped(
    chunks, max_bytes: int, deadline: Optional[float]
) -> tuple[bytes, bool, bool]:
    """Join ``chunks`` until the size cap or the deadline stops the read."""
    parts: list[bytes] = []
    size = 0
    if deadline is not None and time.monotonic() >= deadline:
        return b"", False, True
    for chunk in chunks:
        if chunk:
            size += len(chunk)
            if size > max_bytes:
                return b"".join(parts), True, False
            parts.append(chunk)
        if deadline is not None and time.monotonic() >= deadline:
            return b"".join(parts), False, True
    return b"".join(parts), False, False


def _iter_as_received(response, chunk_size: int = 65536) -> Iterator[bytes]:
    """Yield a streamed body as each socket read delivers it.

    ``iter_content(n)`` blocks until ``n`` bytes have arrived, so a slow drip
    could hold one 64 KiB chunk for hours between two deadline checks.
    urllib3's ``read1`` returns what a single read brings, still decompressed
    and at most ``chunk_size`` bytes. Errors are mapped to the requests
    exceptions ``iter_content`` raises.

    A body that is already in memory has nothing left on the socket:
    requests read it itself (``stream=False``), or the redirect hook filled
    in a 3xx body and closed the connection. ``iter_content`` replays that
    body, and cannot block doing so.
    """
    raw = getattr(response, "raw", None)
    if getattr(response, "_content_consumed", False) or not isinstance(
        raw, _Urllib3Response  # Anything else is a test double, not a socket.
    ):
        yield from response.iter_content(chunk_size=chunk_size)
        return
    try:
        while True:
            data = raw.read1(chunk_size, decode_content=True)
            if not data:
                return
            yield data
    except _urllib3_exceptions.ProtocolError as exc:
        raise requests.exceptions.ChunkedEncodingError(exc) from exc
    except _urllib3_exceptions.DecodeError as exc:
        raise requests.exceptions.ContentDecodingError(exc) from exc
    except _urllib3_exceptions.ReadTimeoutError as exc:
        raise requests.exceptions.ConnectionError(exc) from exc
    except _urllib3_exceptions.SSLError as exc:
        raise requests.exceptions.SSLError(exc) from exc


# Deepest JSON nesting a fetched document may have. Real discovery and
# profile documents stay under 20 levels. From Python 3.14 the json module's
# recursion limit follows the C stack size, so a 100k-deep document may parse
# on one machine and raise on another; check depth first for one answer.
MAX_JSON_DEPTH = 256

# The closing quote is optional so an unterminated string ends the scan in one
# pass; requiring it made hostile input like '"\\' * n take quadratic time.
_JSON_DEPTH_TOKEN_RE = re.compile(r'"(?:[^"\\]|\\[\s\S])*"?|[\[\]{}]')


def json_depth_exceeds(text: str, max_depth: int = MAX_JSON_DEPTH) -> bool:
    """Return True when ``text`` nests arrays or objects past ``max_depth``.

    Brackets inside JSON strings are skipped. The scan does not validate the
    document; call it before ``json.loads`` and treat True as a finding.
    """
    depth = 0
    for match in _JSON_DEPTH_TOKEN_RE.finditer(text):
        token = match.group()
        if token in "[{":
            depth += 1
            if depth > max_depth:
                return True
        elif token in "]}":
            depth -= 1
    return False


def _bound_redirect_body(response, *args, **kwargs):  # type: ignore[no-untyped-def]
    """``response`` hook: read at most MAX_REDIRECT_BODY_BYTES of a 3xx body.

    requests runs response hooks before it follows a redirect, and following
    one reads the whole body (``resp.content``), decompressed and unbounded.
    Filling the body here from a capped read means a redirect that carries a
    decompression bomb is cut off; the connection is then closed rather than
    drained. Non-redirect responses are left untouched.
    """
    if not response.is_redirect or response._content is not False:
        return response
    try:
        body, _too_large = read_bounded(response, MAX_REDIRECT_BODY_BYTES)
    except (requests.RequestException, RuntimeError):
        body = b""
    if response.raw is not None:
        response.raw.close()
    response._content = body
    response._content_consumed = True
    return response


def _with_redirect_body_cap(kwargs: dict) -> dict:
    """Put :func:`_bound_redirect_body` first in the call's response hooks."""
    hooks = dict(kwargs.get("hooks") or {})
    existing = hooks.get("response") or []
    if callable(existing):
        existing = [existing]
    hooks["response"] = [_bound_redirect_body, *existing]
    kwargs["hooks"] = hooks
    return kwargs


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
    kwargs = _with_redirect_body_cap(_with_default_headers(kwargs))
    exempt = _validated_proxy_hosts(norm_url, kwargs.get("proxies"))
    with _pin_dns(parsed.hostname, pinned_ip, port, exempt_hosts=exempt):
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
    exempt = _validated_proxy_hosts(norm_url, kwargs.get("proxies"))
    with _pin_dns(parsed.hostname, pinned_ip, port, exempt_hosts=exempt):
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
    # Session hooks apply to every request made on it, including each
    # redirect hop, unless a request passes its own response hooks.
    session.hooks["response"].append(_bound_redirect_body)
    exempt = _validated_proxy_hosts(norm_url, session.proxies)
    with _pin_dns(parsed.hostname, pinned_ip, port, exempt_hosts=exempt):
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
                # In-memory resources need no socket. Refuse file:, chrome:
                # and extension schemes rather than trusting page navigation.
                if parsed.scheme in ("data", "blob", "about"):
                    route.continue_()
                else:
                    route.abort()
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


def new_guarded_context(browser, route_handler, **context_kwargs):  # type: ignore[no-untyped-def]
    """
    Create a Playwright browser context with the SSRF guard on every page.

    ``page.route()`` does not see WebSocket traffic or requests a service
    worker makes, so page JavaScript could still reach loopback or LAN
    hosts through them. This context:

    * blocks service worker registration (``service_workers="block"``),
      so every request stays visible to the route handler;
    * routes every request of every page, popups included, through
      ``route_handler`` (a page-level route still takes precedence);
    * routes every WebSocket to a handler that never calls
      ``connect_to_server()``, so Playwright mocks the socket and no
      connection ever reaches a server (Playwright 1.48+). The handler
      must not call ``ws.close()``: in the sync API that deadlocks the
      navigation.

    Args:
        browser: a Playwright ``Browser``.
        route_handler: the callback from
            :func:`make_safe_playwright_route_handler`.
        **context_kwargs: passed to ``browser.new_context()`` (viewport,
            user_agent, and so on).

    Returns:
        The new ``BrowserContext``.
    """
    context = browser.new_context(service_workers="block", **context_kwargs)
    context.route("**/*", route_handler)
    context.route_web_socket("**/*", _never_connect_web_socket)
    return context


def _never_connect_web_socket(ws) -> None:  # type: ignore[no-untyped-def]
    """Leave the routed WebSocket mocked: it is never connected to a server."""
    return None


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
        help="Run DNS resolution and refuse on any non-public A or AAAA record.",
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
