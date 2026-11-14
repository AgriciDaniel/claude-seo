"""parse_html --url must not wait on a stdin nobody writes to (issue #459).

``main()`` used to call ``sys.stdin.read()`` before it looked at ``--url``.
When stdin is open but silent (a socket in the Claude desktop app, a
terminal) that read never returns. With ``--url`` and no file, stdin is now
read only when it is a pipe or a regular file; anything else goes straight
to the fetch. A positional argument that looks like a URL gets an error that
names ``--url``.
"""

from __future__ import annotations

import io
import json
import os
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("bs4")
pytest.importorskip("requests")
import parse_html  # noqa: E402

FETCHED = b"<html><head><title>Fetched</title></head><body><h1>Hi</h1></body></html>"
PIPED = "<html><head><title>Piped</title></head><body><h1>Hi</h1></body></html>"


class _Response:
    url = "https://example.com/final"
    status_code = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}
    history = []
    encoding = "utf-8"

    def iter_content(self, chunk_size=None):
        yield FETCHED

    def close(self) -> None:
        pass


class _FdStdin:
    """Stands in for sys.stdin on top of a real descriptor."""

    def __init__(self, fd: int, readable: bool = True) -> None:
        self._fd = fd
        self._readable = readable

    def fileno(self) -> int:
        return self._fd

    def read(self) -> str:
        if not self._readable:
            raise AssertionError("stdin was read although nothing can arrive on it")
        chunks = []
        while True:
            chunk = os.read(self._fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks).decode("utf-8")


def _run(monkeypatch, capsys, stdin, argv):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return _Response()

    monkeypatch.setattr(parse_html, "safe_requests_get", fake_get)
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "argv", ["parse_html.py", *argv])
    parse_html.main()
    return calls, json.loads(capsys.readouterr().out)


def test_open_but_silent_socket_stdin_goes_to_the_fetch(monkeypatch, capsys) -> None:
    ours, theirs = socket.socketpair()
    try:
        # The peer stays open and never writes: a read would block forever.
        calls, result = _run(
            monkeypatch,
            capsys,
            _FdStdin(ours.fileno(), readable=False),
            ["--url", "https://example.com/", "--json"],
        )
    finally:
        ours.close()
        theirs.close()
    assert calls == ["https://example.com/"]
    assert result["title"] == "Fetched"


def test_piped_html_is_still_read_with_url_as_base(monkeypatch, capsys) -> None:
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, PIPED.encode("utf-8"))
        os.close(write_fd)
        calls, result = _run(
            monkeypatch,
            capsys,
            _FdStdin(read_fd),
            ["--url", "https://example.com/", "--json"],
        )
    finally:
        os.close(read_fd)
    assert calls == []
    assert result["title"] == "Piped"


def test_regular_file_stdin_is_read(monkeypatch, capsys, tmp_path) -> None:
    page = tmp_path / "page.html"
    page.write_text(PIPED, encoding="utf-8")
    fd = os.open(page, os.O_RDONLY)
    try:
        calls, result = _run(
            monkeypatch, capsys, _FdStdin(fd), ["--url", "https://example.com/", "--json"]
        )
    finally:
        os.close(fd)
    assert calls == []
    assert result["title"] == "Piped"


def test_empty_closed_pipe_falls_through_to_the_fetch(monkeypatch, capsys) -> None:
    read_fd, write_fd = os.pipe()
    os.close(write_fd)
    try:
        calls, result = _run(
            monkeypatch, capsys, _FdStdin(read_fd), ["--url", "https://example.com/", "--json"]
        )
    finally:
        os.close(read_fd)
    assert calls == ["https://example.com/"]
    assert result["title"] == "Fetched"


def test_devnull_stdin_falls_through_to_the_fetch(monkeypatch, capsys) -> None:
    fd = os.open(os.devnull, os.O_RDONLY)
    try:
        calls, result = _run(
            monkeypatch,
            capsys,
            _FdStdin(fd, readable=False),
            ["--url", "https://example.com/", "--json"],
        )
    finally:
        os.close(fd)
    assert calls == ["https://example.com/"]
    assert result["title"] == "Fetched"


def test_stdin_without_a_descriptor_is_read(monkeypatch, capsys) -> None:
    calls, result = _run(
        monkeypatch, capsys, io.StringIO(PIPED), ["--url", "https://example.com/", "--json"]
    )
    assert calls == []
    assert result["title"] == "Piped"


def test_missing_stdin_goes_to_the_fetch(monkeypatch, capsys) -> None:
    calls, result = _run(
        monkeypatch, capsys, None, ["--url", "https://example.com/", "--json"]
    )
    assert calls == ["https://example.com/"]
    assert result["title"] == "Fetched"


def test_positional_url_error_names_the_url_flag(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["parse_html.py", "https://example.com/page"])
    with pytest.raises(SystemExit) as exc:
        parse_html.main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "--url" in err
    assert "https://example.com/page" in err


def test_missing_file_error_is_unchanged(monkeypatch, capsys, tmp_path) -> None:
    missing = str(tmp_path / "nope.html")
    monkeypatch.setattr(sys, "argv", ["parse_html.py", missing])
    with pytest.raises(SystemExit):
        parse_html.main()
    err = capsys.readouterr().err
    assert "File not found" in err
    assert "--url" not in err


def test_shipped_instructions_never_pass_the_url_positionally() -> None:
    root = Path(__file__).resolve().parents[1]
    bad = []
    for folder in ("skills", "agents", "extensions"):
        for path in sorted((root / folder).rglob("*.md")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for call in line.split("parse_html.py")[1:]:
                    first = call.strip().split(" ")[0].strip("`\"'").lower()
                    if first.startswith(("<url", "http://", "https://")):
                        bad.append(f"{path.relative_to(root)}:{number}")
    assert not bad, f"parse_html.py takes the URL with --url, not positionally: {bad}"
