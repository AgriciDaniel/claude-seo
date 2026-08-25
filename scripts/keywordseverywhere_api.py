#!/usr/bin/env python3
"""
Keywords Everywhere (formerly OpenPageRank) API client for Claude SEO.

Queries the Keywords Everywhere Open PageRank API for a single domain-level
rank metric (0-10 scale). Cheap, single-endpoint fallback source -- does not
provide referring domains, anchors, or top pages like Moz.

Usage:
    python keywordseverywhere_api.py rank example.com --json
    python keywordseverywhere_api.py rank example.com another.com --json
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

import os
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
try:
    from backlinks_auth import get_keywordseverywhere_api_key
    from url_safety import validate_url, normalize_hostname
except ImportError:
    print("Error: backlinks_auth.py and url_safety.py required in scripts/", file=sys.stderr)
    sys.exit(1)

KWE_BASE = "https://openpagerank.keywordseverywhere.com/api/v1.0/getPageRank"
MAX_DOMAINS = 100


def normalize_domain(raw: str) -> Optional[str]:
    """
    Reduce a URL or bare domain to a validated public hostname.

    Strips scheme/path, rejects localhost/private/reserved IPs and hosts
    via the shared SSRF check, and returns None on anything invalid.
    """
    lowered = raw.lower()
    if "://" in lowered and not lowered.startswith(("http://", "https://")):
        return None
    candidate = raw if lowered.startswith(("http://", "https://")) else f"https://{raw}"
    if not validate_url(candidate):
        return None
    from urllib.parse import urlparse
    hostname = urlparse(candidate).hostname
    return normalize_hostname(hostname) if hostname else None


def get_rank(domains: list, api_key: str) -> dict:
    """
    Get Open PageRank (0-10 scale) for up to MAX_DOMAINS domains in one call.

    Args:
        domains: List of already-validated, normalized hostnames.
        api_key: Keywords Everywhere API key (opr_live_...).

    Returns:
        Standard response dict with rank data per domain.
    """
    headers = {"API-OPR": api_key}
    params = [("domains[]", d) for d in domains]

    try:
        response = requests.get(KWE_BASE, headers=headers, params=params, timeout=30)

        if response.status_code == 401 or response.status_code == 403:
            return {
                "status": "error",
                "data": None,
                "error": "Invalid Keywords Everywhere API key. Check your key in the Keywords Everywhere dashboard.",
                "metadata": {"source": "keywordseverywhere"},
            }

        if response.status_code == 429:
            return {
                "status": "rate_limited",
                "data": None,
                "error": "Keywords Everywhere rate limit exceeded.",
                "metadata": {"source": "keywordseverywhere", "rate_limited": True},
            }

        if response.status_code >= 400:
            try:
                err_body = response.json()
                err_msg = err_body.get("message") or err_body.get("error") or response.text
            except ValueError:
                err_msg = response.text or f"HTTP {response.status_code}"
            return {
                "status": "error",
                "data": None,
                "error": f"HTTP {response.status_code}: {err_msg}",
                "metadata": {"source": "keywordseverywhere"},
            }

        body = response.json()
        results = body.get("response") or []
        ranks = [
            {
                "domain": item.get("domain"),
                "page_rank_decimal": item.get("page_rank_decimal"),
                "page_rank_integer": item.get("page_rank_integer"),
                "rank": item.get("rank"),
            }
            for item in results
        ]

        return {
            "status": "success",
            "data": {"domains": ranks},
            "error": None,
            "metadata": {
                "source": "keywordseverywhere",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "data": None,
            "error": "Request timed out after 30 seconds",
            "metadata": {"source": "keywordseverywhere"},
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "data": None,
            "error": str(e),
            "metadata": {"source": "keywordseverywhere"},
        }


def main():
    parser = argparse.ArgumentParser(
        description="Keywords Everywhere (Open PageRank) API client for Claude SEO"
    )
    parser.add_argument("command", choices=["rank"], help="API command: rank (0-10 domain rank)")
    parser.add_argument("domains", nargs="+", help="Target domain(s) to look up (max 100)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if len(args.domains) > MAX_DOMAINS:
        result = {
            "status": "error",
            "data": None,
            "error": f"Too many domains ({len(args.domains)}); max {MAX_DOMAINS} per request.",
            "metadata": {"source": "keywordseverywhere"},
        }
        print(json.dumps(result, indent=2) if args.json else f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    targets = []
    for d in args.domains:
        normalized = normalize_domain(d)
        if not normalized:
            result = {
                "status": "error",
                "data": None,
                "error": f"Invalid, private, or blocked domain: {d}",
                "metadata": {"source": "keywordseverywhere"},
            }
            print(json.dumps(result, indent=2) if args.json else f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        targets.append(normalized)

    api_key = get_keywordseverywhere_api_key()
    if not api_key:
        result = {
            "status": "error",
            "data": None,
            "error": "No Keywords Everywhere API key configured. Run: python scripts/backlinks_auth.py --setup",
            "metadata": {"source": "keywordseverywhere"},
        }
        print(json.dumps(result, indent=2) if args.json else f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    result = get_rank(targets, api_key)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["status"] == "success" and result["data"]:
            for d in result["data"]["domains"]:
                print(f"  {d.get('domain', '?'):40s} rank={d.get('page_rank_decimal', '?')}/10 ({d.get('rank', '?')})")
        elif result["error"]:
            print(f"Error: {result['error']}", file=sys.stderr)
        else:
            print("No data returned.", file=sys.stderr)


if __name__ == "__main__":
    main()
