"""fetch_page.py: the wall-clock deadline and the timing fields.

``--timeout`` limits each socket read on its own, so a server that sends one
byte every few seconds was never cut off. The deadline covers the whole
fetch. The slow servers here are real local stubs, reached through the narrow
CLAUDE_SEO_LOCAL_TARGETS allowlist the way ``test_redirect_body_cap.py`` does;
no network is used.
"""

from __future__ import annotations

import gzip
import http.server
import io
import json
import socket
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from urllib3.response import HTTPResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_page  # noqa: E402
import render_page  # noqa: E402
import url_safety  # noqa: E402

DRIP_BYTES = 400
DRIP_INTERVAL = 0.02  # the whole drip takes about 8 seconds if nothing stops it
TIMING_KEYS = ("ttfb_ms", "response_time_ms", "fetch_duration_ms")
CYRILLIC_TEXT = "<html><title>" + "Привет, мир. " * 40 + "</title></html>"
CYRILLIC_BYTES = CYRILLIC_TEXT.encode("windows-1251")


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802 (http.server API)
        if self.path == "/drip":
            self._headers(200, {"Content-Length": str(DRIP_BYTES)})
            self._drip(lambda: self.wfile.write(b"x"))
        elif self.path == "/drip-chunked":
            self._headers(200, {"Transfer-Encoding": "chunked"})
            self._drip(lambda: self.wfile.write(b"1\r\nx\r\n"))
        elif self.path == "/slow-redirect":
            time.sleep(0.2)
            self._headers(302, {"Location": "/slow-final", "Content-Length": "0"})
        elif self.path == "/moved":
            self._headers(302, {"Location": "/plain", "Content-Length": "15"})
            self.wfile.write(b"moved-body-here")
        elif self.path == "/not-modified":
            self._headers(304, {})
        elif self.path == "/cyrillic":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=windows-1251")
            self.send_header("Content-Length", str(len(CYRILLIC_BYTES)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self.wfile.write(CYRILLIC_BYTES)
        elif self.path == "/slow-final":
            time.sleep(0.1)
            self._headers(200, {"Content-Length": "5"})
            time.sleep(0.15)
            self.wfile.write(b"final")
        else:
            self._headers(200, {"Content-Length": "5"})
            self.wfile.write(b"plain")

    def do_HEAD(self):  # noqa: N802 (http.server API)
        self._headers(200, {"Content-Length": "5"})

    def _headers(self, status: int, headers: dict) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Connection", "close")
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.close_connection = True

    def _drip(self, send_one) -> None:
        try:
            for _ in range(DRIP_BYTES):
                if self.server.stop.is_set():
                    return
                send_one()
                time.sleep(DRIP_INTERVAL)
        except OSError:
            pass  # The client hung up, which is the point of the test.

    def log_message(self, *args):
        pass


@pytest.fixture
def server(monkeypatch):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.daemon_threads = True
    httpd.stop = threading.Event()
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", f"127.0.0.1:{port}")
    monkeypatch.setattr(url_safety.requests.utils, "getproxies", lambda: {})
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.stop.set()
        httpd.shutdown()
        httpd.server_close()


# ---------------------------------------------------------------------------
# The deadline against a real slow server
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/drip", "/drip-chunked"])
def test_dripping_body_is_cut_off_at_the_deadline(server, path):
    """One byte every 20 ms never trips the 5 second read timeout. With a
    Content-Length body, a 64 KiB chunked read would also sit through the
    whole drip before the deadline was looked at again."""
    began = time.monotonic()
    result = fetch_page.fetch_page(f"{server}{path}", timeout=5, max_time=0.4)
    took = time.monotonic() - began

    assert took < 4, f"the drip held the fetch for {took:.1f}s"
    assert "0.4 second wall-clock deadline" in result["error"]
    assert result["status_code"] == 200
    assert result["too_large"] is False
    # The partial body is returned, the way the size cap returns its part.
    assert 0 < len(result["content"]) < DRIP_BYTES
    assert set(result["content"]) == {"x"}
    assert result["fetch_duration_ms"] >= 400
    assert result["response_time_ms"] >= 300
    assert result["ttfb_ms"] is not None


def test_fast_page_is_untouched_by_the_deadline(server):
    result = fetch_page.fetch_page(f"{server}/plain", timeout=5)
    assert result["error"] is None
    assert result["content"] == "plain"
    assert result["too_large"] is False


def test_timing_fields_separate_the_final_request_from_the_redirect_hops(server):
    """The stub waits 0.2 s before the redirect, 0.1 s before the final
    headers and 0.15 s before the final body. Only lower bounds are asserted:
    a loaded machine can be slower, never faster."""
    result = fetch_page.fetch_page(f"{server}/slow-redirect", timeout=5)

    assert result["error"] is None
    assert result["content"] == "final"
    assert result["redirect_details"] == [{"url": f"{server}/slow-redirect", "status_code": 302}]
    for key in TIMING_KEYS:
        assert isinstance(result[key], int), key
    # Time to first byte of the final response: its 0.1 s wait, not the hop's.
    assert result["ttfb_ms"] >= 95
    # The final request alone: headers, then the 0.15 s before the body.
    assert result["response_time_ms"] >= result["ttfb_ms"] + 140
    # Every hop: the 0.2 s redirect is in this number and in no other.
    assert result["fetch_duration_ms"] >= result["response_time_ms"] + 190


# ---------------------------------------------------------------------------
# A body that was already read before the deadline reader sees the response
# ---------------------------------------------------------------------------


def test_unfollowed_redirect_keeps_its_body(server):
    """The redirect hook reads a 3xx body into the response and closes the
    socket. --no-redirects must still return that body, as it did before the
    deadline reader replaced read_bounded here."""
    result = fetch_page.fetch_page(f"{server}/moved", timeout=5, follow_redirects=False)
    assert result["error"] is None
    assert result["status_code"] == 302
    assert result["headers"]["Location"] == "/plain"
    assert result["content"] == "moved-body-here"
    assert result["content_bytes"] == 15


@pytest.mark.parametrize(
    "method,path,kwargs,expected",
    [
        # 3xx: the redirect hook has consumed and closed the stream.
        ("get", "/moved", {"allow_redirects": False, "stream": True}, b"moved-body-here"),
        ("get", "/moved", {"allow_redirects": False, "stream": False}, b"moved-body-here"),
        # stream=False: requests has read the body itself.
        ("get", "/plain", {"stream": False}, b"plain"),
        ("get", "/plain", {"stream": True}, b"plain"),
        # No body at all: 304 and HEAD, streamed or not.
        ("get", "/not-modified", {"stream": True}, b""),
        ("get", "/not-modified", {"stream": False}, b""),
        ("head", "/plain", {"stream": True}, b""),
        ("head", "/plain", {"stream": False}, b""),
    ],
)
def test_deadline_reader_returns_what_read_bounded_returns(server, method, path, kwargs, expected):
    def fetch(reader):
        with url_safety.safe_requests_session(f"{server}{path}") as session:
            response = getattr(session, method)(f"{server}{path}", timeout=5, **kwargs)
            try:
                return reader(response)
            finally:
                response.close()

    far = time.monotonic() + 30
    assert fetch(lambda r: url_safety.read_bounded(r, 1000)) == (expected, False)
    assert fetch(lambda r: url_safety.read_bounded_until(r, 1000, far)) == (expected, False, False)


def test_already_read_body_still_honours_the_cap_and_the_deadline(server):
    with url_safety.safe_requests_session(f"{server}/moved") as session:
        response = session.get(f"{server}/moved", timeout=5, allow_redirects=False, stream=True)
        assert url_safety.read_bounded_until(response, 5, time.monotonic() + 30) == (b"", True, False)
        assert url_safety.read_bounded_until(response, 1000, time.monotonic() - 1) == (b"", False, True)


# ---------------------------------------------------------------------------
# content_bytes: the size of the body as bytes, not of the decoded text
# ---------------------------------------------------------------------------


def test_content_bytes_counts_the_body_not_its_utf8_re_encoding(server):
    """A windows-1251 page is one byte per Cyrillic letter. Measuring the
    decoded text as UTF-8 nearly doubles it."""
    result = fetch_page.fetch_page(f"{server}/cyrillic", timeout=5)
    assert result["error"] is None
    assert result["content"] == CYRILLIC_TEXT
    assert result["content_bytes"] == len(CYRILLIC_BYTES)
    assert len(result["content"].encode("utf-8")) > 1.5 * result["content_bytes"]


def test_content_bytes_is_counted_after_decompression(monkeypatch):
    body = CYRILLIC_BYTES * 20
    page = _streamed_response(body, gzipped=True, headers={"Content-Type": "text/html; charset=windows-1251"})
    result = _patched_fetch(monkeypatch, page)
    assert result["content"] == CYRILLIC_TEXT * 20
    assert result["content_bytes"] == len(body)


def test_content_bytes_counts_the_part_read_when_the_body_is_cut(monkeypatch):
    capped = _patched_fetch(monkeypatch, _streamed_response(b"A" * 300_000), max_bytes=100_000)
    assert capped["too_large"] is True
    assert capped["content_bytes"] == len(capped["content"]) <= 100_000

    unread = _patched_fetch(monkeypatch, _streamed_response(b"<html></html>"), max_time=1e-9)
    assert "wall-clock deadline" in unread["error"]
    assert unread["content_bytes"] == 0


def test_content_bytes_is_none_when_no_body_was_read(monkeypatch):
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)
    assert fetch_page.fetch_page("http://127.0.0.1:1/")["content_bytes"] is None
    stalled = _streamed_response(b"", fp=_TimingOutBody())
    assert _patched_fetch(monkeypatch, stalled)["content_bytes"] is None


# ---------------------------------------------------------------------------
# read_bounded_until, with a clock the test controls
# ---------------------------------------------------------------------------


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


def _ticking_response(clock: _Clock, chunks: list, calls: list | None = None):
    """A response double whose every chunk takes one second to arrive."""
    def iter_content(chunk_size=None):
        if calls is not None:
            calls.append(chunk_size)
        for chunk in chunks:
            clock.now += 1.0
            yield chunk

    return SimpleNamespace(raw=None, iter_content=iter_content)


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr(url_safety, "time", fake)
    return fake


def test_read_stops_at_the_deadline_and_keeps_what_arrived(clock):
    response = _ticking_response(clock, [b"ab"] * 10)
    assert url_safety.read_bounded_until(response, 1000, 3.0) == (b"ababab", False, True)


def test_read_past_the_deadline_never_starts(clock):
    calls: list = []
    clock.now = 5.0
    response = _ticking_response(clock, [b"ab"], calls)
    assert url_safety.read_bounded_until(response, 1000, 5.0) == (b"", False, True)
    assert calls == []


def test_complete_body_inside_the_deadline_is_not_flagged(clock):
    response = _ticking_response(clock, [b"ab", b"", b"cd"])
    assert url_safety.read_bounded_until(response, 1000, 60.0) == (b"abcd", False, False)


def test_size_cap_still_wins_when_it_is_hit_first(clock):
    response = _ticking_response(clock, [b"ab"] * 10)
    assert url_safety.read_bounded_until(response, 3, 60.0) == (b"ab", True, False)


def test_read_bounded_keeps_its_two_value_contract_and_has_no_deadline(clock):
    response = _ticking_response(clock, [b"ab"] * 10)
    clock.now = 10_000.0
    assert url_safety.read_bounded(response, 1000) == (b"ab" * 10, False)


def _streamed_response(body: bytes, *, gzipped: bool = False, headers: dict | None = None,
                       fp=None) -> requests.Response:
    """A streamed requests.Response built the way the HTTP adapter builds one."""
    all_headers = {"Content-Type": "text/html; charset=utf-8", **(headers or {})}
    payload = body
    if gzipped:
        payload = gzip.compress(body)
        all_headers["Content-Encoding"] = "gzip"
    raw = HTTPResponse(
        body=fp or io.BytesIO(payload), headers=all_headers, status=200, preload_content=False
    )
    resp = requests.Response()
    resp.status_code = 200
    resp.headers.update(all_headers)
    resp.raw = raw
    resp.url = "https://example.com/"
    return resp


def test_deadline_read_still_counts_decompressed_bytes():
    far = time.monotonic() + 60
    bomb = _streamed_response(b"A" * (8 * 1024 * 1024), gzipped=True)
    raw, too_large, timed_out = url_safety.read_bounded_until(bomb, 1024 * 1024, far)
    assert too_large is True and timed_out is False
    assert 0 < len(raw) <= 1024 * 1024

    page = _streamed_response(b"B" * 300_000, gzipped=True)
    assert url_safety.read_bounded_until(page, 1024 * 1024, far) == (b"B" * 300_000, False, False)


class _TimingOutBody(io.BytesIO):
    def read1(self, *args):
        raise socket.timeout("timed out")

    read = read1


def test_deadline_read_raises_the_same_requests_errors_as_iter_content():
    """fetch_page catches requests exceptions only, so a urllib3 error from
    the direct read must not escape as itself."""
    far = time.monotonic() + 60
    stalled = _streamed_response(b"", fp=_TimingOutBody())
    with pytest.raises(requests.exceptions.ConnectionError, match="Read timed out"):
        url_safety.read_bounded_until(stalled, 1000, far)

    short = _streamed_response(b"abc", headers={"Content-Length": "10"})
    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        url_safety.read_bounded_until(short, 1000, far)

    garbage = _streamed_response(b"not gzip", headers={"Content-Encoding": "gzip"})
    with pytest.raises(requests.exceptions.ContentDecodingError):
        url_safety.read_bounded_until(garbage, 1000, far)


# ---------------------------------------------------------------------------
# fetch_page(): budget, result keys, error paths
# ---------------------------------------------------------------------------


def _patched_fetch(monkeypatch, response: requests.Response, **kwargs) -> dict:
    class _Session:
        max_redirects = 5

        def get(self, url, **kw):
            return response

    @contextmanager
    def fake_session(_url):
        yield _Session()

    monkeypatch.setattr(fetch_page, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(fetch_page, "safe_requests_session", fake_session)
    return fetch_page.fetch_page("https://example.com/", **kwargs)


@pytest.mark.parametrize(
    "timeout,expected", [(30, 60.0), (10, 60.0), (1, 60.0), (45, 90.0), (120, 240.0)]
)
def test_default_budget_is_twice_the_timeout_and_at_least_a_minute(timeout, expected):
    assert fetch_page._default_max_time(timeout) == expected


def test_budget_spent_before_the_body_leaves_the_body_unread(monkeypatch):
    """Redirect hops count: if they used the budget, the body is not started."""
    page = _streamed_response(b"<html>never read</html>")
    result = _patched_fetch(monkeypatch, page, max_time=1e-9)
    assert "wall-clock deadline" in result["error"]
    assert result["content"] == ""
    assert result["status_code"] == 200
    assert page.raw.tell() == 0


def test_default_budget_is_used_when_none_is_given(monkeypatch):
    seen: list = []

    def tiny(timeout):
        seen.append(timeout)
        return 1e-9

    monkeypatch.setattr(fetch_page, "_default_max_time", tiny)
    result = _patched_fetch(monkeypatch, _streamed_response(b"<html></html>"), timeout=17)
    assert seen == [17]
    assert "wall-clock deadline" in result["error"]


def test_result_carries_integer_timings_on_success(monkeypatch):
    result = _patched_fetch(monkeypatch, _streamed_response(b"<html>ok</html>"))
    assert result["error"] is None
    assert result["content"] == "<html>ok</html>"
    for key in TIMING_KEYS:
        assert isinstance(result[key], int) and result[key] >= 0, key


def test_refused_url_reports_only_the_total(monkeypatch):
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)
    result = fetch_page.fetch_page("http://127.0.0.1:1/")
    assert result["error"].startswith("url_safety:")
    assert result["ttfb_ms"] is None
    assert result["response_time_ms"] is None
    assert isinstance(result["fetch_duration_ms"], int)


def test_read_error_reports_only_the_total(monkeypatch):
    stalled = _streamed_response(b"", fp=_TimingOutBody())
    result = _patched_fetch(monkeypatch, stalled)
    assert result["error"].startswith("Connection error:")
    assert result["ttfb_ms"] is None
    assert isinstance(result["fetch_duration_ms"], int)


def test_timing_is_labelled_as_a_local_measurement():
    for doc in (fetch_page.__doc__, fetch_page.fetch_page.__doc__):
        assert "from this machine" in doc
        assert "not Core Web Vitals" in " ".join(doc.split())
        assert "field metric" in doc


# ---------------------------------------------------------------------------
# CLI: --max-time and the JSON keys
# ---------------------------------------------------------------------------

_RAW = {
    "url": "https://example.com/",
    "status_code": 200,
    "content": "<p>partial",
    "headers": {},
    "redirect_chain": [],
    "redirect_details": [],
    "too_large": False,
    "error": None,
    "ttfb_ms": 120,
    "response_time_ms": 340,
    "fetch_duration_ms": 910,
    "content_bytes": 10,
}


def _run_cli(monkeypatch, capsys, argv: list, result: dict):
    seen: dict = {}

    def fake_fetch(*args, **kwargs):
        seen.update(kwargs)
        return dict(result)

    monkeypatch.setattr(fetch_page, "fetch_page", fake_fetch)
    monkeypatch.setattr(sys, "argv", ["fetch_page.py", "https://example.com", *argv])
    code = 0
    try:
        fetch_page.main()
    except SystemExit as exc:
        code = exc.code
    return code, seen, capsys.readouterr()


def test_cli_passes_max_time_through(monkeypatch, capsys):
    _code, seen, _out = _run_cli(monkeypatch, capsys, ["--max-time", "7.5"], _RAW)
    assert seen["max_time"] == 7.5
    _code, seen, _out = _run_cli(monkeypatch, capsys, [], _RAW)
    assert seen["max_time"] is None  # fetch_page() then applies the default


@pytest.mark.parametrize("value", ["0", "-5", "nan", "inf", "soon"])
def test_cli_rejects_a_budget_that_is_not_a_positive_number(monkeypatch, capsys, value):
    code, seen, captured = _run_cli(monkeypatch, capsys, ["--max-time", value], _RAW)
    assert code == 2
    assert seen == {}
    assert "--max-time" in captured.err


def test_cli_json_reports_the_timings_of_a_raw_fetch(monkeypatch, capsys):
    code, _seen, captured = _run_cli(monkeypatch, capsys, ["--json"], _RAW)
    payload = json.loads(captured.out)
    assert code == 0
    assert {key: payload[key] for key in TIMING_KEYS} == {
        "ttfb_ms": 120,
        "response_time_ms": 340,
        "fetch_duration_ms": 910,
    }


def test_cli_json_reports_content_bytes_of_a_raw_fetch(monkeypatch, capsys):
    code, _seen, captured = _run_cli(monkeypatch, capsys, ["--json"], _RAW)
    assert code == 0
    assert json.loads(captured.out)["content_bytes"] == 10


def test_cli_json_keeps_one_key_set_for_a_rendered_fetch(monkeypatch, capsys):
    """A rendered result has render_ms instead; the raw timings are null."""
    rendered = {
        "url": "https://example.com/", "status_code": 200, "content": "<p>x</p>",
        "raw_content": "<p>x</p>", "render_ms": 12.5, "mode_used": "rendered", "error": None,
    }
    monkeypatch.setattr(render_page, "render_page", lambda *a, **kw: dict(rendered))
    monkeypatch.setattr(
        sys, "argv", ["fetch_page.py", "https://example.com", "--render", "always", "--json"]
    )
    with pytest.raises(SystemExit) as exc:
        fetch_page.main()
    payload = json.loads(capsys.readouterr().out)
    assert exc.value.code == 0
    assert {key: payload[key] for key in TIMING_KEYS} == dict.fromkeys(TIMING_KEYS)
    assert payload["content_bytes"] is None
    assert payload["render_ms"] == 12.5


def test_cli_deadline_is_an_error_that_keeps_the_partial_content(monkeypatch, capsys, tmp_path):
    cut = dict(_RAW, error="Fetch exceeded the 5 second wall-clock deadline; "
                           "content holds the part read before it")
    output = tmp_path / "page.html"
    code, _seen, captured = _run_cli(
        monkeypatch, capsys, ["--json", "--output", str(output)], cut
    )
    payload = json.loads(captured.out)
    assert code == 1
    assert "wall-clock deadline" in payload["error"]
    assert payload["content"] == "<p>partial"
    # A cut-off page is never saved as if it were the page.
    assert payload["output_written"] is False
    assert not output.exists()
