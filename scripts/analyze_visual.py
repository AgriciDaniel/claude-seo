#!/usr/bin/env python3
"""
Analyze visual aspects of a web page using Playwright.

Chromium is launched through browser_proxy.guarded_chromium: sandboxed where
the host can start the Chromium sandbox, with every connection forced through
a local proxy that refuses non-public destinations, redirect hops included.
Where the sandbox cannot start (Ubuntu 23.10 and later, most containers,
root) the browser runs without it, with a warning on stderr and
"sandbox": false in the result. CLAUDE_SEO_CHROMIUM_REQUIRE_SANDBOX=1 makes
that an error; CLAUDE_SEO_CHROMIUM_NO_SANDBOX=1 skips the sandbox attempt.

Usage:
    python analyze_visual.py https://example.com
"""

import argparse
import json
import os
import sys
from urllib.parse import ParseResult, urlparse

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright required. Install with: pip install playwright && playwright install chromium")
    sys.exit(1)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from browser_proxy import (  # noqa: E402
    PageNotLoadedError,
    chromium_sandboxed,
    guarded_chromium,
    require_public_page,
)
from url_safety import (  # noqa: E402  (sys.path massage above is intentional)
    URLSafetyError,
    make_safe_playwright_route_handler,
    new_guarded_context,
    validate_url_strict,
)


def normalize_url(url: str) -> tuple[str, ParseResult]:
    """Normalize URL and return (url, parsed_url)."""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise ValueError("Invalid URL: missing hostname")

    return url, parsed


def analyze_visual(url: str, timeout: int = 30000) -> dict:
    """
    Analyze visual aspects of a web page.

    Args:
        url: URL to analyze
        timeout: Page load timeout in milliseconds

    Returns:
        Dictionary with visual analysis results
    """
    result = {
        "url": url,
        "above_fold": {
            "h1_visible": False,
            "cta_visible": False,
            "hero_image": None,
        },
        "mobile": {
            "viewport_meta": False,
            "horizontal_scroll": False,
            "touch_targets_ok": True,
        },
        "layout": {
            "overlapping_elements": [],
            "text_overflow": [],
        },
        "fonts": {
            "base_size": None,
            "readable": True,
        },
        # True or False once a browser was launched (False: no Chromium
        # sandbox on this system); None when none was.
        "sandbox": None,
        "error": None,
    }

    try:
        url, _parsed = normalize_url(url)
        result["url"] = url
    except ValueError as e:
        result["error"] = str(e)
        return result

    try:
        url, _pinned_ip = validate_url_strict(url)
        result["url"] = url
    except URLSafetyError as e:
        result["error"] = f"url_safety: {e}"
        return result

    route_handler = make_safe_playwright_route_handler()

    try:
        with sync_playwright() as p, guarded_chromium(p.chromium, url) as browser:
            result["sandbox"] = chromium_sandboxed(browser)

            # Desktop analysis
            desktop = new_guarded_context(browser, route_handler, viewport={"width": 1920, "height": 1080})
            page = desktop.new_page()
            page.route("**/*", route_handler)
            page.goto(url, wait_until="networkidle", timeout=timeout)
            require_public_page(page)

            # Check H1 visibility above fold
            h1 = page.query_selector("h1")
            if h1:
                box = h1.bounding_box()
                if box and box["y"] < 1080:
                    result["above_fold"]["h1_visible"] = True

            # Check for CTA buttons above fold
            cta_selectors = [
                "a[href*='signup']",
                "a[href*='contact']",
                "a[href*='demo']",
                "button:has-text('Get Started')",
                "button:has-text('Sign Up')",
                "button:has-text('Contact')",
                ".cta",
                "[class*='cta']",
            ]
            for selector in cta_selectors:
                try:
                    cta = page.query_selector(selector)
                    if cta:
                        box = cta.bounding_box()
                        if box and box["y"] < 1080:
                            result["above_fold"]["cta_visible"] = True
                            break
                except Exception:
                    pass

            # Check hero image
            hero_selectors = [
                ".hero img",
                "[class*='hero'] img",
                "header img",
                "main img:first-of-type",
            ]
            for selector in hero_selectors:
                try:
                    hero = page.query_selector(selector)
                    if hero:
                        src = hero.get_attribute("src")
                        if src:
                            result["above_fold"]["hero_image"] = src
                            break
                except Exception:
                    pass

            desktop.close()

            # Mobile analysis
            mobile = new_guarded_context(browser, route_handler, viewport={"width": 375, "height": 812})
            page = mobile.new_page()
            page.route("**/*", route_handler)
            page.goto(url, wait_until="networkidle", timeout=timeout)
            require_public_page(page)

            # Check viewport meta
            viewport_meta = page.query_selector('meta[name="viewport"]')
            result["mobile"]["viewport_meta"] = viewport_meta is not None

            # Check for horizontal scroll
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            viewport_width = page.evaluate("window.innerWidth")
            result["mobile"]["horizontal_scroll"] = scroll_width > viewport_width

            # Check font size
            base_font_size = page.evaluate("""
                () => {
                    const body = document.body;
                    const style = window.getComputedStyle(body);
                    return parseFloat(style.fontSize);
                }
            """)
            result["fonts"]["base_size"] = base_font_size
            result["fonts"]["readable"] = base_font_size >= 16

            mobile.close()

    except PlaywrightTimeout:
        result["error"] = f"Page load timed out after {timeout}ms"
    except URLSafetyError as e:
        # The browser ended on a non-public document (a refused redirect).
        result["error"] = f"url_safety: {e}"
    except PageNotLoadedError as e:
        result["error"] = f"Page did not load: {e}"
    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="Analyze visual aspects of a web page")
    parser.add_argument("url", help="URL to analyze")
    parser.add_argument("--timeout", "-t", type=int, default=30000, help="Timeout in ms")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    result = analyze_visual(args.url, timeout=args.timeout)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Visual Analysis Results")
        print("=" * 40)

        print("\nAbove the Fold:")
        print(f"  H1 Visible: {'✓' if result['above_fold']['h1_visible'] else '✗'}")
        print(f"  CTA Visible: {'✓' if result['above_fold']['cta_visible'] else '✗'}")
        print(f"  Hero Image: {result['above_fold']['hero_image'] or 'None found'}")

        print("\nMobile Responsiveness:")
        print(f"  Viewport Meta: {'✓' if result['mobile']['viewport_meta'] else '✗'}")
        print(f"  Horizontal Scroll: {'✗ (problem)' if result['mobile']['horizontal_scroll'] else '✓'}")

        print("\nTypography:")
        print(f"  Base Font Size: {result['fonts']['base_size']}px")
        print(f"  Readable (≥16px): {'✓' if result['fonts']['readable'] else '✗'}")

        if result["error"]:
            print(f"\nError: {result['error']}")


if __name__ == "__main__":
    main()
