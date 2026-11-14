#!/usr/bin/env python3
"""
Capture screenshots of web pages using Playwright.

The SSRF pre-flight check is delegated to url_safety. Chromium is launched
through browser_proxy.guarded_chromium: sandboxed, with every connection
(redirect hops included) forced through a local proxy that validates and
pins the destination. A Playwright route() handler also aborts any request
whose hostname resolves to a non-public IP (defence in depth). Set
CLAUDE_SEO_CHROMIUM_NO_SANDBOX=1 only where the Chromium sandbox cannot
start (root, some containers).

Full-page captures (--full) get two hygiene steps before the picture is
taken, both bounded so a page cannot hang the capture:

- scroll-through: the page is scrolled once from top to bottom so lazy
  images load, then returned to the top. At most SCROLL_MAX_STEPS steps
  and SCROLL_MAX_MS on the way down, and SCROLL_TOTAL_MS of wall-clock
  time for the whole phase; the page height is read once, so an
  infinite-scroll page cannot extend it. Turn off with --no-scroll.
- settle: waits up to SETTLE_MAX_MS for finite animations to finish and,
  after a scroll-through, for the images it triggered (SETTLE_TOTAL_MS of
  wall-clock time at most).

--hide-overlays is opt-in and off by default: it hides fixed or stuck
floating elements (cookie banners, chat widgets, bottom bars) before the
capture. Leave it off for a visual audit, which has to see intrusive
overlays. When it is used the result says so.

Neither step opens a new navigation or request path: they only scroll and
restyle the page already loaded behind the url_safety route guard.

How the page-side steps are bounded
===================================
Each of these steps runs a few lines of JavaScript in the page, and the
page is hostile input: a scroll handler that loops forever blocks its main
thread for good. ``page.evaluate`` takes no timeout in Playwright's sync
API, so a call into such a page would never return. No step uses it. Each
one goes through ``Locator.wait_for_function`` (and ``get_attribute`` to
read the result back), which take a timeout that the Playwright driver
enforces with a timer of its own, outside the page. When a step times out,
or its phase runs out of wall-clock budget, no further page-side step is
made and the capture goes straight on to the picture, which has its own
Playwright timeout. The result then says ``scroll_timed_out`` (or
``timed_out`` under ``settle``, or ``hide_overlays_error``). A Playwright
without ``Locator.wait_for_function`` skips these steps and says so.

Usage:
    python capture_screenshot.py https://example.com
    python capture_screenshot.py https://example.com --viewport mobile
    python capture_screenshot.py https://example.com --output screenshots/
    python capture_screenshot.py https://example.com --full --json
    python capture_screenshot.py https://example.com --full --hide-overlays

Output (--json prints {"captures": [...]}, one entry per viewport):
    url, output, viewport, success, error   as before
    full_page        True for a full-page capture
    scroll_through   None, or {steps, capped, returned_to_top} (plus error,
                     and timed_out: true when the page stopped answering)
    scroll_timed_out True when the scroll-through hit its time bound; the
                     picture was still attempted and may lack lazy content
    settle           None (also when skipped after a timeout), or
                     {waited_ms, animations_pending, images_pending}
                     (plus error, and timed_out: true)
    hide_overlays    True when --hide-overlays was used
    overlays_hidden  None, or the number of elements hidden for the capture
                     (hide_overlays_error is added when hiding failed, timed
                     out or was skipped)
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
from urllib.parse import ParseResult, urlparse

try:
    from playwright.sync_api import (
        TimeoutError as PlaywrightTimeout,
    )
    from playwright.sync_api import (
        sync_playwright,
    )
except ImportError:
    print(
        "Error: playwright required. Install with: "
        "pip install playwright && playwright install chromium"
    )
    sys.exit(1)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from browser_proxy import (  # noqa: E402
    PageNotLoadedError,
    guarded_chromium,
    require_public_page,
)
from url_safety import (  # noqa: E402  (sys.path massage above is intentional)
    URLSafetyError,
    make_safe_playwright_route_handler,
    new_guarded_context,
    validate_url_strict,
)

VIEWPORTS = {
    "desktop": {"width": 1920, "height": 1080},
    "laptop": {"width": 1366, "height": 768},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 375, "height": 812},
}

# Full-page hygiene bounds. The scroll-through stops at whichever limit
# comes first, so an infinite-scroll page cannot hang the capture.
SCROLL_MAX_STEPS = 40     # viewport-height steps down the page
SCROLL_PAUSE_MS = 120     # pause per step so lazy loaders can fire
SCROLL_MAX_MS = 6000      # wall-clock budget for the scroll down
SCROLL_TOP_RETRIES = 10   # tries, SCROLL_TOP_PAUSE_MS apart, to get back to the top
SCROLL_TOP_PAUSE_MS = 50
SCROLL_REST_MS = 250      # after the return, so scroll handlers can run
SETTLE_MAX_MS = 1500      # wait for finite animations and triggered images
SETTLE_POLL_MS = 100

# Wall-clock limits for the JavaScript run in the page. The Playwright driver
# enforces them, so they hold when the page's main thread is stuck.
JS_STEP_TIMEOUT_MS = 2000    # one driver call (run a snippet, or read its result)
SCROLL_TOTAL_MS = 9000       # the whole scroll phase: down, back to the top, rest
SETTLE_TOTAL_MS = SETTLE_MAX_MS + JS_STEP_TIMEOUT_MS
HIDE_OVERLAYS_MAX_MS = 5000  # the one pass that hides overlays, on a large DOM

# Where a page-side step runs and where it leaves its result for the read.
_ROOT = ":root"
_RESULT_ATTR = "data-claude-seo-result"
_RESULT_MAX_CHARS = 1000
_CALL_IDS = itertools.count(1)

# The snippets below are adapted from web-obs (engine/page_snapshots.py).
# Each one is synchronous and is written to return at once; the waiting
# happens in Python, where it is counted against the bounds above. They are
# never handed to page.evaluate: see _page_step.

# Smooth scrolling (common) turns every jump into a slow glide, so the
# steps would never reach their positions and the picture would be taken
# part way down. Scrolling is forced to be instant first. The height is
# read once here and never again.
_JS_SCROLL_PREPARE = """() => {
  for (const el of [document.documentElement, document.body]) {
    if (el) el.style.setProperty('scroll-behavior', 'auto', 'important');
  }
  return {
    height: document.documentElement.scrollHeight,
    step: Math.max(400, window.innerHeight),
  };
}"""

_JS_SCROLL_TO = """(y) => {
  window.scrollTo({ top: y, left: 0, behavior: 'instant' });
  return Math.round(window.scrollY);
}"""

# Animations that never end (spinners, marquees) are not waited for.
_JS_PENDING = """() => {
  let animations = 0;
  if (document.getAnimations) {
    for (const animation of document.getAnimations()) {
      if (animation.playState !== 'running') continue;
      const effect = animation.effect;
      const timing = effect && effect.getComputedTiming ? effect.getComputedTiming() : null;
      if (timing && timing.endTime === Infinity) continue;
      animations++;
    }
  }
  let images = 0;
  for (const img of document.images) if (!img.complete) images++;
  return { animations, images };
}"""

# Floating elements land on top of the content in a full-page picture.
# Hidden: fixed elements, except a bar pinned to the top edge (the site
# header) and a full-height rail on one side (a docs sidebar), and sticky
# elements that are stuck to the bottom edge. Other sticky elements sit in
# the page flow and stay. Styles are set through the CSSOM, which a strict
# Content-Security-Policy still allows.
_JS_HIDE_OVERLAYS = """() => {
  const vh = window.innerHeight, vw = window.innerWidth;
  let hidden = 0;
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' && cs.position !== 'sticky') continue;
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (el.closest('[data-claude-seo-hidden]')) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (cs.position === 'fixed') {
      const atTop = r.top <= vh * 0.1;
      const header = atTop && r.height <= vh * 0.3;
      const sideRail = atTop && r.height >= vh * 0.9 && r.width <= vw * 0.35;
      if (header || sideRail) continue;
    } else {
      const offset = parseFloat(cs.bottom);
      if (Number.isNaN(offset) || Math.abs(r.bottom + offset - vh) > 2) continue;
    }
    el.setAttribute('data-claude-seo-hidden', '');
    el.style.setProperty('visibility', 'hidden', 'important');
    hidden++;
  }
  return hidden;
}"""


def normalize_url(url: str) -> tuple[str, ParseResult]:
    """Normalize URL and return (url, parsed_url).

    Raises ValueError on invalid scheme or missing hostname (caller-side
    contract preserved from v1.x). SSRF validation is performed separately
    via url_safety.validate_url_strict before any network I/O.
    """
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise ValueError("Invalid URL: missing hostname")

    return url, parsed


def _error_text(exc: Exception) -> str:
    lines = str(exc).splitlines()
    return f"{type(exc).__name__}: {lines[0][:200] if lines else 'failed'}"


class _StepTimeout(Exception):
    """A page-side step did not finish inside its wall-clock limit."""


class _Budget:
    """Wall-clock allowance for one group of page-side steps."""

    def __init__(self, total_ms: float, clock=time.monotonic,  # type: ignore[no-untyped-def]
                 step_ms: float = JS_STEP_TIMEOUT_MS) -> None:
        self._clock = clock
        self._end = clock() + total_ms / 1000.0
        self._step_ms = step_ms

    def step_timeout(self) -> int:
        """Timeout in ms for the next driver call. Raises once the allowance is spent.

        Never 0: Playwright reads a timeout of 0 as "no timeout".
        """
        left = int((self._end - self._clock()) * 1000.0)
        if left < 1:
            raise _StepTimeout("TimeoutError: the time budget for this phase is spent")
        return min(int(self._step_ms), left)


def _timed(snippet: str) -> str:
    """Wrap a snippet as a ``Locator.wait_for_function`` expression.

    The wrapper runs the snippet once, leaves its result as JSON on the root
    element for a second, equally bounded call to read, and returns true so
    the driver does not poll.
    """
    return (
        "(root, call) => {\n"
        f"  const value = ({snippet})(call.arg);\n"
        "  const result = { id: call.id, value: value === undefined ? null : value };\n"
        f"  root.setAttribute('{_RESULT_ATTR}', JSON.stringify(result));\n"
        "  return true;\n"
        "}"
    )


def _page_step(page, snippet: str, arg=None, *, budget: _Budget,  # type: ignore[no-untyped-def]
               want_result: bool = True):
    """Run one snippet in the page under a timeout the Playwright driver enforces.

    ``page.evaluate`` takes no timeout, so a page whose main thread is stuck
    would block it for good. ``Locator.wait_for_function`` and
    ``Locator.get_attribute`` carry one, and the driver races the page
    against its own timer for the whole call, so they give up on time
    whatever the page does. Raises _StepTimeout when a limit is hit.

    The result is whatever the page left: treat it as untrusted.
    """
    root = page.locator(_ROOT)
    run = getattr(root, "wait_for_function", None)
    if run is None:
        raise RuntimeError(
            "this Playwright has no Locator.wait_for_function, so page-side steps "
            "cannot be time-limited and are skipped"
        )
    call_id = next(_CALL_IDS)
    try:
        run(_timed(snippet), arg={"id": call_id, "arg": arg}, timeout=budget.step_timeout())
        if not want_result:
            return None
        raw = root.get_attribute(_RESULT_ATTR, timeout=budget.step_timeout())
    except PlaywrightTimeout as exc:
        raise _StepTimeout(_error_text(exc)) from exc
    # The id shows the result belongs to this call and not to an earlier one.
    try:
        if not isinstance(raw, str) or len(raw) > _RESULT_MAX_CHARS:
            raise ValueError
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("id") != call_id:
            raise ValueError
    except (ValueError, RecursionError):
        raise ValueError("the page-side step left no usable result") from None
    return payload.get("value")


def _scroll_through(page, clock=time.monotonic) -> dict:  # type: ignore[no-untyped-def]
    """Scroll once down the page so lazy images load, then back to the top.

    The way down is bounded by SCROLL_MAX_STEPS and SCROLL_MAX_MS, whichever
    comes first; ``capped`` is True when a limit cut it short. The whole
    phase is bounded by SCROLL_TOTAL_MS, and every page-side step by a
    driver timeout: when either is hit, ``timed_out`` is set and nothing
    more is run in the page. Never raises: a failure is recorded under
    ``error`` and the capture goes on.
    """
    info: dict = {"steps": 0, "capped": False, "returned_to_top": False}
    budget = _Budget(SCROLL_TOTAL_MS, clock)
    deadline = clock() + SCROLL_MAX_MS / 1000.0
    try:
        dims = _page_step(page, _JS_SCROLL_PREPARE, budget=budget)
        dims = dims if isinstance(dims, dict) else {}
        height = int(dims.get("height") or 0)
        step = max(1, int(dims.get("step") or 0))
        # The first screen is already on display, so start one step down.
        y = step
        while y < height:
            if info["steps"] >= SCROLL_MAX_STEPS or clock() >= deadline:
                info["capped"] = True
                break
            _page_step(page, _JS_SCROLL_TO, y, budget=budget, want_result=False)
            page.wait_for_timeout(SCROLL_PAUSE_MS)
            info["steps"] += 1
            y += step
    except _StepTimeout as exc:
        info["timed_out"] = True
        info["error"] = str(exc)
        return info  # the page is not answering: do not ask it to scroll back
    except Exception as exc:
        info["error"] = _error_text(exc)
    try:
        for _ in range(SCROLL_TOP_RETRIES):
            if not _page_step(page, _JS_SCROLL_TO, 0, budget=budget):
                info["returned_to_top"] = True
                break
            page.wait_for_timeout(SCROLL_TOP_PAUSE_MS)
        if info["steps"]:
            page.wait_for_timeout(SCROLL_REST_MS)
    except _StepTimeout as exc:
        info["timed_out"] = True
        info.setdefault("error", str(exc))
    except Exception as exc:
        info.setdefault("error", _error_text(exc))
    return info


def _settle(page, wait_images: bool, clock=time.monotonic) -> dict:  # type: ignore[no-untyped-def]
    """Wait up to SETTLE_MAX_MS for finite animations (and images) to finish.

    The ``*_pending`` counts are what was still unfinished when the wait
    ended. Bounded by SETTLE_TOTAL_MS of wall-clock time and a driver
    timeout per page-side step; ``timed_out`` is set when one is hit.
    Never raises.
    """
    info: dict = {"waited_ms": 0, "animations_pending": 0, "images_pending": 0}
    budget = _Budget(SETTLE_TOTAL_MS, clock)
    try:
        while True:
            pending = _page_step(page, _JS_PENDING, budget=budget)
            pending = pending if isinstance(pending, dict) else {}
            info["animations_pending"] = int(pending.get("animations") or 0)
            info["images_pending"] = int(pending.get("images") or 0) if wait_images else 0
            busy = info["animations_pending"] or info["images_pending"]
            if not busy or info["waited_ms"] >= SETTLE_MAX_MS:
                break
            page.wait_for_timeout(SETTLE_POLL_MS)
            info["waited_ms"] += SETTLE_POLL_MS
    except _StepTimeout as exc:
        info["timed_out"] = True
        info["error"] = str(exc)
    except Exception as exc:
        info["error"] = _error_text(exc)
    return info


def _hide_overlays(page, clock=time.monotonic) -> dict:  # type: ignore[no-untyped-def]
    """Hide floating elements; returns the result keys to merge. Never raises."""
    budget = _Budget(HIDE_OVERLAYS_MAX_MS, clock, step_ms=HIDE_OVERLAYS_MAX_MS)
    try:
        return {"overlays_hidden": int(_page_step(page, _JS_HIDE_OVERLAYS, budget=budget) or 0)}
    except _StepTimeout as exc:
        return {"overlays_hidden": 0, "hide_overlays_error": str(exc)}
    except Exception as exc:
        return {"overlays_hidden": 0, "hide_overlays_error": _error_text(exc)}


def capture_screenshot(
    url: str,
    output_path: str,
    viewport: str = "desktop",
    full_page: bool = False,
    timeout: int = 30000,
    scroll_through: bool = True,
    hide_overlays: bool = False,
) -> dict:
    """
    Capture a screenshot of a web page.

    Args:
        url: URL to capture
        output_path: Output file path
        viewport: Viewport preset (desktop, laptop, tablet, mobile)
        full_page: Whether to capture full page or just viewport
        timeout: Page load timeout in milliseconds
        scroll_through: For full-page captures, scroll the page once first
            so lazy images load (bounded). Ignored for viewport captures.
        hide_overlays: Hide fixed or stuck floating elements before the
            capture. Off by default: a visual audit must see them.

    Returns:
        Dictionary with capture results
    """
    result = {
        "url": url,
        "output": output_path,
        "viewport": viewport,
        "success": False,
        "error": None,
        "full_page": full_page,
        "scroll_through": None,
        "scroll_timed_out": False,
        "settle": None,
        "hide_overlays": hide_overlays,
        "overlays_hidden": None,
    }

    if viewport not in VIEWPORTS:
        result["error"] = f"Invalid viewport: {viewport}. Choose from: {list(VIEWPORTS.keys())}"
        return result

    try:
        url, _parsed = normalize_url(url)
        result["url"] = url
    except ValueError as e:
        result["error"] = str(e)
        return result

    # SSRF pre-flight via the canonical safety module: resolves DNS,
    # rejects any non-public A record, blocks cloud-metadata endpoints.
    try:
        url, _pinned_ip = validate_url_strict(url)
        result["url"] = url
    except URLSafetyError as e:
        result["error"] = f"url_safety: {e}"
        return result

    vp = VIEWPORTS[viewport]
    route_handler = make_safe_playwright_route_handler()
    loaded = False

    try:
        with sync_playwright() as p, guarded_chromium(p.chromium, url) as browser:
            context = new_guarded_context(
                browser,
                route_handler,
                viewport={"width": vp["width"], "height": vp["height"]},
                device_scale_factor=2 if viewport == "mobile" else 1,
            )
            page = context.new_page()

            # Defence in depth: abort any subresource that lands on a
            # private IP even after Chromium re-resolves DNS.
            page.route("**/*", route_handler)

            # Navigate and wait for network idle
            page.goto(url, wait_until="networkidle", timeout=timeout)
            # A blank or error page, or one reached through a refused
            # redirect, is an error result below, never a screenshot.
            require_public_page(page)
            loaded = True

            # Wait a bit more for any lazy-loaded content
            page.wait_for_timeout(1000)

            # Once a page-side step has timed out the page is not answering:
            # the steps left are skipped and the picture is tried at once.
            stalled = False
            if full_page:
                if scroll_through:
                    result["scroll_through"] = _scroll_through(page)
                    stalled = bool(result["scroll_through"].get("timed_out"))
                    result["scroll_timed_out"] = stalled
                if not stalled:
                    result["settle"] = _settle(page, wait_images=scroll_through)
                    stalled = bool(result["settle"].get("timed_out"))

            if hide_overlays and stalled:
                result["overlays_hidden"] = 0
                result["hide_overlays_error"] = "skipped: an earlier page-side step timed out"
            elif hide_overlays:
                result.update(_hide_overlays(page))

            # Page scripts may have navigated since the load; check again
            # so the picture is never of a refused or failed document.
            require_public_page(page)

            # Capture screenshot
            page.screenshot(path=output_path, full_page=full_page)

            result["success"] = True

    except PlaywrightTimeout:
        # After the load, only the screenshot can time out here: the page-side
        # steps record their own timeouts and never raise.
        if loaded:
            result["error"] = "Screenshot timed out: the page did not answer in time"
        else:
            result["error"] = f"Page load timed out after {timeout}ms"
    except URLSafetyError as e:
        result["error"] = f"url_safety: {e}"
    except PageNotLoadedError as e:
        result["error"] = f"Page did not load: {e}"
    except Exception as e:
        result["error"] = str(e)

    return result


def _within(path: str, root: str) -> bool:
    """True when ``path`` is ``root`` or inside it (both already resolved)."""
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives on Windows
        return False


def safe_output_dir(path: str) -> str | None:
    """Resolve ``path`` and return it when it lies within the current
    directory or the home directory, else None.

    Both roots are resolved too: a plain string prefix check let
    ``/home/user2`` pass for ``/home/user``, and a symlinked home (for
    example ``/home`` -> ``/var/home``) never matched a resolved path.
    """
    resolved = os.path.realpath(path)
    roots = (os.path.realpath(os.getcwd()), os.path.realpath(os.path.expanduser("~")))
    return resolved if any(_within(resolved, root) for root in roots) else None


def main():
    parser = argparse.ArgumentParser(description="Capture web page screenshots")
    parser.add_argument("url", help="URL to capture")
    parser.add_argument("--output", "-o", default="screenshots", help="Output directory")
    parser.add_argument("--viewport", "-v", default="desktop", choices=VIEWPORTS.keys())
    parser.add_argument("--all", "-a", action="store_true", help="Capture all viewports")
    parser.add_argument("--full", "-f", action="store_true", help="Capture full page")
    parser.add_argument("--timeout", "-t", type=int, default=30000, help="Timeout in ms")
    parser.add_argument(
        "--no-scroll",
        action="store_true",
        help="With --full: skip the scroll-through that loads lazy images",
    )
    parser.add_argument(
        "--hide-overlays",
        action="store_true",
        help="Hide fixed or stuck floating elements (cookie banners, chat widgets) "
             "before the capture. Off by default; do not use for a visual audit",
    )
    parser.add_argument("--json", action="store_true", help="Print the results as JSON")

    args = parser.parse_args()

    # Sanitize output path - prevent directory traversal
    output_dir = safe_output_dir(args.output)
    if output_dir is None:
        print("Error: Output path must be within current directory or home directory", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    try:
        normalized_url, parsed_url = normalize_url(args.url)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate filename from URL
    base_name = parsed_url.netloc.replace(".", "_")

    viewports = VIEWPORTS.keys() if args.all else [args.viewport]
    # With --json, stdout carries the JSON only; progress goes to stderr.
    progress = sys.stderr if args.json else sys.stdout
    captures = []

    for viewport in viewports:
        filename = f"{base_name}_{viewport}.png"
        output_path = os.path.join(output_dir, filename)

        print(f"Capturing {viewport} screenshot...", file=progress)
        result = capture_screenshot(
            normalized_url,
            output_path,
            viewport=viewport,
            full_page=args.full,
            timeout=args.timeout,
            scroll_through=not args.no_scroll,
            hide_overlays=args.hide_overlays,
        )
        captures.append(result)

        if result.get("scroll_timed_out"):
            print(
                "  scroll-through timed out: the page stopped answering, "
                "lazy content may be missing",
                file=progress,
            )
        if result["success"]:
            print(f"  ✓ Saved to {output_path}", file=progress)
            if args.hide_overlays:
                print(
                    f"  --hide-overlays: {result.get('overlays_hidden') or 0} "
                    "floating element(s) hidden, this is not what a visitor sees",
                    file=progress,
                )
        else:
            print(f"  ✗ Failed: {result['error']}", file=progress)

    if args.json:
        print(json.dumps({"captures": captures}, indent=2, default=str))
        if not all(capture.get("success") for capture in captures):
            sys.exit(1)


if __name__ == "__main__":
    main()
