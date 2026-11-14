"""capture_screenshot.py full-page hygiene: scroll-through, settle, --hide-overlays.

Playwright is mocked the way tests/test_render_page.py does it: a fake page
records every call in order, and the context is built by the real
url_safety.new_guarded_context, so the tests also prove the guards are still
installed. No browser and no network.

Page-side steps must go through calls that carry a driver-enforced timeout
(Locator.wait_for_function, Locator.get_attribute). The fake records every
timeout it is given, and an autouse fixture fails any test in which
page.evaluate, which takes no timeout, was called.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("playwright")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import capture_screenshot as cs  # noqa: E402
import url_safety  # noqa: E402

URL = "https://site.example/"


@pytest.fixture(autouse=True)
def _browser_launch_environment(monkeypatch):
    """The fake browser launches the same for any user, proxy or opt-out."""
    import browser_proxy

    monkeypatch.setattr(browser_proxy.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(url_safety.requests.utils, "getproxies", lambda: {})
    monkeypatch.delenv(browser_proxy.NO_SANDBOX_ENV, raising=False)


class FakeRoot:
    """The locator the page-side steps run through; every call carries a timeout."""

    def __init__(self, page: FakePage) -> None:
        self._page = page

    def wait_for_function(self, expression, *, arg=None, timeout=None):
        page = self._page
        snippet = {cs._timed(known): known for known in SNIPPETS}[expression]
        name = SNIPPETS[snippet]
        page.timeouts.append((name, timeout))
        page.calls.append((name, arg["arg"]))
        page.spend(name, timeout, "Locator.wait_for_function")
        if page.fail == name:
            raise RuntimeError("Execution context was destroyed\nstack line")
        value = page.run_snippet(snippet, arg["arg"])
        page.attribute = json.dumps({"id": arg["id"], "value": value})

    def get_attribute(self, name, *, timeout=None):
        page = self._page
        assert name == cs._RESULT_ATTR
        page.timeouts.append(("read", timeout))
        page.spend("read", timeout, "Locator.get_attribute")
        return page.attribute


class FakePage:
    """Records calls in order; answers the hygiene snippets like a page would.

    ``calls`` holds one entry per page-side step, as it did when the steps
    went through page.evaluate; the read of a step's result is not a step.
    """

    instances: list[FakePage] = []

    def __init__(self, *, height=5000, step=1000, pending=(), overlays=3, top_lag=(),
                 fail=None, hang=None, cost_ms=None):
        self.height = height
        self.step = step
        self.pending = list(pending)  # successive _JS_PENDING answers; last one repeats
        self.overlays = overlays
        self.top_lag = list(top_lag)  # scrollY values reported before the page is at 0
        self.fail = fail  # snippet whose evaluation raises
        self.hang = hang  # step that never answers: "prepare", ..., or "read"
        self.hang_everything = False  # a stuck main thread also stalls the picture
        self.cost_ms = dict(cost_ms or {})  # fake time a step takes, by name
        self.now = 0.0  # fake clock in seconds, moved by spend() and waits
        self.attribute = None
        self.calls: list[tuple] = []
        self.timeouts: list[tuple] = []  # (step name or "read", timeout in ms)
        self.untimed: list[tuple] = []
        self.routes: list[tuple] = []
        FakePage.instances.append(self)

    def clock(self) -> float:
        return self.now

    def spend(self, name, timeout, api) -> None:
        """Behave like the driver: give up when the step outlasts its timeout."""
        assert isinstance(timeout, (int, float)) and timeout >= 1, (name, timeout)
        cost = self.cost_ms.get(name, 0)
        if self.hang == name or cost > timeout:
            self.now += timeout / 1000
            # The wording Playwright 1.65 uses, call log included.
            raise cs.PlaywrightTimeout(
                f"{api}: Timeout {timeout}ms exceeded.\nCall log:\n  - waiting for locator(':root')"
            )
        self.now += cost / 1000

    def locator(self, selector):
        assert selector == cs._ROOT
        return FakeRoot(self)

    def route(self, pattern, handler):
        self.routes.append((pattern, handler))

    def goto(self, url, **kwargs):
        self.calls.append(("goto", url, kwargs))
        if self.hang == "goto":
            raise cs.PlaywrightTimeout("Page.goto: Timeout 30000ms exceeded.")

    def wait_for_timeout(self, ms):
        self.calls.append(("wait", ms))
        self.now += ms / 1000

    def screenshot(self, **kwargs):
        self.calls.append(("screenshot", kwargs))
        if self.hang == "screenshot" or self.hang_everything:
            raise cs.PlaywrightTimeout("Page.screenshot: Timeout 30000ms exceeded.")

    def evaluate(self, *args, **kwargs):
        # No timeout: a stuck page would block this for good. Recorded, because
        # the code under test swallows exceptions from page-side steps.
        self.untimed.append(args)
        raise AssertionError("page.evaluate takes no timeout and must not be used")

    def run_snippet(self, snippet, arg=None):
        name = SNIPPETS[snippet]
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


SNIPPETS = {
    cs._JS_SCROLL_PREPARE: "prepare",
    cs._JS_SCROLL_TO: "scroll_to",
    cs._JS_PENDING: "pending",
    cs._JS_HIDE_OVERLAYS: "hide_overlays",
}
STEP_NAMES = ("prepare", "scroll_to", "pending", "hide_overlays")


@pytest.fixture(autouse=True)
def no_untimed_page_calls():
    """No test may end with an untimed call into the page, or a call without a timeout."""
    FakePage.instances.clear()
    yield
    for page in FakePage.instances:
        assert page.untimed == [], "page.evaluate was called; it has no timeout"
        for name, timeout in page.timeouts:
            assert 1 <= timeout <= cs.HIDE_OVERLAYS_MAX_MS, (name, timeout)


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
    monkeypatch.setattr(cs, "require_public_page", lambda page: None)
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
    original = page.run_snippet

    def growing(snippet, arg=None):
        answer = original(snippet, arg)
        page.height += 5000  # infinite scroll: the page is taller after every call
        return answer

    page.run_snippet = growing
    info = cs._scroll_through(page)
    assert info == {"steps": 2, "capped": False, "returned_to_top": True}
    assert page.names().count("prepare") == 1


def test_scroll_stops_at_the_time_budget() -> None:
    # The fake clock moves when the page is used: every scroll step takes 1.5 s
    # and its pause 0.12 s. Budget is SCROLL_MAX_MS (6 s): steps start at 0 s,
    # 1.62 s, 3.24 s and 4.86 s, and the check at 6.48 s stops the scroll.
    page = FakePage(height=10**9, step=1000, cost_ms={"scroll_to": 1500})
    info = cs._scroll_through(page, clock=page.clock)
    assert info == {"steps": 4, "capped": True, "returned_to_top": True}
    assert page.now <= cs.SCROLL_TOTAL_MS / 1000


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
# A page whose main thread is stuck: every page-side step is time-limited
# ---------------------------------------------------------------------------


def test_worst_case_wall_clock_is_the_sum_of_the_phase_budgets() -> None:
    # The waits counted above are what a healthy page costs. The ceiling with a
    # slow or stuck page is the budgets, which also cover the page-side steps.
    healthy_scroll_ms = (
        cs.SCROLL_MAX_MS + cs.SCROLL_PAUSE_MS
        + cs.SCROLL_TOP_RETRIES * cs.SCROLL_TOP_PAUSE_MS + cs.SCROLL_REST_MS
    )
    assert healthy_scroll_ms + cs.JS_STEP_TIMEOUT_MS <= cs.SCROLL_TOTAL_MS
    assert cs.SETTLE_TOTAL_MS == cs.SETTLE_MAX_MS + cs.JS_STEP_TIMEOUT_MS
    assert cs.SCROLL_TOTAL_MS + cs.SETTLE_TOTAL_MS + cs.HIDE_OVERLAYS_MAX_MS == 17500


@pytest.mark.parametrize("stuck", ["prepare", "scroll_to", "read"])
def test_stuck_scroll_step_times_out_and_the_picture_is_still_tried(monkeypatch, stuck) -> None:
    page = FakePage(hang=stuck)
    result = _capture(monkeypatch, page, full_page=True, hide_overlays=True)
    # The screenshot is still attempted, and the result says what happened.
    assert page.names()[-1] == "screenshot"
    assert result["success"] is True and result["error"] is None
    assert result["scroll_timed_out"] is True
    info = result["scroll_through"]
    assert info["timed_out"] is True
    assert info["returned_to_top"] is False
    api = "get_attribute" if stuck == "read" else "wait_for_function"
    assert info["error"] == (
        f"TimeoutError: Locator.{api}: Timeout {cs.JS_STEP_TIMEOUT_MS}ms exceeded."
    )
    # Nothing else is asked of a page that stopped answering.
    assert page.timeouts[-1][0] == stuck
    assert "pending" not in page.names() and "hide_overlays" not in page.names()
    assert result["settle"] is None
    assert result["overlays_hidden"] == 0
    assert result["hide_overlays_error"] == "skipped: an earlier page-side step timed out"
    # One driver timeout, not one per remaining step.
    assert page.now == 1 + cs.JS_STEP_TIMEOUT_MS / 1000


def test_page_that_gets_stuck_part_way_down_stops_the_scroll_at_once(monkeypatch) -> None:
    page = FakePage(height=10**9, step=1000)
    answered = []
    original = page.spend

    def stuck_after_three(name, timeout, api):
        if name == "scroll_to" and answered.count("scroll_to") >= 3:
            page.hang = "scroll_to"  # the scroll handler now loops forever
        answered.append(name)
        return original(name, timeout, api)

    page.spend = stuck_after_three
    result = _capture(monkeypatch, page, full_page=True)
    assert result["scroll_through"]["steps"] == 3
    assert result["scroll_through"]["timed_out"] is True
    assert result["scroll_timed_out"] is True
    assert page.names().count("scroll_to") == 4  # three answered, one timed out, no more
    assert page.names()[-1] == "screenshot"


def test_picture_that_also_times_out_is_a_failed_capture_that_says_why(monkeypatch) -> None:
    # With the main thread stuck for good the screenshot runs into its own
    # Playwright timeout. The capture ends, and the result names both facts.
    page = FakePage(hang="scroll_to")
    page.hang_everything = True
    result = _capture(monkeypatch, page, full_page=True)
    assert page.names()[-1] == "screenshot"
    assert result["success"] is False
    assert result["error"] == "Screenshot timed out: the page did not answer in time"
    assert result["scroll_timed_out"] is True

    # A navigation timeout keeps its own message.
    page = FakePage(hang="goto")
    result = _capture(monkeypatch, page, full_page=True, timeout=1234)
    assert result["error"] == "Page load timed out after 1234ms"
    assert result["scroll_timed_out"] is False
    assert "screenshot" not in page.names()


def test_stuck_settle_step_is_flagged_and_overlays_are_skipped(monkeypatch) -> None:
    page = FakePage(hang="pending")
    result = _capture(monkeypatch, page, full_page=True, hide_overlays=True)
    assert result["scroll_through"] == {"steps": 4, "capped": False, "returned_to_top": True}
    assert result["scroll_timed_out"] is False
    assert result["settle"]["timed_out"] is True
    assert result["settle"]["error"].startswith(
        "TimeoutError: Locator.wait_for_function: Timeout ")
    assert page.names().count("pending") == 1
    assert "hide_overlays" not in page.names()
    assert result["hide_overlays_error"] == "skipped: an earlier page-side step timed out"
    assert page.names()[-1] == "screenshot" and result["success"] is True


def test_stuck_hide_overlays_is_reported_and_the_picture_is_still_tried(monkeypatch) -> None:
    page = FakePage(hang="hide_overlays")
    result = _capture(monkeypatch, page, hide_overlays=True)
    assert page.names() == ["goto", "wait", "hide_overlays", "screenshot"]
    assert result["overlays_hidden"] == 0
    # The whole allowance for this step, less the instant it took to get here.
    waited = re.fullmatch(r"TimeoutError: Locator\.wait_for_function: Timeout (\d+)ms exceeded\.",
                          result["hide_overlays_error"])
    assert waited and cs.HIDE_OVERLAYS_MAX_MS - 100 <= int(waited[1]) <= cs.HIDE_OVERLAYS_MAX_MS
    assert result["scroll_timed_out"] is False and result["success"] is True


def test_every_page_side_call_carries_a_driver_timeout(monkeypatch) -> None:
    page = FakePage(
        height=10**9, top_lag=[900, 300], overlays=2,
        pending=[{"animations": 1, "images": 1}, {"animations": 0, "images": 0}],
    )
    result = _capture(monkeypatch, page, full_page=True, hide_overlays=True)
    assert result["success"] is True and result["overlays_hidden"] == 2
    steps = [name for name in page.names() if name in STEP_NAMES]
    assert set(steps) == set(STEP_NAMES)
    # One timeout per step, plus one per result that was read back; the scroll
    # steps on the way down need no result.
    assert [name for name, _timeout in page.timeouts if name != "read"] == steps
    reads = sum(1 for name, _timeout in page.timeouts if name == "read")
    assert reads == len(steps) - cs.SCROLL_MAX_STEPS
    scroll_and_settle = [t for name, t in page.timeouts if name != "hide_overlays"][:-1]
    assert all(1 <= timeout <= cs.JS_STEP_TIMEOUT_MS for timeout in scroll_and_settle)
    assert page.untimed == []


def test_scroll_phase_has_a_total_wall_clock_budget() -> None:
    # No single step outlasts its own limit, but together they would run for
    # more than 80 s. The phase stops when SCROLL_TOTAL_MS is spent.
    slow = cs.JS_STEP_TIMEOUT_MS - 100
    page = FakePage(height=10**9, cost_ms={"prepare": slow, "read": slow, "scroll_to": slow})
    info = cs._scroll_through(page, clock=page.clock)
    assert info["timed_out"] is True
    assert info["returned_to_top"] is False
    assert info["steps"] <= 2
    assert page.now <= cs.SCROLL_TOTAL_MS / 1000
    # The last call was only given what was left of the budget.
    assert page.timeouts[-1][1] < cs.JS_STEP_TIMEOUT_MS


def test_spent_budget_never_becomes_a_zero_timeout() -> None:
    # Playwright reads timeout=0 as "wait for ever".
    page = FakePage()
    budget = cs._Budget(1000, clock=page.clock)
    assert budget.step_timeout() == 1000
    page.now = 0.5004
    assert budget.step_timeout() == 499  # whole milliseconds, rounded down
    page.now = 0.9995
    with pytest.raises(cs._StepTimeout):
        budget.step_timeout()
    page.now = 5.0
    with pytest.raises(cs._StepTimeout):
        cs._page_step(page, cs._JS_PENDING, budget=budget)
    assert page.timeouts == [] and page.calls == []


def test_settle_has_a_total_wall_clock_budget() -> None:
    slow = cs.JS_STEP_TIMEOUT_MS - 100
    page = FakePage(pending=[{"animations": 4, "images": 9}], cost_ms={"pending": slow})
    info = cs._settle(page, wait_images=True, clock=page.clock)
    assert info["timed_out"] is True
    assert page.now <= cs.SETTLE_TOTAL_MS / 1000


@pytest.mark.parametrize("left_by_the_page", [
    None,                                        # the attribute was never written
    json.dumps({"id": -1, "value": {"height": 10**9, "step": 1}}),  # an earlier call's
    "not json",
    "[" * 900,
    json.dumps({"id": 0, "value": "x" * 5000}),  # oversized
    json.dumps([1, 2, 3]),
])
def test_result_the_page_tampered_with_is_an_error_not_a_value(left_by_the_page) -> None:
    page = FakePage()

    def tamper(_snippet, _arg=None):
        return None

    page.run_snippet = tamper
    root = FakeRoot(page)
    page.locator = lambda _selector: root
    root.get_attribute = lambda _name, *, timeout=None: left_by_the_page
    info = cs._scroll_through(page)
    assert info["steps"] == 0
    assert info["error"] == "ValueError: the page-side step left no usable result"
    assert "timed_out" not in info


def test_odd_values_from_the_page_do_not_raise() -> None:
    for dims in ({"height": "tall", "step": []}, {"height": float("inf")}, "x", 7, None):
        page = FakePage()
        page.run_snippet = lambda snippet, arg=None, dims=dims: (
            dims if SNIPPETS[snippet] == "prepare" else 0
        )
        info = cs._scroll_through(page)
        assert info["steps"] == 0, dims
        assert info["returned_to_top"] is True, dims  # the return to the top still ran
        assert "timed_out" not in info, dims
    page = FakePage(pending=[{"animations": "many", "images": None}])
    assert "error" in cs._settle(page, wait_images=True)


def test_playwright_without_a_timed_page_call_skips_the_steps(monkeypatch) -> None:
    # Older Playwright has no Locator.wait_for_function. The steps are skipped
    # with a clear reason; falling back to page.evaluate would bring the hang back.
    page = FakePage()
    page.locator = lambda _selector: SimpleNamespace()
    result = _capture(monkeypatch, page, full_page=True, hide_overlays=True)
    assert result["success"] is True and page.names()[-1] == "screenshot"
    assert not set(page.names()) & set(STEP_NAMES)
    for error in (result["scroll_through"]["error"], result["settle"]["error"],
                  result["hide_overlays_error"]):
        assert error.startswith("RuntimeError: this Playwright has no Locator.wait_for_function")
    assert result["scroll_timed_out"] is False


def test_source_makes_no_untimed_call_into_the_page() -> None:
    source = Path(cs.__file__).read_text(encoding="utf-8")
    for untimed in ("evaluate", "evaluate_handle", "eval_on_selector", "eval_on_selector_all",
                    "add_script_tag", "add_init_script", "json_value"):
        assert not re.search(rf"\.{untimed}\(", source), untimed
    # Each timed call names its timeout.
    assert len(re.findall(r"timeout=budget\.step_timeout\(\)", source)) == 2


def test_wrapper_runs_the_snippet_once_and_never_polls() -> None:
    wrapped = cs._timed(cs._JS_SCROLL_TO)
    assert wrapped.startswith("(root, call) => {")
    assert f"({cs._JS_SCROLL_TO})(call.arg)" in wrapped
    assert cs._RESULT_ATTR in wrapped and "JSON.stringify" in wrapped
    # A truthy return ends Locator.wait_for_function at the first run.
    assert wrapped.rstrip().endswith("return true;\n}")
    forbidden = (
        "fetch", "XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource", "import(",
        "location", "open(", "href", "src", "createElement", "innerHTML", "eval(",
        "navigator", "postMessage", "submit", "click", "url(", "async", "await",
    )
    for token in forbidden:
        assert token not in cs._timed("() => 1"), token


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


def test_cli_json_says_when_the_scroll_timed_out(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    page = FakePage(hang="scroll_to")
    monkeypatch.setattr(cs, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(cs, "require_public_page", lambda page: None)
    monkeypatch.setattr(cs, "sync_playwright", lambda: FakeManager(page))
    monkeypatch.setattr(sys, "argv", ["capture_screenshot.py", URL, "--full", "--json"])
    cs.main()
    captured = capsys.readouterr()
    (capture,) = json.loads(captured.out)["captures"]
    assert capture["scroll_timed_out"] is True
    assert capture["scroll_through"]["timed_out"] is True
    assert capture["success"] is True  # the picture was still taken
    assert "scroll-through timed out" in captured.err
    assert page.names()[-1] == "screenshot"


# ---------------------------------------------------------------------------
# What a finished navigation may be photographed as (browser egress guard)
# ---------------------------------------------------------------------------


def _capture_checking_the_page(monkeypatch, page, **kwargs):
    """Like _capture, with the real require_public_page."""
    import browser_proxy

    monkeypatch.setattr(url_safety.requests.utils, "getproxies", lambda: {})
    monkeypatch.delenv(browser_proxy.NO_SANDBOX_ENV, raising=False)
    monkeypatch.setattr(cs, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(cs, "sync_playwright", lambda: FakeManager(page))
    return cs.capture_screenshot(URL, "/out/shot.png", **kwargs)


@pytest.mark.parametrize("url", ["about:blank", "chrome-error://chromewebdata/"])
def test_a_page_that_never_loaded_is_an_error_not_a_picture(monkeypatch, url) -> None:
    page = FakePage()
    page.url = url
    result = _capture_checking_the_page(monkeypatch, page)
    assert result["success"] is False
    assert result["error"].startswith("Page did not load: ")
    assert "Invalid URL scheme" not in result["error"]
    assert "screenshot" not in page.names()


@pytest.mark.parametrize("url", ["http://127.0.0.1:9000/", "http://10.0.0.5/", "file:///etc/passwd"])
def test_a_page_on_a_non_public_address_is_never_photographed(monkeypatch, url) -> None:
    page = FakePage()
    page.url = url
    result = _capture_checking_the_page(monkeypatch, page)
    assert result["success"] is False
    assert result["error"].startswith("url_safety: ")
    assert "screenshot" not in page.names()


def test_a_page_that_navigates_away_after_load_is_not_photographed(monkeypatch) -> None:
    """Page scripts can navigate after the load. The guard refuses the new
    destination, and the picture must not be of that refusal."""
    import browser_proxy

    monkeypatch.setattr(
        browser_proxy, "_destination", lambda url: ("93.184.216.34", "site.example", 443)
        if url == URL else (_ for _ in ()).throw(url_safety.URLSafetyError("refused")),
    )

    class Wanderer(FakePage):
        url = URL

        def wait_for_timeout(self, ms):
            super().wait_for_timeout(ms)
            self.url = "http://127.0.0.1:9000/"

    page = Wanderer()
    result = _capture_checking_the_page(monkeypatch, page)
    assert result["success"] is False
    assert result["error"].startswith("url_safety: ")
    assert page.names() == ["goto", "wait"]


def test_capture_reports_a_sandbox_failure_with_the_opt_out(monkeypatch) -> None:
    import browser_proxy

    monkeypatch.setattr(browser_proxy.os, "geteuid", lambda: 0, raising=False)
    page = FakePage()
    result = _capture_checking_the_page(monkeypatch, page)
    assert result["success"] is False
    assert "CLAUDE_SEO_CHROMIUM_NO_SANDBOX=1" in result["error"]
    assert page.calls == []
