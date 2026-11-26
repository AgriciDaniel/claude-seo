"""WHOIS backends must receive one ASCII IDNA domain, including from the CLI."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import domain_history as dh  # noqa: E402


@pytest.mark.parametrize(("domain", "expected"), [
    ("bücher.example", "xn--bcher-kva.example"),
    ("Bücher.Example.", "xn--bcher-kva.example"),
    ("faß.de", "xn--fa-hia.de"),
    ("例え.テスト", "xn--r8jz45g.xn--zckzah"),
    ("xn--bcher-kva.example", "xn--bcher-kva.example"),
    ("example.com", "example.com"),
])
def test_cli_passes_canonical_domain_to_system_whois(monkeypatch, capsys, domain, expected):
    calls = []
    monkeypatch.setattr(dh.shutil, "which", lambda _: "/fixture/whois")

    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="Creation Date: 2000-01-01\n")

    monkeypatch.setattr(dh.subprocess, "run", run)
    monkeypatch.setattr(sys, "argv", ["domain_history.py", domain, "--json"])
    assert dh.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert calls == [["/fixture/whois", expected]]
    assert report["domain"] == expected
    assert report["created"] == "2000-01-01"
    assert report["whois_source"] == "whois-binary"


def test_unicode_domain_survives_both_socket_hops(monkeypatch):
    sent = []
    connections = []
    monkeypatch.setattr(dh.shutil, "which", lambda _: None)
    monkeypatch.setattr(dh, "validate_url_strict", lambda _: ("unused", "203.0.113.8"))

    class Sock:
        def __init__(self, reply):
            self.reply = reply

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def sendall(self, query):
            sent.append(query)

        def recv(self, _size):
            reply, self.reply = self.reply, b""
            return reply

    def connect(address, timeout):
        connections.append(address)
        return Sock(b"refer: whois.example\n" if len(connections) == 1 else
                    b"Creation Date: 2000-01-01\nRegistrar: Example Registrar\n")

    monkeypatch.setattr(dh.socket, "create_connection", connect)
    report = dh.lookup("bücher.example")
    assert connections == [("whois.iana.org", 43), ("203.0.113.8", 43)]
    assert sent == [b"xn--bcher-kva.example\r\n"] * 2
    assert report["created"] == "2000-01-01"
    assert report["registrar"] == "Example Registrar"
    assert report["whois_source"] == "fallback"


@pytest.mark.parametrize("domain", [
    "example.com\r\nother.example", "--help", "https://example.com/",
    "example.com:43", "example..com", "a" * 64 + ".com", "xn--.com", "",
])
def test_invalid_domain_never_reaches_either_backend(monkeypatch, domain):
    calls = []
    monkeypatch.setattr(dh, "_shell_whois", lambda value: calls.append(value))
    monkeypatch.setattr(dh, "_socket_whois", lambda value: calls.append(value))
    with pytest.raises(ValueError, match="domain"):
        dh.lookup(domain)
    assert calls == []


def test_cli_reports_invalid_domain_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["domain_history.py", "https://example.com", "--json"])
    monkeypatch.setattr(dh, "_shell_whois", lambda _: pytest.fail("invalid WHOIS query"))
    with pytest.raises(SystemExit) as error:
        dh.main()
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "domain" in output.err
    assert "Traceback" not in output.err
