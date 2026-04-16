#!/usr/bin/env python3
"""
Fetch a web page with proper headers and error handling.

Usage:
    python fetch_page.py https://example.com
    python fetch_page.py https://example.com --output page.html
"""

import argparse
import ipaddress
import socket
import sys
from typing import Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 ClaudeSEO/1.2"
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


def fetch_page(
    url: str,
    timeout: int = 30,
    follow_redirects: bool = True,
    max_redirects: int = 5,
    user_agent: Optional[str] = None,
) -> dict:
    """
    Fetch a web page and return response details.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds
        follow_redirects: Whether to follow redirects
        max_redirects: Maximum number of redirects to follow

    Returns:
        Dictionary with:
            - url: Final URL after redirects
            - status_code: HTTP status code
            - content: Response body
            - headers: Response headers
            - redirect_chain: List of redirect URLs
            - error: Error message if failed
    """
    result = {
        "url": url,
        "status_code": None,
        "content": None,
        "headers": {},
        "redirect_chain": [],
        "redirect_details": [],
        "error": None,
    }

    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        result["error"] = f"Invalid URL scheme: {parsed.scheme}"
        return result

    # SSRF prevention: block private/internal IPs
    try:
        resolved_ip = socket.gethostbyname(parsed.hostname)
        ip = ipaddress.ip_address(resolved_ip)
        if ip.is_private or ip.is_loopback or ip.is_reserved:
            result["error"] = f"Blocked: URL resolves to private/internal IP ({resolved_ip})"
            return result
    except (socket.gaierror, ValueError):
        pass  # DNS resolution failure handled by requests below

    try:
        session = requests.Session()
        session.max_redirects = max_redirects

        headers = dict(DEFAULT_HEADERS)
        if user_agent:
            headers["User-Agent"] = user_agent

        response = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=follow_redirects,
        )

        result["url"] = response.url
        result["status_code"] = response.status_code
        result["content"] = response.text
        result["headers"] = dict(response.headers)

        # Track redirect chain with status codes
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

    args = parser.parse_args()

    ua = args.user_agent
    if args.googlebot:
        ua = GOOGLEBOT_USER_AGENT

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
