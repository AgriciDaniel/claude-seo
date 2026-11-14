"""Adversarial tests for CLAUDE_SEO_TRUSTED_PROXIES (PR #398, issue #280).

The variable lets an operator name a proxy on loopback or a private address.
These tests hold it to that: it trusts a proxy endpoint and nothing else. The
contributor's own tests live in test_url_safety.py; the browser guard's are in
test_browser_proxy.py.
"""

from __future__ import annotations

import io
import os
import socket
import sys

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

requests = pytest.importorskip("requests")
import url_safety  # noqa: E402

ENV = "CLAUDE_SEO_TRUSTED_PROXIES"
LOOPBACK_PROXY = "http://127.0.0.1:3128"


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    """No test inherits the developer's proxy, allowlists or NO_PROXY."""
    monkeypatch.setattr(url_safety.requests.utils, "getproxies", lambda: {})
    for name in (ENV, "CLAUDE_SEO_LOCAL_TARGETS", "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)


def _proxies(monkeypatch, mapping: dict) -> None:
    monkeypatch.setattr(url_safety.requests.utils, "getproxies", lambda: dict(mapping))


def _records(port, *addresses: str) -> list:
    out = []
    for address in addresses:
        if ":" in address:
            out.append((socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, port or 0, 0, 0)))
        else:
            out.append((socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port or 0)))
    return out


def _dns(monkeypatch, mapping: dict) -> list:
    """Resolve only the named hosts; each value is one address or a list.

    A value that is a list of lists is a sequence of answers, one per lookup
    (the last one repeats): that is DNS rebinding. Returns the lookup log.
    """
    lookups: list = []
    state = {name: 0 for name in mapping}

    def fake_getaddrinfo(host, port, *args, **kwargs):
        lookups.append(host)
        if host not in mapping:
            try:
                socket.inet_pton(socket.AF_INET6 if ":" in host else socket.AF_INET, host)
            except (OSError, TypeError):
                raise socket.gaierror(socket.EAI_NONAME, f"unmocked host {host!r}") from None
            return _records(port, host)
        answer = mapping[host]
        if isinstance(answer, str):
            answer = [answer]
        if answer and isinstance(answer[0], list):
            index = min(state[host], len(answer) - 1)
            state[host] += 1
            answer = answer[index]
        return _records(port, *answer)

    monkeypatch.setattr(url_safety.socket, "getaddrinfo", fake_getaddrinfo)
    return lookups


# ---------------------------------------------------------------------------
# The parser: a malformed entry trusts nothing
# ---------------------------------------------------------------------------

MALFORMED = [
    "",
    " ",
    ",",
    ",,,",
    "*",
    "*:3128",
    "*.corp.example:3128",
    "127.*",
    "127.0.0.*:3128",
    "10.0.0.0/8",
    "127.0.0.1/32",
    "127.0.0.0/8:3128",
    "::/0",
    "http://127.0.0.1:3128",
    "http://127.0.0.1:3128/",
    "https://127.0.0.1",
    "socks5://127.0.0.1:1080",
    "//127.0.0.1:3128",
    "user:pw@127.0.0.1:3128",
    "user@127.0.0.1",
    "@127.0.0.1:3128",
    "127.0.0.1:3128/path",
    "127.0.0.1:3128?x=1",
    "127.0.0.1:3128#frag",
    "127.0.0.1:0",
    "[::1]:0",
    "127.0.0.1:65536",
    "127.0.0.1:99999",
    "127.0.0.1:123456",
    "127.0.0.1:-1",
    "127.0.0.1:abc",
    "127.0.0.1:",
    "127.0.0.1 3128",
    "127.0.0.1\t:3128",
    "[::1",
    "::1]",
    "[::1]]:3128",
    "[]:3128",
    "fe80::1%eth0",
    "[fe80::1%25eth0]:3128",
    "host name:3128",
    "-proxy:3128",
    ".",
    ":3128",
    "127.0.0.1;10.0.0.1",
    "127.0.0.1|3128",
    "é.example:3128",
]


@pytest.mark.parametrize("entry", MALFORMED)
def test_a_malformed_entry_is_dropped(monkeypatch, entry) -> None:
    monkeypatch.setenv(ENV, entry)
    assert url_safety._trusted_proxies() == ()


@pytest.mark.parametrize("entry", MALFORMED)
@pytest.mark.parametrize(
    "host,port",
    [("127.0.0.1", 3128), ("10.0.0.5", 8080), ("::1", 3128), ("localhost", 3128), ("http", 80)],
)
def test_a_malformed_entry_never_matches_a_proxy(monkeypatch, entry, host, port) -> None:
    """No wildcard, range or half-parsed URL ends up trusting some proxy."""
    monkeypatch.setenv(ENV, entry)
    assert url_safety._is_trusted_proxy(host, port) is False
    assert url_safety._is_trusted_proxy(host, None) is False


def test_a_malformed_entry_does_not_spoil_or_widen_its_neighbours(monkeypatch) -> None:
    monkeypatch.setenv(ENV, "*, http://10.0.0.1:1 ,127.0.0.1:3128,10.0.0.0/8,,")
    assert url_safety._trusted_proxies() == (("127.0.0.1", 3128),)


@pytest.mark.parametrize(
    "entry,expected",
    [
        ("127.0.0.1", ("127.0.0.1", None)),
        (" 127.0.0.1:3128 ", ("127.0.0.1", 3128)),
        ("LOCALHOST:3128", ("localhost", 3128)),
        ("Proxy.Sandbox.:3128", ("proxy.sandbox", 3128)),
        ("proxy.sandbox.", ("proxy.sandbox", None)),
        ("[::1]:3128", ("::1", 3128)),
        ("[::1]", ("::1", None)),
        ("::1", ("::1", None)),
        ("127.0.0.1:65535", ("127.0.0.1", 65535)),
        ("127.0.0.1:1", ("127.0.0.1", 1)),
        ("127.0.0.1:03128", ("127.0.0.1", 3128)),
        # Obfuscated IPv4 becomes the address it really is, as for a target.
        ("2130706433:3128", ("127.0.0.1", 3128)),
        ("0x7f.0.0.1:3128", ("127.0.0.1", 3128)),
    ],
)
def test_entries_are_normalised(monkeypatch, entry, expected) -> None:
    monkeypatch.setenv(ENV, entry)
    assert url_safety._trusted_proxies() == (expected,)


def test_a_bare_ipv6_entry_with_a_port_like_tail_is_one_address(monkeypatch) -> None:
    """Without brackets the last group is part of the address, so ``::1:3128``
    does not trust the proxy on ``[::1]:3128``."""
    monkeypatch.setenv(ENV, "::1:3128")
    assert url_safety._is_trusted_proxy("::1", 3128) is False
    with pytest.raises(url_safety.URLSafetyError, match="Refusing configured HTTP proxy"):
        url_safety._validate_proxy_endpoint("::1", 3128)


@pytest.mark.parametrize("entry", ["[::1]:3128", "::1", "[::1]"])
def test_an_ipv6_loopback_proxy_can_be_trusted(monkeypatch, entry) -> None:
    monkeypatch.setenv(ENV, entry)
    _proxies(monkeypatch, {"https": "http://[::1]:3128"})
    assert url_safety.upstream_http_proxy("https://example.com/") == ("::1", 3128, None)


@pytest.mark.parametrize(
    "entry", ["fe80::1", "[fe80::1]:3128", "[fd00:ec2::254]:3128", "[::ffff:169.254.169.254]:3128", "::"]
)
def test_ipv6_link_local_and_metadata_stay_refused_when_listed(monkeypatch, entry) -> None:
    monkeypatch.setenv(ENV, entry)
    host = url_safety._trusted_proxies()[0][0]
    assert url_safety._is_trusted_proxy(host, 3128) is False
    with pytest.raises(url_safety.URLSafetyError):
        url_safety._validate_proxy_endpoint(host, 3128)


# ---------------------------------------------------------------------------
# Port matching uses the port the connection really uses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "proxy_url,entry,trusted",
    [
        ("http://127.0.0.1", "127.0.0.1:80", True),
        ("http://127.0.0.1", "127.0.0.1:3128", False),
        ("http://127.0.0.1:3128", "127.0.0.1:3128", True),
        ("http://127.0.0.1:3128", "127.0.0.1:80", False),
        ("127.0.0.1:3128", "127.0.0.1:3128", True),  # no scheme: http
        ("http://127.0.0.1:3128", "127.0.0.1", True),
        ("http://LOCALHOST.:3128", "localhost:3128", True),
        ("http://user:pw@127.0.0.1:3128", "127.0.0.1:3128", True),
    ],
)
def test_host_port_entries_match_the_effective_proxy_port(
    monkeypatch, proxy_url, entry, trusted
) -> None:
    monkeypatch.setenv(ENV, entry)
    _proxies(monkeypatch, {"https": proxy_url})
    _dns(monkeypatch, {"localhost": "127.0.0.1"})
    if trusted:
        assert len(url_safety._validated_proxy_hosts("https://example.com/")) == 1
        assert url_safety.upstream_http_proxy("https://example.com/")[0] == "127.0.0.1"
    else:
        for check in (url_safety._validated_proxy_hosts, url_safety.upstream_http_proxy):
            with pytest.raises(url_safety.URLSafetyError, match="Refusing configured HTTP proxy"):
                check("https://example.com/")


def test_both_paths_share_one_verdict(monkeypatch) -> None:
    """The raw HTTP path and the browser guard ask the same function."""
    seen = []
    real = url_safety._resolve_proxy_endpoint

    def spy(host, port):
        seen.append((host, port))
        return real(host, port)

    monkeypatch.setattr(url_safety, "_resolve_proxy_endpoint", spy)
    monkeypatch.setenv(ENV, "127.0.0.1:3128")
    _proxies(monkeypatch, {"https": LOOPBACK_PROXY})
    url_safety._validated_proxy_hosts("https://example.com/")
    url_safety.upstream_http_proxy("https://example.com/")
    assert seen == [("127.0.0.1", 3128), ("127.0.0.1", 3128)]


# ---------------------------------------------------------------------------
# The browser guard's upstream: upstream_http_proxy
# ---------------------------------------------------------------------------


def test_upstream_proxy_unlisted_is_refused_and_the_error_names_the_opt_in(monkeypatch) -> None:
    _proxies(monkeypatch, {"https": LOOPBACK_PROXY})
    with pytest.raises(url_safety.URLSafetyError) as excinfo:
        url_safety.upstream_http_proxy("https://example.com/")
    assert "Refusing configured HTTP proxy" in str(excinfo.value)
    assert f"{ENV} (host:port)" in str(excinfo.value)


@pytest.mark.parametrize(
    "proxy_url", ["http://localhost:3128", "http://10.0.0.5:3128", "http://100.64.0.7:3128"]
)
def test_refusals_an_entry_could_lift_name_the_opt_in(monkeypatch, proxy_url) -> None:
    _proxies(monkeypatch, {"https": proxy_url})
    with pytest.raises(url_safety.URLSafetyError, match=ENV):
        url_safety.upstream_http_proxy("https://example.com/")


@pytest.mark.parametrize(
    "proxy_url",
    [
        "http://169.254.169.254:3128",
        "http://169.254.10.10:3128",
        "http://100.100.100.200:3128",
        "http://metadata.google.internal:3128",
        "http://[fe80::1]:3128",
        "http://0.0.0.0:3128",
    ],
)
def test_refusals_no_entry_can_lift_do_not_suggest_the_opt_in(monkeypatch, proxy_url) -> None:
    """Listed or not, and the message does not send the operator to a variable
    that cannot help."""
    _proxies(monkeypatch, {"https": proxy_url})
    host = url_safety.urlparse(proxy_url).hostname
    for value in (None, f"{host}:3128,[{host}]:3128,{host}"):
        if value is not None:
            monkeypatch.setenv(ENV, value)
        with pytest.raises(url_safety.URLSafetyError) as excinfo:
            url_safety.upstream_http_proxy("https://example.com/")
        assert ENV not in str(excinfo.value)


@pytest.mark.parametrize(
    "proxy_url",
    [
        "socks5://127.0.0.1:1080",
        "socks5h://127.0.0.1:1080",
        "socks4://127.0.0.1:1080",
        "https://127.0.0.1:3129",
    ],
)
def test_socks_and_https_upstreams_stay_refused_for_the_browser_when_listed(
    monkeypatch, proxy_url
) -> None:
    monkeypatch.setenv(ENV, "127.0.0.1,127.0.0.1:1080,127.0.0.1:3129")
    _proxies(monkeypatch, {"https": proxy_url, "http": proxy_url})
    for url in ("https://example.com/", "http://example.com/"):
        with pytest.raises(url_safety.URLSafetyError, match="Only http:// proxies"):
            url_safety.upstream_http_proxy(url)


def test_no_proxy_still_decides_whether_the_upstream_is_used(monkeypatch) -> None:
    monkeypatch.setenv(ENV, "127.0.0.1:3128")
    monkeypatch.setenv("NO_PROXY", "direct.example")
    _proxies(monkeypatch, {"https": LOOPBACK_PROXY})
    assert url_safety.upstream_http_proxy("https://direct.example/") is None
    assert url_safety.upstream_http_proxy("https://example.com/") == ("127.0.0.1", 3128, None)


def test_trusted_upstream_keeps_the_operator_credential(monkeypatch) -> None:
    monkeypatch.setenv(ENV, "127.0.0.1:3128")
    _proxies(monkeypatch, {"https": "http://user:p%40ss@127.0.0.1:3128"})
    assert url_safety.upstream_http_proxy("https://example.com/") == (
        "127.0.0.1",
        3128,
        "Basic dXNlcjpwQHNz",
    )


# ---------------------------------------------------------------------------
# Names: mixed answers and rebinding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answers",
    [
        ["127.0.0.1", "169.254.169.254"],  # loopback and metadata
        ["10.0.0.5", "169.254.7.7"],  # private and link-local
        ["127.0.0.1", "100.100.100.200"],  # loopback and the RFC 6598 metadata address
        ["127.0.0.1", "fe80::1"],  # loopback and IPv6 link-local
        ["127.0.0.1", "fd00:ec2::254"],  # loopback and AWS IMDS IPv6
        ["93.184.216.34", "169.254.169.254"],  # public and metadata
        ["127.0.0.1", "0.0.0.0"],
        ["127.0.0.1", "224.0.0.1"],
    ],
)
def test_one_unreachable_record_refuses_the_whole_trusted_name(monkeypatch, answers) -> None:
    monkeypatch.setenv(ENV, "proxy.sandbox:3128")
    _proxies(monkeypatch, {"https": "http://proxy.sandbox:3128"})
    _dns(monkeypatch, {"proxy.sandbox": answers})
    for check in (url_safety._validated_proxy_hosts, url_safety.upstream_http_proxy):
        with pytest.raises(url_safety.URLSafetyError, match="Refusing trusted HTTP proxy"):
            check("https://example.com/")


def test_a_trusted_name_on_private_and_public_addresses_is_accepted(monkeypatch) -> None:
    """Each address is one the proxy could have without the other: a public
    proxy needs no entry and a private one is what the entry is for. Without
    the entry the same name is refused."""
    _proxies(monkeypatch, {"https": "http://proxy.sandbox:3128"})
    _dns(monkeypatch, {"proxy.sandbox": ["93.184.216.34", "10.0.0.5"]})
    with pytest.raises(url_safety.URLSafetyError, match="non-public IP 10.0.0.5"):
        url_safety.upstream_http_proxy("https://example.com/")
    monkeypatch.setenv(ENV, "proxy.sandbox:3128")
    address, port, _auth = url_safety.upstream_http_proxy("https://example.com/")
    assert (address, port) == ("10.0.0.5", 3128)


def test_the_browser_upstream_is_dialled_at_an_address_the_check_saw(monkeypatch) -> None:
    """Rebinding between check and connect: there is no second lookup to race.
    One call resolves the name once and returns the address to dial."""
    monkeypatch.setenv(ENV, "proxy.sandbox:3128")
    _proxies(monkeypatch, {"https": "http://proxy.sandbox:3128"})
    lookups = _dns(monkeypatch, {"proxy.sandbox": [["127.0.0.1"], ["169.254.169.254"]]})
    assert url_safety.upstream_http_proxy("https://example.com/") == ("127.0.0.1", 3128, None)
    assert lookups == ["proxy.sandbox"]
    # The next request checks again, sees the rebound answer and refuses.
    with pytest.raises(url_safety.URLSafetyError, match="169.254.169.254"):
        url_safety.upstream_http_proxy("https://example.com/")


@pytest.mark.parametrize("rebound", ["169.254.169.254", "100.100.100.200", "fe80::1", "0.0.0.0"])
def test_raw_http_pin_refuses_a_trusted_name_that_rebinds(monkeypatch, rebound) -> None:
    """Validated on loopback, then answers with a metadata address when
    requests resolves it to open the tunnel."""
    monkeypatch.setenv(ENV, "proxy.sandbox:3128")
    _proxies(monkeypatch, {"https": "http://proxy.sandbox:3128"})
    _dns(monkeypatch, {"proxy.sandbox": [["127.0.0.1"], [rebound]]})
    exempt = url_safety._validated_proxy_hosts("https://example.com/")
    assert exempt == frozenset({"proxy.sandbox"})
    with url_safety._pin_dns("example.com", "93.184.216.34", 443, exempt_hosts=exempt):
        with pytest.raises(socket.gaierror, match="after validation"):
            socket.getaddrinfo("proxy.sandbox", 3128)


def test_raw_http_pin_lets_a_trusted_name_move_inside_the_opt_in_ranges(monkeypatch) -> None:
    monkeypatch.setenv(ENV, "proxy.sandbox:3128")
    _proxies(monkeypatch, {"https": "http://proxy.sandbox:3128"})
    _dns(monkeypatch, {"proxy.sandbox": [["127.0.0.1"], ["10.0.0.5"]]})
    exempt = url_safety._validated_proxy_hosts("https://example.com/")
    with url_safety._pin_dns("example.com", "93.184.216.34", 443, exempt_hosts=exempt):
        assert socket.getaddrinfo("proxy.sandbox", 3128)[0][4][0] == "10.0.0.5"


# ---------------------------------------------------------------------------
# The pin: the exemption is the proxy's endpoint, not its address
# ---------------------------------------------------------------------------


def _pinned_behind(monkeypatch, entry: str, proxy_url: str = LOOPBACK_PROXY):
    monkeypatch.setenv(ENV, entry)
    _proxies(monkeypatch, {"https": proxy_url, "http": proxy_url})
    _dns(monkeypatch, {"localhost": "127.0.0.1", "alias.example": "127.0.0.1"})
    exempt = url_safety._validated_proxy_hosts("https://example.com/")
    return url_safety._pin_dns("example.com", "93.184.216.34", 443, exempt_hosts=exempt)


@pytest.mark.parametrize("entry", ["127.0.0.1:3128", "127.0.0.1"])
@pytest.mark.parametrize("port", [22, 80, 443, 3129, 8080, 9200, None, "http", 0])
def test_pin_refuses_every_other_port_on_the_trusted_proxy_address(
    monkeypatch, entry, port
) -> None:
    """A redirect that NO_PROXY sends direct is resolved here. Even a bare
    ``host`` entry reaches the configured proxy port only."""
    with _pinned_behind(monkeypatch, entry):
        assert socket.getaddrinfo("127.0.0.1", 3128)[0][4][0] == "127.0.0.1"
        with pytest.raises(socket.gaierror, match="non-public IP"):
            socket.getaddrinfo("127.0.0.1", port)


def test_pin_refuses_other_names_for_the_trusted_proxy_address(monkeypatch) -> None:
    with _pinned_behind(monkeypatch, "127.0.0.1:3128"):
        for host in ("alias.example", "localhost"):
            with pytest.raises(socket.gaierror, match="non-public IP"):
                socket.getaddrinfo(host, 3128)


def test_pin_stops_trusting_when_the_entry_is_gone(monkeypatch) -> None:
    """The list is read again at connect time, as it is at validation."""
    with _pinned_behind(monkeypatch, "127.0.0.1:3128"):
        monkeypatch.delenv(ENV)
        with pytest.raises(socket.gaierror, match="non-public IP"):
            socket.getaddrinfo("127.0.0.1", 3128)


def test_a_hand_built_exempt_set_cannot_trust_an_unlisted_endpoint(monkeypatch) -> None:
    exempt = url_safety._ExemptProxies({"127.0.0.1"})
    exempt.trusted = frozenset({("127.0.0.1", 3128)})
    _dns(monkeypatch, {})
    with url_safety._pin_dns("example.com", "93.184.216.34", 443, exempt_hosts=exempt):
        with pytest.raises(socket.gaierror, match="non-public IP"):
            socket.getaddrinfo("127.0.0.1", 3128)


def test_a_public_proxy_is_exempt_on_any_port_as_before(monkeypatch) -> None:
    _proxies(monkeypatch, {"https": "http://proxy.corp.example:8080"})
    _dns(monkeypatch, {"proxy.corp.example": "8.8.4.4"})
    exempt = url_safety._validated_proxy_hosts("https://example.com/")
    assert exempt == frozenset({"proxy.corp.example"}) and exempt.trusted == frozenset()
    with url_safety._pin_dns("example.com", "93.184.216.34", 443, exempt_hosts=exempt):
        assert socket.getaddrinfo("proxy.corp.example", 8080)[0][4][0] == "8.8.4.4"
        assert socket.getaddrinfo("proxy.corp.example", 443)[0][4][0] == "8.8.4.4"


# ---------------------------------------------------------------------------
# A trusted proxy never makes a target reachable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target",
    [
        "http://127.0.0.1:3128/",
        "http://127.0.0.1/",
        "http://127.0.0.1:8080/admin",
        "https://localhost:3128/",
        "http://10.0.0.5:3128/",
        "http://[::1]:3128/",
        "http://2130706433:3128/",
        "http://alias.example:3128/",
    ],
)
def test_a_listed_proxy_address_is_not_an_audit_target(monkeypatch, target) -> None:
    monkeypatch.setenv(ENV, "127.0.0.1,127.0.0.1:3128,localhost,10.0.0.5,[::1]:3128,alias.example")
    _dns(monkeypatch, {"localhost": "127.0.0.1", "alias.example": "127.0.0.1"})
    for validator in (
        url_safety.validate_url_strict,
        url_safety.validate_public_url_strict,
        url_safety.validate_public_url_addresses,
    ):
        with pytest.raises(url_safety.URLSafetyError):
            validator(target)
    if "alias.example" not in target:
        assert url_safety.validate_url(target) is False


def test_the_two_lists_stay_separate_in_both_directions(monkeypatch) -> None:
    monkeypatch.setenv(ENV, "127.0.0.1:3128")
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "127.0.0.1:3000")
    _proxies(monkeypatch, {"https": "http://127.0.0.1:3000"})
    # The local target is not a trusted proxy,
    with pytest.raises(url_safety.URLSafetyError, match="Refusing configured HTTP proxy"):
        url_safety.upstream_http_proxy("https://example.com/")
    # and the trusted proxy is not a local target.
    with pytest.raises(url_safety.URLSafetyError):
        url_safety.validate_url_strict("http://127.0.0.1:3128/")
    assert url_safety.validate_url_strict("http://127.0.0.1:3000/")[1] == "127.0.0.1"


class _Wire:
    """Stands in for the network behind ``HTTPAdapter.send``."""

    def __init__(self, script: dict):
        self.script = script
        self.sent: list = []

    def send(self, request, **kwargs):
        proxy = requests.utils.select_proxy(request.url, kwargs.get("proxies") or {})
        self.sent.append((request.url, proxy))
        status, location = self.script.get(request.url, (200, None))
        response = requests.Response()
        response.status_code = status
        response.url = request.url
        response.request = request
        response.raw = io.BytesIO(b"body")
        if location:
            response.headers["Location"] = location
        return response


def _behind_trusted_proxy(monkeypatch, script: dict, *, no_proxy: str = "") -> _Wire:
    monkeypatch.setenv(ENV, "127.0.0.1:3128")
    _proxies(monkeypatch, {"http": LOOPBACK_PROXY, "https": LOOPBACK_PROXY})
    if no_proxy:
        monkeypatch.setenv("NO_PROXY", no_proxy)
    _dns(
        monkeypatch,
        {
            "start.example": "93.184.216.34",
            "public.example": "93.184.216.35",
            "internal.example": "10.0.0.5",
            "localhost": "127.0.0.1",
        },
    )
    wire = _Wire(script)
    monkeypatch.setattr(
        requests.adapters.HTTPAdapter, "send", lambda self, request, **kw: wire.send(request, **kw)
    )
    return wire


def test_a_fetch_goes_through_the_trusted_proxy(monkeypatch) -> None:
    wire = _behind_trusted_proxy(
        monkeypatch, {"http://start.example/": (302, "http://public.example/")}
    )
    assert url_safety.safe_requests_get("http://start.example/", timeout=5).status_code == 200
    assert wire.sent == [
        ("http://start.example/", LOOPBACK_PROXY),
        ("http://public.example/", LOOPBACK_PROXY),
    ]


REDIRECTS = [
    "http://127.0.0.1:3128/",  # the trusted proxy's own endpoint
    "http://127.0.0.1:8080/admin",  # another service on its address
    "http://127.0.0.1/",
    "http://localhost:3128/",
    "http://[::1]:3128/",
    "http://10.0.0.5/",
    "http://internal.example/",
    "http://169.254.169.254/latest/meta-data/",
    "http://2130706433:3128/",
]


@pytest.mark.parametrize("location", REDIRECTS)
def test_a_redirect_through_the_trusted_proxy_must_be_public(monkeypatch, location) -> None:
    wire = _behind_trusted_proxy(monkeypatch, {"http://start.example/": (302, location)})
    with pytest.raises(url_safety.ProxiedRequestRefused):
        url_safety.safe_requests_get("http://start.example/", timeout=5)
    assert wire.sent == [("http://start.example/", LOOPBACK_PROXY)]


@pytest.mark.parametrize("location", ["http://127.0.0.1:3128/", "http://127.0.0.1:3128/x?y=1"])
@pytest.mark.parametrize("helper", ["get", "head", "session"])
def test_a_direct_redirect_to_the_trusted_proxy_itself_is_never_sent(
    monkeypatch, location, helper
) -> None:
    """NO_PROXY=127.0.0.1 is common where the proxy is local. It makes the hop
    direct, and the pin would resolve the proxy's own endpoint for it."""
    wire = _behind_trusted_proxy(
        monkeypatch, {"http://start.example/": (302, location)}, no_proxy="127.0.0.1,localhost"
    )
    with pytest.raises(url_safety.ProxiedRequestRefused):
        if helper == "get":
            url_safety.safe_requests_get("http://start.example/", timeout=5)
        elif helper == "head":
            url_safety.safe_requests_head("http://start.example/", timeout=5, allow_redirects=True)
        else:
            with url_safety.safe_requests_session("http://start.example/") as session:
                session.get("http://start.example/", timeout=5)
    assert wire.sent == [("http://start.example/", LOOPBACK_PROXY)]


def test_a_local_target_on_the_proxy_host_keeps_working(monkeypatch) -> None:
    """The first URL is an allowlisted dev server on the address the trusted
    proxy also lives on. Its own pages stay reachable; the proxy port, which
    is not a local target, does not become one."""
    wire = _behind_trusted_proxy(
        monkeypatch,
        {"http://127.0.0.1:3000/": (302, "http://127.0.0.1:3000/next")},
        no_proxy="127.0.0.1",
    )
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "127.0.0.1:3000")
    assert url_safety.safe_requests_get("http://127.0.0.1:3000/", timeout=5).status_code == 200
    assert [url for url, _proxy in wire.sent] == [
        "http://127.0.0.1:3000/",
        "http://127.0.0.1:3000/next",
    ]
    wire.script = {"http://127.0.0.1:3000/": (302, "http://127.0.0.1:3128/")}
    with pytest.raises(url_safety.ProxiedRequestRefused):
        url_safety.safe_requests_get("http://127.0.0.1:3000/", timeout=5)


def test_nothing_in_a_response_can_add_to_the_list(monkeypatch) -> None:
    """The list is the process environment and nothing else: a hostile
    response cannot name a new proxy or a new entry."""
    wire = _behind_trusted_proxy(monkeypatch, {})
    before = dict(os.environ)
    real_send = wire.send

    def hostile(request, **kwargs):
        response = real_send(request, **kwargs)
        response.headers["Proxy-Authenticate"] = 'Basic realm="10.0.0.5:3128"'
        response.headers["Set-Cookie"] = f"{ENV}=10.0.0.5"
        response.headers["X-Claude-Seo-Trusted-Proxies"] = "10.0.0.5,*"
        return response

    wire.send = hostile
    url_safety.safe_requests_get("http://start.example/", timeout=5)
    assert os.environ.get(ENV) == before.get(ENV) == "127.0.0.1:3128"
    assert url_safety._trusted_proxies() == (("127.0.0.1", 3128),)
    assert url_safety._is_trusted_proxy("10.0.0.5", 3128) is False


# Review round 3: metadata addresses the first list missed, 6to4 wrapping,
# and proxy URLs whose parse errors would echo credentials.
@pytest.mark.parametrize(
    "address",
    ["fd20:ce::254", "fd20:00ce:0:0:0:0:0:254", "192.0.0.192", "::ffff:192.0.0.192",
     "2002:a9fe:a9fe::1", "2002:6464:64c8::"],
)
def test_more_metadata_forms_are_never_allowlistable(address):
    assert not url_safety._is_allowlistable_ip(address)


def test_a_6to4_wrapped_private_address_is_judged_by_the_wrapped_address():
    assert url_safety._is_allowlistable_ip("2002:0a00:0001::1")  # 10.0.0.1


@pytest.mark.parametrize(
    "proxy",
    ["http://puser:S3cretPw-zzQ@127.0.0.1:99999", "http://puser:S3cretPw-zzQ@127.0.0.1:70000"],
)
def test_a_malformed_proxy_url_never_echoes_its_credentials(monkeypatch, proxy):
    _proxies(monkeypatch, {"http": proxy, "https": proxy})
    for call in (lambda: url_safety.upstream_http_proxy("http://example.com/"),
                 lambda: url_safety._proxy_endpoints("http://example.com/")):
        with pytest.raises(url_safety.URLSafetyError) as info:
            call()
        assert "S3cretPw" not in str(info.value) and "puser" not in str(info.value)


def test_an_unknown_proxy_scheme_is_not_echoed(monkeypatch):
    _proxies(monkeypatch, {"http": "puser:pw@127.0.0.1:3128"})
    with pytest.raises(url_safety.URLSafetyError) as info:
        url_safety.upstream_http_proxy("http://example.com/")
    assert "puser" not in str(info.value)
