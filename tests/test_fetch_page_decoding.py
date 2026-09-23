"""Deterministic response decoding for fetch_page.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

pytest.importorskip("requests")
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


def _real_response(body: bytes, content_type: str):
    """A requests.Response built the way the HTTP adapter builds one."""
    import io

    import requests

    resp = requests.Response()
    resp.status_code = 200
    resp.headers["Content-Type"] = content_type
    resp.raw = io.BytesIO(body)
    resp.encoding = requests.utils.get_encoding_from_headers(resp.headers)
    return resp


def test_issue_314_bare_text_html_utf8_is_not_decoded_as_latin1():
    from url_safety import decode_response_text

    body = "<html><head><title>Spécialité</title></head></html>".encode()
    assert "SpÃ©cialitÃ©" in _real_response(body, "text/html").text  # the bug
    assert "Spécialité" in decode_response_text(_real_response(body, "text/html"))


def test_issue_314_explicit_charset_is_still_honoured():
    from url_safety import decode_response_text

    body = "Café".encode("iso-8859-1")
    assert decode_response_text(_real_response(body, "text/html; charset=iso-8859-1")) == "Café"


def test_issue_314_fetching_scripts_use_the_shared_decoder():
    """Scripts that fetch pages must not fall back to response.text."""
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    for name in ("render_page.py", "parse_html.py", "nlp_analyze.py", "preload_check.py",
                 "parasite_risk.py", "ucp_check.py", "gbp_deprecation_lint.py"):
        text = (scripts / name).read_text(encoding="utf-8")
        assert "decode_response_text(" in text, name
        assert "resp.text" not in text, name
