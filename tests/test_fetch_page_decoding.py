"""Deterministic response decoding for fetch_page.py."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_page  # noqa: E402


class FakeResponse:
    def __init__(self, content: bytes, content_type: str = "") -> None:
        self.content = content
        self.headers = {"Content-Type": content_type} if content_type else {}


def test_no_charset_defaults_to_utf8_with_replacement() -> None:
    response = FakeResponse("Café".encode("utf-8"))
    assert fetch_page._decode_response_content(response) == "Café"


def test_explicit_charset_from_content_type_wins() -> None:
    response = FakeResponse("Café".encode("iso-8859-1"), "text/html; charset=iso-8859-1")
    assert fetch_page._decode_response_content(response) == "Café"


def test_meta_charset_is_used_when_header_has_no_charset() -> None:
    html = '<meta charset="windows-1252"><p>Smart quote: “</p>'.encode("windows-1252")
    response = FakeResponse(html, "text/html")
    assert "Smart quote: “" in fetch_page._decode_response_content(response)


def test_invalid_bytes_are_replaced_not_dropped() -> None:
    response = FakeResponse(b"valid utf8 then invalid: \x8f")
    decoded = fetch_page._decode_response_content(response)
    assert "valid utf8" in decoded
    assert "\ufffd" in decoded
