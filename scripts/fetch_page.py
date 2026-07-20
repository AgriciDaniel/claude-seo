#!/usr/bin/env python3
"""
Fetch a web page with proper headers and error handling.

In v2.0.0 the raw-HTTP path delegates to url_safety.safe_requests_get for
DNS-rebinding protection, and a --render flag delegates to render_page for
SPA-aware fetching.

Usage:
    python fetch_page.py https://example.com
    python fetch_page.py https://example.com --output page.html
    python fetch_page.py https://example.com --render auto    # SPA-aware
    python fetch_page.py https://example.com --render always  # force render
"""

from __future__ import annotations

import argparse
import os
import re
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
from url_safety import URLSafetyError, safe_requests_session, validate_url_strict  # noqa: E402


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.7871.114 Safari/537.36 ClaudeSEO/2.0"
)

# Googlebot UA for prerender/dynamic rendering detection.
# Prerender services (Prerender.io, Rendertron) serve fully rendered HTML to
# Googlebot but raw JS shells to other UAs. Comparing response sizes between
# DEFAULT_USER_AGENT and GOOGLEBOT_USER_AGENT reveals whether a site uses
# dynamic rendering, a key signal for SPA detection.
GOOGLEBOT_USER_AGENT = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

_CONTENT_TYPE_CHARSET_RE = re.compile(r"charset\s*=\s*['\"]?([^;,'\"\s>]+)", re.IGNORECASE)
_META_CHARSET_RE = re.compile(
    r"<meta[^>]+charset\s*=\s*['\"]?([^;,'\"\s/>]+)",
    re.IGNORECASE,
)
_BOMS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


def _decode_bytes(raw: bytes, encoding: str) -> str:
    try:
        return raw.decode(encoding, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _extract_charset_from_content_type(content_type: str) -> str | None:
    match = _CONTENT_TYPE_CHARSET_RE.search(content_type or "")
    return match.group(1).strip() if match else None


def _extract_meta_charset(raw: bytes) -> str | None:
    head = raw[:4096].decode("ascii", errors="ignore")
    match = _META_CHARSET_RE.search(head)
    return match.group(1).strip() if match else None


def _decode_response_content(response) -> str:
    """Decode HTTP bytes deterministically for stable SEO snapshots."""
    raw = response.content or b""
    for marker, encoding in _BOMS:
        if raw.startswith(marker):
            return _decode_bytes(raw, encoding)

    content_type = response.headers.get("Content-Type", "") if response.headers else ""
    charset = _extract_charset_from_content_type(content_type)
    if charset:
        return _decode_bytes(raw, charset)

    charset = _extract_meta_charset(raw)
    if charset:
        return _decode_bytes(raw, charset)

    return raw.decode("utf-8", errors="replace")


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


def main():
    parser = argparse.ArgumentParser(description="Fetch a web page for SEO analysis")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--output", "-o", help="Output file path")
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
