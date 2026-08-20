"""
Tests for scripts/domain_history.py.

Focus: the WHOIS referral chain in `_socket_whois`. It asks IANA for the
authoritative WHOIS server and then connects to whatever host IANA names. WHOIS
is plaintext on port 43, so anyone able to tamper with that response can inject
a `refer:` line pointing at an internal address and turn the fallback into a
port-43 probe of the operator's private network. The referral is now resolved
and validated through url_safety before being dialled.

No network: socket.create_connection is stubbed throughout.
"""

from __future__ import annotations

import os
import sys

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import domain_history as dh  # noqa: E402


class _FakeSock:
    """Minimal stand-in for a connected socket that yields one payload."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._drained = False
        self.sent = b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def recv(self, _n: int) -> bytes:
        if self._drained:
            return b""
        self._drained = True
        return self._payload


def _stub_chain(monkeypatch, referral_line: bytes, referral_payload: bytes):
    """Stub the IANA hop and the referral hop, recording every dial."""
    attempts: list[tuple] = []

    def fake_connection(address, timeout=None):
        attempts.append(address)
        if address[0] == "whois.iana.org":
            return _FakeSock(referral_line)
        return _FakeSock(referral_payload)

    monkeypatch.setattr(dh.socket, "create_connection", fake_connection)
    return attempts


@pytest.mark.parametrize(
    "hostile",
    [
        b"refer: 169.254.169.254\n",   # cloud metadata endpoint
        b"refer: 127.0.0.1\n",         # loopback
        b"refer: 10.0.0.5\n",          # RFC1918
        b"refer: localhost\n",
    ],
)
def test_hostile_referral_is_never_dialled(monkeypatch, hostile):
    attempts = _stub_chain(monkeypatch, hostile, b"SHOULD NOT BE REACHED\n")
    result = dh._socket_whois("example.com")

    dialled = [host for host, _port in attempts]
    assert dialled == ["whois.iana.org"], f"followed a hostile referral: {dialled}"
    assert "SHOULD NOT BE REACHED" not in (result or "")
    # IANA's own answer is still returned -- a bad referral degrades the
    # lookup, it does not blank it.
    assert "refer:" in (result or "")


def test_legitimate_referral_is_still_followed(monkeypatch):
    """The guard must not break the normal path."""
    attempts = _stub_chain(
        monkeypatch,
        b"refer: whois.verisign-grs.com\n",
        b"Creation Date: 1995-08-14T04:00:00Z\n",
    )
    result = dh._socket_whois("example.com")

    assert len(attempts) == 2, "referral hop did not happen"
    assert "Creation Date" in (result or "")


def test_direct_iana_answer_needs_no_referral(monkeypatch):
    """.arpa and friends come back without a refer: line."""
    attempts = _stub_chain(monkeypatch, b"domain: ARPA\nstatus: ACTIVE\n", b"unused")
    result = dh._socket_whois("in-addr.arpa")

    assert len(attempts) == 1
    assert "ARPA" in (result or "")
