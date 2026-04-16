#!/usr/bin/env python3
"""
Backlink verification crawler for Claude SEO.

Verifies whether known backlinks still exist by fetching source pages and
checking if the target URL appears in their outbound links. Uses HTTP HEAD
for fast existence checks and full GET + HTML parsing for link verification.

Usage:
    python verify_backlinks.py --target https://example.com --links links.json --json
    python verify_backlinks.py --target https://example.com --links links.json --head-only --json
    echo '[{"source_url": "https://blog.example.org/post"}]' | python verify_backlinks.py --target https://example.com --links - --json
"""

import argparse
import json
import sys
import time
from typing import Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

import os
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
try:
    from fetch_page import fetch_page
    from parse_html import parse_html
    from google_auth import validate_url
except ImportError as e:
    print(f"Error: Required scripts not found in scripts/: {e}", file=sys.stderr)
    sys.exit(1)

# Polite crawling: delay between requests to same domain
DOMAIN_DELAY = 1.0
_domain_last_request = {}


def _polite_delay(domain: str):
    """Wait between requests to the same domain to be a polite crawler."""
    now = time.time()
    last = _domain_last_request.get(domain, 0)
    elapsed = now - last
    if elapsed < DOMAIN_DELAY and last > 0:
        time.sleep(DOMAIN_DELAY - elapsed)
    _domain_last_request[domain] = time.time()


def _head_check(url: str, timeout: int = 15) -> dict:
    """
    Quick HTTP HEAD check to see if a page exists.

    Returns:
        Dict with status_code, exists (bool), redirect_url (if redirected).
    """
    try:
        resp = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "ClaudeSEO/1.8.0 BacklinkVerifier"},
        )
        return {
            "status_code": resp.status_code,
            "exists": resp.status_code == 200,
            "redirect_url": str(resp.url) if str(resp.url) != url else None,
            "error": None,
        }
    except requests.exceptions.Timeout:
        return {"status_code": None, "exists": False, "redirect_url": None, "error": "timeout"}
    except requests.exceptions.RequestException as e:
        return {"status_code": None, "exists": False, "redirect_url": None, "error": str(e)}


def _normalize_url(url: str) -> str:
    """Normalize a URL for comparison (lowercase, strip trailing slash, strip fragment)."""
    parsed = urlparse(url.lower())
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def verify_single_backlink(source_url: str, target_url: str,
                            head_only: bool = False, timeout: int = 30) -> dict:
    """
    Verify a single backlink by checking if target_url appears on source_url page.

    Args:
        source_url: The page that should contain the backlink.
        target_url: The URL that should be linked to.
        head_only: If True, only check page existence (no link verification).
        timeout: Request timeout.

    Returns:
        Verification result dict.
    """
    result = {
        "source_url": source_url,
        "target_url": target_url,
        "status": "unknown",
        "http_status": None,
        "target_found": False,
        "anchor_text": None,
        "rel_attributes": [],
        "link_context": None,
        "error": None,
    }

    # SSRF protection
    if not validate_url(source_url):
        result["status"] = "error"
        result["error"] = "Source URL blocked by SSRF protection"
        return result

    source_domain = urlparse(source_url).netloc
    _polite_delay(source_domain)

    # Step 1: HEAD check
    head_result = _head_check(source_url, timeout=min(timeout, 15))
    result["http_status"] = head_result["status_code"]

    if not head_result["exists"]:
        if head_result["status_code"] == 404:
            result["status"] = "lost"
        elif head_result["status_code"] and 300 <= head_result["status_code"] < 400:
            result["status"] = "moved"
            result["redirect_url"] = head_result.get("redirect_url")
        elif head_result["error"]:
            result["status"] = "error"
            result["error"] = head_result["error"]
        else:
            result["status"] = "error"
            result["http_status"] = head_result["status_code"]
        return result

    if head_only:
        result["status"] = "exists"
        result["target_found"] = None  # Unknown without full check
        return result

    # Step 2: Full GET + parse
    _polite_delay(source_domain)
    page_data = fetch_page(source_url, timeout=timeout)

    if page_data.get("error"):
        result["status"] = "error"
        result["error"] = page_data["error"]
        result["http_status"] = page_data.get("status_code")
        return result

    if not page_data.get("content"):
        result["status"] = "error"
        result["error"] = "Page returned no content"
        return result

    result["http_status"] = page_data.get("status_code", 200)

    # Step 3: Parse HTML and find target link
    parsed = parse_html(page_data["content"], base_url=source_url)
    all_links = parsed.get("links", {})
    external_links = all_links.get("external", [])
    internal_links = all_links.get("internal", [])
    all_page_links = external_links + internal_links

    normalized_target = _normalize_url(target_url)
    raw_target_host = urlparse(target_url).netloc.lower()
    target_domain = raw_target_host[4:] if raw_target_host.startswith("www.") else raw_target_host

    for link in all_page_links:
        link_href = link.get("href", "")
        if not link_href:
            continue

        normalized_href = _normalize_url(link_href)
        raw_link_host = urlparse(link_href).netloc.lower()
        link_domain = raw_link_host[4:] if raw_link_host.startswith("www.") else raw_link_host

        # Match: exact URL, same domain, or subdomain of target
        if normalized_href == normalized_target:
            match_type = "exact_url"
        elif link_domain == target_domain:
            match_type = "domain_match"
        elif link_domain.endswith(f".{target_domain}"):
            match_type = "subdomain_match"
        else:
            continue

        result["target_found"] = True
        result["match_type"] = match_type
        result["anchor_text"] = link.get("text", "").strip()[:200]
        rel = link.get("rel", "")
        if rel:
            result["rel_attributes"] = rel.split() if isinstance(rel, str) else rel
        else:
            result["rel_attributes"] = ["follow"]  # No rel = dofollow
        result["status"] = "verified"
        return result

    # Target not found — check if page is JS-rendered (false negative risk)
    content = page_data.get("content", "")
    js_indicators = [
        '<div id="root"', '<div id="app"', '<div id="__next"',
        "__NEXT_DATA__", "__nuxt", "ng-app=", "ng-version=",
        "react-root", "data-reactroot", "_reactListening",
    ]
    content_lower = content.lower()
    is_likely_js = any(ind.lower() in content_lower for ind in js_indicators)

    # Also flag if HTML is large but visible text is tiny (JS shell)
    word_count = parsed.get("word_count", 0)
    if isinstance(word_count, str):
        word_count = 0
    low_text_ratio = len(content) > 5000 and word_count < 50

    if is_likely_js or low_text_ratio:
        result["status"] = "unverifiable_js"
        result["target_found"] = None
        result["error"] = "Page appears JS-rendered; link may exist but cannot be confirmed via HTTP GET"
        return result

    result["status"] = "link_removed"
    result["target_found"] = False
    return result


def verify_backlinks(target_url: str, links: list, head_only: bool = False,
                      timeout: int = 30) -> dict:
    """
    Verify a batch of backlinks.

    Args:
        target_url: The URL that should be linked to.
        links: List of dicts with 'source_url' and optional 'expected_anchor'.
        head_only: Only check page existence.
        timeout: Per-request timeout.

    Returns:
        Standard response dict with verification results and summary.
    """
    results = []
    summary = {"total": 0, "verified": 0, "lost": 0, "moved": 0,
               "link_removed": 0, "unverifiable_js": 0, "exists": 0, "error": 0}

    for item in links:
        source_url = item.get("source_url", "")
        if not source_url:
            continue

        summary["total"] += 1
        result = verify_single_backlink(source_url, target_url,
                                         head_only=head_only, timeout=timeout)
        results.append(result)

        status = result.get("status", "error")
        if status in summary:
            summary[status] += 1
        else:
            summary["error"] += 1

    return {
        "status": "success",
        "data": {
            "target_url": target_url,
            "summary": summary,
            "results": results,
        },
        "error": None,
        "metadata": {
            "source": "verify_crawler",
            "head_only": head_only,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backlink verification crawler for Claude SEO"
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Target URL to verify backlinks for",
    )
    parser.add_argument(
        "--links",
        required=True,
        help="JSON file with backlink list (or '-' for stdin). Format: [{\"source_url\": \"...\"}]",
    )
    parser.add_argument(
        "--head-only",
        action="store_true",
        help="Only check page existence (faster, no link verification)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Per-request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    # Validate target URL
    if not validate_url(args.target):
        result = {
            "status": "error",
            "data": None,
            "error": f"Invalid or blocked target URL: {args.target}",
            "metadata": {"source": "verify_crawler"},
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    # Load links
    try:
        if args.links == "-":
            links = json.load(sys.stdin)
        else:
            with open(args.links, "r") as f:
                links = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        result = {
            "status": "error",
            "data": None,
            "error": f"Could not load links file: {e}",
            "metadata": {"source": "verify_crawler"},
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(links, list):
        links = [links]

    # Run verification
    result = verify_backlinks(
        target_url=args.target,
        links=links,
        head_only=args.head_only,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        data = result.get("data", {})
        summary = data.get("summary", {})
        print(f"Backlink Verification: {data.get('target_url', args.target)}")
        print(f"  Total checked:  {summary.get('total', 0)}")
        print(f"  Verified:       {summary.get('verified', 0)}")
        print(f"  Lost (404):     {summary.get('lost', 0)}")
        print(f"  Moved (3xx):    {summary.get('moved', 0)}")
        print(f"  Link removed:   {summary.get('link_removed', 0)}")
        print(f"  Errors:         {summary.get('error', 0)}")
        if args.head_only:
            print(f"  Exists (HEAD):  {summary.get('exists', 0)}")
        print()
        for r in data.get("results", []):
            status = r.get("status", "?")
            anchor = r.get("anchor_text", "")
            anchor_display = f" [{anchor[:30]}]" if anchor else ""
            rel = r.get("rel_attributes", [])
            rel_display = f" rel={','.join(rel)}" if rel and rel != ["follow"] else ""
            print(f"  [{status:13s}] {r.get('source_url', '?')}{anchor_display}{rel_display}")


if __name__ == "__main__":
    main()
