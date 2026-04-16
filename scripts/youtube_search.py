#!/usr/bin/env python3
"""
YouTube Data API v3 - Search, video details, and channel data for SEO.

YouTube mentions have the strongest AI visibility correlation (0.737).
This script provides authoritative YouTube data directly from Google.

Usage:
    python youtube_search.py search "claude code seo"
    python youtube_search.py video dQw4w9WgXcQ --json
    python youtube_search.py channel UCxxxxxx --json
"""

import argparse
import json
import sys
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
    from google_auth import get_api_key
except ImportError:
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from google_auth import get_api_key

# YouTube Data API v3 quota costs:
# search.list = 100 units, videos.list = 1 unit, channels.list = 1 unit
# Default quota: 10,000 units/day = ~100 searches or ~10,000 video lookups
YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION = "v3"


def _build_youtube_service(api_key: Optional[str] = None):
    """Build the YouTube Data API v3 service."""
    key = api_key or get_api_key()
    if not key:
        return None
    try:
        return build(YOUTUBE_API_SERVICE, YOUTUBE_API_VERSION, developerKey=key)
    except Exception as e:
        print(f"Error building YouTube service: {e}", file=sys.stderr)
        return None


def search_videos(
    query: str,
    max_results: int = 10,
    order: str = "relevance",
    api_key: Optional[str] = None,
) -> dict:
    """
    Search YouTube for videos matching a query.

    Args:
        query: Search query string.
        max_results: Max results (1-50, default 10).
        order: Sort order: relevance, date, rating, viewCount, title.
        api_key: Optional API key override.

    Returns:
        Dictionary with videos list and metadata.
    """
    result = {"query": query, "videos": [], "total_results": 0, "error": None}

    service = _build_youtube_service(api_key)
    if not service:
        result["error"] = "No API key. Set GOOGLE_API_KEY or add 'api_key' to config."
        return result

    try:
        response = service.search().list(
            q=query,
            part="snippet",
            type="video",
            maxResults=min(max_results, 50),
            order=order,
        ).execute()

        result["total_results"] = response.get("pageInfo", {}).get("totalResults", 0)

        # Get video IDs for statistics
        video_ids = []
        snippets = {}
        for item in response.get("items", []):
            vid = item["id"].get("videoId")
            if vid:
                video_ids.append(vid)
                snippets[vid] = item.get("snippet", {})

        # Fetch statistics for all videos in one call (1 unit)
        if video_ids:
            stats_response = service.videos().list(
                id=",".join(video_ids),
                part="statistics,contentDetails",
            ).execute()

            stats_map = {}
            for item in stats_response.get("items", []):
                stats_map[item["id"]] = {
                    "views": int(item.get("statistics", {}).get("viewCount", 0)),
                    "likes": int(item.get("statistics", {}).get("likeCount", 0)),
                    "comments": int(item.get("statistics", {}).get("commentCount", 0)),
                    "duration": item.get("contentDetails", {}).get("duration", ""),
                }

            for vid in video_ids:
                snip = snippets.get(vid, {})
                stats = stats_map.get(vid, {})
                result["videos"].append({
                    "video_id": vid,
                    "title": snip.get("title", ""),
                    "channel": snip.get("channelTitle", ""),
                    "channel_id": snip.get("channelId", ""),
                    "published": snip.get("publishedAt", ""),
                    "description": snip.get("description", "")[:300],
                    "thumbnail": snip.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "views": stats.get("views", 0),
                    "likes": stats.get("likes", 0),
                    "comments": stats.get("comments", 0),
                    "duration": stats.get("duration", ""),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                })

    except Exception as e:
        error_str = str(e)
        if "403" in error_str:
            result["error"] = (
                "YouTube Data API access denied. Ensure the API is enabled "
                "in your GCP project (APIs & Services > Library > YouTube Data API v3)."
            )
        elif "429" in error_str:
            result["error"] = "YouTube API quota exceeded (10,000 units/day). Search costs 100 units."
        else:
            result["error"] = f"YouTube API error: {e}"

    return result


def get_video_details(
    video_id: str,
    api_key: Optional[str] = None,
) -> dict:
    """
    Get detailed information about a specific YouTube video.

    Args:
        video_id: YouTube video ID.
        api_key: Optional API key override.

    Returns:
        Dictionary with video details, statistics, and top comments.
    """
    result = {"video_id": video_id, "details": None, "comments": [], "error": None}

    service = _build_youtube_service(api_key)
    if not service:
        result["error"] = "No API key configured."
        return result

    try:
        # Video details (1 unit)
        response = service.videos().list(
            id=video_id,
            part="snippet,statistics,contentDetails,topicDetails",
        ).execute()

        items = response.get("items", [])
        if not items:
            result["error"] = f"Video not found: {video_id}"
            return result

        item = items[0]
        snip = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        topics = item.get("topicDetails", {})

        result["details"] = {
            "title": snip.get("title", ""),
            "channel": snip.get("channelTitle", ""),
            "channel_id": snip.get("channelId", ""),
            "published": snip.get("publishedAt", ""),
            "description": snip.get("description", ""),
            "tags": snip.get("tags", []),
            "category_id": snip.get("categoryId", ""),
            "duration": content.get("duration", ""),
            "definition": content.get("definition", ""),
            "caption": content.get("caption", "false"),
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments_count": int(stats.get("commentCount", 0)),
            "favorites": int(stats.get("favoriteCount", 0)),
            "topic_categories": topics.get("topicCategories", []),
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }

        # Top comments (1 unit)
        try:
            comments_response = service.commentThreads().list(
                videoId=video_id,
                part="snippet",
                maxResults=10,
                order="relevance",
                textFormat="plainText",
            ).execute()

            for thread in comments_response.get("items", []):
                comment = thread.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                result["comments"].append({
                    "author": comment.get("authorDisplayName", ""),
                    "text": comment.get("textDisplay", "")[:500],
                    "likes": comment.get("likeCount", 0),
                    "published": comment.get("publishedAt", ""),
                })
        except Exception:
            pass  # Comments may be disabled

    except Exception as e:
        result["error"] = f"YouTube API error: {e}"

    return result


def get_channel_info(
    channel_id: str,
    api_key: Optional[str] = None,
) -> dict:
    """
    Get channel information.

    Args:
        channel_id: YouTube channel ID.
        api_key: Optional API key override.

    Returns:
        Dictionary with channel details.
    """
    result = {"channel_id": channel_id, "channel": None, "error": None}

    service = _build_youtube_service(api_key)
    if not service:
        result["error"] = "No API key configured."
        return result

    try:
        response = service.channels().list(
            id=channel_id,
            part="snippet,statistics,brandingSettings",
        ).execute()

        items = response.get("items", [])
        if not items:
            result["error"] = f"Channel not found: {channel_id}"
            return result

        item = items[0]
        snip = item.get("snippet", {})
        stats = item.get("statistics", {})

        result["channel"] = {
            "title": snip.get("title", ""),
            "description": snip.get("description", "")[:500],
            "custom_url": snip.get("customUrl", ""),
            "published": snip.get("publishedAt", ""),
            "country": snip.get("country", ""),
            "subscribers": int(stats.get("subscriberCount", 0)),
            "videos": int(stats.get("videoCount", 0)),
            "views": int(stats.get("viewCount", 0)),
            "thumbnail": snip.get("thumbnails", {}).get("high", {}).get("url", ""),
        }

    except Exception as e:
        result["error"] = f"YouTube API error: {e}"

    return result


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Data API v3 - Search and video analysis for SEO"
    )
    parser.add_argument(
        "command",
        choices=["search", "video", "channel"],
        help="Command: search, video (details), channel (info)",
    )
    parser.add_argument("query", help="Search query, video ID, or channel ID")
    parser.add_argument("--limit", type=int, default=10, help="Max results for search (default: 10)")
    parser.add_argument(
        "--order",
        choices=["relevance", "date", "rating", "viewCount", "title"],
        default="relevance",
        help="Sort order for search (default: relevance)",
    )
    parser.add_argument("--api-key", help="API key override")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "search":
        result = search_videos(args.query, max_results=args.limit, order=args.order, api_key=args.api_key)
    elif args.command == "video":
        result = get_video_details(args.query, api_key=args.api_key)
    elif args.command == "channel":
        result = get_channel_info(args.query, api_key=args.api_key)

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        if not args.json:
            sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if args.command == "search":
            print(f"=== YouTube Search: {args.query} ===")
            print(f"Results: {result.get('total_results', 0):,}")
            for i, v in enumerate(result.get("videos", []), 1):
                print(f"\n  {i}. {v['title']}")
                print(f"     {v['channel']} | {v['views']:,} views | {v['likes']:,} likes | {v['duration']}")
                print(f"     {v['url']}")
        elif args.command == "video":
            d = result.get("details", {})
            if d:
                print(f"=== {d.get('title')} ===")
                print(f"Channel: {d.get('channel')}")
                print(f"Views: {d.get('views', 0):,} | Likes: {d.get('likes', 0):,} | Comments: {d.get('comments_count', 0):,}")
                print(f"Published: {d.get('published', '')[:10]} | Duration: {d.get('duration')}")
                tags = d.get("tags", [])
                if tags:
                    print(f"Tags: {', '.join(tags[:10])}")
                comments = result.get("comments", [])
                if comments:
                    print(f"\nTop Comments ({len(comments)}):")
                    for c in comments[:5]:
                        print(f"  [{c['likes']} likes] {c['author']}: {c['text'][:100]}")
        elif args.command == "channel":
            ch = result.get("channel", {})
            if ch:
                print(f"=== {ch.get('title')} ===")
                print(f"Subscribers: {ch.get('subscribers', 0):,} | Videos: {ch.get('videos', 0):,} | Views: {ch.get('views', 0):,}")


if __name__ == "__main__":
    main()
