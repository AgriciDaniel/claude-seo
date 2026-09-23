#!/usr/bin/env python3
"""
Fetch a web page with proper headers and error handling.

In v2.0.0 the raw-HTTP path delegates to url_safety.safe_requests_get for
DNS-rebinding protection, and a --render flag delegates to render_page for
SPA-aware fetching.

Usage:
    python fetch_page.py https://example.com
    python fetch_page.py https://example.com --output page.html
    python fetch_page.py https://example.com --json
    python fetch_page.py https://example.com --render auto    # SPA-aware
    python fetch_page.py https://example.com --render always  # force render
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from url_safety import (  # noqa: E402
    DEFAULT_REQUEST_HEADERS,
    URLSafetyError,
    decode_response_text,
    safe_requests_session,
    validate_url_strict,
)
from url_safety import DEFAULT_USER_AGENT as DEFAULT_USER_AGENT  # noqa: E402,F401

# DEFAULT_USER_AGENT and the header block now live in url_safety, the lower
# layer that both this script and the safe_requests_* helpers go through, so
# there is one place to change them. The name is re-exported above because
# fetch_page.DEFAULT_USER_AGENT was the public spelling before v2.3.0.

# Googlebot UA for prerender/dynamic rendering detection.
# Prerender services (Prerender.io, Rendertron) serve fully rendered HTML to
# Googlebot but raw JS shells to other UAs. Comparing response sizes between
# DEFAULT_USER_AGENT and GOOGLEBOT_USER_AGENT reveals whether a site uses
# dynamic rendering, a key signal for SPA detection.
GOOGLEBOT_USER_AGENT = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

# One source of truth with the safe_requests_* helpers. Accept-Language is
# absent by design: announcing en-US makes multi-locale sites serve their
# English variant, which corrupts hreflang and international audits.
DEFAULT_HEADERS = dict(DEFAULT_REQUEST_HEADERS)

# Response decoding lives in url_safety (decode_response_text) so every script
# that fetches through the safe helpers decodes the same way (issue #314).
_decode_response_content = decode_response_text


def fetch_page(
    url: str,
    timeout: int = 30,
    follow_redirects: bool = True,
    max_redirects: int = 5,
    user_agent: Optional[str] = None,
) -> dict:
    """
    Fetch a web page and return response details.

    SSRF protection is delegated to url_safety.validate_url_strict +
    safe_requests_session, which resolves DNS once, validates every A
    record against private/loopback/reserved ranges, and pins the
    connection so the resolver cannot rebind between checks.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds
        follow_redirects: Whether to follow redirects
        max_redirects: Maximum number of redirects to follow
        user_agent: Override the default User-Agent

    Returns:
        Dictionary with url, status_code, content, headers, redirect_chain,
        redirect_details, and error.
    """
    result: dict = {
        "url": url,
        "status_code": None,
        "content": None,
        "headers": {},
        "redirect_chain": [],
        "redirect_details": [],
        "error": None,
    }

    # Normalize scheme-less inputs (e.g. "example.com") before validation.
    if "://" not in url:
        url = f"https://{url}"

    try:
        norm_url, _pinned_ip = validate_url_strict(url)
    except URLSafetyError as exc:
        result["error"] = f"url_safety: {exc}"
        return result

    result["url"] = norm_url

    headers = dict(DEFAULT_HEADERS)
    if user_agent:
        headers["User-Agent"] = user_agent

    try:
        with safe_requests_session(norm_url) as session:
            session.max_redirects = max_redirects
            response = session.get(
                norm_url,
                headers=headers,
                timeout=timeout,
                allow_redirects=follow_redirects,
            )

        result["url"] = response.url
        result["status_code"] = response.status_code
        result["content"] = _decode_response_content(response)
        result["headers"] = dict(response.headers)

        if response.history:
            result["redirect_chain"] = [r.url for r in response.history]
            result["redirect_details"] = [
                {"url": r.url, "status_code": r.status_code}
                for r in response.history
            ]

    except requests.exceptions.Timeout:
        result["error"] = f"Request timed out after {timeout} seconds"
    except requests.exceptions.TooManyRedirects:
        result["error"] = f"Too many redirects (max {max_redirects})"
    except requests.exceptions.SSLError as e:
        result["error"] = f"SSL error: {e}"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"Connection error: {e}"
    except requests.exceptions.RequestException as e:
        result["error"] = f"Request failed: {e}"
    except URLSafetyError as e:
        # Raised if a redirect tries to land on a non-public IP and the
        # rebinding-pinned session is asked to chase it.
        result["error"] = f"url_safety: {e}"

    return result


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def _as_render_result(result: dict, *, mode_used: str) -> dict:
    """Map a raw ``fetch_page()`` result onto the ``render_page()`` contract.

    ``render_page._json_summary`` is written against the render_page result
    shape. Normalizing the raw-fetch result onto that same shape before
    calling it (rather than dumping the raw dict as-is) means ``--json``
    emits an identical key set whether or not ``--render`` was used, and the
    raw path gets ``--max-text`` truncation for free.
    """
    redirect_chain = result.get("redirect_details")
    if not redirect_chain:
        redirect_chain = [
            {"url": u, "status_code": None} for u in result.get("redirect_chain") or []
        ]
    return {
        "url": result.get("url"),
        "status_code": result.get("status_code"),
        "content": result.get("content"),
        "raw_content": result.get("content"),
        "is_spa": None,
        "extracted_text": None,
        "publication_date": None,
        "accessibility_tree": None,
        "accessibility_error": None,
        "accessibility_partial": False,
        "headers": result.get("headers", {}),
        "redirect_chain": redirect_chain,
        "console_errors": [],
        "render_diagnostics": [],
        "render_engine": None,
        "render_ms": None,
        "mode_used": mode_used,
        "error": result.get("error"),
    }


def _emit_json(result: dict, output: Optional[str], *, max_text: int = 0) -> None:
    """Emit a fetch result as JSON via ``render_page._json_summary``.

    Both the raw and rendered fetch paths are normalized onto the render_page
    result contract before this is called, so the emitted JSON has an
    identical key set (and honours ``--max-text``) regardless of ``--render``.
    """
    from render_page import _json_summary

    output_written = False
    if output and not result.get("error"):
        with open(output, "w", encoding="utf-8") as f:
            f.write(result.get("content") or "")
        output_written = True
    summary = _json_summary(result, max_text=max_text)
    summary["output_written"] = output_written
    print(json.dumps(summary, indent=2, default=str))
    sys.exit(1 if result.get("error") else 0)


def main():
    parser = argparse.ArgumentParser(description="Fetch a web page for SEO analysis")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--json", action="store_true", help="Emit full fetch result as JSON")
    parser.add_argument(
        "--max-text",
        type=_non_negative_int,
        default=0,
        help=(
            "maximum characters returned for each JSON content field "
            "(content, raw_content, extracted_text); 0 keeps full text "
            "(default: 0). Only applies with --json."
        ),
    )
    parser.add_argument("--timeout", "-t", type=int, default=30, help="Timeout in seconds")
    parser.add_argument("--no-redirects", action="store_true", help="Don't follow redirects")
    parser.add_argument("--user-agent", help="Custom User-Agent string")
    parser.add_argument(
        "--googlebot",
        action="store_true",
        help=(
            "Use Googlebot UA to detect dynamic rendering / prerender services. "
            "Compare response size with default UA to identify SPA prerender configuration."
        ),
    )
    parser.add_argument(
        "--render",
        choices=("auto", "always", "never"),
        default="never",
        help=(
            "Delegate to scripts/render_page.py for SPA-aware fetching. "
            "auto: render only when an SPA shell is detected. "
            "always: force headless render. "
            "never (default): raw HTTP only, preserves v1.x behaviour."
        ),
    )

    args = parser.parse_args()

    ua = args.user_agent
    if args.googlebot:
        ua = GOOGLEBOT_USER_AGENT

    if args.render != "never":
        # Delegate to render_page for SPA-aware fetching.
        from render_page import render_page as _render
        rendered = _render(
            args.url,
            mode=args.render,
            timeout_ms=args.timeout * 1000,
            user_agent=ua,
        )
        if args.json:
            _emit_json(rendered, args.output, max_text=args.max_text)
        if rendered["error"]:
            print(f"Error: {rendered['error']}", file=sys.stderr)
            sys.exit(1)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(rendered["content"] or "")
            print(f"Saved to {args.output}")
        else:
            print(rendered["content"])
        print(
            f"\nURL: {rendered['url']}\n"
            f"Status: {rendered['status_code']} | "
            f"render={rendered['mode_used']} | is_spa={rendered['is_spa']}",
            file=sys.stderr,
        )
        return

    result = fetch_page(
        args.url,
        timeout=args.timeout,
        follow_redirects=not args.no_redirects,
        user_agent=ua,
    )

    if args.json:
        _emit_json(
            _as_render_result(result, mode_used="raw"),
            args.output,
            max_text=args.max_text,
        )

    if result["error"]:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result["content"])
        print(f"Saved to {args.output}")
    else:
        print(result["content"])

    # Print metadata to stderr
    print(f"\nURL: {result['url']}", file=sys.stderr)
    print(f"Status: {result['status_code']}", file=sys.stderr)
    if result["redirect_details"]:
        for rd in result["redirect_details"]:
            print(f"  {rd['status_code']} -> {rd['url']}", file=sys.stderr)
        print(f"  {result['status_code']} -> {result['url']} (final)", file=sys.stderr)
    elif result["redirect_chain"]:
        print(f"Redirects: {' -> '.join(result['redirect_chain'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
