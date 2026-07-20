#!/usr/bin/env python3
"""
Capture screenshots of web pages using Playwright.

In v2.0.0 the SSRF pre-flight check is delegated to url_safety, and a
Playwright route() handler aborts any subresource request whose hostname
resolves to a non-public IP (defence in depth against DNS rebinding
inside Chromium's resolver).

Usage:
    python capture_screenshot.py https://example.com
    python capture_screenshot.py https://example.com --viewport mobile
    python capture_screenshot.py https://example.com --output screenshots/
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import ParseResult, urlparse

try:
    from playwright.sync_api import (
        sync_playwright,
        TimeoutError as PlaywrightTimeout,
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
from url_safety import (  # noqa: E402  (sys.path massage above is intentional)
    URLSafetyError,
    make_safe_playwright_route_handler,
    validate_url_strict,
)


VIEWPORTS = {
    "desktop": {"width": 1920, "height": 1080},
    "laptop": {"width": 1366, "height": 768},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 375, "height": 812},
}


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


def capture_screenshot(
    url: str,
    output_path: str,
    viewport: str = "desktop",
    full_page: bool = False,
    timeout: int = 30000,
) -> dict:
    """
    Capture a screenshot of a web page.

    Args:
        url: URL to capture
        output_path: Output file path
        viewport: Viewport preset (desktop, laptop, tablet, mobile)
        full_page: Whether to capture full page or just viewport
        timeout: Page load timeout in milliseconds

    Returns:
        Dictionary with capture results
    """
    result = {
        "url": url,
        "output": output_path,
        "viewport": viewport,
        "success": False,
        "error": None,
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

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                device_scale_factor=2 if viewport == "mobile" else 1,
            )
            page = context.new_page()

            # Defence in depth: abort any subresource that lands on a
            # private IP even after Chromium re-resolves DNS.
            page.route("**/*", route_handler)

            # Navigate and wait for network idle
            page.goto(url, wait_until="networkidle", timeout=timeout)

            # Wait a bit more for any lazy-loaded content
            page.wait_for_timeout(1000)

            # Capture screenshot
            page.screenshot(path=output_path, full_page=full_page)

            result["success"] = True
            browser.close()

    except PlaywrightTimeout:
        result["error"] = f"Page load timed out after {timeout}ms"
    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="Capture web page screenshots")
    parser.add_argument("url", help="URL to capture")
    parser.add_argument("--output", "-o", default="screenshots", help="Output directory")
    parser.add_argument("--viewport", "-v", default="desktop", choices=VIEWPORTS.keys())
    parser.add_argument("--all", "-a", action="store_true", help="Capture all viewports")
    parser.add_argument("--full", "-f", action="store_true", help="Capture full page")
    parser.add_argument("--timeout", "-t", type=int, default=30000, help="Timeout in ms")

    args = parser.parse_args()

    # Sanitize output path - prevent directory traversal
    output_dir = os.path.realpath(args.output)
    cwd = os.getcwd()
    home = os.path.expanduser("~")
    if not (output_dir.startswith(cwd) or output_dir.startswith(home)):
        print("Error: Output path must be within current directory or home directory", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    os.makedirs(args.output, exist_ok=True)

    try:
        normalized_url, parsed_url = normalize_url(args.url)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate filename from URL
    base_name = parsed_url.netloc.replace(".", "_")

    viewports = VIEWPORTS.keys() if args.all else [args.viewport]

    for viewport in viewports:
        filename = f"{base_name}_{viewport}.png"
        output_path = os.path.join(args.output, filename)

        print(f"Capturing {viewport} screenshot...")
        result = capture_screenshot(
            normalized_url,
            output_path,
            viewport=viewport,
            full_page=args.full,
            timeout=args.timeout,
        )

        if result["success"]:
            print(f"  ✓ Saved to {output_path}")
        else:
            print(f"  ✗ Failed: {result['error']}")


if __name__ == "__main__":
    main()
