#!/usr/bin/env python3
"""
Fetch a web page with proper headers and error handling.

Usage:
    python fetch_page.py https://example.com
    python fetch_page.py https://example.com --output page.html
    python fetch_page.py https://example.com --extract
    python fetch_page.py https://example.com --extract -o extracted.txt
"""

import argparse
import ipaddress
import json
import re
import socket
import sys
from typing import Optional
from urllib.parse import urlparse, urljoin

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


def extract_seo_content(html: str, url: str) -> str:
    """
    Extract SEO-relevant content from raw HTML.

    Strips ~95% of bloat (scripts, styles, WordPress markup) while preserving
    all data needed for SEO analysis: meta tags, schema, headings, body text,
    images, and internal links.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "Error: beautifulsoup4 required for --extract. Install with: pip install beautifulsoup4"

    soup = BeautifulSoup(html, "html.parser")
    parsed_url = urlparse(url)
    base_domain = parsed_url.netloc
    sections = []

    # --- 1. Meta Tags ---
    meta_lines = []
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        meta_lines.append(f"  title: {title_tag.string.strip()}")

    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        meta_lines.append(f"  lang: {html_tag['lang']}")

    meta_names = ["description", "robots", "viewport", "author", "generator"]
    for name in meta_names:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            meta_lines.append(f"  {name}: {tag['content']}")

    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        meta_lines.append(f"  canonical: {canonical['href']}")

    # OG tags
    for og in soup.find_all("meta", attrs={"property": re.compile(r"^og:")}):
        if og.get("content"):
            meta_lines.append(f"  {og['property']}: {og['content']}")

    # Twitter cards
    for tw in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")}):
        if tw.get("content"):
            meta_lines.append(f"  {tw['name']}: {tw['content']}")

    # Hreflang
    for hl in soup.find_all("link", attrs={"rel": "alternate", "hreflang": True}):
        meta_lines.append(f"  hreflang[{hl['hreflang']}]: {hl.get('href', '')}")

    if meta_lines:
        sections.append("=== META TAGS ===\n" + "\n".join(meta_lines))

    # --- 2. Schema JSON-LD ---
    schema_blocks = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if script.string:
            try:
                data = json.loads(script.string)
                schema_blocks.append(json.dumps(data, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                schema_blocks.append(script.string.strip())
    if schema_blocks:
        sections.append("=== SCHEMA JSON-LD ===\n" + "\n---\n".join(schema_blocks))

    # --- Remove noise before content extraction ---
    for tag in soup.find_all(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    # --- 3. Heading Structure ---
    heading_lines = []
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            text = h.get_text(separator=" ", strip=True)
            if text:
                indent = "  " * (level - 1)
                heading_lines.append(f"{indent}h{level}: {text}")
    if heading_lines:
        sections.append("=== HEADINGS ===\n" + "\n".join(heading_lines))

    # --- 4. Body Content ---
    content_container = (
        soup.find("main")
        or soup.find("article")
        or soup.find(id="content")
        or soup.find(class_="content")
        or soup.find("body")
    )
    content_lines = []
    if content_container:
        for el in content_container.find_all(
            ["p", "li", "td", "blockquote", "figcaption"]
        ):
            text = el.get_text(separator=" ", strip=True)
            if len(text) >= 20:
                content_lines.append(text)
    if content_lines:
        sections.append("=== BODY CONTENT ===\n" + "\n".join(content_lines))

    # --- 5. Images ---
    seen_srcs = set()
    image_lines = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src in seen_srcs:
            continue
        seen_srcs.add(src)
        parts = [f"src={src}"]
        alt = img.get("alt", "")
        parts.append(f'alt="{alt}"')
        for attr in ("width", "height", "loading"):
            val = img.get(attr)
            if val:
                parts.append(f"{attr}={val}")
        image_lines.append("  " + " | ".join(parts))
    if image_lines:
        sections.append("=== IMAGES ===\n" + "\n".join(image_lines))

    # --- 6. Internal Links ---
    seen_hrefs = set()
    link_lines = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Resolve relative URLs
        full_url = urljoin(url, href)
        parsed_link = urlparse(full_url)
        # Only internal links
        if parsed_link.netloc and parsed_link.netloc != base_domain:
            continue
        # Normalize
        normalized = parsed_link.path.rstrip("/") or "/"
        if normalized in seen_hrefs:
            continue
        seen_hrefs.add(normalized)
        anchor = a.get_text(separator=" ", strip=True)
        if anchor:
            link_lines.append(f"  {anchor} -> {normalized}")
        else:
            link_lines.append(f"  [no text] -> {normalized}")
    if link_lines:
        sections.append("=== INTERNAL LINKS ===\n" + "\n".join(link_lines))

    return "\n\n".join(sections)


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
        "--extract",
        action="store_true",
        help=(
            "Extract SEO-relevant content instead of raw HTML. "
            "Returns meta tags, schema JSON-LD, headings, body text, images, "
            "and internal links. ~95%% size reduction."
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

    output = result["content"]
    if args.extract:
        output = extract_seo_content(result["content"], result["url"])

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(output)

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
