#!/usr/bin/env python3
"""
Bing Webmaster Tools API client for Claude SEO.

Queries the Bing Webmaster API for inbound link data, referring domain counts,
and comparison between properties accessible to the same API account.

Usage:
    python bing_webmaster.py links https://example.com --json
    python bing_webmaster.py counts https://example.com --json
    python bing_webmaster.py compare https://example.com https://competitor.com --json
"""

import argparse
import json
import os
import sys
import time
from typing import Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
try:
    from backlinks_auth import get_bing_api_key, get_bing_verified_sites
    from google_auth import validate_url
except ImportError:
    print("Error: backlinks_auth.py and google_auth.py required in scripts/", file=sys.stderr)
    sys.exit(1)

BING_API_BASE = "https://ssl.bing.com/webmaster/api.svc/json"
MAX_LINK_COUNT_PAGES = 10
MAX_TARGETS_TO_EXPAND = 10
MAX_URL_LINK_PAGES = 3

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
    request_params = dict(params or {})
    request_params["apikey"] = api_key

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ClaudeSEO/1.8.0",
    }

    try:
        if method == "GET":
            response = requests.get(url, params=request_params, headers=headers, timeout=30)
        else:
            response = requests.post(url, params=request_params, headers=headers, timeout=30)

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
            "error": f"Bing Webmaster request failed ({type(e).__name__})",
            "metadata": {"source": "bing_webmaster"},
        }


def _normalize_site_url(url: str) -> str:
    """Normalize a site URL for Bing API (needs trailing slash for domains)."""
    if not url.lower().startswith("http"):
        url = f"https://{url}"
    parsed = urlparse(url)
    # Bing expects: https://example.com/
    if not parsed.path or parsed.path == "/":
        return f"{parsed.scheme}://{parsed.netloc}/"
    return url


def _bing_payload(data: object) -> dict:
    """Unwrap Bing's JSON ``d`` envelope without trusting response shape."""
    if not isinstance(data, dict):
        return {}
    payload = data.get("d", data)
    return payload if isinstance(payload, dict) else {}


def _bounded_int(value: object, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return default


def _metadata(endpoint: str) -> dict:
    return {
        "source": "bing_webmaster",
        "endpoint": endpoint,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _link_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _safe_output_url(url: str) -> str:
    """Remove userinfo, query, and fragment from API-returned URLs."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port:
        host = f"{host}:{port}"
    return parsed._replace(netloc=host, query="", fragment="").geturl()


def get_link_details(
    site_url: str,
    api_key: str,
    page: int = 0,
    max_pages_to_expand: int = MAX_TARGETS_TO_EXPAND,
    max_detail_pages: int = MAX_URL_LINK_PAGES,
) -> dict:
    """
    Get inbound link details for a verified site.

    Args:
        site_url: Verified site URL.
        api_key: Bing API key.
        page: GetLinkCounts discovery page (0-based).
        max_pages_to_expand: Maximum target URLs to expand from that page.
        max_detail_pages: Maximum GetUrlLinks pages fetched per target URL.

    Returns:
        Standard response dict with link data.
    """
    limits = (page, max_pages_to_expand, max_detail_pages)
    if any(not isinstance(value, int) or isinstance(value, bool) for value in limits) \
            or page < 0 or max_pages_to_expand < 1 or max_detail_pages < 1:
        return {
            "status": "error", "data": None,
            "error": "page must be non-negative and expansion limits must be positive",
            "metadata": _metadata("GetLinkCounts+GetUrlLinks"),
        }

    normalized = _normalize_site_url(site_url)
    counts = _bing_request("GetLinkCounts", api_key, {"siteUrl": normalized, "page": page})
    if counts.get("status") != "success":
        return counts

    payload = _bing_payload(counts.get("data"))
    raw_targets = payload.get("Links", [])
    targets = [item for item in raw_targets if isinstance(item, dict) and item.get("Url")]
    targets.sort(key=lambda item: _bounded_int(item.get("Count")), reverse=True)
    targets = targets[:max_pages_to_expand]

    links = []
    seen = set()
    warnings = []
    partial_errors = []
    successful_detail_calls = 0
    detail_pages_fetched = 0
    count_total_pages = max(1, _bounded_int(payload.get("TotalPages"), 1))
    complete = len(targets) == len(raw_targets) and page + 1 >= count_total_pages

    for target in targets:
        target_url = target["Url"]
        detail_page = 0
        total_detail_pages = 1
        while detail_page < total_detail_pages and detail_page < max_detail_pages:
            detail = _bing_request(
                "GetUrlLinks",
                api_key,
                {"siteUrl": normalized, "link": target_url, "page": detail_page},
            )
            if detail.get("status") != "success":
                partial_errors.append({"target_url": _safe_output_url(target_url), "page": detail_page})
                complete = False
                break
            successful_detail_calls += 1
            detail_pages_fetched += 1
            detail_payload = _bing_payload(detail.get("data"))
            details = detail_payload.get("Details", [])
            if not isinstance(details, list):
                details = []
                complete = False
                warnings.append(f"Unexpected GetUrlLinks payload for target page {len(warnings) + 1}")
            total_detail_pages = max(1, _bounded_int(detail_payload.get("TotalPages"), 1))
            for item in details:
                if not isinstance(item, dict):
                    continue
                source_url = item.get("Url", "")
                safe_source = _safe_output_url(source_url)
                safe_target = _safe_output_url(target_url)
                key = (safe_source, safe_target, item.get("AnchorText", ""))
                if not source_url or key in seen:
                    continue
                seen.add(key)
                links.append({
                    "source_url": safe_source,
                    "target_url": safe_target,
                    "anchor_text": item.get("AnchorText", ""),
                })
            detail_page += 1
        if detail_page < total_detail_pages:
            complete = False

    if targets and successful_detail_calls == 0:
        return {
            "status": "error",
            "data": None,
            "error": "Bing returned link-count targets but none could be expanded",
            "metadata": _metadata("GetLinkCounts+GetUrlLinks"),
        }
    if targets and not links:
        warnings.append("Bing returned target pages but no referring-link details")
        complete = False

    status = "success" if complete and not partial_errors else "partial"
    return {
        "status": status,
        "data": {
            "site_url": _safe_output_url(site_url),
            "count_page": page,
            "targets_available_on_page": len(raw_targets) if isinstance(raw_targets, list) else 0,
            "targets_expanded": len(targets),
            "detail_pages_fetched": detail_pages_fetched,
            "total_returned": len(links),
            "complete": complete,
            "links": links,
            "warnings": warnings,
            "partial_errors": partial_errors,
        },
        "error": None,
        "metadata": _metadata("GetLinkCounts+GetUrlLinks"),
    }


def get_link_counts(
    site_url: str, api_key: str, max_pages: int = MAX_LINK_COUNT_PAGES
) -> dict:
    """
    Get total backlink and referring domain counts for a site.

    Args:
        site_url: Site URL to query.
        api_key: Bing API key.

    Returns:
        Standard response dict with count data.
    """
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages < 1:
        return {
            "status": "error", "data": None,
            "error": "max_pages must be positive",
            "metadata": _metadata("GetLinkCounts"),
        }
    normalized = _normalize_site_url(site_url)
    page = 0
    total_pages = 1
    pages_fetched = 0
    targets = {}
    while page < total_pages and page < max_pages:
        response = _bing_request("GetLinkCounts", api_key, {"siteUrl": normalized, "page": page})
        if response.get("status") != "success":
            if page == 0:
                return response
            return {
                "status": "partial",
                "data": {
                    "site_url": _safe_output_url(site_url),
                    "pages_fetched": pages_fetched,
                    "total_pages": total_pages,
                    "pages_with_links_sample": len(targets),
                    "sampled_inbound_link_count": sum(targets.values()),
                    "complete": False,
                    "warnings": [{"endpoint": "GetLinkCounts", "page": page}],
                },
                "error": None,
                "metadata": _metadata("GetLinkCounts"),
            }
        payload = _bing_payload(response.get("data"))
        links = payload.get("Links", [])
        if not isinstance(links, list):
            links = []
        total_pages = max(1, _bounded_int(payload.get("TotalPages"), 1))
        for item in links:
            if isinstance(item, dict) and item.get("Url"):
                targets[item["Url"]] = _bounded_int(item.get("Count"))
        pages_fetched += 1
        page += 1

    complete = page >= total_pages
    return {
        "status": "success" if complete else "partial",
        "data": {
            "site_url": _safe_output_url(site_url),
            "pages_fetched": pages_fetched,
            "total_pages": total_pages,
            "pages_with_links_sample": len(targets),
            "sampled_inbound_link_count": sum(targets.values()),
            "complete": complete,
            "warnings": [] if complete else [f"GetLinkCounts was capped at {max_pages} pages"],
        },
        "error": None,
        "metadata": _metadata("GetLinkCounts"),
    }


def compare_links(site_url: str, competitor_url: str, api_key: str) -> dict:
    """
    Compare backlink profiles between your site and a competitor.

    Both properties must be registered and accessible to the API account.

    Args:
        site_url: Your verified site URL.
        competitor_url: Competitor URL to compare against.
        api_key: Bing API key.

    Returns:
        Standard response dict with comparison data.
    """
    own_result = get_link_details(site_url, api_key)
    competitor_result = get_link_details(competitor_url, api_key)

    if own_result.get("status") == "error":
        return {
            "status": "error", "data": None,
            "error": "Could not retrieve links for the first registered property",
            "metadata": _metadata("verified-site-comparison"),
        }
    if competitor_result.get("status") == "error":
        return {
            "status": "error", "data": None,
            "error": "The second property is not accessible or its links could not be retrieved",
            "metadata": _metadata("verified-site-comparison"),
        }
    if not isinstance(own_result.get("data"), dict) or not isinstance(competitor_result.get("data"), dict):
        return {
            "status": "error", "data": None,
            "error": "Bing returned an invalid comparison payload",
            "metadata": _metadata("verified-site-comparison"),
        }

    own_links = []
    competitor_links = []
    own_domains = set()
    competitor_domains = set()

    if own_result.get("status") in {"success", "partial"} and own_result.get("data"):
        own_links = own_result["data"].get("links", [])
        for link in own_links:
            source = link.get("source_url", "")
            if source:
                domain = _link_domain(source)
                if domain:
                    own_domains.add(domain)

    if competitor_result.get("status") in {"success", "partial"} and competitor_result.get("data"):
        competitor_links = competitor_result["data"].get("links", [])
        for link in competitor_links:
            source = link.get("source_url", "")
            if source:
                domain = _link_domain(source)
                if domain:
                    competitor_domains.add(domain)

    # Gap analysis
    gap_domains = competitor_domains - own_domains  # Competitor has, you don't
    shared_domains = own_domains & competitor_domains
    unique_domains = own_domains - competitor_domains  # You have, competitor doesn't

    return {
        "status": "partial" if "partial" in {own_result.get("status"), competitor_result.get("status")} else "success",
        "data": {
            "site_url": _safe_output_url(site_url),
            "competitor_url": _safe_output_url(competitor_url),
            "your_linking_domains": len(own_domains),
            "competitor_linking_domains": len(competitor_domains),
            "gap_domains": sorted(list(gap_domains))[:50],
            "shared_domains": sorted(list(shared_domains))[:50],
            "unique_to_you": sorted(list(unique_domains))[:50],
            "gap_count": len(gap_domains),
            "shared_count": len(shared_domains),
            "unique_count": len(unique_domains),
            "complete": bool(
                own_result["data"].get("complete") and competitor_result["data"].get("complete")
            ),
            "note": "Bing comparison covers only properties accessible to the same API account.",
        },
        "error": None,
        "metadata": {
            "source": "bing_webmaster",
            "comparison": "verified_properties",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Bing Webmaster Tools API client for registered properties"
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
        help="Second registered property URL (required for 'compare' command)",
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
    target = args.url if "://" in args.url else f"https://{args.url}"
    if not validate_url(target):
        result = {
            "status": "error",
            "data": None,
            "error": "Invalid or blocked target URL",
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
        comp = (
            args.competitor_url
            if "://" in args.competitor_url
            else f"https://{args.competitor_url}"
        )
        if not validate_url(comp):
            result = {
                "status": "error",
                "data": None,
                "error": "Invalid or blocked competitor URL",
                "metadata": {"source": "bing_webmaster"},
            }
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        args.competitor_url = comp

    # Get API key
    api_key = get_bing_api_key()
    if not api_key:
        result = {
            "status": "error",
            "data": None,
            "error": "No Bing Webmaster API key configured. Run: "${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run backlinks_auth.py --setup",
            "metadata": {"source": "bing_webmaster"},
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    # Warn if site not in verified list
    verified = get_bing_verified_sites()
    parsed_target = urlparse(target)
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
        if result["status"] in {"success", "partial"} and result["data"]:
            data = result["data"]
            if args.command == "links":
                print(f"Bing Inbound Links for: {data.get('site_url', target)} ({data.get('total_returned', 0)} returned)")
                for link in data.get("links", [])[:20]:
                    anchor = link.get("anchor_text", "")[:40]
                    print(f"  {link.get('source_url', '?'):60s} [{anchor}]")
            elif args.command == "counts":
                print(f"Bing Link Counts for: {data.get('site_url', target)}")
                print(f"  Pages with links (sample): {data.get('pages_with_links_sample', 'N/A')}")
                print(f"  Sampled inbound link count: {data.get('sampled_inbound_link_count', 'N/A')}")
            elif args.command == "compare":
                print(f"Backlink Gap: {data.get('site_url', '')} vs {data.get('competitor_url', '')}")
                print(f"  Your linking domains:       {data.get('your_linking_domains', 0)}")
                print(f"  Competitor linking domains:  {data.get('competitor_linking_domains', 0)}")
                print(f"  Gap (they have, you don't): {data.get('gap_count', 0)}")
                print(f"  Shared:                     {data.get('shared_count', 0)}")
                print(f"  Unique to you:              {data.get('unique_count', 0)}")
                if data.get("gap_domains"):
                    print("\n  Top gap domains:")
                    for d in data["gap_domains"][:10]:
                        print(f"    {d}")
        elif result.get("error"):
            print(f"Error: {result['error']}", file=sys.stderr)
    return 1 if result.get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
