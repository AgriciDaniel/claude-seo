#!/usr/bin/env python3
"""
Umami self-hosted analytics query helper.

Reads stats, pageviews, and metrics from a self-hosted Umami instance for
SEO behavioral analysis. Provides the cookieless on-site engagement layer
(per-page bounce, time, referrers, events) that GA4 covers upstream.

Usage:
    python umami_stats.py check
    python umami_stats.py stats           --website-id <uuid> [--days 28]
    python umami_stats.py pageviews       --website-id <uuid> [--days 28] [--unit day] [--timezone Europe/London]
    python umami_stats.py metrics         --website-id <uuid> --type path   [--days 28] [--limit 100]
    python umami_stats.py metrics-expanded --website-id <uuid> [--type path] [--days 28] [--limit 100]
    python umami_stats.py active          --website-id <uuid>

Auth:
    Reads UMAMI_USERNAME and UMAMI_PASSWORD from the environment, or from
    a .env file at the repo root. Optional UMAMI_BASE_URL overrides the
    default https://analytics.crafts.software. Optional UMAMI_WEBSITE_ID
    supplies a default for --website-id.

    Credentials follow the Foundry service-credentials standard: the
    source of truth is the 1Password TSE vault "Umami" item. The .env
    in this repo is a gitignored consumer copy.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

DEFAULT_BASE_URL = "https://analytics.crafts.software"
DEFAULT_TIMEZONE = "Europe/London"
DEFAULT_DAYS = 28
# Cloudflare in front of self-hosted Umami blocks the default urllib UA.
USER_AGENT = "claude-seo-umami/0.1 (+https://github.com/the-software-engineer/claude-seo)"


class UmamiError(Exception):
    pass


def _load_dotenv(path: str) -> None:
    """Minimal .env loader. Doesn't override existing env vars. No dep on python-dotenv."""
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config() -> dict:
    _load_dotenv(os.path.join(_repo_root(), ".env"))
    return {
        "base_url": os.environ.get("UMAMI_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "username": os.environ.get("UMAMI_USERNAME"),
        "password": os.environ.get("UMAMI_PASSWORD"),
        "website_id": os.environ.get("UMAMI_WEBSITE_ID"),
    }


def login(base_url: str, username: str, password: str) -> str:
    payload = json.dumps({"username": username, "password": password}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/auth/login",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise UmamiError(f"login failed: HTTP {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise UmamiError(f"login failed: {e.reason}") from e
    token = data.get("token")
    if not token:
        raise UmamiError("login response missing token")
    return token


def _get(base_url: str, token: str, path: str):
    req = urllib.request.Request(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise UmamiError(f"GET {path} -> HTTP {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise UmamiError(f"GET {path} -> {e.reason}") from e


def _ms_range(days: int):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _qs(params: dict) -> str:
    return urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})


# ---- API calls ----

def list_websites(base_url, token):
    return _get(base_url, token, "/api/websites")


def get_stats(base_url, token, website_id, start_at, end_at):
    qs = _qs({"startAt": start_at, "endAt": end_at})
    return _get(base_url, token, f"/api/websites/{website_id}/stats?{qs}")


def get_pageviews(base_url, token, website_id, start_at, end_at, unit, timezone_str):
    qs = _qs({"startAt": start_at, "endAt": end_at, "unit": unit, "timezone": timezone_str})
    return _get(base_url, token, f"/api/websites/{website_id}/pageviews?{qs}")


def get_metrics(base_url, token, website_id, start_at, end_at, metric_type, limit):
    qs = _qs({"startAt": start_at, "endAt": end_at, "type": metric_type, "limit": limit})
    return _get(base_url, token, f"/api/websites/{website_id}/metrics?{qs}")


def get_metrics_expanded(base_url, token, website_id, start_at, end_at, metric_type, limit):
    qs = _qs({"startAt": start_at, "endAt": end_at, "type": metric_type, "limit": limit})
    return _get(base_url, token, f"/api/websites/{website_id}/metrics/expanded?{qs}")


def get_active(base_url, token, website_id):
    return _get(base_url, token, f"/api/websites/{website_id}/active")


# ---- CLI helpers ----

def _need_token(cfg: dict) -> str:
    if not cfg["username"] or not cfg["password"]:
        raise UmamiError(
            "UMAMI_USERNAME and UMAMI_PASSWORD must be set. "
            "Populate .env at the repo root (see .env.example) or export them."
        )
    return login(cfg["base_url"], cfg["username"], cfg["password"])


def _need_website_id(args, cfg: dict) -> str:
    wid = getattr(args, "website_id", None) or cfg["website_id"]
    if not wid:
        raise UmamiError(
            "Website ID required: pass --website-id or set UMAMI_WEBSITE_ID. "
            "Run `python scripts/umami_stats.py check` to list available website IDs."
        )
    return wid


def _ms_window(args):
    if getattr(args, "start_at", None) and getattr(args, "end_at", None):
        return int(args.start_at), int(args.end_at)
    return _ms_range(args.days)


# ---- Commands ----

def cmd_check(_args, cfg):
    out = {
        "base_url": cfg["base_url"],
        "username_set": bool(cfg["username"]),
        "password_set": bool(cfg["password"]),
        "default_website_id": cfg["website_id"],
    }
    if not cfg["username"] or not cfg["password"]:
        out["status"] = "missing-credentials"
        out["error"] = (
            "UMAMI_USERNAME and/or UMAMI_PASSWORD not set. "
            "Copy .env.example to .env at the repo root and fill values "
            "from the 1Password TSE vault 'Umami' item."
        )
        print(json.dumps(out, indent=2))
        return 1
    try:
        token = login(cfg["base_url"], cfg["username"], cfg["password"])
        websites = list_websites(cfg["base_url"], token)
    except UmamiError as e:
        out["status"] = "error"
        out["error"] = str(e)
        print(json.dumps(out, indent=2))
        return 1

    nodes = websites
    if isinstance(websites, dict) and "data" in websites:
        nodes = websites["data"]
    if not isinstance(nodes, list):
        nodes = []
    out["status"] = "ok"
    out["websites"] = [
        {"id": w.get("id"), "name": w.get("name"), "domain": w.get("domain")}
        for w in nodes
    ]
    print(json.dumps(out, indent=2))
    return 0


def cmd_stats(args, cfg):
    wid = _need_website_id(args, cfg)
    token = _need_token(cfg)
    start_at, end_at = _ms_window(args)
    data = get_stats(cfg["base_url"], token, wid, start_at, end_at)
    print(json.dumps(
        {"website_id": wid, "start_at": start_at, "end_at": end_at, "stats": data},
        indent=2,
    ))
    return 0


def cmd_pageviews(args, cfg):
    wid = _need_website_id(args, cfg)
    token = _need_token(cfg)
    start_at, end_at = _ms_window(args)
    data = get_pageviews(cfg["base_url"], token, wid, start_at, end_at, args.unit, args.timezone)
    print(json.dumps(
        {"website_id": wid, "start_at": start_at, "end_at": end_at, "unit": args.unit, "data": data},
        indent=2,
    ))
    return 0


def cmd_metrics(args, cfg):
    wid = _need_website_id(args, cfg)
    token = _need_token(cfg)
    start_at, end_at = _ms_window(args)
    data = get_metrics(cfg["base_url"], token, wid, start_at, end_at, args.type, args.limit)
    print(json.dumps(
        {"website_id": wid, "start_at": start_at, "end_at": end_at, "type": args.type, "data": data},
        indent=2,
    ))
    return 0


def cmd_metrics_expanded(args, cfg):
    wid = _need_website_id(args, cfg)
    token = _need_token(cfg)
    start_at, end_at = _ms_window(args)
    data = get_metrics_expanded(cfg["base_url"], token, wid, start_at, end_at, args.type, args.limit)
    print(json.dumps(
        {"website_id": wid, "start_at": start_at, "end_at": end_at, "type": args.type, "data": data},
        indent=2,
    ))
    return 0


def cmd_active(args, cfg):
    wid = _need_website_id(args, cfg)
    token = _need_token(cfg)
    data = get_active(cfg["base_url"], token, wid)
    print(json.dumps({"website_id": wid, "active": data}, indent=2))
    return 0


def _add_window_args(p):
    p.add_argument("--website-id", help="Umami website UUID. Falls back to UMAMI_WEBSITE_ID.")
    p.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"Lookback window in days (default {DEFAULT_DAYS}).")
    p.add_argument("--start-at", type=int, help="Override window start (ms since epoch).")
    p.add_argument("--end-at", type=int, help="Override window end (ms since epoch).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="umami_stats", description=__doc__.splitlines()[1])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="Verify credentials and list available websites.")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("stats", help="Pageviews, visitors, visits, bounces, totaltime over a window.")
    _add_window_args(p)
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("pageviews", help="Pageviews + sessions timeseries.")
    _add_window_args(p)
    p.add_argument("--unit", default="day", choices=["year", "month", "day", "hour", "minute"])
    p.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    p.set_defaults(func=cmd_pageviews)

    p = sub.add_parser("metrics", help="Top values by type (path, referrer, browser, device, country, event...).")
    _add_window_args(p)
    p.add_argument("--type", required=True, help="path | referrer | browser | os | device | country | event ...")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_metrics)

    p = sub.add_parser(
        "metrics-expanded",
        help="Per-value engagement: pageviews, visitors, visits, bounces, totaltime. The SXO/content layer.",
    )
    _add_window_args(p)
    p.add_argument("--type", default="path", help="Default 'path' returns per-URL engagement (the SXO/content layer).")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_metrics_expanded)

    p = sub.add_parser("active", help="Active visitors in the last 5 minutes.")
    p.add_argument("--website-id", help="Umami website UUID. Falls back to UMAMI_WEBSITE_ID.")
    p.set_defaults(func=cmd_active)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    cfg = _config()
    try:
        return args.func(args, cfg)
    except UmamiError as e:
        print(json.dumps({"status": "error", "error": str(e)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
