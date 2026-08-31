#!/usr/bin/env python3
"""
Matomo Reporting API client for Claude SEO.

Queries the Matomo Reporting API for organic traffic, top landing pages,
device and country breakdowns, and referrer analysis. Self-hosted Matomo
is supported alongside Matomo Cloud.

Usage:
    python matomo_report.py organic
    python matomo_report.py top-pages --site-id 1 --days 28 --limit 50 --json
    python matomo_report.py device
    python matomo_report.py country
    python matomo_report.py referrers
    python matomo_report.py keywords
    python matomo_report.py check
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests",
          file=sys.stderr)
    sys.exit(1)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
try:
    from matomo_auth import (
        get_matomo_site_id,
        get_matomo_token,
        get_matomo_url,
        load_config,
    )
except ImportError:
    print("Error: matomo_auth.py required in scripts/", file=sys.stderr)
    sys.exit(1)

DEFAULT_TIMEOUT = 30
DEFAULT_DAYS = 28
DEFAULT_LIMIT = 50
MAX_LIMIT = 500

_TOKEN_REDACTION_RE = re.compile(r"(token_auth=|token=|password=)[^\s&]+", re.IGNORECASE)


def _redact(text: str) -> str:
    """Strip token_auth and password query values from any error string."""
    return _TOKEN_REDACTION_RE.sub(r"\1<redacted>", text)


def _envelope(status: str, data: Any = None, error: Optional[str] = None,
              method: Optional[str] = None) -> dict:
    """Build a standard response envelope matching repo-wide contract."""
    metadata = {
        "source": "matomo_report",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if method:
        metadata["method"] = method
    return {
        "status": status,
        "data": data,
        "error": error,
        "metadata": metadata,
    }


def _request(url: str, token: str, params: dict, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    POST to Matomo with token_auth in body.

    Matomo accepts both GET and POST. POST keeps the token out of URLs and
    access logs.

    Returns:
        Standard response envelope; on Matomo API ``result=error`` payloads,
        the envelope is ``status=error``.
    """
    body = dict(params)
    body["module"] = "API"
    body["format"] = "JSON"
    body["token_auth"] = token

    headers = {"User-Agent": "ClaudeSEO/2.2.5"}
    try:
        resp = requests.post(
            f"{url.rstrip('/')}/index.php",
            data=body,
            headers=headers,
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        return _envelope("error", None,
                         f"Matomo request timed out after {timeout}s")
    except requests.exceptions.SSLError as e:
        return _envelope("error", None,
                         f"SSL error contacting Matomo: {type(e).__name__}")
    except requests.exceptions.ConnectionError as e:
        return _envelope("error", None,
                         f"Connection error contacting Matomo: {type(e).__name__}")
    except requests.exceptions.RequestException as e:
        return _envelope("error", None,
                         f"Matomo request failed ({type(e).__name__})")

    if resp.status_code == 401 or resp.status_code == 403:
        return _envelope("error", None,
                         "Matomo authentication failed. Verify token_auth and that the "
                         "API token has view access to the site.",
                         method=params.get("method"))
    if resp.status_code >= 400:
        return _envelope("error", None,
                         f"Matomo HTTP {resp.status_code}",
                         method=params.get("method"))

    try:
        payload = resp.json()
    except ValueError:
        return _envelope("error", None,
                         "Matomo returned a non-JSON response. "
                         "Check that MATOMO_URL points at the Matomo root.",
                         method=params.get("method"))

    if isinstance(payload, dict) and payload.get("result") == "error":
        msg = str(payload.get("message", "Matomo API error"))
        return _envelope("error", None, _redact(msg), method=params.get("method"))

    return _envelope("success", payload, None, method=params.get("method"))


def _bounded_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return default


def _bounded_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_site_id(args: argparse.Namespace) -> Optional[str]:
    sid = args.site_id or get_matomo_site_id()
    if sid is None:
        return None
    return str(sid).strip() or None


def _date_range(days: int) -> tuple:
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def organic_traffic_report(site_id: str, url: str, token: str,
                           days: int = DEFAULT_DAYS,
                           limit: int = DEFAULT_LIMIT) -> dict:
    """
    Organic traffic trend from Matomo using the ``referrerType==search`` segment.

    Combines a per-day VisitsSummary with the top organic landing pages.
    Returns an envelope with date_range, totals, daily_data, and top_pages.
    """
    start, end = _date_range(days)
    date_arg = f"{start},{end}"

    summary_resp = _request(url, token, {
        "method": "VisitsSummary.get",
        "idSite": site_id,
        "period": "day",
        "date": date_arg,
        "segment": "referrerType==search",
    })
    if summary_resp["status"] != "success":
        return summary_resp

    raw = summary_resp["data"] or {}
    daily_data = []
    totals = {"visits": 0, "unique_visitors": 0, "pageviews": 0,
              "bounce_count": 0, "sum_visit_length": 0, "actions": 0}
    if isinstance(raw, dict):
        for date_str in sorted(raw.keys()):
            row = raw[date_str] or {}
            visits = _bounded_int(row.get("nb_visits"))
            uniq = _bounded_int(row.get("nb_uniq_visitors"))
            actions = _bounded_int(row.get("nb_actions"))
            pageviews = _bounded_int(row.get("nb_pageviews"), actions)
            bounce_count = _bounded_int(row.get("bounce_count"))
            sum_visit_length = _bounded_int(row.get("sum_visit_length"))
            bounce_rate = (bounce_count / visits * 100.0) if visits else 0.0
            avg_time = (sum_visit_length / visits) if visits else 0.0
            daily_data.append({
                "date": date_str,
                "visits": visits,
                "unique_visitors": uniq,
                "pageviews": pageviews,
                "actions": actions,
                "bounce_rate": round(bounce_rate, 1),
                "avg_time_on_site": round(avg_time, 1),
            })
            totals["visits"] += visits
            totals["unique_visitors"] += uniq
            totals["pageviews"] += pageviews
            totals["bounce_count"] += bounce_count
            totals["sum_visit_length"] += sum_visit_length
            totals["actions"] += actions

    if totals["visits"]:
        totals["bounce_rate"] = round(totals["bounce_count"] / totals["visits"] * 100.0, 1)
        totals["avg_time_on_site"] = round(totals["sum_visit_length"] / totals["visits"], 1)
        totals["avg_daily_visits"] = round(totals["visits"] / max(1, len(daily_data)), 1)
    else:
        totals["bounce_rate"] = 0.0
        totals["avg_time_on_site"] = 0.0
        totals["avg_daily_visits"] = 0.0

    pages_resp = _request(url, token, {
        "method": "Actions.getEntryPageUrls",
        "idSite": site_id,
        "period": "range",
        "date": date_arg,
        "segment": "referrerType==search",
        "filter_limit": str(min(limit, MAX_LIMIT)),
        "filter_sort_column": "nb_visits",
        "filter_sort_order": "desc",
    })
    top_pages = []
    pages_error: Optional[str] = None
    if pages_resp["status"] == "success":
        raw_pages = pages_resp["data"]
        if isinstance(raw_pages, list):
            for entry in raw_pages:
                if not isinstance(entry, dict):
                    continue
                top_pages.append({
                    "url": entry.get("label", ""),
                    "visits": _bounded_int(entry.get("nb_visits")),
                    "unique_visitors": _bounded_int(entry.get("nb_uniq_visitors")),
                    "actions": _bounded_int(entry.get("nb_actions")),
                    "bounce_rate": round(_bounded_float(entry.get("bounce_rate")) * 100, 1),
                })
        elif isinstance(raw_pages, dict):
            for url_key, entry in raw_pages.items():
                if not isinstance(entry, dict):
                    continue
                top_pages.append({
                    "url": entry.get("label") or url_key,
                    "visits": _bounded_int(entry.get("nb_visits")),
                    "unique_visitors": _bounded_int(entry.get("nb_uniq_visitors")),
                    "actions": _bounded_int(entry.get("nb_actions")),
                    "bounce_rate": round(_bounded_float(entry.get("bounce_rate")) * 100, 1),
                })
    else:
        pages_error = pages_resp.get("error")

    result = {
        "site_id": site_id,
        "date_range": {"start": start, "end": end},
        "segment": "referrerType==search",
        "totals": totals,
        "daily_data": daily_data,
        "top_pages": top_pages,
    }
    if pages_error:
        result["pages_error"] = pages_error

    return _envelope("success", result, None, method="VisitsSummary.get")


def top_pages_report(site_id: str, url: str, token: str,
                     days: int = DEFAULT_DAYS,
                     limit: int = DEFAULT_LIMIT) -> dict:
    """Top organic landing pages only."""
    full = organic_traffic_report(site_id, url, token, days=days, limit=limit)
    if full["status"] != "success":
        return full
    return _envelope("success", {
        "site_id": site_id,
        "date_range": full["data"]["date_range"],
        "segment": full["data"]["segment"],
        "total_organic_visits": full["data"]["totals"]["visits"],
        "pages": full["data"]["top_pages"],
    }, None, method="Actions.getEntryPageUrls")


def device_breakdown(site_id: str, url: str, token: str,
                     days: int = DEFAULT_DAYS) -> dict:
    """Visits by device type (Desktop / Smartphone / Tablet / ...)."""
    start, end = _date_range(days)
    date_arg = f"{start},{end}"

    resp = _request(url, token, {
        "method": "DevicesDetection.getType",
        "idSite": site_id,
        "period": "range",
        "date": date_arg,
        "segment": "referrerType==search",
    })
    if resp["status"] != "success":
        return resp

    raw = resp["data"]
    devices = []
    if isinstance(raw, dict):
        for device_type, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            visits = _bounded_int(entry.get("nb_visits"))
            devices.append({
                "device_type": entry.get("label") or device_type,
                "visits": visits,
                "unique_visitors": _bounded_int(entry.get("nb_uniq_visitors")),
                "bounce_rate": round(_bounded_float(entry.get("bounce_rate")) * 100, 1),
            })
    devices.sort(key=lambda d: d["visits"], reverse=True)

    return _envelope("success", {
        "site_id": site_id,
        "date_range": {"start": start, "end": end},
        "segment": "referrerType==search",
        "devices": devices,
    }, None, method="DevicesDetection.getType")


def country_breakdown(site_id: str, url: str, token: str,
                      days: int = DEFAULT_DAYS,
                      limit: int = 20) -> dict:
    """Visits by country (ISO-3166-1 alpha-2)."""
    start, end = _date_range(days)
    date_arg = f"{start},{end}"

    resp = _request(url, token, {
        "method": "UserCountry.getCountry",
        "idSite": site_id,
        "period": "range",
        "date": date_arg,
        "segment": "referrerType==search",
        "filter_limit": str(min(limit, MAX_LIMIT)),
    })
    if resp["status"] != "success":
        return resp

    raw = resp["data"]
    countries = []
    if isinstance(raw, dict):
        for code, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            countries.append({
                "country_code": code,
                "country": entry.get("label", code),
                "visits": _bounded_int(entry.get("nb_visits")),
                "unique_visitors": _bounded_int(entry.get("nb_uniq_visitors")),
            })
    countries.sort(key=lambda c: c["visits"], reverse=True)

    return _envelope("success", {
        "site_id": site_id,
        "date_range": {"start": start, "end": end},
        "segment": "referrerType==search",
        "countries": countries[:limit],
    }, None, method="UserCountry.getCountry")


def referrers_report(site_id: str, url: str, token: str,
                     days: int = DEFAULT_DAYS) -> dict:
    """
    Channel breakdown: direct, search, websites, social, campaigns.
    Plus top search engines for the search channel.
    """
    start, end = _date_range(days)
    date_arg = f"{start},{end}"

    types_resp = _request(url, token, {
        "method": "Referrers.getReferrersType",
        "idSite": site_id,
        "period": "range",
        "date": date_arg,
    })
    if types_resp["status"] != "success":
        return types_resp

    raw = types_resp["data"]
    channels = []
    if isinstance(raw, dict):
        for key, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            channels.append({
                "channel": entry.get("label") or key,
                "visits": _bounded_int(entry.get("nb_visits")),
                "unique_visitors": _bounded_int(entry.get("nb_uniq_visitors")),
                "actions": _bounded_int(entry.get("nb_actions")),
            })
    channels.sort(key=lambda c: c["visits"], reverse=True)

    engines_resp = _request(url, token, {
        "method": "Referrers.getSearchEngines",
        "idSite": site_id,
        "period": "range",
        "date": date_arg,
    })
    engines: list = []
    engines_error: Optional[str] = None
    if engines_resp["status"] == "success":
        raw_engines = engines_resp["data"]
        if isinstance(raw_engines, dict):
            for key, entry in raw_engines.items():
                if not isinstance(entry, dict):
                    continue
                engines.append({
                    "search_engine": entry.get("label") or key,
                    "visits": _bounded_int(entry.get("nb_visits")),
                })
        engines.sort(key=lambda e: e["visits"], reverse=True)
    else:
        engines_error = engines_resp.get("error")

    return _envelope("success", {
        "site_id": site_id,
        "date_range": {"start": start, "end": end},
        "channels": channels,
        "search_engines": engines,
    }, engines_error, method="Referrers.getReferrersType")


def keywords_report(site_id: str, url: str, token: str,
                    days: int = DEFAULT_DAYS,
                    limit: int = 50) -> dict:
    """
    Organic search keywords. Many entries will be '(not provided)' or
    '(no keyword)' due to browser privacy and Matomo's keyword anonymization.
    The report surfaces the raw distribution and flags when >50% of entries
    are anonymized, which is the norm on modern browsers.
    """
    start, end = _date_range(days)
    date_arg = f"{start},{end}"

    resp = _request(url, token, {
        "method": "Referrers.getKeywords",
        "idSite": site_id,
        "period": "range",
        "date": date_arg,
        "segment": "referrerType==search",
        "filter_limit": str(min(limit, MAX_LIMIT)),
    })
    if resp["status"] != "success":
        return resp

    raw = resp["data"]
    keywords_by_label: dict[str, dict] = {}
    anonymized_count = 0
    if isinstance(raw, dict):
        for kw, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            visits = _bounded_int(entry.get("nb_visits"))
            label = entry.get("label") or kw
            if label in ("", "(not provided)", "(no keyword)"):
                anonymized_count += visits or 0
                label = "(not provided)"
            bucket = keywords_by_label.setdefault(label, {"keyword": label, "visits": 0})
            bucket["visits"] += visits
    keywords = list(keywords_by_label.values())
    keywords.sort(key=lambda k: k["visits"], reverse=True)
    total_visits = sum(k["visits"] for k in keywords)
    anonymized_share = (
        round(anonymized_count / total_visits * 100, 1) if total_visits else 0.0
    )

    return _envelope("success", {
        "site_id": site_id,
        "date_range": {"start": start, "end": end},
        "segment": "referrerType==search",
        "keywords": keywords,
        "anonymized_share_pct": anonymized_share,
        "note": (
            "Many keywords surface as '(not provided)' due to browser and "
            "Matomo privacy anonymization. High anonymized_share_pct is normal."
        ),
    }, None, method="Referrers.getKeywords")


def check_command() -> dict:
    """Lightweight probe: who am I + version, used by --check subcommand."""
    from matomo_auth import _probe_version, _sanity_check_instance_url

    config = load_config()
    url = _sanity_check_instance_url(config.get("matomo_url") or "")
    token = config.get("matomo_token")
    site_id = config.get("matomo_site_id")

    if not url or not token:
        return _envelope("error", None,
                         "Matomo credentials incomplete. Run python matomo_auth.py --setup.")

    probe = _probe_version(url, token)
    if not probe["ok"]:
        return _envelope("error", None, probe.get("error"), method="API.getMatomoVersion")
    return _envelope("success", {
        "instance": url,
        "site_id": site_id,
        "version": probe.get("version"),
    }, None, method="API.getMatomoVersion")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Matomo Reporting API - traffic reports (GA4 alternative)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--site-id", "-s",
                        help="Matomo idSite (overrides config default)")
    common.add_argument("--days", "-d", type=int, default=DEFAULT_DAYS,
                        help=f"Number of days (default: {DEFAULT_DAYS})")
    common.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"Max rows (default: {DEFAULT_LIMIT})")
    common.add_argument("--json", "-j", action="store_true",
                        help="Output as JSON")

    sub.add_parser("check", parents=[common],
                   help="Verify Matomo credentials and connectivity")
    sub.add_parser("organic", parents=[common],
                   help="Organic traffic trend + top landing pages")
    sub.add_parser("top-pages", parents=[common],
                   help="Top organic landing pages only")
    sub.add_parser("device", parents=[common],
                   help="Visits broken down by device type")
    sub.add_parser("country", parents=[common],
                   help="Visits broken down by country")
    sub.add_parser("referrers", parents=[common],
                   help="Channel breakdown (direct / search / website / social) + search engines")
    sub.add_parser("keywords", parents=[common],
                   help="Organic search keywords (often '(not provided)')")

    args = parser.parse_args()

    if args.command == "check":
        result = check_command()
    else:
        url = get_matomo_url()
        token = get_matomo_token()
        site_id = _resolve_site_id(args)

        if not url:
            print("Error: MATOMO_URL is not configured. "
                  "Set MATOMO_URL env or add 'matomo_url' to "
                  f"{_SCRIPTS_DIR}/../../scripts/matomo_auth.py config.",
                  file=sys.stderr)
            return 1
        if not token:
            print("Error: MATOMO_API_TOKEN (or MATOMO_TOKEN) is not configured.",
                  file=sys.stderr)
            return 1
        if not site_id:
            print("Error: --site-id or MATOMO_SITE_ID is required.", file=sys.stderr)
            return 1

        if args.command == "organic":
            result = organic_traffic_report(site_id, url, token,
                                            days=args.days, limit=args.limit)
        elif args.command == "top-pages":
            result = top_pages_report(site_id, url, token,
                                      days=args.days, limit=args.limit)
        elif args.command == "device":
            result = device_breakdown(site_id, url, token, days=args.days)
        elif args.command == "country":
            result = country_breakdown(site_id, url, token,
                                       days=args.days, limit=args.limit)
        elif args.command == "referrers":
            result = referrers_report(site_id, url, token, days=args.days)
        elif args.command == "keywords":
            result = keywords_report(site_id, url, token,
                                    days=args.days, limit=args.limit)
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2

    if result.get("error") and not args.json:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        _print_human(result, args.command)

    return 0 if result.get("status") == "success" else 1


def _print_human(result: dict, command: str) -> None:
    data = result.get("data") or {}
    if command == "check":
        print("=== Matomo Connectivity Check ===")
        print(f"Instance: {data.get('instance')}")
        print(f"Site ID:  {data.get('site_id')}")
        print(f"Version:  {data.get('version')}")
        return

    dr = data.get("date_range", {})
    print(f"=== Matomo {command} Report ===")
    if "site_id" in data:
        print(f"Site ID: {data['site_id']}")
    if dr:
        print(f"Period: {dr.get('start')} to {dr.get('end')}")

    if command == "organic":
        totals = data.get("totals", {})
        print(f"\nVisits: {totals.get('visits', 0):,} | "
              f"Unique Visitors: {totals.get('unique_visitors', 0):,}")
        print(f"Avg Daily Visits: {totals.get('avg_daily_visits', 0):,.0f} | "
              f"Bounce: {totals.get('bounce_rate', 0)}%")
        print(f"Avg Time on Site: {totals.get('avg_time_on_site', 0):.1f}s")
        pages = data.get("top_pages", [])
        if pages:
            print(f"\nTop {min(10, len(pages))} Organic Landing Pages:")
            for i, p in enumerate(pages[:10], 1):
                print(f"  {i:2d}. {p['url']} ({p['visits']:,} visits)")
    elif command == "top-pages":
        print(f"Total organic visits: {data.get('total_organic_visits', 0):,}")
        for i, p in enumerate(data.get("pages", [])[:20], 1):
            print(f"  {i:2d}. {p['url']} ({p['visits']:,})")
    elif command == "device":
        for d in data.get("devices", []):
            print(f"  {d['device_type']}: {d['visits']:,} visits "
                  f"(bounce {d['bounce_rate']}%)")
    elif command == "country":
        for c in data.get("countries", [])[:20]:
            print(f"  {c['country']} ({c['country_code']}): {c['visits']:,}")
    elif command == "referrers":
        for ch in data.get("channels", []):
            print(f"  {ch['channel']}: {ch['visits']:,} visits")
        engines = data.get("search_engines", [])
        if engines:
            print("\nSearch Engines:")
            for e in engines[:10]:
                print(f"  {e['search_engine']}: {e['visits']:,}")
    elif command == "keywords":
        note = data.get("note")
        share = data.get("anonymized_share_pct", 0)
        print(f"\nAnonymized share: {share}%")
        if note:
            print(f"Note: {note}")
        for k in data.get("keywords", [])[:20]:
            print(f"  {k['keyword']}: {k['visits']:,}")


if __name__ == "__main__":
    sys.exit(main())