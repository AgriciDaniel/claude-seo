#!/usr/bin/env python3
"""
Google Search Console URL Inspection API helper.

Inspects URLs for indexing status, canonical selection, crawl info,
mobile usability, and rich results. Supports single URL and batch mode.

Usage:
    python gsc_inspect.py https://example.com/page --site-url sc-domain:example.com
    python gsc_inspect.py --batch urls.txt --site-url sc-domain:example.com
    python gsc_inspect.py https://example.com/page --json
"""

import argparse
import json
import sys
import time
from typing import Optional

try:
    from googleapiclient.discovery import build
except ImportError:
    print(
        "Error: google-api-python-client required. "
        "Install with: pip install google-api-python-client",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from google_auth import get_oauth_credentials, load_config
except ImportError:
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from google_auth import get_oauth_credentials, load_config

GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# Daily limit per site
DAILY_LIMIT = 2000
QPM_LIMIT = 600


def _build_inspection_service():
    """Build the Search Console v1 service for URL Inspection."""
    credentials = get_oauth_credentials(GSC_SCOPES)
    if not credentials:
        return None
    try:
        return build("searchconsole", "v1", credentials=credentials)
    except Exception as e:
        print(f"Error building service: {e}", file=sys.stderr)
        return None


def inspect_url(
    inspection_url: str,
    site_url: str,
    language_code: str = "en",
) -> dict:
    """
    Inspect a single URL via the GSC URL Inspection API.

    Args:
        inspection_url: The URL to inspect.
        site_url: The GSC property (e.g., 'sc-domain:example.com').
        language_code: Language for localized messages (default: 'en').

    Returns:
        Dictionary with inspection results including index status,
        crawl info, canonical, mobile usability, and rich results.
    """
    result = {
        "url": inspection_url,
        "property": site_url,
        "index_status": None,
        "crawl_info": None,
        "canonical": None,
        "mobile_usability": None,
        "rich_results": None,
        "verdict": None,
        "error": None,
    }

    service = _build_inspection_service()
    if not service:
        result["error"] = "Could not build GSC service. Check service account credentials."
        return result

    body = {
        "inspectionUrl": inspection_url,
        "siteUrl": site_url,
        "languageCode": language_code,
    }

    try:
        response = service.urlInspection().index().inspect(body=body).execute()
    except Exception as e:
        error_str = str(e)
        if "403" in error_str:
            result["error"] = (
                f"Permission denied. Add the service account as an Owner "
                f"in GSC property '{site_url}'."
            )
        elif "429" in error_str:
            result["error"] = (
                f"Rate limit exceeded. URL Inspection: {QPM_LIMIT} QPM / {DAILY_LIMIT} QPD per site."
            )
        elif "400" in error_str:
            result["error"] = (
                f"Invalid request. Ensure the URL '{inspection_url}' belongs to "
                f"property '{site_url}'."
            )
        else:
            result["error"] = f"URL Inspection API error: {e}"
        return result

    ir = response.get("inspectionResult", {})

    # Index status
    idx = ir.get("indexStatusResult", {})
    result["verdict"] = idx.get("verdict", "VERDICT_UNSPECIFIED")
    result["index_status"] = {
        "verdict": idx.get("verdict"),
        "coverage_state": idx.get("coverageState"),
        "robots_txt_state": idx.get("robotsTxtState"),
        "indexing_state": idx.get("indexingState"),
        "page_fetch_state": idx.get("pageFetchState"),
        "last_crawl_time": idx.get("lastCrawlTime"),
        "crawled_as": idx.get("crawledAs"),
        "referring_urls": idx.get("referringUrls", []),
    }

    # Canonical
    result["canonical"] = {
        "google_canonical": idx.get("googleCanonical"),
        "user_canonical": idx.get("userCanonical"),
        "match": idx.get("googleCanonical") == idx.get("userCanonical")
        if idx.get("googleCanonical") and idx.get("userCanonical") else None,
    }

    # Mobile usability (deprecated April 2023 but may still return data)
    mu = ir.get("mobileUsabilityResult", {})
    if mu:
        result["mobile_usability"] = {
            "verdict": mu.get("verdict"),
            "issues": [
                {"type": issue.get("issueType"), "message": issue.get("message")}
                for issue in mu.get("issues", [])
            ],
        }

    # Rich results
    rr = ir.get("richResultsResult", {})
    if rr:
        result["rich_results"] = {
            "verdict": rr.get("verdict"),
            "detected_items": [
                {
                    "type": item.get("richResultType"),
                    "items": [
                        {"name": i.get("name"), "issues": i.get("issues", [])}
                        for i in item.get("items", [])
                    ],
                }
                for item in rr.get("detectedItems", [])
            ],
        }

    return result


def batch_inspect(
    urls: list,
    site_url: str,
    delay: float = 1.0,
    language_code: str = "en",
) -> dict:
    """
    Batch inspect multiple URLs with rate limiting.

    Args:
        urls: List of URLs to inspect.
        site_url: GSC property.
        delay: Seconds between requests (default: 1.0 for safety).
        language_code: Language code.

    Returns:
        Dictionary with results list and summary.
    """
    result = {
        "property": site_url,
        "total": len(urls),
        "results": [],
        "summary": {
            "pass": 0,
            "fail": 0,
            "neutral": 0,
            "error": 0,
        },
        "error": None,
    }

    if len(urls) > DAILY_LIMIT:
        result["error"] = (
            f"Batch size ({len(urls)}) exceeds daily limit ({DAILY_LIMIT}). "
            f"Only the first {DAILY_LIMIT} URLs will be processed."
        )
        urls = urls[:DAILY_LIMIT]

    for i, url in enumerate(urls):
        url = url.strip()
        if not url:
            continue

        print(f"Inspecting [{i + 1}/{len(urls)}]: {url}", file=sys.stderr)

        inspection = inspect_url(url, site_url, language_code)
        result["results"].append(inspection)

        verdict = inspection.get("verdict", "")
        if inspection.get("error"):
            result["summary"]["error"] += 1
        elif verdict == "PASS":
            result["summary"]["pass"] += 1
        elif verdict == "FAIL":
            result["summary"]["fail"] += 1
        else:
            result["summary"]["neutral"] += 1

        # Rate limiting
        if i < len(urls) - 1:
            time.sleep(delay)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Google Search Console URL Inspection API helper"
    )
    parser.add_argument("url", nargs="?", help="URL to inspect")
    parser.add_argument(
        "--site-url", "-s",
        help="GSC property (e.g., sc-domain:example.com). Uses default from config if not specified.",
    )
    parser.add_argument(
        "--batch", "-b",
        help="File with URLs to inspect (one per line)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between batch requests in seconds (default: 1.0)",
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Resolve site URL
    site_url = args.site_url
    if not site_url:
        config = load_config()
        site_url = config.get("default_property")
    if not site_url:
        print("Error: No site URL specified. Use --site-url or set default_property in config.", file=sys.stderr)
        sys.exit(1)

    if args.batch:
        # Batch mode
        try:
            with open(args.batch, "r") as f:
                urls = [line.strip() for line in f if line.strip()]
        except IOError as e:
            print(f"Error reading batch file: {e}", file=sys.stderr)
            sys.exit(1)

        result = batch_inspect(urls, site_url, delay=args.delay)
    elif args.url:
        result = inspect_url(args.url, site_url)
    else:
        parser.print_help()
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if args.batch:
            summary = result.get("summary", {})
            print(f"=== URL Inspection Batch Results ===")
            print(f"Property: {site_url}")
            print(f"Total: {result.get('total', 0)} | Pass: {summary.get('pass', 0)} | Fail: {summary.get('fail', 0)} | Errors: {summary.get('error', 0)}")
            print()
            for r in result.get("results", []):
                verdict = r.get("verdict", "?")
                status = {"PASS": "OK", "FAIL": "FAIL", "NEUTRAL": "--"}.get(verdict, "ERR")
                print(f"  [{status}] {r.get('url')}")
                if r.get("error"):
                    print(f"       Error: {r['error']}")
                elif verdict == "FAIL":
                    idx = r.get("index_status", {})
                    print(f"       Coverage: {idx.get('coverage_state')} | Fetch: {idx.get('page_fetch_state')}")
        else:
            if result.get("error"):
                print(f"Error: {result['error']}", file=sys.stderr)
                sys.exit(1)

            verdict = result.get("verdict", "?")
            print(f"=== URL Inspection: {result.get('url')} ===")
            print(f"Verdict: {verdict}")

            idx = result.get("index_status", {})
            if idx:
                print(f"\nIndex Status:")
                print(f"  Coverage: {idx.get('coverage_state')}")
                print(f"  Robots.txt: {idx.get('robots_txt_state')}")
                print(f"  Indexing: {idx.get('indexing_state')}")
                print(f"  Page Fetch: {idx.get('page_fetch_state')}")
                print(f"  Last Crawl: {idx.get('last_crawl_time', 'N/A')}")
                print(f"  Crawled As: {idx.get('crawled_as')}")

            canon = result.get("canonical", {})
            if canon:
                print(f"\nCanonical:")
                print(f"  Google: {canon.get('google_canonical', 'N/A')}")
                print(f"  User: {canon.get('user_canonical', 'N/A')}")
                match = canon.get("match")
                if match is not None:
                    print(f"  Match: {'Yes' if match else 'MISMATCH'}")

            rr = result.get("rich_results")
            if rr and rr.get("detected_items"):
                print(f"\nRich Results: {rr.get('verdict')}")
                for item in rr.get("detected_items", []):
                    print(f"  Type: {item.get('type')}")


if __name__ == "__main__":
    main()
