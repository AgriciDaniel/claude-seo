#!/usr/bin/env python3
"""Collect bounded public-topic evidence from Xquik for SEO research."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests


def _load_url_safety() -> None:
    script = Path(__file__).resolve()
    candidates = (script.parents[3] / "scripts", script.parents[2] / "seo" / "scripts")
    for candidate in candidates:
        if (candidate / "url_safety.py").is_file():
            sys.path.insert(0, str(candidate))
            return
    raise ImportError("Claude SEO URL safety module is unavailable")


_load_url_safety()
from url_safety import URLSafetyError, safe_requests_session  # noqa: E402

API_ORIGIN = "https://xquik.com"
API_BASE = f"{API_ORIGIN}/api/v1"
SEARCH_PATH = "/x/tweets/search"
RADAR_PATH = "/radar"
REQUEST_TIMEOUT = (5, 30)
MAX_SEARCH_RESULTS = 100
MAX_RADAR_RESULTS = 100
MAX_POST_TEXT = 2_000
MAX_QUERY_LENGTH = 512
LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
TWEET_ID_RE = re.compile(r"^[0-9]{1,32}$")
ERROR_CODE_RE = re.compile(r"^[a-z0-9_]{1,64}$")
RADAR_SOURCES = (
    "github",
    "google_trends",
    "hacker_news",
    "polymarket",
    "reddit",
    "trustmrr",
    "wikipedia",
)
RADAR_CATEGORIES = (
    "general",
    "tech",
    "dev",
    "science",
    "culture",
    "politics",
    "business",
    "entertainment",
)


class ResearchError(Exception):
    """Structured command failure safe for user-facing output."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retry_after = retry_after


class JsonArgumentParser(argparse.ArgumentParser):
    """Report CLI errors through the script's JSON envelope."""

    def error(self, message: str) -> None:
        raise ResearchError("invalid_arguments", f"Invalid arguments: {message}.")


def _observed_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bounded_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float) and value.is_integer():
        return max(int(value), 0)
    return None


def _bounded_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return max(value, 0)


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _api_key(environ: Mapping[str, str] = os.environ) -> str:
    key = environ.get("X_TWITTER_SCRAPER_API_KEY", "").strip()
    if not key:
        raise ResearchError(
            "missing_api_key",
            "Xquik API key missing. Set X_TWITTER_SCRAPER_API_KEY first.",
        )
    return key


def _provider_error_code(payload: Any) -> str:
    raw: Any = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(raw, dict):
        raw = raw.get("code") or raw.get("type")
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if ERROR_CODE_RE.fullmatch(normalized):
            return normalized
    return "http_error"


def _http_message(status: int) -> str:
    messages = {
        400: "Xquik rejected the request. Check the query and filters.",
        401: "Xquik authentication failed. Check the API key.",
        402: "Xquik subscription or credits required. Review the account first.",
        403: "Xquik denied this request. Check account access.",
        404: "Xquik endpoint unavailable. Check the current API contract.",
        408: "Xquik request timed out. Retry shortly.",
        422: "Xquik could not validate the request. Check each filter.",
        424: "X data is temporarily unavailable. Retry shortly.",
        429: "Xquik rate limit reached. Wait before retrying.",
        500: "Xquik returned a server error. Retry shortly.",
        502: "X data is temporarily unavailable. Retry shortly.",
        503: "Xquik is temporarily unavailable. Retry shortly.",
    }
    return messages.get(status, f"Xquik request failed with HTTP {status}.")


def _request_json(
    session: requests.Session,
    path: str,
    params: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    if path not in {SEARCH_PATH, RADAR_PATH}:
        raise ResearchError("invalid_endpoint", "Unsupported Xquik research endpoint.")
    try:
        response = session.get(
            f"{API_BASE}{path}",
            params=params,
            headers={"Accept": "application/json", "x-api-key": api_key},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise ResearchError(
            "network_error",
            f"Xquik request failed ({type(exc).__name__}). Retry shortly.",
        ) from None

    if 300 <= response.status_code < 400:
        raise ResearchError(
            "redirect_refused",
            "Xquik returned an unexpected redirect. Check the endpoint contract.",
            status=response.status_code,
        )

    try:
        payload = response.json()
    except (TypeError, ValueError):
        payload = None

    if response.status_code >= 400:
        retry_after = response.headers.get("Retry-After")
        raise ResearchError(
            _provider_error_code(payload),
            _http_message(response.status_code),
            status=response.status_code,
            retry_after=retry_after if retry_after and len(retry_after) <= 32 else None,
        )
    if not isinstance(payload, dict):
        raise ResearchError(
            "invalid_response",
            "Xquik returned an invalid JSON response. Retry shortly.",
            status=response.status_code,
        )
    return payload


def _tweet_url(tweet_id: str | None, username: str | None) -> str | None:
    if (
        not tweet_id
        or not TWEET_ID_RE.fullmatch(tweet_id)
        or not username
        or not USERNAME_RE.fullmatch(username)
    ):
        return None
    return f"https://x.com/{username}/status/{tweet_id}"


def _public_url(value: Any) -> str | None:
    candidate = _text(value)
    if not candidate or len(candidate) > 2_048:
        return None
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    return candidate


def _normalize_tweet(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    tweet_id = _text(raw.get("id"))
    text = _text(raw.get("text")) or ""
    if not tweet_id or not text:
        return None
    author_raw = raw.get("author")
    author = author_raw if isinstance(author_raw, dict) else {}
    username_raw = _text(author.get("username"))
    username = username_raw.lstrip("@") if username_raw else None
    truncated = len(text) > MAX_POST_TEXT
    return {
        "id": tweet_id,
        "text": text[:MAX_POST_TEXT],
        "text_truncated": truncated,
        "created_at": _text(raw.get("createdAt")) or _text(raw.get("created_at")),
        "author": {
            "username": username,
            "name": _text(author.get("name")),
            "verified": author.get("verified")
            if isinstance(author.get("verified"), bool)
            else None,
        },
        "metrics": {
            "likes": _bounded_int(_first(raw, "likeCount", "like_count")),
            "replies": _bounded_int(_first(raw, "replyCount", "reply_count")),
            "reposts": _bounded_int(_first(raw, "retweetCount", "retweet_count")),
            "quotes": _bounded_int(_first(raw, "quoteCount", "quote_count")),
            "views": _bounded_int(_first(raw, "viewCount", "view_count")),
            "bookmarks": _bounded_int(_first(raw, "bookmarkCount", "bookmark_count")),
        },
        "url": _tweet_url(tweet_id, username),
    }


def _normalize_radar_item(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    if not any(_text(raw.get(key)) for key in ("id", "title", "url")):
        return None
    return {
        "id": _text(raw.get("id")),
        "source_id": _text(raw.get("sourceId")),
        "title": _text(raw.get("title")),
        "description": _text(raw.get("description")),
        "url": _public_url(raw.get("url")),
        "source": _text(raw.get("source")),
        "category": _text(raw.get("category")),
        "region": _text(raw.get("region")),
        "language": _text(raw.get("language")),
        "score": _bounded_number(raw.get("score")),
        "published_at": _text(raw.get("publishedAt")) or _text(raw.get("published_at")),
    }


def search_posts(
    session: requests.Session,
    api_key: str,
    *,
    query: str,
    limit: int,
    query_type: str,
    since_time: str | None = None,
    until_time: str | None = None,
    language: str | None = None,
    replies: str = "exclude",
    retweets: str = "exclude",
) -> dict[str, Any]:
    query = query.strip()
    if not query or len(query) > MAX_QUERY_LENGTH:
        raise ResearchError(
            "invalid_query",
            f"Search query must contain 1 to {MAX_QUERY_LENGTH} characters.",
        )
    if not 1 <= limit <= MAX_SEARCH_RESULTS:
        raise ResearchError("invalid_limit", "Search limit must be between 1 and 100.")
    if query_type not in {"Latest", "Top"}:
        raise ResearchError("invalid_query_type", "Search order must be Latest or Top.")
    if language and not LANGUAGE_RE.fullmatch(language):
        raise ResearchError("invalid_language", "Use a language code such as en or es-MX.")
    if replies not in {"include", "exclude", "only"}:
        raise ResearchError("invalid_replies", "Replies filter is invalid.")
    if retweets not in {"include", "exclude", "only"}:
        raise ResearchError("invalid_retweets", "Retweets filter is invalid.")
    try:
        since = _parse_iso_time(since_time) if since_time else None
        until = _parse_iso_time(until_time) if until_time else None
    except ValueError:
        raise ResearchError(
            "invalid_time",
            "Search timestamps must use ISO 8601 and include a timezone.",
        ) from None
    if since and until:
        if since >= until:
            raise ResearchError(
                "invalid_time_range",
                "Search start time must be earlier than the end time.",
            )
    params: dict[str, Any] = {
        "q": query,
        "limit": limit,
        "queryType": query_type,
        "replies": replies,
        "retweets": retweets,
    }
    for key, value in (
        ("sinceTime", since_time),
        ("untilTime", until_time),
        ("language", language),
    ):
        if value:
            params[key] = value
    payload = _request_json(session, SEARCH_PATH, params, api_key)
    raw_tweets = payload.get("tweets")
    if not isinstance(raw_tweets, list):
        raise ResearchError("invalid_response", "Xquik search response has no tweet list.")
    results = [item for raw in raw_tweets[:limit] if (item := _normalize_tweet(raw)) is not None]
    return {
        "query": query,
        "query_type": query_type,
        "filters": {
            "since_time": since_time,
            "until_time": until_time,
            "language": language,
            "replies": replies,
            "retweets": retweets,
        },
        "total_returned": len(results),
        "results": results,
        "pagination": {
            "has_next_page": payload.get("has_next_page") is True,
        },
    }


def radar_topics(
    session: requests.Session,
    api_key: str,
    *,
    source: str | None,
    category: str | None,
    hours: int,
    limit: int,
    region: str,
) -> dict[str, Any]:
    if not 1 <= hours <= 72:
        raise ResearchError("invalid_hours", "Radar hours must be between 1 and 72.")
    if not 1 <= limit <= MAX_RADAR_RESULTS:
        raise ResearchError("invalid_limit", "Radar limit must be between 1 and 100.")
    if source and source not in RADAR_SOURCES:
        raise ResearchError("invalid_source", "Radar source is invalid.")
    if category and category not in RADAR_CATEGORIES:
        raise ResearchError("invalid_category", "Radar category is invalid.")
    try:
        region = _region(region)
    except argparse.ArgumentTypeError as exc:
        raise ResearchError("invalid_region", str(exc).capitalize() + ".") from None
    params: dict[str, Any] = {"hours": hours, "limit": limit, "region": region}
    if source:
        params["source"] = source
    if category:
        params["category"] = category
    payload = _request_json(session, RADAR_PATH, params, api_key)
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ResearchError("invalid_response", "Xquik Radar response has no item list.")
    results = [
        item for raw in raw_items[:limit] if (item := _normalize_radar_item(raw)) is not None
    ]
    return {
        "filters": {
            "source": source,
            "category": category,
            "hours": hours,
            "region": region,
        },
        "total_returned": len(results),
        "results": results,
        "pagination": {
            "has_more": payload.get("hasMore") is True,
        },
    }


def _parse_iso_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed


def _iso_time(value: str) -> str:
    try:
        _parse_iso_time(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "use an ISO 8601 timestamp with a timezone",
        ) from exc
    return value


def _language(value: str) -> str:
    if not LANGUAGE_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("use a language code such as en or es-MX")
    return value


def _query(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_QUERY_LENGTH:
        raise argparse.ArgumentTypeError(
            f"query must contain 1 to {MAX_QUERY_LENGTH} characters",
        )
    return normalized


def _region(value: str) -> str:
    normalized = value.strip()
    if normalized.lower() == "global":
        return "global"
    if len(normalized) == 2 and normalized.isascii() and normalized.isalpha():
        return normalized.upper()
    raise argparse.ArgumentTypeError("use global or a 2-letter region code")


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(
        description="Collect bounded public-topic evidence from Xquik.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    search = commands.add_parser("listen", help="Search public X posts.")
    search.add_argument("query", type=_query)
    search.add_argument("--limit", type=int, choices=range(1, MAX_SEARCH_RESULTS + 1), default=20)
    search.add_argument("--query-type", choices=("Latest", "Top"), default="Latest")
    search.add_argument("--since-time", type=_iso_time)
    search.add_argument("--until-time", type=_iso_time)
    search.add_argument("--language", type=_language)
    search.add_argument("--replies", choices=("include", "exclude", "only"), default="exclude")
    search.add_argument("--retweets", choices=("include", "exclude", "only"), default="exclude")

    radar = commands.add_parser("radar", help="Collect recent topic signals.")
    radar.add_argument("--source", choices=RADAR_SOURCES)
    radar.add_argument("--category", choices=RADAR_CATEGORIES)
    radar.add_argument("--hours", type=int, choices=range(1, 73), default=24)
    radar.add_argument("--limit", type=int, choices=range(1, MAX_RADAR_RESULTS + 1), default=20)
    radar.add_argument("--region", type=_region, default="global")
    return parser


def _success(command: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "success",
        "data": data,
        "error": None,
        "metadata": {
            "source": "xquik",
            "command": command,
            "observed_at": _observed_at(),
        },
    }


def _failure(command: str | None, error: ResearchError) -> dict[str, Any]:
    detail: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.status is not None:
        detail["http_status"] = error.status
    if error.retry_after is not None:
        detail["retry_after"] = error.retry_after
    return {
        "status": "error",
        "data": None,
        "error": detail,
        "metadata": {
            "source": "xquik",
            "command": command,
            "observed_at": _observed_at(),
        },
    }


def main(argv: list[str] | None = None) -> int:
    command = None
    try:
        args = _parser().parse_args(argv)
        command = args.command
        key = _api_key()
        with safe_requests_session(API_ORIGIN) as session:
            if command == "listen":
                data = search_posts(
                    session,
                    key,
                    query=args.query,
                    limit=args.limit,
                    query_type=args.query_type,
                    since_time=args.since_time,
                    until_time=args.until_time,
                    language=args.language,
                    replies=args.replies,
                    retweets=args.retweets,
                )
            else:
                data = radar_topics(
                    session,
                    key,
                    source=args.source,
                    category=args.category,
                    hours=args.hours,
                    limit=args.limit,
                    region=args.region,
                )
        output = _success(command, data)
        exit_code = 0
    except URLSafetyError:
        output = _failure(
            command,
            ResearchError(
                "network_policy_error",
                "Xquik endpoint failed URL safety validation. Stop this research run.",
            ),
        )
        exit_code = 1
    except ResearchError as exc:
        output = _failure(command, exc)
        exit_code = 1
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
