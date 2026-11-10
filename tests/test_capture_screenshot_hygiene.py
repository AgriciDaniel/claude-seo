"""capture_screenshot.py full-page hygiene: scroll-through, settle, --hide-overlays.

Playwright is mocked the way tests/test_render_page.py does it: a fake page
records every call in order, and the context is built by the real
url_safety.new_guarded_context, so the tests also prove the guards are still
installed. No browser and no network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("playwright")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import capture_screenshot as cs  # noqa: E402
import url_safety  # noqa: E402

URL = "https://site.example/"


class FakePage:
    """Records calls in order; answers the hygiene snippets like a page would."""

    def __init__(self, *, height=5000, step=1000, pending=(), overlays=3, top_lag=(), fail=None):
        self.height = height
        self.step = step
        self.pending = list(pending)  # successive _JS_PENDING answers; last one repeats
        self.overlays = overlays
        self.top_lag = list(top_lag)  # scrollY values reported before the page is at 0
        self.fail = fail  # snippet whose evaluation raises
        self.calls: list[tuple] = []
        self.routes: list[tuple] = []

    def route(self, pattern, handler):
        self.routes.append((pattern, handler))

    def goto(self, url, **kwargs):
        self.calls.append(("goto", url, kwargs))

    def wait_for_timeout(self, ms):
        self.calls.append(("wait", ms))

    def screenshot(self, **kwargs):
        self.calls.append(("screenshot", kwargs))

    def evaluate(self, snippet, arg=None):
        name = {
            cs._JS_SCROLL_PREPARE: "prepare",
            cs._JS_SCROLL_TO: "scroll_to",
            cs._JS_PENDING: "pending",
            cs._JS_HIDE_OVERLAYS: "hide_overlays",
        }[snippet]
        self.calls.append((name, arg))
        if self.fail == name:
            raise RuntimeError("Execution context was destroyed\nstack line")
        if name == "prepare":
            return {"height": self.height, "step": self.step}
        if name == "scroll_to":
            if arg == 0 and self.top_lag:
                return self.top_lag.pop(0)
            return arg
        if name == "pending":
            if len(self.pending) > 1:
                return self.pending.pop(0)
            return self.pending[0] if self.pending else {"animations": 0, "images": 0}
        return self.overlays

    def names(self) -> list[str]:
        return [call[0] for call in self.calls]

    def waited(self) -> int:
        return sum(call[1] for call in self.calls if call[0] == "wait")


class FakeManager:
    def __init__(self, page):
        page.context_kwargs = None
        page.context_routes = []
        page.context_ws_routes = []
        context = SimpleNamespace(
            new_page=lambda: page,
            route=lambda pattern, handler: page.context_routes.append((pattern, handler)),
            route_web_socket=lambda pattern, handler: page.context_ws_routes.append(
                (pattern, handler)
            ),
        )

        def new_context(**kwargs):
            page.context_kwargs = kwargs
            return context

        browser = SimpleNamespace(new_context=new_context, close=lambda: None)
        self.playwright = SimpleNamespace(
            chromium=SimpleNamespace(launch=lambda **_kwargs: browser)
        )

    def __enter__(self):
        return self.playwright

    def __exit__(self, *_args):
        return False


def _capture(monkeypatch, page, **kwargs):
    monkeypatch.setattr(cs, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(cs, "sync_playwright", lambda: FakeManager(page))
    return cs.capture_screenshot(URL, "/out/shot.png", **kwargs)


# ---------------------------------------------------------------------------
# Defaults: who gets the new steps and who does not
# ---------------------------------------------------------------------------


def test_viewport_capture_is_unchanged(monkeypatch) -> None:
    page = FakePage()
    result = _capture(monkeypatch, page)
    assert result["success"] is True
    # Same call sequence as before: no snippet runs for a viewport capture.
    assert page.calls == [
        ("goto", URL, {"wait_until": "networkidle", "timeout": 30000}),
        ("wait", 1000),
        ("screenshot", {"path": "/out/shot.png", "full_page": False}),
    ]
    assert result["full_page"] is False
    assert result["scroll_through"] is None
    assert result["settle"] is None
    assert result["hide_overlays"] is False
    assert result["overlays_hidden"] is None


def test_full_page_capture_scrolls_returns_to_top_then_settles(monkeypatch) -> None:
    page = FakePage(height=5000, step=1000)
    result = _capture(monkeypatch, page, full_page=True)
    assert result["success"] is True
    assert result["scroll_through"] == {"steps": 4, "capped": False, "returned_to_top": True}
    assert result["settle"] == {"waited_ms": 0, "animations_pending": 0, "images_pending": 0}
    scrolls = [call[1] for call in page.calls if call[0] == "scroll_to"]
    assert scrolls == [1000, 2000, 3000, 4000, 0]
    # Order: load, scroll down, back to the top, settle, and only then the picture.
    names = page.names()
    assert names[:2] == ["goto", "wait"]
    assert names.index("prepare") < names.index("scroll_to") < names.index("pending")
    assert names[-1] == "screenshot"
    assert page.calls[-1] == ("screenshot", {"path": "/out/shot.png", "full_page": True})
    # Overlays stay: hiding them is opt-in.
    assert "hide_overlays" not in names
    assert result["hide_overlays"] is False
    assert result["overlays_hidden"] is None


def test_no_scroll_flag_skips_the_scroll_but_still_settles(monkeypatch) -> None:
    # Images below the fold never load without the scroll, so they are not waited for.
    page = FakePage(pending=[{"animations": 0, "images": 7}])
    result = _capture(monkeypatch, page, full_page=True, scroll_through=False)
    assert result["scroll_through"] is None
    assert result["settle"] == {"waited_ms": 0, "animations_pending": 0, "images_pending": 0}
    assert "prepare" not in page.names() and "scroll_to" not in page.names()
    assert page.names()[-1] == "screenshot"


def test_page_shorter_than_the_viewport_adds_no_wait(monkeypatch) -> None:
    page = FakePage(height=700, step=1080)
    result = _capture(monkeypatch, page, full_page=True)
    assert result["scroll_through"] == {"steps": 0, "capped": False, "returned_to_top": True}
    assert page.waited() == 1000  # only the wait that was always there


# ---------------------------------------------------------------------------
# Bounds: an endless or slow page cannot hang the capture
# ---------------------------------------------------------------------------


def test_scroll_steps_are_capped_on_an_endless_page(monkeypatch) -> None:
    page = FakePage(height=10**9, step=1000)
    result = _capture(monkeypatch, page, full_page=True)
    assert result["scroll_through"] == {
        "steps": cs.SCROLL_MAX_STEPS, "capped": True, "returned_to_top": True,
    }
    assert result["success"] is True
    assert page.names()[-1] == "screenshot"
    # Worst case added by the scroll: the steps plus the rest at the top.
    assert page.waited() - 1000 == cs.SCROLL_MAX_STEPS * cs.SCROLL_PAUSE_MS + cs.SCROLL_REST_MS


def test_height_is_read_once_so_a_growing_page_cannot_extend_the_scroll() -> None:
    page = FakePage(height=3000, step=1000)
    original = page.evaluate

    def growing(snippet, arg=None):
        answer = original(snippet, arg)
        page.height += 5000  # infinite scroll: the page is taller after every call
        return answer

    page.evaluate = growing
    info = cs._scroll_through(page)
    assert info == {"steps": 2, "capped": False, "returned_to_top": True}
    assert page.names().count("prepare") == 1


def test_scroll_stops_at_the_time_budget() -> None:
    page = FakePage(height=10**9, step=1000)
    ticks = iter(range(0, 1000, 2))  # the fake clock advances 2 s per reading
    info = cs._scroll_through(page, clock=lambda: float(next(ticks)))
    # Budget is SCROLL_MAX_MS (6 s): readings at 2 s and 4 s pass, 6 s stops it.
    assert info == {"steps": 2, "capped": True, "returned_to_top": True}


def test_return_to_top_retries_are_bounded() -> None:
    page = FakePage(height=3000, step=1000, top_lag=[900, 300])
    info = cs._scroll_through(page)
    assert info["returned_to_top"] is True
    assert [call[1] for call in page.calls if call[0] == "scroll_to"][-3:] == [0, 0, 0]

    stuck = FakePage(height=3000, step=1000, top_lag=[500] * 100)
    info = cs._scroll_through(stuck)
    assert info["returned_to_top"] is False
    top_tries = [call for call in stuck.calls if call == ("scroll_to", 0)]
    assert len(top_tries) == cs.SCROLL_TOP_RETRIES


def test_settle_waits_for_animations_and_images_then_stops() -> None:
    page = FakePage(pending=[
        {"animations": 2, "images": 3},
        {"animations": 0, "images": 1},
        {"animations": 0, "images": 0},
    ])
    info = cs._settle(page, wait_images=True)
    assert info == {
        "waited_ms": 2 * cs.SETTLE_POLL_MS, "animations_pending": 0, "images_pending": 0,
    }


def test_settle_is_bounded_and_reports_what_was_still_pending() -> None:
    page = FakePage(pending=[{"animations": 4, "images": 9}])
    info = cs._settle(page, wait_images=True)
    assert info == {
        "waited_ms": cs.SETTLE_MAX_MS, "animations_pending": 4, "images_pending": 9,
    }
    assert page.waited() == cs.SETTLE_MAX_MS


def test_worst_case_added_time_stays_under_nine_seconds() -> None:
    worst_ms = (
        cs.SCROLL_MAX_MS + cs.SCROLL_PAUSE_MS
        + cs.SCROLL_TOP_RETRIES * cs.SCROLL_TOP_PAUSE_MS + cs.SCROLL_REST_MS
        + cs.SETTLE_MAX_MS
    )
    assert worst_ms == 8370
    assert cs.SCROLL_MAX_STEPS * cs.SCROLL_PAUSE_MS <= cs.SCROLL_MAX_MS


def test_hygiene_failure_never_fails_the_capture(monkeypatch) -> None:
    for snippet in ("prepare", "scroll_to", "pending", "hide_overlays"):
        page = FakePage(fail=snippet)
        result = _capture(monkeypatch, page, full_page=True, hide_overlays=True)
        assert result["success"] is True, snippet
        assert result["error"] is None, snippet
        assert page.names()[-1] == "screenshot", snippet
    assert result["overlays_hidden"] == 0
    assert result["hide_overlays_error"] == "RuntimeError: Execution context was destroyed"

    page = FakePage(fail="scroll_to")
    result = _capture(monkeypatch, page, full_page=True)
    assert result["scroll_through"]["error"] == "RuntimeError: Execution context was destroyed"
    assert result["scroll_through"]["returned_to_top"] is False


# ---------------------------------------------------------------------------
# --hide-overlays: opt-in, and said so in the result
# ---------------------------------------------------------------------------


def test_hide_overlays_is_opt_in_and_reported(monkeypatch) -> None:
    page = FakePage(overlays=3)
    result = _capture(monkeypatch, page, full_page=True, hide_overlays=True)
    assert result["hide_overlays"] is True
    assert result["overlays_hidden"] == 3
    names = page.names()
    # After the scroll and settle (overlays can appear on scroll), before the picture.
    assert names.index("pending") < names.index("hide_overlays") < names.index("screenshot")
    assert names.count("hide_overlays") == 1


def test_hide_overlays_also_works_for_a_viewport_capture(monkeypatch) -> None:
    page = FakePage(overlays=1)
    result = _capture(monkeypatch, page, hide_overlays=True)
    assert page.names() == ["goto", "wait", "hide_overlays", "screenshot"]
    assert result["overlays_hidden"] == 1
    assert result["scroll_through"] is None


# ---------------------------------------------------------------------------
# Safety properties are untouched
# ---------------------------------------------------------------------------


def test_guards_are_installed_and_only_one_navigation_happens(monkeypatch) -> None:
    page = FakePage()
    result = _capture(monkeypatch, page, full_page=True, hide_overlays=True)
    assert result["success"] is True
    assert page.context_kwargs["service_workers"] == "block"
    assert [pattern for pattern, _handler in page.context_routes] == ["**/*"]
    assert [pattern for pattern, _handler in page.context_ws_routes] == ["**/*"]
    assert page.context_ws_routes[0][1] is url_safety._never_connect_web_socket
    # The page-level route uses the same guard as the context.
    assert page.routes == [("**/*", page.context_routes[0][1])]
    assert page.names().count("goto") == 1
    # The route guard is installed before the page is loaded.
    assert page.calls[0][0] == "goto"


def test_private_address_is_refused_before_any_browser_starts(monkeypatch) -> None:
    def no_browser():
        raise AssertionError("the browser must not start for a refused URL")

    monkeypatch.setattr(cs, "sync_playwright", no_browser)
    result = cs.capture_screenshot(
        "http://127.0.0.1/", "/out/shot.png", full_page=True, hide_overlays=True
    )
    assert result["success"] is False
    assert result["error"].startswith("url_safety:")


def test_snippets_open_no_request_or_navigation_path() -> None:
    """The page-side code only scrolls, reads state and restyles elements."""
    forbidden = (
        "fetch", "XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource", "import(",
        "location", "open(", "href", "src", "createElement", "innerHTML", "eval(",
        "navigator", "postMessage", "submit", "click", "url(",
    )
    for snippet in (
        cs._JS_SCROLL_PREPARE, cs._JS_SCROLL_TO, cs._JS_PENDING, cs._JS_HIDE_OVERLAYS,
    ):
        for token in forbidden:
            assert token not in snippet, (token, snippet[:40])
        assert "async" not in snippet and "await" not in snippet


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    calls: list[dict] = []
    outcome = {"success": True}

    def fake_capture(url, path, **kwargs):
        calls.append(kwargs)
        return {
            "url": url, "output": path, "viewport": kwargs["viewport"],
            "success": outcome["success"],
            "error": None if outcome["success"] else "boom",
            "hide_overlays": kwargs["hide_overlays"],
            "overlays_hidden": 2 if kwargs["hide_overlays"] else None,
        }

    monkeypatch.setattr(cs, "capture_screenshot", fake_capture)

    def run(*args):
        monkeypatch.setattr(sys, "argv", ["capture_screenshot.py", URL, *args])
        cs.main()
        return calls

    run.outcome = outcome
    return run


def test_cli_defaults_scroll_on_and_overlays_visible(cli, capsys) -> None:
    calls = cli("--full")
    assert calls[0]["full_page"] is True
    assert calls[0]["scroll_through"] is True
    assert calls[0]["hide_overlays"] is False
    out = capsys.readouterr().out
    assert "Capturing desktop screenshot..." in out
    assert "hide-overlays" not in out


def test_cli_flags_reach_the_capture_and_are_announced(cli, capsys) -> None:
    calls = cli("--full", "--no-scroll", "--hide-overlays")
    assert calls[0]["scroll_through"] is False
    assert calls[0]["hide_overlays"] is True
    assert "--hide-overlays: 2 floating element(s) hidden" in capsys.readouterr().out


def test_cli_json_prints_one_document_and_names_the_overlay_flag(cli, capsys) -> None:
    cli("--all", "--full", "--hide-overlays", "--json")
    captured = capsys.readouterr()
    payload = json.loads(captured.out)  # stdout is JSON only
    assert [item["viewport"] for item in payload["captures"]] == list(cs.VIEWPORTS)
    assert all(item["hide_overlays"] is True for item in payload["captures"])
    assert all(item["overlays_hidden"] == 2 for item in payload["captures"])
    assert "Capturing desktop screenshot..." in captured.err


def test_cli_json_exits_non_zero_when_a_capture_fails(cli, capsys) -> None:
    cli.outcome["success"] = False
    with pytest.raises(SystemExit) as exc:
        cli("--json")
    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out)["captures"][0]["error"] == "boom"
