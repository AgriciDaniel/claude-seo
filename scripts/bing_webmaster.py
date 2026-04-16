#!/usr/bin/env python3
"""
Bing Webmaster Tools API client for Claude SEO.

Queries the Bing Webmaster API for inbound link data, referring domain counts,
and competitor backlink comparison. Free for verified site owners.

Usage:
    python bing_webmaster.py links https://example.com --json
    python bing_webmaster.py counts https://example.com --json
    python bing_webmaster.py compare https://example.com https://competitor.com --json
"""

import argparse
import json
import sys
import time
from typing import Optional
from urllib.parse import urlparse, quote

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

import os
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
try:
    from backlinks_auth import get_bing_api_key, get_bing_verified_sites, load_config
    from google_auth import validate_url
except ImportError:
    print("Error: backlinks_auth.py and google_auth.py required in scripts/", file=sys.stderr)
    sys.exit(1)

BING_API_BASE = "https://ssl.bing.com/webmaster/api.svc/json"

# Polite delay between requests
REQUEST_DELAY = 1
_last_request_time = 0


def _rate_limit():
    """Enforce polite 1-second delay between Bing API requests."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < REQUEST_DELAY and _last_request_time > 0:
        time.sleep(REQUEST_DELAY - elapsed)
    _last_request_time = time.time()


def _bing_request(endpoint: str, api_key: str, params: Optional[dict] = None,
                  method: str = "GET") -> dict:
    """
    Make a request to the Bing Webmaster API.

    Args:
        endpoint: API endpoint path (appended to BING_API_BASE).
        api_key: Bing Webmaster API key.
        params: Query parameters.
        method: HTTP method (GET or POST).

    Returns:
        Standard response dict.
    """
    _rate_limit()

    url = f"{BING_API_BASE}/{endpoint}"
    if params is None:
        params = {}
    params["apikey"] = api_key

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ClaudeSEO/1.8.0",
    }

    try:
        if method == "GET":
            response = requests.get(url, params=params, headers=headers, timeout=30)
        else:
            response = requests.post(url, params=params, headers=headers, timeout=30)

        if response.status_code == 401:
            return {
                "status": "error",
                "data": None,
                "error": "Invalid Bing Webmaster API key. Get one at https://www.bing.com/webmasters",
                "metadata": {"source": "bing_webmaster"},
            }

        if response.status_code == 403:
            return {
                "status": "error",
                "data": None,
                "error": "Access denied. Ensure the site is verified in Bing Webmaster Tools.",
                "metadata": {"source": "bing_webmaster"},
            }

        response.raise_for_status()

        # Bing API may return empty body for some endpoints
        if response.text.strip():
            result_data = response.json()
        else:
            result_data = {}

        return {
            "status": "success",
            "data": result_data,
            "error": None,
            "metadata": {
                "source": "bing_webmaster",
                "endpoint": endpoint,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "data": None,
            "error": "Request timed out after 30 seconds",
            "metadata": {"source": "bing_webmaster"},
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "data": None,
            "error": str(e),
            "metadata": {"source": "bing_webmaster"},
        }


def _normalize_site_url(url: str) -> str:
    """Normalize a site URL for Bing API (needs trailing slash for domains)."""
    if not url.startswith("http"):
        url = f"https://{url}"
    parsed = urlparse(url)
    # Bing expects: https://example.com/
    if not parsed.path or parsed.path == "/":
        return f"{parsed.scheme}://{parsed.netloc}/"
    return url


def get_link_details(site_url: str, api_key: str, page: int = 0) -> dict:
    """
    Get inbound link details for a verified site.

    Args:
        site_url: Verified site URL.
        api_key: Bing API key.
        page: Page number for pagination (0-based).

    Returns:
        Standard response dict with link data.
    """
    normalized = _normalize_site_url(site_url)
    endpoint = "GetLinkDetails"
    params = {
        "siteUrl": normalized,
        "page": page,
    }

    result = _bing_request(endpoint, api_key, params)

    if result["status"] == "success" and result["data"]:
        raw_data = result["data"]
        links = []
        link_list = raw_data if isinstance(raw_data, list) else raw_data.get("d", raw_data.get("results", []))
        if isinstance(link_list, list):
            for item in link_list:
                links.append({
                    "source_url": item.get("SourceUrl", item.get("sourceUrl", "")),
                    "target_url": item.get("TargetUrl", item.get("targetUrl", "")),
                    "anchor_text": item.get("AnchorText", item.get("anchorText", "")),
                    "date_discovered": item.get("DateDiscovered", item.get("dateDiscovered", "")),
                })
        result["data"] = {
            "site_url": site_url,
            "page": page,
            "total_returned": len(links),
            "links": links,
        }

    return result


def get_link_counts(site_url: str, api_key: str) -> dict:
    """
    Get total backlink and referring domain counts for a site.

    Args:
        site_url: Site URL to query.
        api_key: Bing API key.

    Returns:
        Standard response dict with count data.
    """
    normalized = _normalize_site_url(site_url)
    endpoint = "GetUrlTrafficInfo"
    params = {"siteUrl": normalized}

    result = _bing_request(endpoint, api_key, params)

    # Also get link details page 0 for basic counts
    links_result = get_link_details(site_url, api_key, page=0)

    if result["status"] == "success":
        raw = result["data"] or {}
        link_count = 0
        if links_result["status"] == "success" and links_result["data"]:
            link_count = links_result["data"].get("total_returned", 0)

        result["data"] = {
            "site_url": site_url,
            "total_links_sample": link_count,
            "traffic_info": raw,
            "note": "Link counts are sampled from Bing's index. For comprehensive data, use Moz API or DataForSEO.",
        }

    return result


def compare_links(site_url: str, competitor_url: str, api_key: str) -> dict:
    """
    Compare backlink profiles between your site and a competitor.

    This is Bing's unique free feature not available in other free tools.

    Args:
        site_url: Your verified site URL.
        competitor_url: Competitor URL to compare against.
        api_key: Bing API key.

    Returns:
        Standard response dict with comparison data.
    """
    # Get links for both sites
    own_result = get_link_details(site_url, api_key)
    competitor_result = get_link_details(competitor_url, api_key)

    own_links = []
    competitor_links = []
    own_domains = set()
    competitor_domains = set()

    if own_result["status"] == "success" and own_result["data"]:
        own_links = own_result["data"].get("links", [])
        for link in own_links:
            source = link.get("source_url", "")
            if source:
                parsed = urlparse(source)
                own_domains.add(parsed.netloc)

    if competitor_result["status"] == "success" and competitor_result["data"]:
        competitor_links = competitor_result["data"].get("links", [])
        for link in competitor_links:
            source = link.get("source_url", "")
            if source:
                parsed = urlparse(source)
                competitor_domains.add(parsed.netloc)

    # Gap analysis
    gap_domains = competitor_domains - own_domains  # Competitor has, you don't
    shared_domains = own_domains & competitor_domains
    unique_domains = own_domains - competitor_domains  # You have, competitor doesn't

    return {
        "status": "success",
        "data": {
            "site_url": site_url,
            "competitor_url": competitor_url,
            "your_linking_domains": len(own_domains),
            "competitor_linking_domains": len(competitor_domains),
            "gap_domains": sorted(list(gap_domains))[:50],
            "shared_domains": sorted(list(shared_domains))[:50],
            "unique_to_you": sorted(list(unique_domains))[:50],
            "gap_count": len(gap_domains),
            "shared_count": len(shared_domains),
            "unique_count": len(unique_domains),
            "note": "Based on Bing's index sample. Bing indexes ~15% of the web.",
        },
        "error": None,
        "metadata": {
            "source": "bing_webmaster",
            "comparison": True,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Bing Webmaster Tools API client for Claude SEO"
    )
    parser.add_argument(
        "command",
        choices=["links", "counts", "compare"],
        help="API command: links (inbound), counts (totals), compare (vs competitor)",
    )
    parser.add_argument(
        "url",
        help="Target site URL",
    )
    parser.add_argument(
        "competitor_url",
        nargs="?",
        default=None,
        help="Competitor URL (required for 'compare' command)",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=0,
        help="Page number for pagination (default: 0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    # Validate URLs
    target = args.url
    if target.startswith("http") and not validate_url(target):
        result = {
            "status": "error",
            "data": None,
            "error": f"Invalid or blocked URL: {target}",
            "metadata": {"source": "bing_webmaster"},
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if args.command == "compare" and not args.competitor_url:
        print("Error: compare command requires a competitor URL", file=sys.stderr)
        sys.exit(1)

    # Validate competitor URL if provided (SSRF protection)
    if args.competitor_url:
        comp = args.competitor_url
        if comp.startswith("http") and not validate_url(comp):
            result = {
                "status": "error",
                "data": None,
                "error": f"Invalid or blocked competitor URL: {comp}",
                "metadata": {"source": "bing_webmaster"},
            }
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

    # Get API key
    api_key = get_bing_api_key()
    if not api_key:
        result = {
            "status": "error",
            "data": None,
            "error": "No Bing Webmaster API key configured. Run: python scripts/backlinks_auth.py --setup",
            "metadata": {"source": "bing_webmaster"},
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    # Warn if site not in verified list
    verified = get_bing_verified_sites()
    parsed_target = urlparse(target if target.startswith("http") else f"https://{target}")
    if verified and parsed_target.netloc not in verified and parsed_target.netloc.replace("www.", "") not in verified:
        print(f"Warning: {parsed_target.netloc} not in bing_verified_sites config. API may return limited data.",
              file=sys.stderr)

    # Execute command
    if args.command == "links":
        result = get_link_details(target, api_key, page=args.page)
    elif args.command == "counts":
        result = get_link_counts(target, api_key)
    elif args.command == "compare":
        result = compare_links(target, args.competitor_url, api_key)
    else:
        result = {"status": "error", "data": None, "error": f"Unknown command: {args.command}"}

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["status"] == "success" and result["data"]:
            data = result["data"]
            if args.command == "links":
                print(f"Bing Inbound Links for: {data.get('site_url', target)} ({data.get('total_returned', 0)} returned)")
                for link in data.get("links", [])[:20]:
                    anchor = link.get("anchor_text", "")[:40]
                    print(f"  {link.get('source_url', '?'):60s} [{anchor}]")
            elif args.command == "counts":
                print(f"Bing Link Counts for: {data.get('site_url', target)}")
                print(f"  Sample links found: {data.get('total_links_sample', 'N/A')}")
            elif args.command == "compare":
                print(f"Backlink Gap: {data.get('site_url', '')} vs {data.get('competitor_url', '')}")
                print(f"  Your linking domains:       {data.get('your_linking_domains', 0)}")
                print(f"  Competitor linking domains:  {data.get('competitor_linking_domains', 0)}")
                print(f"  Gap (they have, you don't): {data.get('gap_count', 0)}")
                print(f"  Shared:                     {data.get('shared_count', 0)}")
                print(f"  Unique to you:              {data.get('unique_count', 0)}")
                if data.get("gap_domains"):
                    print(f"\n  Top gap domains:")
                    for d in data["gap_domains"][:10]:
                        print(f"    {d}")
        elif result.get("error"):
            print(f"Error: {result['error']}", file=sys.stderr)


if __name__ == "__main__":
    main()
