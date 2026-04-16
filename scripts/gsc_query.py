#!/usr/bin/env python3
"""
Google Search Console Search Analytics query helper.

Queries the GSC Search Analytics API for clicks, impressions, CTR, and position
data. Supports filtering by dimensions, auto-pagination, and quick-win detection.

Usage:
    python gsc_query.py --property sc-domain:example.com
    python gsc_query.py --property sc-domain:example.com --days 90 --dimensions query
    python gsc_query.py sitemaps --property sc-domain:example.com
    python gsc_query.py sites
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
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


def _build_gsc_service():
    """Build the Search Console API service."""
    credentials = get_oauth_credentials(GSC_SCOPES)
    if not credentials:
        return None
    try:
        return build("searchconsole", "v1", credentials=credentials)
    except Exception as e:
        print(f"Error building GSC service: {e}", file=sys.stderr)
        return None


def query_search_analytics(
    site_url: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    dimensions: Optional[list] = None,
    search_type: str = "web",
    row_limit: int = 1000,
    filters: Optional[list] = None,
    data_state: str = "final",
) -> dict:
    """
    Query GSC Search Analytics API.

    Args:
        site_url: GSC property (e.g., 'sc-domain:example.com' or 'https://example.com/').
        start_date: Start date (YYYY-MM-DD). Default: 28 days ago.
        end_date: End date (YYYY-MM-DD). Default: 3 days ago (data lag).
        dimensions: List of dimensions: query, page, country, device, date, searchAppearance.
        search_type: web, image, video, news, discover, googleNews.
        row_limit: Max rows per request (1-25000). Auto-paginates if more.
        filters: List of filter dicts with dimension, operator, expression.
        data_state: 'final' or 'all' (includes fresh/unfinalized data).

    Returns:
        Dictionary with rows, totals, and quick_wins.
    """
    result = {
        "property": site_url,
        "rows": [],
        "totals": {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0},
        "quick_wins": [],
        "row_count": 0,
        "error": None,
    }

    service = _build_gsc_service()
    if not service:
        result["error"] = "Could not build GSC service. Check service account credentials."
        return result

    if not start_date:
        start_date = (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    if dimensions is None:
        dimensions = ["query", "page"]

    result["date_range"] = {"start": start_date, "end": end_date}

    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "type": search_type,
        "rowLimit": min(row_limit, 25000),
        "dataState": data_state,
    }

    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]

    # Auto-paginate
    all_rows = []
    start_row = 0
    page_size = min(row_limit, 25000)

    try:
        while True:
            body["startRow"] = start_row
            body["rowLimit"] = page_size

            response = service.searchanalytics().query(
                siteUrl=site_url, body=body
            ).execute()

            rows = response.get("rows", [])
            all_rows.extend(rows)

            if len(rows) < page_size:
                break

            start_row += page_size

            # Safety: cap at 100,000 rows
            if start_row >= 100000:
                break

    except Exception as e:
        error_str = str(e)
        if "403" in error_str:
            result["error"] = (
                f"Permission denied for property '{site_url}'. "
                "Ensure the service account email is added as a user in "
                "Google Search Console > Settings > Users and permissions."
            )
        elif "404" in error_str:
            result["error"] = (
                f"Property '{site_url}' not found. "
                "Use 'sc-domain:example.com' for domain properties or "
                "'https://example.com/' for URL-prefix properties."
            )
        else:
            result["error"] = f"GSC API error: {e}"
        return result

    # Process rows
    total_clicks = 0
    total_impressions = 0

    for row in all_rows:
        keys = row.get("keys", [])
        clicks = row.get("clicks", 0)
        impressions = row.get("impressions", 0)
        ctr = row.get("ctr", 0)
        position = row.get("position", 0)

        processed = {
            "keys": keys,
            "clicks": clicks,
            "impressions": impressions,
            "ctr": round(ctr * 100, 2),
            "position": round(position, 1),
        }

        # Label keys by dimension name
        for i, dim in enumerate(dimensions):
            if i < len(keys):
                processed[dim] = keys[i]

        result["rows"].append(processed)
        total_clicks += clicks
        total_impressions += impressions

    result["row_count"] = len(all_rows)
    result["totals"]["clicks"] = total_clicks
    result["totals"]["impressions"] = total_impressions
    if total_impressions > 0:
        result["totals"]["ctr"] = round((total_clicks / total_impressions) * 100, 2)

    # Quick wins: position 4-10 with high impressions
    if "query" in dimensions:
        sorted_by_impressions = sorted(all_rows, key=lambda r: r.get("impressions", 0), reverse=True)
        for row in sorted_by_impressions[:200]:
            pos = row.get("position", 0)
            if 4 <= pos <= 10 and row.get("impressions", 0) > 50:
                result["quick_wins"].append({
                    "keys": row.get("keys", []),
                    "position": round(pos, 1),
                    "impressions": row.get("impressions", 0),
                    "clicks": row.get("clicks", 0),
                    "ctr": round(row.get("ctr", 0) * 100, 2),
                    "opportunity": "Position 4-10 with high impressions -- small ranking improvement yields significant traffic gain",
                })

        result["quick_wins"] = result["quick_wins"][:20]

    return result


def list_sitemaps(site_url: str) -> dict:
    """
    List sitemaps for a GSC property.

    Args:
        site_url: GSC property URL.

    Returns:
        Dictionary with sitemaps list.
    """
    result = {"property": site_url, "sitemaps": [], "error": None}

    service = _build_gsc_service()
    if not service:
        result["error"] = "Could not build GSC service."
        return result

    try:
        response = service.sitemaps().list(siteUrl=site_url).execute()
        for sm in response.get("sitemap", []):
            result["sitemaps"].append({
                "path": sm.get("path"),
                "last_submitted": sm.get("lastSubmitted"),
                "is_pending": sm.get("isPending"),
                "is_index": sm.get("isSitemapsIndex"),
                "type": sm.get("type"),
                "warnings": sm.get("warnings", 0),
                "errors": sm.get("errors", 0),
                "contents": sm.get("contents", []),
            })
    except Exception as e:
        result["error"] = f"Error listing sitemaps: {e}"

    return result


def list_sites() -> dict:
    """
    List all verified GSC properties.

    Returns:
        Dictionary with sites list.
    """
    result = {"sites": [], "error": None}

    service = _build_gsc_service()
    if not service:
        result["error"] = "Could not build GSC service."
        return result

    try:
        response = service.sites().list().execute()
        for site in response.get("siteEntry", []):
            result["sites"].append({
                "url": site.get("siteUrl"),
                "permission": site.get("permissionLevel"),
            })
    except Exception as e:
        result["error"] = f"Error listing sites: {e}"

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Google Search Console Search Analytics query helper"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="query",
        choices=["query", "sitemaps", "sites"],
        help="Command: query (default), sitemaps, sites",
    )
    parser.add_argument(
        "--property", "-p",
        help="GSC property (e.g., sc-domain:example.com). Uses default from config if not specified.",
    )
    parser.add_argument("--days", "-d", type=int, default=28, help="Number of days (default: 28)")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--dimensions",
        default="query,page",
        help="Comma-separated dimensions (default: query,page)",
    )
    parser.add_argument("--type", default="web", help="Search type (default: web)")
    parser.add_argument("--limit", type=int, default=1000, help="Row limit (default: 1000)")
    parser.add_argument(
        "--device",
        choices=["desktop", "mobile", "tablet"],
        help="Filter by device type",
    )
    parser.add_argument("--country", help="Filter by country (ISO 3166-1 alpha-3, e.g., USA)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Resolve property
    prop = args.property
    if not prop:
        config = load_config()
        prop = config.get("default_property")
    if not prop and args.command != "sites":
        print("Error: No property specified. Use --property or set default_property in config.", file=sys.stderr)
        sys.exit(1)

    if args.command == "sites":
        result = list_sites()
    elif args.command == "sitemaps":
        result = list_sitemaps(prop)
    else:
        start = args.start_date or (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
        end = args.end_date or (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        dims = [d.strip() for d in args.dimensions.split(",")]
        filters = []
        if args.device:
            filters.append({
                "dimension": "device",
                "operator": "equals",
                "expression": args.device.upper(),
            })
        if args.country:
            filters.append({
                "dimension": "country",
                "operator": "equals",
                "expression": args.country.upper(),
            })
        result = query_search_analytics(
            prop, start_date=start, end_date=end,
            dimensions=dims, search_type=args.type, row_limit=args.limit,
            filters=filters if filters else None,
        )

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        if not args.json:
            sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if args.command == "sites":
            print("=== Verified GSC Properties ===")
            for site in result.get("sites", []):
                print(f"  {site['url']} ({site['permission']})")
        elif args.command == "sitemaps":
            print(f"=== Sitemaps for {prop} ===")
            for sm in result.get("sitemaps", []):
                status = "pending" if sm.get("is_pending") else "processed"
                print(f"  {sm['path']} [{status}] errors={sm.get('errors', 0)} warnings={sm.get('warnings', 0)}")
        else:
            totals = result.get("totals", {})
            print(f"=== Search Analytics: {prop} ===")
            print(f"Period: {result.get('date_range', {}).get('start')} to {result.get('date_range', {}).get('end')}")
            print(f"Clicks: {totals.get('clicks', 0):,} | Impressions: {totals.get('impressions', 0):,} | CTR: {totals.get('ctr', 0)}% | Rows: {result.get('row_count', 0)}")

            qw = result.get("quick_wins", [])
            if qw:
                print(f"\nQuick Wins ({len(qw)} found):")
                for w in qw[:10]:
                    keys = " | ".join(w.get("keys", []))
                    print(f"  Pos {w['position']} | {w['impressions']:,} imp | {w['clicks']} clicks | {keys}")


if __name__ == "__main__":
    main()
