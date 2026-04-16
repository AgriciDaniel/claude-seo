#!/usr/bin/env python3
"""
Google Indexing API v3 - notify Google of URL updates and removals.

Publishes URL_UPDATED or URL_DELETED notifications. Supports single URL
and batch mode (up to 200 URLs/day). Includes quota tracking.

IMPORTANT: The Indexing API is officially restricted to pages with
JobPosting or BroadcastEvent/VideoObject structured data. Google may
process other page types but provides no guarantees.

Usage:
    python indexing_notify.py https://example.com/jobs/123
    python indexing_notify.py https://example.com/jobs/123 --action URL_DELETED
    python indexing_notify.py --batch urls.txt
    python indexing_notify.py --status https://example.com/jobs/123
"""

import argparse
import json
import sys
import time
from typing import Optional

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import BatchHttpRequest
except ImportError:
    print(
        "Error: google-api-python-client required. "
        "Install with: pip install google-api-python-client",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from google_auth import get_oauth_credentials
except ImportError:
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from google_auth import get_oauth_credentials

INDEXING_SCOPES = ["https://www.googleapis.com/auth/indexing"]
DAILY_QUOTA = 200

SCOPE_WARNING = (
    "NOTE: The Indexing API is officially for JobPosting and "
    "BroadcastEvent/VideoObject pages only. Google may process other "
    "page types but provides no guarantees."
)


def _build_indexing_service():
    """Build the Indexing API v3 service."""
    credentials = get_oauth_credentials(INDEXING_SCOPES)
    if not credentials:
        return None
    try:
        return build("indexing", "v3", credentials=credentials)
    except Exception as e:
        print(f"Error building Indexing service: {e}", file=sys.stderr)
        return None


def notify_url(
    url: str,
    action: str = "URL_UPDATED",
) -> dict:
    """
    Publish a single URL notification to the Indexing API.

    Args:
        url: The URL to notify about.
        action: 'URL_UPDATED' or 'URL_DELETED'.

    Returns:
        Dictionary with notification result.
    """
    result = {
        "url": url,
        "action": action,
        "notify_time": None,
        "error": None,
    }

    service = _build_indexing_service()
    if not service:
        result["error"] = (
            "Could not build Indexing service. Ensure the service account has "
            "'https://www.googleapis.com/auth/indexing' scope and is added as "
            "Owner in Google Search Console for the target domain."
        )
        return result

    body = {
        "url": url,
        "type": action,
    }

    try:
        response = service.urlNotifications().publish(body=body).execute()
        metadata = response.get("urlNotificationMetadata", {})
        latest = metadata.get("latestUpdate", {}) or metadata.get("latestRemove", {})
        result["notify_time"] = latest.get("notifyTime")
    except Exception as e:
        error_str = str(e)
        if "403" in error_str:
            result["error"] = (
                "Permission denied. The service account must be added as an "
                "Owner in Google Search Console for this domain. "
                "Also ensure the Indexing API is enabled in your GCP project."
            )
        elif "429" in error_str:
            result["error"] = (
                f"Quota exceeded. Daily limit: {DAILY_QUOTA} publish requests. "
                "Apply for a quota increase at https://developers.google.com/search/apis/indexing-api/v3/quota-increase"
            )
        elif "400" in error_str:
            result["error"] = f"Invalid URL or request: {e}"
        else:
            result["error"] = f"Indexing API error: {e}"

    return result


def get_notification_metadata(url: str) -> dict:
    """
    Get the latest notification metadata for a URL.

    Args:
        url: The URL to check.

    Returns:
        Dictionary with latest update and remove timestamps.
    """
    result = {
        "url": url,
        "latest_update": None,
        "latest_remove": None,
        "error": None,
    }

    service = _build_indexing_service()
    if not service:
        result["error"] = "Could not build Indexing service."
        return result

    try:
        response = service.urlNotifications().getMetadata(url=url).execute()
        update = response.get("latestUpdate", {})
        remove = response.get("latestRemove", {})

        if update:
            result["latest_update"] = {
                "url": update.get("url"),
                "type": update.get("type"),
                "notify_time": update.get("notifyTime"),
            }
        if remove:
            result["latest_remove"] = {
                "url": remove.get("url"),
                "type": remove.get("type"),
                "notify_time": remove.get("notifyTime"),
            }
    except Exception as e:
        if "404" in str(e):
            result["error"] = "No notification metadata found for this URL."
        else:
            result["error"] = f"Error fetching metadata: {e}"

    return result


def batch_notify(
    urls: list,
    action: str = "URL_UPDATED",
    delay: float = 0.5,
) -> dict:
    """
    Batch notify multiple URLs with quota awareness.

    Args:
        urls: List of URLs.
        action: 'URL_UPDATED' or 'URL_DELETED'.
        delay: Seconds between requests.

    Returns:
        Dictionary with results and quota usage.
    """
    result = {
        "action": action,
        "total": len(urls),
        "results": [],
        "summary": {"success": 0, "error": 0},
        "quota_warning": None,
        "error": None,
    }

    if len(urls) > DAILY_QUOTA:
        result["quota_warning"] = (
            f"Batch size ({len(urls)}) exceeds daily quota ({DAILY_QUOTA}). "
            f"Only the first {DAILY_QUOTA} URLs will be submitted."
        )
        urls = urls[:DAILY_QUOTA]

    if len(urls) > 50:
        result["quota_warning"] = (
            f"Submitting {len(urls)} URLs will use {len(urls)}/{DAILY_QUOTA} "
            f"of your daily quota."
        )

    for i, url in enumerate(urls):
        url = url.strip()
        if not url:
            continue

        print(f"Notifying [{i + 1}/{len(urls)}]: {url}", file=sys.stderr)

        notification = notify_url(url, action)
        result["results"].append(notification)

        if notification.get("error"):
            result["summary"]["error"] += 1
            # Stop on quota errors
            if "429" in str(notification.get("error", "")):
                result["error"] = "Stopped: daily quota exceeded."
                break
        else:
            result["summary"]["success"] += 1

        if i < len(urls) - 1:
            time.sleep(delay)

    remaining = DAILY_QUOTA - result["summary"]["success"]
    result["estimated_remaining_quota"] = max(0, remaining)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Google Indexing API v3 - URL notification helper"
    )
    parser.add_argument("url", nargs="?", help="URL to notify")
    parser.add_argument(
        "--action", "-a",
        choices=["URL_UPDATED", "URL_DELETED"],
        default="URL_UPDATED",
        help="Notification type (default: URL_UPDATED)",
    )
    parser.add_argument("--batch", "-b", help="File with URLs (one per line)")
    parser.add_argument("--status", help="Check notification status for a URL")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between batch requests in seconds (default: 0.5)",
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.status:
        result = get_notification_metadata(args.status)
    elif args.batch:
        print(SCOPE_WARNING, file=sys.stderr)
        try:
            with open(args.batch, "r") as f:
                urls = [line.strip() for line in f if line.strip()]
        except IOError as e:
            print(f"Error reading batch file: {e}", file=sys.stderr)
            sys.exit(1)
        result = batch_notify(urls, args.action, delay=args.delay)
    elif args.url:
        print(SCOPE_WARNING, file=sys.stderr)
        result = notify_url(args.url, args.action)
    else:
        parser.print_help()
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("error"):
            print(f"Error: {result['error']}", file=sys.stderr)

        if args.status:
            print(f"=== Notification Status: {args.status} ===")
            update = result.get("latest_update")
            remove = result.get("latest_remove")
            if update:
                print(f"  Latest Update: {update.get('notify_time')} ({update.get('type')})")
            if remove:
                print(f"  Latest Remove: {remove.get('notify_time')} ({remove.get('type')})")
            if not update and not remove and not result.get("error"):
                print("  No notifications found.")
        elif args.batch:
            summary = result.get("summary", {})
            print(f"=== Batch Indexing Notification ===")
            print(f"Action: {args.action}")
            print(f"Total: {result.get('total', 0)} | Success: {summary.get('success', 0)} | Errors: {summary.get('error', 0)}")
            print(f"Estimated remaining daily quota: {result.get('estimated_remaining_quota', '?')}")
            if result.get("quota_warning"):
                print(f"Warning: {result['quota_warning']}")
        else:
            if result.get("notify_time"):
                print(f"Notified: {result['url']} ({result['action']}) at {result['notify_time']}")
            elif not result.get("error"):
                print(f"Notification sent for: {result['url']} ({result['action']})")


if __name__ == "__main__":
    main()
