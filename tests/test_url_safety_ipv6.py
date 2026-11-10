"""
IPv6 in scripts/url_safety.py: the address policy, dual-family resolution,
and a DNS pin that answers in the pinned address's own family.

The resolver and ``socket.socket`` are replaced throughout, and the end-to-end
cases drive the real ``requests`` and ``urllib3`` stack the way
``test_url_safety_port_pin.py`` does. No test here touches the network.
"""

from __future__ import annotations

import io
import ipaddress
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
import urllib3.util.connection as urllib3_connection  # noqa: E402

PUBLIC_V4 = "93.184.216.34"
PUBLIC_V6 = "2606:4700:4700::1111"
OTHER_PUBLIC_V6 = "2001:4860:4860::8888"


def _info(ip: str, port) -> tuple:
    """One getaddrinfo row, shaped the way the real resolver shapes it."""
    if ":" in ip:
        return (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ip, port, 0, 0))
    return (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))


def _resolver(records: dict, families: list | None = None):
    """getaddrinfo stand-in: ``records`` maps a name to its A and AAAA answers."""
    def fake_getaddrinfo(host, port, *args, **kwargs):
        if families is not None:
            families.append(kwargs.get("family", args[0] if args else 0))
        if host not in records:
            raise socket.gaierror(socket.EAI_NONAME, f"unmocked host {host!r}")
        return [_info(ip, port or 0) for ip in records[host]]

    return fake_getaddrinfo


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    """No developer allowlist, no developer proxy."""
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)
    monkeypatch.setattr(url_safety.requests.utils, "getproxies", lambda: {})


# ---------------------------------------------------------------------------
# is_safe_ip: every IPv6 range that is not a public audit target
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        pytest.param("::1", id="loopback"),
        pytest.param("::", id="unspecified"),
        pytest.param("fe80::1", id="link-local"),
        pytest.param("febf::1", id="link-local-upper"),
        pytest.param("fc00::1", id="unique-local-fc"),
        pytest.param("fd12:3456:789a::1", id="unique-local-fd"),
        pytest.param("fec0::1", id="site-local"),
        pytest.param("feff::1", id="site-local-upper"),
        pytest.param("ff02::1", id="multicast-link"),
        pytest.param("ff0e::1", id="multicast-global"),
        pytest.param("::ffff:127.0.0.1", id="mapped-loopback"),
        pytest.param("::ffff:10.0.0.1", id="mapped-rfc1918"),
        pytest.param("::ffff:169.254.169.254", id="mapped-metadata"),
        pytest.param("::ffff:100.64.0.1", id="mapped-rfc6598"),
        pytest.param("::127.0.0.1", id="compatible-loopback"),
        pytest.param("::8.8.8.8", id="compatible-public"),
        pytest.param("64:ff9b::10.0.0.1", id="nat64-private"),
        pytest.param("64:ff9b::169.254.169.254", id="nat64-metadata"),
        pytest.param("64:ff9b::8.8.8.8", id="nat64-public"),
        pytest.param("64:ff9b:1::1", id="nat64-local-use"),
        pytest.param("64:ff9b:1:ffff::8.8.8.8", id="nat64-local-use-upper"),
        pytest.param("2002:7f00:1::1", id="6to4-loopback"),
        pytest.param("2002:a00:1::1", id="6to4-rfc1918"),
        pytest.param("2002:808:808::1", id="6to4-public"),
        pytest.param("2001::1", id="teredo"),
        pytest.param("2001:0:4136:e378:8000:63bf:3fff:fdd2", id="teredo-real-shape"),
        pytest.param("2001:db8::1", id="documentation"),
        pytest.param("3fff::1", id="documentation-rfc9637"),
        pytest.param("2001:10::1", id="orchid"),
        pytest.param("2001:1f:ffff::1", id="orchid-upper"),
        pytest.param("2001:20::1", id="orchid-v2"),
        pytest.param("2001:2f:ffff::1", id="orchid-v2-upper"),
        pytest.param("fd00:ec2::254", id="aws-imds"),
    ],
)
def test_is_safe_ip_refuses_ipv6_special_ranges(ip: str) -> None:
    assert url_safety.is_safe_ip(ip) is False


@pytest.mark.parametrize(
    "network", [str(network) for network in url_safety._UNSAFE_IPV6_NETWORKS]
)
def test_every_unsafe_ipv6_network_is_refused_at_both_ends(network: str) -> None:
    parsed = ipaddress.ip_network(network)
    assert url_safety.is_safe_ip(str(parsed[0])) is False
    assert url_safety.is_safe_ip(str(parsed[-1])) is False


def test_the_unsafe_ipv6_table_names_every_range_the_policy_promises() -> None:
    """The flags in ``ipaddress`` move between Python releases; the table is
    what the policy rests on, so a range cannot drop out of it unnoticed."""
    assert {str(network) for network in url_safety._UNSAFE_IPV6_NETWORKS} == {
        "::/96",
        "64:ff9b::/96",
        "64:ff9b:1::/48",
        "2001::/32",
        "2001:10::/28",
        "2001:20::/28",
        "2001:db8::/32",
        "2002::/16",
        "3fff::/20",
        "fc00::/7",
        "fe80::/10",
        "fec0::/10",
        "ff00::/8",
    }


@pytest.mark.parametrize(
    "ip",
    [
        "fe80::1%eth0",
        "fe80::1%1",
        "::1%lo",
        f"{PUBLIC_V6}%eth0",  # public address, still machine-local with a zone
        "::ffff:8.8.8.8%eth0",
        "fe80::1%",
    ],
)
def test_is_safe_ip_refuses_zone_identifiers(ip: str) -> None:
    assert url_safety.is_safe_ip(ip) is False
    assert url_safety._is_allowlistable_ip(ip) is False


@pytest.mark.parametrize(
    "ip,expected",
    [
        ("::ffff:8.8.8.8", True),
        ("::ffff:1.1.1.1", True),
        ("::ffff:127.0.0.1", False),
        ("::ffff:192.168.1.1", False),
        ("::ffff:100.100.100.200", False),
        ("::ffff:0.0.0.0", False),
        ("::ffff:224.0.0.1", False),
    ],
)
def test_ipv4_mapped_ipv6_is_judged_by_the_embedded_ipv4(ip: str, expected: bool) -> None:
    assert url_safety.is_safe_ip(ip) is expected


@pytest.mark.parametrize(
    "ip",
    [
        PUBLIC_V6,
        OTHER_PUBLIC_V6,
        "2620:fe::fe",
        "2a00:1450:4001:81b::200e",
        "2001:200::1",   # first block past the IETF 2001::/23 assignments
        "2001:db9::1",   # one past the documentation range
        "2003::1",       # one past 6to4
    ],
)
def test_is_safe_ip_still_accepts_public_ipv6(ip: str) -> None:
    assert url_safety.is_safe_ip(ip) is True


# ---------------------------------------------------------------------------
# validate_url and validate_url_strict: IPv6 literals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        (f"http://[{PUBLIC_V6}]/", True),
        (f"https://[{PUBLIC_V6}]:8443/path?q=1", True),
        ("http://[::ffff:8.8.8.8]/", True),
        ("http://[::1]/", False),
        ("http://[::]/", False),
        ("http://[fe80::1]/", False),
        ("http://[fd00::1]/", False),
        ("http://[fec0::1]/", False),
        ("http://[ff02::1]/", False),
        ("http://[::ffff:127.0.0.1]/", False),
        ("http://[::127.0.0.1]/", False),
        ("http://[64:ff9b::7f00:1]/", False),
        ("http://[64:ff9b:1::1]/", False),
        ("http://[2002:7f00:1::1]/", False),
        ("http://[2001::1]/", False),
        ("http://[2001:db8::1]/", False),
        ("http://[2001:10::1]/", False),
        ("http://[2001:20::1]/", False),
        ("http://[fd00:ec2::254]/latest/meta-data/", False),
    ],
)
def test_validate_url_ipv6_literals(url: str, expected: bool) -> None:
    assert url_safety.validate_url(url) is expected
    if expected:
        assert url_safety.validate_url_strict(url)[0] == url
    else:
        with pytest.raises(url_safety.URLSafetyError):
            url_safety.validate_url_strict(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://[fe80::1%25eth0]/",
        "http://[fe80::1%eth0]/",
        f"http://[{PUBLIC_V6}%25eth0]/",
        f"http://[{PUBLIC_V6}%eth0]:8080/",
    ],
)
def test_zone_identifier_in_a_url_is_refused(url: str) -> None:
    assert url_safety.validate_url(url) is False
    with pytest.raises(url_safety.URLSafetyError):
        url_safety.validate_url_strict(url)


def test_strict_keeps_the_brackets_of_a_public_ipv6_literal() -> None:
    url = f"https://[{PUBLIC_V6}]:8443/path?q=1"
    with patch.object(
        url_safety.socket, "getaddrinfo", side_effect=AssertionError("literal resolved")
    ):
        assert url_safety.validate_url_strict(url) == (url, PUBLIC_V6)


# ---------------------------------------------------------------------------
# validate_url_strict: both families resolved, every record checked
# ---------------------------------------------------------------------------


def test_strict_resolves_both_families_in_one_lookup() -> None:
    families: list = []
    resolver = _resolver({"example.com": [PUBLIC_V4]}, families)
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        url_safety.validate_url_strict("https://example.com/")
    assert families == [socket.AF_UNSPEC]


def test_strict_pins_ipv6_for_a_host_with_only_aaaa_records() -> None:
    """Before this, an AAAA-only host failed with 'DNS resolution failed'."""
    resolver = _resolver({"v6only.example": [OTHER_PUBLIC_V6, PUBLIC_V6]})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        url, pinned = url_safety.validate_url_strict("https://v6only.example/")
    assert url == "https://v6only.example/"
    assert pinned == OTHER_PUBLIC_V6  # lowest address, as for A records


@pytest.mark.parametrize(
    "answers",
    [
        [PUBLIC_V4, PUBLIC_V6],
        [PUBLIC_V6, PUBLIC_V4],
        [PUBLIC_V6, OTHER_PUBLIC_V6, "93.184.216.99", PUBLIC_V4],
    ],
)
def test_strict_prefers_ipv4_for_a_dual_stack_host(answers) -> None:
    """Whatever order the resolver uses, the pin is the address it always was."""
    resolver = _resolver({"dual.example": answers})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        assert url_safety.validate_url_strict("https://dual.example/")[1] == PUBLIC_V4


@pytest.mark.parametrize(
    "answers,refused",
    [
        ([PUBLIC_V4, "fd00::1"], "fd00::1"),            # public A, private AAAA
        ([PUBLIC_V4, "::1"], "::1"),
        ([PUBLIC_V4, "fe80::1"], "fe80::1"),
        ([PUBLIC_V4, "fec0::1"], "fec0::1"),
        ([PUBLIC_V4, "::ffff:10.0.0.1"], "::ffff:10.0.0.1"),
        ([PUBLIC_V4, "fc00::1"], "fc00::1"),
        ([PUBLIC_V4, "64:ff9b:1::1"], "64:ff9b:1::1"),  # local-use NAT64
        ([PUBLIC_V4, "2002:a00:1::1"], "2002:a00:1::1"),
        ([PUBLIC_V4, "fd00:ec2::254"], "fd00:ec2::254"),
        ([PUBLIC_V6, "10.0.0.7"], "10.0.0.7"),          # public AAAA, private A
        ([PUBLIC_V6, "169.254.169.254"], "169.254.169.254"),
        ([PUBLIC_V6, "fd00::1"], "fd00::1"),            # two AAAA, one private
        ([PUBLIC_V4, PUBLIC_V6, "fd00::1"], "fd00::1"),
    ],
)
def test_strict_refuses_a_host_with_any_unsafe_record_in_either_family(
    answers, refused
) -> None:
    """The multi-A-record rule, across both families: one bad record refuses
    the host, even though the address that would be pinned is public."""
    resolver = _resolver({"mixed.example": answers})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with pytest.raises(url_safety.URLSafetyError, match="non-public IP") as excinfo:
            url_safety.validate_url_strict("https://mixed.example/")
    assert str(excinfo.value).endswith(f"non-public IP {refused}")


@pytest.mark.parametrize(
    "address",
    [
        "::1", "fe80::1", "fd00::1", "fec0::1", "ff02::1", "::ffff:127.0.0.1",
        "::10.0.0.1", "64:ff9b::808:808", "64:ff9b:1::1", "2002:808:808::1",
        "2001::1", "2001:db8::1", "2001:10::1", "2001:20::1", "fd00:ec2::254",
        "fe80::1%eth0", f"{PUBLIC_V6}%eth0",
    ],
)
def test_strict_refuses_an_aaaa_only_host_in_an_unsafe_range(address: str) -> None:
    resolver = _resolver({"v6only.example": [address]})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with pytest.raises(url_safety.URLSafetyError, match="non-public IP"):
            url_safety.validate_url_strict("https://v6only.example/")


# ---------------------------------------------------------------------------
# DNS64: a synthesized 64:ff9b::/96 AAAA beside an A record is passed over
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nat64",
    [
        "64:ff9b::5db8:d822",  # the same public IPv4, as DNS64 synthesizes it
        "64:ff9b::808:808",    # another public IPv4
        "64:ff9b::7f00:1",     # loopback embedded: still never dialled
        "64:ff9b::a9fe:a9fe",  # 169.254.169.254 embedded
    ],
)
def test_dns64_aaaa_beside_an_a_record_is_ignored_and_ipv4_is_pinned(nat64) -> None:
    """An IPv4-only site on a DNS64 network: one real A record plus one
    synthesized AAAA. It resolved before this lookup asked for both families
    and must keep resolving, pinned to the A record."""
    resolver = _resolver({"v4only.example": [nat64, PUBLIC_V4]})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        url, pinned = url_safety.validate_url_strict("https://v4only.example/")
    assert (url, pinned) == ("https://v4only.example/", PUBLIC_V4)

    # The pin for that host answers in IPv4 only, so the AAAA has no way in.
    with url_safety._pin_dns("v4only.example", pinned, 443):
        assert socket.getaddrinfo("v4only.example", 443) == [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_V4, 443))
        ]
        with pytest.raises(socket.gaierror, match="refused for pinned IPv4 host"):
            socket.getaddrinfo("v4only.example", 443, socket.AF_INET6)


@pytest.mark.parametrize(
    "answers,refused",
    [
        (["10.0.0.7", "64:ff9b::a00:7"], "10.0.0.7"),         # private A
        (["127.0.0.1", "64:ff9b::7f00:1"], "127.0.0.1"),
        ([PUBLIC_V4, "10.0.0.7", "64:ff9b::5db8:d822"], "10.0.0.7"),
        ([PUBLIC_V4, "64:ff9b::5db8:d822", "fc00::1"], "fc00::1"),
        ([PUBLIC_V4, "64:ff9b::5db8:d822", "64:ff9b:1::1"], "64:ff9b:1::1"),
        ([PUBLIC_V4, "64:ff9b::5db8:d822%eth0"], "64:ff9b::5db8:d822%eth0"),
    ],
)
def test_dns64_pass_covers_nothing_but_the_well_known_prefix(answers, refused) -> None:
    """The A records are judged as always, and every other unsafe AAAA,
    the local-use NAT64 prefix included, still refuses the host."""
    resolver = _resolver({"mixed.example": answers})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with pytest.raises(url_safety.URLSafetyError, match="non-public IP") as excinfo:
            url_safety.validate_url_strict("https://mixed.example/")
    assert str(excinfo.value).endswith(f"non-public IP {refused}")


@pytest.mark.parametrize(
    "answers",
    [
        ["64:ff9b::5db8:d822"],
        ["64:ff9b::5db8:d822", "64:ff9b::808:808"],
        ["64:ff9b::5db8:d822", PUBLIC_V6],        # no A record, so no pass
        ["64:ff9b::5db8:d822", "::ffff:8.8.8.8"],  # IPv4-mapped is not an A record
    ],
)
def test_host_without_an_a_record_gets_no_dns64_pass(answers) -> None:
    resolver = _resolver({"v6only.example": answers})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with pytest.raises(
            url_safety.URLSafetyError, match="non-public IP 64:ff9b::5db8:d822"
        ):
            url_safety.validate_url_strict("https://v6only.example/")


def test_nat64_stays_refused_everywhere_but_the_dns64_case() -> None:
    """is_safe_ip is as strict as before: literals, redirect targets inside
    the pinned scope and the Playwright handler all still refuse the prefix."""
    assert url_safety.is_safe_ip("64:ff9b::5db8:d822") is False
    assert url_safety.validate_url("http://[64:ff9b::5db8:d822]/") is False
    with pytest.raises(url_safety.URLSafetyError, match="Blocked IP literal"):
        url_safety.validate_url_strict("http://[64:ff9b::5db8:d822]/")

    resolver = _resolver({"redirected.example": [PUBLIC_V4, "64:ff9b::5db8:d822"]})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with url_safety._pin_dns("pinned.example", PUBLIC_V4, 443):
            with pytest.raises(socket.gaierror, match="non-public IP"):
                socket.getaddrinfo("redirected.example", 443)


def test_strict_reports_a_host_with_no_records() -> None:
    with patch.object(url_safety.socket, "getaddrinfo", return_value=[]):
        with pytest.raises(url_safety.URLSafetyError, match="No address records"):
            url_safety.validate_url_strict("https://empty.example/")


# ---------------------------------------------------------------------------
# CLAUDE_SEO_LOCAL_TARGETS with IPv6
# ---------------------------------------------------------------------------


def test_allowlisted_ipv6_loopback_literal_is_pinned_as_ipv6(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "[::1]:3000")
    assert url_safety.validate_url_strict("http://[::1]:3000/") == (
        "http://[::1]:3000/",
        "::1",
    )
    with pytest.raises(url_safety.URLSafetyError, match="Blocked hostname"):
        url_safety.validate_url_strict("http://[::1]:3001/")


def test_allowlisted_localhost_with_both_families_still_pins_ipv4(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000")
    resolver = _resolver({"localhost": ["::1", "127.0.0.1"]})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        assert url_safety.validate_url_strict("http://localhost:3000/")[1] == "127.0.0.1"


def test_allowlisted_name_may_resolve_to_unique_local_ipv6(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "staging.internal:8080")
    resolver = _resolver({"staging.internal": ["fd00::5"]})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        assert url_safety.validate_url_strict("http://staging.internal:8080/")[1] == "fd00::5"


@pytest.mark.parametrize(
    "address", ["fe80::1", "fd00:ec2::254", "ff02::1", "::", "fd00::5%eth0", "64:ff9b::a00:1"]
)
def test_allowlist_never_admits_these_ipv6_addresses(monkeypatch, address) -> None:
    """Link-local, metadata, multicast, unspecified, zoned and NAT64 answers
    stay refused for a listed name, exactly as 169.254.169.254 does."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "staging.internal:8080")
    resolver = _resolver({"staging.internal": [address]})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with pytest.raises(url_safety.URLSafetyError, match="DNS rebinding refused"):
            url_safety.validate_url_strict("http://staging.internal:8080/")


def test_allowlist_does_not_forgive_an_unsafe_aaaa_on_an_unlisted_host(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "staging.internal:8080")
    resolver = _resolver({"other.example": [PUBLIC_V4, "fd00::5"]})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with pytest.raises(url_safety.URLSafetyError, match="non-public IP fd00::5"):
            url_safety.validate_url_strict("http://other.example:8080/")


# ---------------------------------------------------------------------------
# _pin_dns: the tuple matches the pinned family, the caller's family is honoured
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "args,kwargs",
    [
        ((), {}),
        ((socket.AF_UNSPEC,), {}),
        ((socket.AF_INET6,), {}),
        ((socket.AF_INET6, socket.SOCK_STREAM), {}),
        ((), {"family": socket.AF_UNSPEC}),
        ((), {"family": socket.AF_INET6, "type": socket.SOCK_STREAM}),
    ],
)
def test_ipv6_pin_returns_an_af_inet6_row_with_a_four_part_sockaddr(args, kwargs) -> None:
    with url_safety._pin_dns("v6only.example", PUBLIC_V6, 443):
        rows = socket.getaddrinfo("v6only.example", 443, *args, **kwargs)
    assert rows == [
        (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_V6, 443, 0, 0))
    ]


@pytest.mark.parametrize(
    "args,kwargs", [((socket.AF_INET,), {}), ((), {"family": socket.AF_INET})]
)
def test_ipv6_pin_fails_closed_for_an_ipv4_only_lookup(args, kwargs) -> None:
    """No AF_INET row carrying an IPv6 address, and no fall-back lookup."""
    with patch.object(
        url_safety.socket, "getaddrinfo", side_effect=AssertionError("real resolver used")
    ):
        with url_safety._pin_dns("v6only.example", PUBLIC_V6, 443):
            with pytest.raises(socket.gaierror, match="refused for pinned IPv6 host"):
                socket.getaddrinfo("v6only.example", 443, *args, **kwargs)


@pytest.mark.parametrize(
    "args,kwargs", [((socket.AF_INET6,), {}), ((), {"family": socket.AF_INET6})]
)
def test_ipv4_pin_fails_closed_for_an_ipv6_only_lookup(args, kwargs) -> None:
    with url_safety._pin_dns("example.com", PUBLIC_V4, 443):
        with pytest.raises(socket.gaierror, match="refused for pinned IPv4 host"):
            socket.getaddrinfo("example.com", 443, *args, **kwargs)


@pytest.mark.parametrize("family", [None, socket.AF_UNSPEC, socket.AF_INET])
def test_ipv4_pin_row_is_unchanged(family) -> None:
    kwargs = {} if family is None else {"family": family}
    with url_safety._pin_dns("example.com", PUBLIC_V4, 443):
        rows = socket.getaddrinfo("example.com", 8443, **kwargs)
    assert rows == [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_V4, 8443))
    ]


@pytest.mark.parametrize("requested_port", [80, 443, 8080, None, 0])
def test_public_ipv6_pin_answers_for_any_port(requested_port) -> None:
    with url_safety._pin_dns("v6only.example", PUBLIC_V6, 80):
        sockaddr = socket.getaddrinfo("v6only.example", requested_port)[0][4]
    assert sockaddr == (PUBLIC_V6, requested_port or 80, 0, 0)


def test_ipv6_local_pin_is_bound_to_the_validated_port(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "[::1]:3000")
    with url_safety._pin_dns("::1", "::1", 3000):
        assert socket.getaddrinfo("::1", 3000)[0][4] == ("::1", 3000, 0, 0)
        assert socket.getaddrinfo("::1", None)[0][4] == ("::1", 3000, 0, 0)
        for port in (6379, 80, 443, 3001, "redis"):
            with pytest.raises(socket.gaierror, match="validated port is 3000"):
                socket.getaddrinfo("::1", port)


def test_ipv6_local_pin_is_port_bound_without_an_allowlist() -> None:
    with url_safety._pin_dns("staging.internal", "fd00::5", 8080):
        assert socket.getaddrinfo("staging.internal", 8080)[0][4] == ("fd00::5", 8080, 0, 0)
        with pytest.raises(socket.gaierror, match="validated port is 8080"):
            socket.getaddrinfo("staging.internal", 9200)


def test_bare_ipv6_allowlist_entry_keeps_matching_any_port(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "fd00::5")
    with url_safety._pin_dns("fd00::5", "fd00::5", 80):
        assert socket.getaddrinfo("fd00::5", 8080)[0][4] == ("fd00::5", 8080, 0, 0)


@pytest.mark.parametrize(
    "address", ["::1", "fd00::1", "fec0::1", "64:ff9b::a00:1", "2002:a00:1::1", "fe80::1%eth0"]
)
def test_redirect_target_on_an_unsafe_ipv6_address_is_refused_in_the_pinned_scope(
    address,
) -> None:
    resolver = _resolver({"redirected.example": [PUBLIC_V4, address]})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with url_safety._pin_dns("pinned.example", PUBLIC_V6, 443):
            with pytest.raises(socket.gaierror, match="non-public IP"):
                socket.getaddrinfo("redirected.example", 443)


def test_redirect_target_on_public_ipv6_resolves_in_the_pinned_scope() -> None:
    resolver = _resolver({"elsewhere.example": [PUBLIC_V6]})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with url_safety._pin_dns("pinned.example", PUBLIC_V4, 443):
            assert socket.getaddrinfo("elsewhere.example", 443)[0][4][0] == PUBLIC_V6


# ---------------------------------------------------------------------------
# Proxy validation picks up the same IPv6 policy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("proxy_host", ["::1", "fd00::1", "fec0::1", "64:ff9b::808:808", "2001:20::1"])
def test_proxy_on_a_non_public_ipv6_literal_is_refused(proxy_host) -> None:
    with pytest.raises(url_safety.URLSafetyError, match="Refusing configured HTTP proxy"):
        url_safety._assert_proxy_host_is_public(proxy_host)


def test_proxy_name_with_an_unsafe_aaaa_record_is_refused() -> None:
    resolver = _resolver({"proxy.corp.example": ["8.8.4.4", "fec0::1"]})
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=resolver):
        with pytest.raises(url_safety.URLSafetyError, match="non-public IP fec0::1"):
            url_safety._assert_proxy_host_is_public("proxy.corp.example")


# ---------------------------------------------------------------------------
# End to end through requests and urllib3
# ---------------------------------------------------------------------------


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
    """Canned HTTP servers keyed by ``(ip, port)``, plus what reached them."""

    def __init__(self, hosts: dict, servers: dict) -> None:
        self.hosts = hosts
        self.servers = servers
        self.connections: list = []  # (socket family, sockaddr)
        self.sent: list = []

    def getaddrinfo(self, host, port, *args, **kwargs):
        if host in self.hosts:
            ips = self.hosts[host]
        else:
            try:
                ipaddress.ip_address(host)
            except ValueError:
                raise socket.gaierror(socket.EAI_NONAME, f"unmocked host {host!r}") from None
            ips = [host]
        return [_info(ip, port or 0) for ip in ips]

    def socket(self, family=socket.AF_INET, *args, **kwargs):
        return _FakeSocket(self, family)


class _FakeSocket:
    """The slice of ``socket.socket`` that urllib3 and http.client use."""

    def __init__(self, net: _FakeNet, family) -> None:
        self._net = net
        self._family = family
        self._key = None

    def connect(self, address) -> None:
        self._net.connections.append((self._family, address))
        key = (address[0], address[1])
        if key not in self._net.servers:
            raise ConnectionRefusedError(111, "no fake server on this port")
        self._key = key

    def makefile(self, *args, **kwargs):
        return io.BytesIO(self._net.servers[self._key])

    def sendall(self, data) -> None:
        self._net.sent.append(bytes(data))

    def setsockopt(self, *args) -> None:
        pass

    def settimeout(self, value) -> None:
        pass

    def shutdown(self, how) -> None:
        pass

    def close(self) -> None:
        pass


def _get(url: str, net: _FakeNet, *, gai_family=socket.AF_UNSPEC):
    """``safe_requests_get`` against the fake network. ``gai_family`` is what
    urllib3 asks the resolver for: AF_UNSPEC on a machine with IPv6, AF_INET
    on one without. It is set here so the result does not depend on the host."""
    with patch.object(url_safety.socket, "getaddrinfo", side_effect=net.getaddrinfo), \
            patch.object(url_safety.socket, "socket", side_effect=net.socket), \
            patch.object(urllib3_connection, "allowed_gai_family", return_value=gai_family):
        return url_safety.safe_requests_get(url, timeout=5)


def test_ipv6_only_host_is_fetched_over_ipv6() -> None:
    net = _FakeNet({"v6only.example": [PUBLIC_V6]}, {(PUBLIC_V6, 80): _ok("over ipv6")})

    response = _get("http://v6only.example/page", net)

    assert response.status_code == 200
    assert response.content == b"over ipv6"
    assert net.connections == [(socket.AF_INET6, (PUBLIC_V6, 80, 0, 0))]
    assert b"Host: v6only.example\r\n" in b"".join(net.sent)


def test_ipv6_literal_keeps_its_brackets_in_the_url_and_host_header() -> None:
    url = f"http://[{PUBLIC_V6}]:8080/page"
    net = _FakeNet({}, {(PUBLIC_V6, 8080): _ok("literal")})

    response = _get(url, net)

    assert response.content == b"literal"
    assert response.url == url
    assert response.request.url == url
    assert net.connections == [(socket.AF_INET6, (PUBLIC_V6, 8080, 0, 0))]
    assert f"Host: [{PUBLIC_V6}]:8080\r\n".encode("ascii") in b"".join(net.sent)


def test_dual_stack_host_still_connects_over_ipv4() -> None:
    net = _FakeNet(
        {"dual.example": [PUBLIC_V6, PUBLIC_V4]},
        {(PUBLIC_V4, 80): _ok("over ipv4"), (PUBLIC_V6, 80): _ok("over ipv6")},
    )

    assert _get("http://dual.example/", net).content == b"over ipv4"
    assert net.connections == [(socket.AF_INET, (PUBLIC_V4, 80))]


def test_ipv4_only_site_on_a_dns64_network_is_fetched_over_ipv4() -> None:
    """Even with a server answering at the synthesized address, only the
    pinned A record is dialled."""
    nat64 = "64:ff9b::5db8:d822"
    net = _FakeNet(
        {"v4only.example": [nat64, PUBLIC_V4]},
        {(PUBLIC_V4, 80): _ok("over ipv4"), (nat64, 80): _ok("over nat64")},
    )

    assert _get("http://v4only.example/", net).content == b"over ipv4"
    assert net.connections == [(socket.AF_INET, (PUBLIC_V4, 80))]


def test_ipv6_only_host_fails_closed_on_a_machine_without_ipv6() -> None:
    """urllib3 asks for AF_INET only there. The pin refuses instead of
    handing back an IPv6 address in an IPv4 row, and nothing is connected."""
    net = _FakeNet({"v6only.example": [PUBLIC_V6]}, {(PUBLIC_V6, 80): _ok("over ipv6")})

    with pytest.raises(requests.exceptions.ConnectionError, match="refused for pinned IPv6 host"):
        _get("http://v6only.example/", net, gai_family=socket.AF_INET)

    assert net.connections == []


def test_ipv6_host_redirect_to_another_port_is_followed_when_public() -> None:
    net = _FakeNet(
        {"v6only.example": [PUBLIC_V6]},
        {
            (PUBLIC_V6, 80): _redirect("http://v6only.example:8080/app"),
            (PUBLIC_V6, 8080): _ok("public app"),
        },
    )

    assert _get("http://v6only.example/", net).content == b"public app"
    assert net.connections == [
        (socket.AF_INET6, (PUBLIC_V6, 80, 0, 0)),
        (socket.AF_INET6, (PUBLIC_V6, 8080, 0, 0)),
    ]


def test_redirect_to_another_port_on_an_allowed_ipv6_local_host_is_refused(monkeypatch) -> None:
    """The port-bound rule for local targets, unchanged, on an IPv6 pin."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "[::1]:3000")
    net = _FakeNet(
        {},
        {
            ("::1", 3000): _redirect("http://[::1]:6379/"),
            ("::1", 6379): _ok("internal service"),
        },
    )

    with pytest.raises(requests.exceptions.ConnectionError, match="validated port"):
        _get("http://[::1]:3000/", net)

    assert net.connections == [(socket.AF_INET6, ("::1", 3000, 0, 0))]


@pytest.mark.parametrize(
    "location",
    [
        "http://[0:0:0:0:0:0:0:1]:6379/",   # the same address, written out
        "http://[::ffff:127.0.0.1]:6379/",  # its IPv4-mapped neighbour
        "http://localhost:6379/",           # a name for it
        "http://127.0.0.1:6379/",
    ],
)
def test_another_spelling_of_the_allowed_ipv6_host_does_not_escape_the_port_rule(
    monkeypatch, location
) -> None:
    """A redirect cannot reach another port by naming the pinned loopback
    address differently: any spelling that is not the pinned host is a new
    host, and a new host on a non-public address is refused."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "[::1]:3000")
    servers = {("::1", 3000): _redirect(location)}
    for ip in ("::1", "127.0.0.1", "::ffff:127.0.0.1", "::ffff:7f00:1"):
        servers[(ip, 6379)] = _ok("internal service")
    net = _FakeNet({"localhost": ["::1", "127.0.0.1"]}, servers)

    with pytest.raises(
        requests.exceptions.ConnectionError, match="non-public IP|validated port"
    ):
        _get("http://[::1]:3000/", net)

    assert net.connections == [(socket.AF_INET6, ("::1", 3000, 0, 0))]


@pytest.mark.parametrize(
    "location", ["http://[::1]:3000/", "http://[fd00::5]/", "http://[fec0::1]/", "http://internal.example/"]
)
def test_public_ipv6_host_redirecting_to_a_local_ipv6_target_is_refused(location) -> None:
    net = _FakeNet(
        {"v6only.example": [PUBLIC_V6], "internal.example": [PUBLIC_V4, "fd00::5"]},
        {
            (PUBLIC_V6, 80): _redirect(location),
            ("::1", 3000): _ok("dev server"),
            ("fd00::5", 80): _ok("internal"),
            ("fec0::1", 80): _ok("internal"),
            (PUBLIC_V4, 80): _ok("internal"),
        },
    )

    with pytest.raises(requests.exceptions.ConnectionError, match="non-public IP"):
        _get("http://v6only.example/", net)

    assert net.connections == [(socket.AF_INET6, (PUBLIC_V6, 80, 0, 0))]
