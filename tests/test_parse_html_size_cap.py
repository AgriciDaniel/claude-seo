"""parse_html --url reads the page body under a cap (GHSA-f8h8-fv8r-g2wh).

With no file and an empty stdin, --url fetches the page. That read used to go
through ``response.content``, which buffers the whole body however large it
is. It is now streamed and stops at MAX_PAGE_BYTES, as in render_page.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("bs4")
pytest.importorskip("requests")
import parse_html  # noqa: E402

CAP = 256 * 1024
CHUNK = 64 * 1024
HEAD = b"<html><head><title>Bounded</title></head><body><h1>Hello</h1>"


class _EndlessResponse:
    """A streamed response whose body never ends on its own."""

    url = "https://example.com/final"
    status_code = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}
    history = []
    encoding = "utf-8"

    def __init__(self, limit: int = 64 * 1024 * 1024) -> None:
        self.sent = 0
        self.closed = False
        self._limit = limit

    def iter_content(self, chunk_size=None):
        yield HEAD
        self.sent += len(HEAD)
        while self.sent < self._limit:
            self.sent += CHUNK
            yield b"a" * CHUNK

    @property
    def content(self):
        raise AssertionError("the whole body was read without a cap (.content)")

    @property
    def text(self):
        raise AssertionError("the whole body was read without a cap (.text)")

    def close(self) -> None:
        self.closed = True


def _run(monkeypatch, response, argv):
    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return response

    monkeypatch.setattr(parse_html, "safe_requests_get", fake_get)
    monkeypatch.setattr(parse_html, "MAX_PAGE_BYTES", CAP)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    monkeypatch.setattr(sys, "argv", ["parse_html.py", *argv])
    parse_html.main()
    return calls


def test_url_fetch_stops_at_the_cap(monkeypatch, capsys) -> None:
    response = _EndlessResponse()
    calls = _run(monkeypatch, response, ["--url", "https://example.com/", "--json"])
    captured = capsys.readouterr()

    assert calls[0]["stream"] is True
    # Only the chunk that crossed the cap was read past it, not the full body.
    assert response.sent <= CAP + CHUNK + len(HEAD)
    assert response.closed is True
    result = json.loads(captured.out)
    assert result["title"] == "Bounded"
    assert result["h1"] == ["Hello"]
    assert "exceeded" in captured.err


def test_small_page_is_parsed_whole_without_a_warning(monkeypatch, capsys) -> None:
    response = _EndlessResponse(limit=len(HEAD) + CHUNK)
    _run(monkeypatch, response, ["--url", "https://example.com/", "--json"])
    captured = capsys.readouterr()
    assert json.loads(captured.out)["title"] == "Bounded"
    assert captured.err == ""
    assert response.closed is True
