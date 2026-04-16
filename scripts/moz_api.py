#!/usr/bin/env python3
"""
Moz Link Explorer API client for Claude SEO.

Queries the Moz API (JSON-RPC 2.0) for Domain Authority, Page Authority,
Spam Score, link counts, and referring domain data. Free tier provides
2,500 rows/month at 1 request per 10 seconds.

Usage:
    python moz_api.py metrics https://example.com --json
    python moz_api.py domains https://example.com --json
    python moz_api.py anchors https://example.com --json
    python moz_api.py pages example.com --json
"""

import argparse
import json
import sys
import time
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

# Import credential helpers (same directory)
import os
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
try:
    from backlinks_auth import get_moz_api_key, load_config
    from google_auth import validate_url
except ImportError:
    print("Error: backlinks_auth.py and google_auth.py required in scripts/", file=sys.stderr)
    sys.exit(1)

MOZ_ENDPOINT = "https://api.moz.com/jsonrpc"

# Rate limit: 1 request per 10 seconds on free tier
RATE_LIMIT_DELAY = 10
RATE_LIMIT_FILE = os.path.expanduser("~/.cache/claude-seo/moz_last_request.lock")


def _rate_limit():
    """Enforce Moz free tier rate limit: 1 request per 10 seconds.

    Persists timestamp to a lockfile so the limit is respected across
    separate CLI invocations (each call is a new process).
    """
    os.makedirs(os.path.dirname(RATE_LIMIT_FILE), exist_ok=True)

    try:
        with open(RATE_LIMIT_FILE, "a+") as f:
            try:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX)
            except (ImportError, OSError):
                pass  # Windows or lock unavailable — skip locking

            f.seek(0)
            content = f.read().strip()
            last_time = float(content) if content else 0

            now = time.time()
            elapsed = now - last_time
            if elapsed < RATE_LIMIT_DELAY and last_time > 0:
                time.sleep(RATE_LIMIT_DELAY - elapsed)

            f.seek(0)
            f.truncate()
            f.write(str(time.time()))
    except (IOError, ValueError):
        pass  # If lockfile fails, fall back to no rate limiting (server-side 429 handles it)


def _moz_request(method: str, params: dict, api_key: str) -> dict:
    """
    Make a JSON-RPC 2.0 request to the Moz API.

    Args:
        method: API method name (e.g., 'data.url_metrics.get').
        params: Method parameters.
        api_key: Moz API key.

    Returns:
        Dictionary with 'status', 'data', 'error', 'metadata'.
    """
    _rate_limit()

    payload = {
        "jsonrpc": "2.0",
        "id": "claude-seo",
        "method": method,
        "params": params,
    }

    headers = {
        "Content-Type": "application/json",
        "x-moz-token": api_key,
        "User-Agent": "ClaudeSEO/1.8.0",
    }

    try:
        response = requests.post(
            MOZ_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code == 429:
            return {
                "status": "rate_limited",
                "data": None,
                "error": "Moz free tier rate limit exceeded. Wait 10 seconds between requests.",
                "metadata": {"source": "moz", "rate_limited": True},
            }

        if response.status_code == 401:
            return {
                "status": "error",
                "data": None,
                "error": "Invalid Moz API key. Check your key at https://moz.com/products/api/keys",
                "metadata": {"source": "moz"},
            }

        if response.status_code == 403:
            return {
                "status": "error",
                "data": None,
                "error": "Moz API access denied. Free tier may not include this endpoint.",
                "metadata": {"source": "moz"},
            }

        response.raise_for_status()
        result = response.json()

        if "error" in result:
            return {
                "status": "error",
                "data": None,
                "error": result["error"].get("message", str(result["error"])),
                "metadata": {"source": "moz"},
            }

        return {
            "status": "success",
            "data": result.get("result"),
            "error": None,
            "metadata": {
                "source": "moz",
                "method": method,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "data": None,
            "error": "Request timed out after 30 seconds",
            "metadata": {"source": "moz"},
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "data": None,
            "error": str(e),
            "metadata": {"source": "moz"},
        }


def get_url_metrics(url: str, api_key: str) -> dict:
    """
    Get URL-level metrics: Domain Authority, Page Authority, Spam Score, link counts.

    Args:
        url: Target URL or domain.
        api_key: Moz API key.

    Returns:
        Standard response dict with metrics data.
    """
    params = {
        "data": {
            "api_target": url,
            "api_target_type": "domain",
        }
    }
    result = _moz_request("data.url_metrics.get", params, api_key)

    if result["status"] == "success" and result["data"]:
        data = result["data"]
        result["data"] = {
            "url": url,
            "domain_authority": data.get("domain_authority"),
            "page_authority": data.get("page_authority"),
            "spam_score": data.get("spam_score"),
            "links": data.get("links", 0),
            "external_links": data.get("external_links_to_root_domain", 0),
            "linking_root_domains": data.get("root_domains_to_root_domain", 0),
            "last_crawled": data.get("last_crawled"),
            "raw": data,
        }

    return result


def get_linking_domains(url: str, api_key: str, limit: int = 50) -> dict:
    """
    Get top referring domains linking to the target.

    Args:
        url: Target URL or domain.
        api_key: Moz API key.
        limit: Max domains to return (default 50).

    Returns:
        Standard response dict with referring domain list.
    """
    params = {
        "data": {
            "api_target": url,
            "api_target_type": "domain",
            "limit": min(limit, 100),
        }
    }
    result = _moz_request("data.linking_root_domains.get", params, api_key)

    if result["status"] == "success" and result["data"]:
        data = result["data"]
        domains = []
        results_list = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(results_list, list):
            for item in results_list:
                domains.append({
                    "domain": item.get("root_domain", item.get("url", "")),
                    "domain_authority": item.get("domain_authority"),
                    "page_authority": item.get("page_authority"),
                    "spam_score": item.get("spam_score"),
                    "links_to_target": item.get("links_to_target", 1),
                })
        result["data"] = {
            "target": url,
            "total_returned": len(domains),
            "referring_domains": domains,
        }

    return result


def get_anchor_text(url: str, api_key: str, limit: int = 50) -> dict:
    """
    Get anchor text distribution for a target domain.

    Args:
        url: Target URL or domain.
        api_key: Moz API key.
        limit: Max anchor texts to return.

    Returns:
        Standard response dict with anchor text data.
    """
    params = {
        "data": {
            "api_target": url,
            "api_target_type": "domain",
            "limit": min(limit, 100),
        }
    }
    result = _moz_request("data.anchor_text.get", params, api_key)

    if result["status"] == "success" and result["data"]:
        data = result["data"]
        anchors = []
        results_list = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(results_list, list):
            for item in results_list:
                anchors.append({
                    "anchor_text": item.get("anchor_text", ""),
                    "external_links": item.get("external_links", 0),
                    "linking_domains": item.get("root_domains", 0),
                })
        result["data"] = {
            "target": url,
            "total_returned": len(anchors),
            "anchor_texts": anchors,
        }

    return result


def get_top_pages(domain: str, api_key: str, limit: int = 50) -> dict:
    """
    Get top pages by backlink count for a domain.

    Args:
        domain: Target domain.
        api_key: Moz API key.
        limit: Max pages to return.

    Returns:
        Standard response dict with top pages data.
    """
    params = {
        "data": {
            "api_target": domain,
            "api_target_type": "domain",
            "limit": min(limit, 100),
        }
    }
    result = _moz_request("data.top_pages.get", params, api_key)

    if result["status"] == "success" and result["data"]:
        data = result["data"]
        pages = []
        results_list = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(results_list, list):
            for item in results_list:
                pages.append({
                    "url": item.get("url", ""),
                    "page_authority": item.get("page_authority"),
                    "links": item.get("links", 0),
                    "linking_domains": item.get("root_domains", 0),
                })
        result["data"] = {
            "domain": domain,
            "total_returned": len(pages),
            "top_pages": pages,
        }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Moz Link Explorer API client for Claude SEO"
    )
    parser.add_argument(
        "command",
        choices=["metrics", "domains", "anchors", "pages"],
        help="API command: metrics (DA/PA), domains (referring), anchors (text), pages (top)",
    )
    parser.add_argument(
        "url",
        help="Target URL or domain to analyze",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max results to return (default: 50, max: 100)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    # Validate URL
    target = args.url
    if target.startswith("http"):
        if not validate_url(target):
            result = {
                "status": "error",
                "data": None,
                "error": f"Invalid or blocked URL: {target}",
                "metadata": {"source": "moz"},
            }
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

    # Get API key
    api_key = get_moz_api_key()
    if not api_key:
        result = {
            "status": "error",
            "data": None,
            "error": "No Moz API key configured. Run: python scripts/backlinks_auth.py --setup",
            "metadata": {"source": "moz"},
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    # Execute command
    if args.command == "metrics":
        result = get_url_metrics(target, api_key)
    elif args.command == "domains":
        result = get_linking_domains(target, api_key, limit=args.limit)
    elif args.command == "anchors":
        result = get_anchor_text(target, api_key, limit=args.limit)
    elif args.command == "pages":
        result = get_top_pages(target, api_key, limit=args.limit)
    else:
        result = {"status": "error", "data": None, "error": f"Unknown command: {args.command}"}

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["status"] == "success" and result["data"]:
            data = result["data"]
            if args.command == "metrics":
                print(f"Moz Metrics for: {data.get('url', target)}")
                print(f"  Domain Authority: {data.get('domain_authority', 'N/A')}")
                print(f"  Page Authority:   {data.get('page_authority', 'N/A')}")
                print(f"  Spam Score:       {data.get('spam_score', 'N/A')}")
                print(f"  Linking Domains:  {data.get('linking_root_domains', 'N/A')}")
                print(f"  External Links:   {data.get('external_links', 'N/A')}")
            elif args.command == "domains":
                print(f"Referring Domains for: {data.get('target', target)} ({data.get('total_returned', 0)} returned)")
                for d in data.get("referring_domains", [])[:20]:
                    print(f"  {d.get('domain', '?'):40s} DA={d.get('domain_authority', '?'):>5} links={d.get('links_to_target', '?')}")
            elif args.command == "anchors":
                print(f"Anchor Text for: {data.get('target', target)} ({data.get('total_returned', 0)} returned)")
                for a in data.get("anchor_texts", [])[:20]:
                    print(f"  {a.get('anchor_text', '?'):50s} links={a.get('external_links', '?')} domains={a.get('linking_domains', '?')}")
            elif args.command == "pages":
                print(f"Top Pages for: {data.get('domain', target)} ({data.get('total_returned', 0)} returned)")
                for p in data.get("top_pages", [])[:20]:
                    print(f"  PA={p.get('page_authority', '?'):>5} links={p.get('links', '?'):>6} {p.get('url', '?')}")
        elif result["error"]:
            print(f"Error: {result['error']}", file=sys.stderr)
        else:
            print("No data returned.", file=sys.stderr)


if __name__ == "__main__":
    main()
