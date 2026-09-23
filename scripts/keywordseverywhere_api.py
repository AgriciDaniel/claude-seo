#!/usr/bin/env python3
"""
Keywords Everywhere (formerly OpenPageRank) API client for Claude SEO.

Queries the Keywords Everywhere Open PageRank API for a domain-level rank
metric (0-10 scale) plus the referring-domain count. Cheap, single-endpoint
fallback source; it does not provide anchors or top pages like Moz.

API contract (https://openpagerank.keywordseverywhere.com/docs, verified
2026-09-23): POST /v1/domains/bulk with ``Authorization: Bearer <key>`` and
``{"domains": [...], "include_history": false}``; up to 100 domains; the
response carries ``results[]`` with ``domain``, ``found``, ``open_page_rank``,
``rank`` and ``referring_domains``. The legacy GET /api/v1.0/getPageRank route
with the ``API-OPR`` header was removed (issue #312).

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
    from url_safety import (
        URLSafetyError,
        normalize_hostname,
        safe_requests_session,
        validate_url,
    )
except ImportError:
    print("Error: backlinks_auth.py and url_safety.py required in scripts/", file=sys.stderr)
    sys.exit(1)

KWE_BASE = "https://openpagerank.keywordseverywhere.com/v1/domains/bulk"
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


def _post(url: str, **kwargs):
    """POST through a DNS-pinned url_safety session; redirects are refused."""
    with safe_requests_session(url) as session:
        return session.post(url, allow_redirects=False, **kwargs)


def get_rank(domains: list, api_key: str) -> dict:
    """
    Get Open PageRank (0-10 scale) for up to MAX_DOMAINS domains in one call.

    Args:
        domains: List of already-validated, normalized hostnames.
        api_key: Keywords Everywhere API key (opr_live_...).

    Returns:
        Standard response dict with rank data per domain.
    """
    raw_key = api_key or ""
    api_key = raw_key.strip()
    if not api_key or any(ord(ch) < 33 for ch in api_key):
        return {
            "status": "error",
            "data": None,
            "error": "The configured Keywords Everywhere API key contains spaces or control "
                     "characters. Re-enter it with backlinks_auth.py --setup.",
            "metadata": {"source": "keywordseverywhere"},
        }

    def _redact(text: object) -> str:
        text = str(text)
        for secret in {raw_key, api_key}:
            if secret:
                text = text.replace(secret, "<redacted>")
        return text[:500]

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    payload = {"domains": domains, "include_history": False}

    try:
        response = _post(KWE_BASE, headers=headers, json=payload, timeout=30)

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
                err = err_body.get("error") if isinstance(err_body, dict) else None
                err_msg = (err.get("message") if isinstance(err, dict) else err) or "no error message"
            except (ValueError, RecursionError):
                # Never echo an HTML error page; the status code says enough.
                err_msg = "no JSON error body"
            # Never echo the key back through an upstream error body.
            err_msg = _redact(err_msg)
            return {
                "status": "error",
                "data": None,
                "error": f"HTTP {response.status_code}: {err_msg}",
                "metadata": {"source": "keywordseverywhere"},
            }

        if response.status_code >= 300:
            return {
                "status": "error",
                "data": None,
                "error": f"HTTP {response.status_code}: unexpected redirect from the API",
                "metadata": {"source": "keywordseverywhere"},
            }
        try:
            body = response.json()
        except (ValueError, RecursionError):
            return {
                "status": "error",
                "data": None,
                "error": f"HTTP {response.status_code}: response was not JSON",
                "metadata": {"source": "keywordseverywhere"},
            }
        if not isinstance(body, dict) or not isinstance(body.get("results", []), list):
            return {
                "status": "error",
                "data": None,
                "error": "Unexpected response shape from the API (no results list).",
                "metadata": {"source": "keywordseverywhere"},
            }
        results = [item for item in body.get("results") or [] if isinstance(item, dict)]
        ranks = [
            {
                "domain": item.get("domain"),
                "found": item.get("found"),
                "open_page_rank": item.get("open_page_rank"),
                # Pre-#312 name kept for existing report consumers.
                "page_rank_decimal": item.get("open_page_rank"),
                "rank": item.get("rank"),
                "referring_domains": item.get("referring_domains"),
            }
            for item in results
        ]

        return {
            "status": "success",
            "data": {"domains": ranks, "as_of": body.get("as_of"),
                     "invalid": body.get("invalid") or []},
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
    except URLSafetyError as e:
        return {
            "status": "error",
            "data": None,
            "error": f"blocked by SSRF protection: {e}",
            "metadata": {"source": "keywordseverywhere"},
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "data": None,
            "error": _redact(e),
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
