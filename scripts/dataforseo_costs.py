#!/usr/bin/env python3
"""
DataForSEO API cost estimation, approval, and budget tracking.

Provides cost-aware guardrails for DataForSEO API usage:
- Estimate costs before API calls
- Threshold-based approval workflow
- Session and daily budget tracking
- Spending history and summaries

Config: ~/.config/claude-seo/dataforseo-costs.json
Ledger: ~/.config/claude-seo/dataforseo-ledger.json
Set CLAUDE_SEO_CONFIG_DIR to point both somewhere else (used by the tests).

Usage:
    python dataforseo_costs.py estimate <endpoint> [--count N] [--items N]
    python dataforseo_costs.py check <endpoint> [--count N] [--items N]

<endpoint> is a v3 path such as /v3/serp/google/organic/live/advanced or a
dataforseo-mcp-server 2.8.10 tool name such as serp_organic_live_advanced.
    python dataforseo_costs.py log <endpoint> <cost> [--note TEXT]
    python dataforseo_costs.py summary [--days N]
    python dataforseo_costs.py today
    python dataforseo_costs.py config [--mode always|threshold|none] [--threshold AMOUNT] [--daily-limit AMOUNT]
    python dataforseo_costs.py reset

Original concept: Matej Marjanovic (Pro Hub Challenge)
Security fixes: config path corrected to ~/.config/claude-seo/
"""

import argparse
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

# ----- paths -----
# CLAUDE_SEO_CONFIG_DIR lets tests (and anyone running an isolated budget) point
# the ledger somewhere other than the real one. Resolved at import.
CONFIG_DIR = Path(
    os.environ.get("CLAUDE_SEO_CONFIG_DIR") or Path.home() / ".config" / "claude-seo"
)
CONFIG_FILE = CONFIG_DIR / "dataforseo-costs.json"
LEDGER_FILE = CONFIG_DIR / "dataforseo-ledger.json"
LOCK_FILE = CONFIG_DIR / "dataforseo-ledger.lock"

# ----- cost table (USD) -----
# Keyed on the DataForSEO v3 endpoint path, which is what DataForSEO bills and
# what dataforseo-mcp-server 3.x takes as `path` in `api_request`.
#
# Source: the per-API pages under https://dataforseo.com/pricing, read
# 2026-11-15. Live mode unless noted; merchant entries use the standard queue,
# because scripts/dataforseo_merchant.py posts tasks there.
#
# Each entry has one of two shapes:
#   {"task": T, "item": I}    T per task plus I per returned item/row
#   {"task": T, "block": N}   T per started block of N results (SERP-style;
#                             depth is rounded up to the next block)
# A price that is per task only is {"task": T, "item": 0}.
#
# Paid parameters are not modelled: search operators (x5) and pixel rankings
# or AI Overview (+1 base) on SERP, include_clickstream_data (x2) on Labs,
# enable_javascript / enable_browser_rendering and similar on On-Page. The
# billed amount is the `cost` field of the real response; with
# dataforseo-mcp-server 3.x it is returned only when `noAiMode` is true.
COST_TABLE = {
    # SERP API
    "/v3/serp/google/organic/live/advanced": {"task": 0.002, "block": 10},
    "/v3/serp/google/organic/live/regular": {"task": 0.002, "block": 10},
    "/v3/serp/google/images/live/advanced": {"task": 0.002, "block": 100},
    "/v3/serp/youtube/organic/live/advanced": {"task": 0.002, "block": 20},
    "/v3/serp/youtube/video_info/live/advanced": {"task": 0.006, "item": 0},
    "/v3/serp/youtube/video_comments/live/advanced": {"task": 0.002, "block": 20},
    "/v3/serp/youtube/video_subtitles/live/advanced": {"task": 0.006, "item": 0},
    # Keywords Data API (billed for setting the task; search_volume takes up
    # to 1,000 keywords, explore up to 5)
    "/v3/keywords_data/google_ads/search_volume/live": {"task": 0.09, "item": 0},
    "/v3/keywords_data/google_trends/explore/live": {"task": 0.011, "item": 0},
    # DataForSEO Labs API (Google): one rate for all endpoints listed here
    "/v3/dataforseo_labs/google/keyword_ideas/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/keyword_suggestions/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/related_keywords/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/bulk_keyword_difficulty/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/search_intent/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/competitors_domain/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/domain_rank_overview/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/bulk_traffic_estimation/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/ranked_keywords/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/relevant_pages/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/domain_intersection/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/subdomains/live": {"task": 0.012, "item": 0.00012},
    "/v3/dataforseo_labs/google/top_searches/live": {"task": 0.012, "item": 0.00012},
    # On-Page API
    "/v3/on_page/instant_pages": {"task": 0.00015, "item": 0},
    "/v3/on_page/content_parsing/live": {"task": 0.00015, "item": 0},
    "/v3/on_page/lighthouse/live/json": {"task": 0.005, "item": 0},
    # Backlinks API: one rate for all endpoints
    "/v3/backlinks/summary/live": {"task": 0.024, "item": 0.000036},
    "/v3/backlinks/backlinks/live": {"task": 0.024, "item": 0.000036},
    "/v3/backlinks/anchors/live": {"task": 0.024, "item": 0.000036},
    "/v3/backlinks/referring_domains/live": {"task": 0.024, "item": 0.000036},
    "/v3/backlinks/bulk_spam_score/live": {"task": 0.024, "item": 0.000036},
    "/v3/backlinks/timeseries_summary/live": {"task": 0.024, "item": 0.000036},
    "/v3/backlinks/domain_intersection/live": {"task": 0.024, "item": 0.000036},
    # Domain Analytics API
    "/v3/domain_analytics/technologies/domain_technologies/live": {"task": 0.012, "item": 0},
    "/v3/domain_analytics/whois/overview/live": {"task": 0.12, "item": 0.0012},
    # Content Analysis API: one rate for all endpoints
    "/v3/content_analysis/search/live": {"task": 0.024, "item": 0.000036},
    "/v3/content_analysis/summary/live": {"task": 0.024, "item": 0.000036},
    "/v3/content_analysis/phrase_trends/live": {"task": 0.024, "item": 0.000036},
    # Business Data API
    "/v3/business_data/business_listings/search/live": {"task": 0.012, "item": 0.00036},
    # AI Optimization API
    "/v3/ai_optimization/chat_gpt/llm_scraper/live/advanced": {"task": 0.004, "item": 0},
    "/v3/ai_optimization/llm_mentions/search/live": {"task": 0.1, "item": 0.001},
    "/v3/ai_optimization/llm_mentions/top_domains/live": {"task": 0.1, "item": 0.001},
    "/v3/ai_optimization/llm_mentions/top_pages/live": {"task": 0.1, "item": 0.001},
    "/v3/ai_optimization/llm_mentions/aggregated_metrics/live": {"task": 0.1, "item": 0.001},
    "/v3/ai_optimization/llm_mentions/cross_aggregated_metrics/live": {"task": 0.1, "item": 0.001},
    # Merchant API (standard queue)
    "/v3/merchant/google/products/task_post": {"task": 0.001, "block": 40},
    "/v3/merchant/google/sellers/task_post": {"task": 0.001, "block": 10},
    "/v3/merchant/amazon/products/task_post": {"task": 0.0015, "block": 100},
}

# Names used with dataforseo-mcp-server 2.8.10 and in older skill texts, so
# callers that pass them keep hitting the budget gate. serp_google_images_live_regular
# has no v3 endpoint (images is advanced or html only) and is no longer priced.
V2_ALIASES = {
    "serp_organic_live_advanced": "/v3/serp/google/organic/live/advanced",
    "serp_organic_live_regular": "/v3/serp/google/organic/live/regular",
    "serp_google_images_live_advanced": "/v3/serp/google/images/live/advanced",
    "serp_youtube_organic_live_advanced": "/v3/serp/youtube/organic/live/advanced",
    "serp_youtube_video_info_live_advanced": "/v3/serp/youtube/video_info/live/advanced",
    "serp_youtube_video_comments_live_advanced": "/v3/serp/youtube/video_comments/live/advanced",
    "serp_youtube_video_subtitles_live_advanced": "/v3/serp/youtube/video_subtitles/live/advanced",
    "kw_data_google_ads_search_volume": "/v3/keywords_data/google_ads/search_volume/live",
    "kw_data_google_trends_explore": "/v3/keywords_data/google_trends/explore/live",
    "dataforseo_labs_google_keyword_ideas": "/v3/dataforseo_labs/google/keyword_ideas/live",
    "dataforseo_labs_google_keyword_suggestions": "/v3/dataforseo_labs/google/keyword_suggestions/live",
    "dataforseo_labs_google_related_keywords": "/v3/dataforseo_labs/google/related_keywords/live",
    "dataforseo_labs_bulk_keyword_difficulty": "/v3/dataforseo_labs/google/bulk_keyword_difficulty/live",
    "dataforseo_labs_search_intent": "/v3/dataforseo_labs/google/search_intent/live",
    "dataforseo_labs_google_competitors_domain": "/v3/dataforseo_labs/google/competitors_domain/live",
    "dataforseo_labs_google_domain_rank_overview": "/v3/dataforseo_labs/google/domain_rank_overview/live",
    "dataforseo_labs_bulk_traffic_estimation": "/v3/dataforseo_labs/google/bulk_traffic_estimation/live",
    "dataforseo_labs_google_ranked_keywords": "/v3/dataforseo_labs/google/ranked_keywords/live",
    "dataforseo_labs_google_relevant_pages": "/v3/dataforseo_labs/google/relevant_pages/live",
    "dataforseo_labs_google_domain_intersection": "/v3/dataforseo_labs/google/domain_intersection/live",
    "dataforseo_labs_google_subdomains": "/v3/dataforseo_labs/google/subdomains/live",
    "dataforseo_labs_google_top_searches": "/v3/dataforseo_labs/google/top_searches/live",
    "on_page_instant_pages": "/v3/on_page/instant_pages",
    "on_page_content_parsing": "/v3/on_page/content_parsing/live",
    "on_page_lighthouse": "/v3/on_page/lighthouse/live/json",
    "backlinks_summary": "/v3/backlinks/summary/live",
    "backlinks_backlinks": "/v3/backlinks/backlinks/live",
    "backlinks_anchors": "/v3/backlinks/anchors/live",
    "backlinks_referring_domains": "/v3/backlinks/referring_domains/live",
    "backlinks_bulk_spam_score": "/v3/backlinks/bulk_spam_score/live",
    "backlinks_timeseries_summary": "/v3/backlinks/timeseries_summary/live",
    "backlinks_domain_intersection": "/v3/backlinks/domain_intersection/live",
    "domain_analytics_technologies_domain_technologies": "/v3/domain_analytics/technologies/domain_technologies/live",
    "domain_analytics_whois_overview": "/v3/domain_analytics/whois/overview/live",
    "content_analysis_search": "/v3/content_analysis/search/live",
    "content_analysis_summary": "/v3/content_analysis/summary/live",
    "content_analysis_phrase_trends": "/v3/content_analysis/phrase_trends/live",
    "business_data_business_listings_search": "/v3/business_data/business_listings/search/live",
    "ai_optimization_chat_gpt_scraper": "/v3/ai_optimization/chat_gpt/llm_scraper/live/advanced",
    "ai_opt_llm_ment_search": "/v3/ai_optimization/llm_mentions/search/live",
    "ai_opt_llm_ment_top_domains": "/v3/ai_optimization/llm_mentions/top_domains/live",
    "ai_opt_llm_ment_top_pages": "/v3/ai_optimization/llm_mentions/top_pages/live",
    "ai_opt_llm_ment_agg_metrics": "/v3/ai_optimization/llm_mentions/aggregated_metrics/live",
    "ai_opt_llm_ment_cross_agg_metrics": "/v3/ai_optimization/llm_mentions/cross_aggregated_metrics/live",
    "merchant_google_products_search": "/v3/merchant/google/products/task_post",
    "merchant_google_sellers_search": "/v3/merchant/google/sellers/task_post",
    "merchant_amazon_products_search": "/v3/merchant/amazon/products/task_post",
}

# Items assumed per call for per-item endpoints when the caller does not pass
# --items. 100 is the default `limit` of the Labs, Backlinks and Content
# Analysis endpoints; pass the real limit for larger requests.
DEFAULT_ITEMS = 100

# Endpoints that always require confirmation regardless of mode
WARN_ENDPOINTS = {
    "/v3/backlinks/backlinks/live",
    "/v3/backlinks/domain_intersection/live",
    "/v3/ai_optimization/chat_gpt/llm_scraper/live/advanced",
    "/v3/ai_optimization/llm_mentions/search/live",
    "/v3/merchant/amazon/products/task_post",
}


def canonical_endpoint(name):
    """Map a v2 tool name or any spelling of a v3 path to the COST_TABLE key.

    Accepts "serp_organic_live_advanced", "/v3/serp/...", "v3/serp/...",
    "serp/google/...", a trailing slash, and the ".ai" suffix that the 3.x MCP
    server appends in its default mode. Unknown names are returned unchanged.
    """
    name = (name or "").strip()
    if name in V2_ALIASES:
        return V2_ALIASES[name]
    path = name.rstrip("/")
    if path.endswith(".ai"):
        path = path[:-3]
    path = "/" + path.lstrip("/")
    if not path.startswith("/v3/"):
        path = "/v3" + path
    return path if path in COST_TABLE else name


def call_cost(endpoint, items=None):
    """Return (cost of one call, items assumed) for a COST_TABLE key."""
    price = COST_TABLE[endpoint]
    block = price.get("block")
    if block:
        n = items if items else block
        return price["task"] * -(-n // block), n
    if price.get("item"):
        n = DEFAULT_ITEMS if items is None else items
        return price["task"] + price["item"] * n, n
    return price["task"], items

DEFAULT_CONFIG = {
    "mode": "threshold",
    "threshold": 0.50,
    "daily_limit": 10.00,
    "warn_endpoints": list(WARN_ENDPOINTS),
}


def _load_config():
    """Load or create configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        # Merge defaults for missing keys
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    return dict(DEFAULT_CONFIG)


def _save_config(cfg):
    """Save configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


class LedgerError(RuntimeError):
    """The ledger could not be read or written safely."""


def _lock(handle, exclusive):
    """Take an advisory lock on an open handle, blocking until acquired.

    Never degrades to running unlocked: a spend ledger that silently drops
    entries is worse than one that refuses to run.
    """
    if fcntl is not None:
        fcntl.flock(handle, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    elif msvcrt is not None:
        # msvcrt has no shared mode, so readers take an exclusive lock too.
        # LK_LOCK retries 10 times at 1s intervals, then raises OSError.
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        raise LedgerError(
            "No file-locking primitive available (neither fcntl nor msvcrt). "
            "Refusing to touch the spend ledger unlocked."
        )


def _unlock(handle):
    if fcntl is not None:
        fcntl.flock(handle, fcntl.LOCK_UN)
    elif msvcrt is not None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def _read_ledger():
    """Read the ledger. Caller must hold the lock."""
    if not LEDGER_FILE.exists():
        return {"entries": []}
    try:
        with open(LEDGER_FILE) as f:
            ledger = json.load(f)
    except json.JSONDecodeError as exc:
        raise LedgerError(
            f"Spend ledger {LEDGER_FILE} is not valid JSON ({exc}). Refusing to "
            "continue from a zero balance, which would under-report spend. "
            "Inspect the file, then repair or remove it."
        ) from exc
    if not isinstance(ledger, dict) or not isinstance(ledger.get("entries"), list):
        raise LedgerError(
            f"Spend ledger {LEDGER_FILE} has an unexpected shape (no 'entries' "
            "list). Inspect the file, then repair or remove it."
        )
    return ledger


def _write_ledger(ledger):
    """Write the ledger atomically. Caller must hold the exclusive lock.

    tempfile + os.replace so a crash mid-write can never leave a truncated,
    unparseable ledger behind (same idiom as scripts/google_auth.py).
    """
    fd, tmp_path = tempfile.mkstemp(
        dir=str(CONFIG_DIR), prefix=".dataforseo-ledger.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(ledger, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, LEDGER_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


@contextmanager
def _locked_ledger(write=False):
    """Yield the ledger under ONE lock held across the whole read-modify-write.

    Taking the lock to read, dropping it, then re-taking it to write loses
    entries: two concurrent writers both read the same ledger and the second
    overwrites the first. The lock has to span both halves.

    The lock lives in a separate .lock file on purpose. The atomic write
    replaces the ledger's inode, so a lock held on the ledger itself would not
    protect the replacement.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "a+") as lock_handle:
        _lock(lock_handle, exclusive=write)
        try:
            ledger = _read_ledger()
            yield ledger
            if write:
                _write_ledger(ledger)
        finally:
            _unlock(lock_handle)


def _ledger_snapshot():
    """Read the ledger under a shared lock. For read-only commands."""
    with _locked_ledger() as ledger:
        return ledger


def _today_str():
    return datetime.now().strftime("%Y-%m-%d")


def _today_spend(ledger):
    """Calculate today's total spend."""
    today = _today_str()
    return sum(
        e["cost"] for e in ledger["entries"]
        if e["timestamp"].startswith(today)
    )


def cmd_estimate(args):
    """Estimate cost for an API call."""
    endpoint = canonical_endpoint(args.endpoint)
    count = args.count or 1

    if endpoint not in COST_TABLE:
        # Try fuzzy match over paths and v2 names
        matches = [k for k in [*COST_TABLE, *V2_ALIASES] if endpoint and endpoint in k]
        if matches:
            result = {
                "status": "unknown_endpoint",
                "endpoint": endpoint,
                "suggestions": matches,
                "message": f"Unknown endpoint '{endpoint}'. Did you mean: {', '.join(matches)}?"
            }
        else:
            result = {
                "status": "unknown_endpoint",
                "endpoint": endpoint,
                "message": f"Unknown endpoint '{endpoint}'. Cost not in database."
            }
        json.dump(result, sys.stdout, indent=2)
        return

    unit_cost, items = call_cost(endpoint, args.items)
    total = unit_cost * count
    result = {
        "status": "estimated",
        "endpoint": endpoint,
        "price": COST_TABLE[endpoint],
        "items_per_call": items,
        "unit_cost_usd": round(unit_cost, 6),
        "count": count,
        "total_cost_usd": round(total, 4),
    }
    json.dump(result, sys.stdout, indent=2)


def _credentials_in_env():
    return bool(os.environ.get("DATAFORSEO_USERNAME") and os.environ.get("DATAFORSEO_PASSWORD"))


def cmd_check(args):
    """Check if an API call should proceed (cost + approval logic)."""
    cfg = _load_config()
    ledger = _ledger_snapshot()
    endpoint = canonical_endpoint(args.endpoint)
    count = args.count or 1
    if endpoint not in COST_TABLE:
        result = {
            "status": "needs_approval",
            "endpoint": endpoint,
            "approval_reason": "unknown_endpoint",
            "message": f"Unknown endpoint '{endpoint}': cost not in database. Requires explicit approval.",
            "estimated_cost_usd": 0.05,
            "credentials_in_env": _credentials_in_env(),
        }
        json.dump(result, sys.stdout, indent=2)
        return
    unit_cost, items = call_cost(endpoint, args.items)
    total = unit_cost * count
    today_total = _today_spend(ledger)
    daily_limit = cfg.get("daily_limit", 10.00)
    mode = cfg.get("mode", "threshold")
    threshold = cfg.get("threshold", 0.50)

    # Check daily limit
    if today_total + total > daily_limit:
        result = {
            "status": "blocked",
            "reason": "daily_limit_exceeded",
            "today_spend_usd": round(today_total, 4),
            "this_call_usd": round(total, 4),
            "daily_limit_usd": daily_limit,
            "credentials_in_env": _credentials_in_env(),
            "message": f"Daily limit ${daily_limit:.2f} would be exceeded. Today's spend: ${today_total:.2f}, this call: ${total:.2f}."
        }
        json.dump(result, sys.stdout, indent=2)
        return

    # Check approval mode
    needs_approval = False
    approval_reason = None

    # Saved configs may still list v2 names; compare canonical forms.
    warn = {canonical_endpoint(e) for e in cfg.get("warn_endpoints", WARN_ENDPOINTS)}
    if endpoint in warn:
        needs_approval = True
        approval_reason = "warn_endpoint"
    elif mode == "always":
        needs_approval = True
        approval_reason = "mode_always"
    elif mode == "threshold" and total >= threshold:
        needs_approval = True
        approval_reason = "above_threshold"
    # mode == "none" -> never needs approval

    result = {
        "status": "needs_approval" if needs_approval else "approved",
        "endpoint": endpoint,
        "items_per_call": items,
        "unit_cost_usd": round(unit_cost, 6),
        "count": count,
        "total_cost_usd": round(total, 4),
        "today_spend_usd": round(today_total, 4),
        "daily_remaining_usd": round(daily_limit - today_total, 4),
        # Budget approval says nothing about whether the call can run. Scripts
        # read these env vars; the MCP server keeps its own copy in its config,
        # which this script cannot see, so False means "not found here", not
        # "the call will fail".
        "credentials_in_env": _credentials_in_env(),
    }
    if needs_approval:
        result["approval_reason"] = approval_reason
        result["message"] = (
            f"This call costs ~${total:.2f}. "
            f"Today's spend: ${today_total:.2f}/${daily_limit:.2f}. "
            f"Reason: {approval_reason}. Proceed?"
        )
    json.dump(result, sys.stdout, indent=2)


def cmd_log(args):
    """Log a completed API call cost."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        # v2 names and path spellings are stored as the v3 path, so `today`
        # groups the same endpoint under one key.
        "endpoint": canonical_endpoint(args.endpoint),
        "cost": args.cost,
    }
    if args.note:
        entry["note"] = args.note
    # Read and write inside one lock, so a concurrent log cannot overwrite this
    # entry with a ledger it read before this one was appended.
    with _locked_ledger(write=True) as ledger:
        ledger["entries"].append(entry)

    result = {
        "status": "logged",
        "entry": entry,
        "today_total_usd": round(_today_spend(ledger), 4),
    }
    json.dump(result, sys.stdout, indent=2)


def cmd_summary(args):
    """Show spending summary for recent days."""
    ledger = _ledger_snapshot()
    days = args.days or 7
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    recent = [e for e in ledger["entries"] if e["timestamp"] >= cutoff]

    # Group by day
    by_day = {}
    for e in recent:
        day = e["timestamp"][:10]
        by_day.setdefault(day, []).append(e)

    daily_totals = {}
    for day, entries in sorted(by_day.items()):
        daily_totals[day] = {
            "total_usd": round(sum(e["cost"] for e in entries), 4),
            "calls": len(entries),
        }

    result = {
        "status": "summary",
        "period_days": days,
        "daily_totals": daily_totals,
        "grand_total_usd": round(sum(e["cost"] for e in recent), 4),
        "total_calls": len(recent),
    }
    json.dump(result, sys.stdout, indent=2)


def cmd_today(args):
    """Show today's spending."""
    ledger = _ledger_snapshot()
    cfg = _load_config()
    today = _today_str()
    today_entries = [e for e in ledger["entries"] if e["timestamp"].startswith(today)]

    # Group by endpoint
    by_endpoint = {}
    for e in today_entries:
        ep = e["endpoint"]
        by_endpoint.setdefault(ep, {"cost": 0, "calls": 0})
        by_endpoint[ep]["cost"] += e["cost"]
        by_endpoint[ep]["calls"] += 1

    total = sum(e["cost"] for e in today_entries)
    daily_limit = cfg.get("daily_limit", 10.00)

    result = {
        "status": "today",
        "date": today,
        "total_usd": round(total, 4),
        "daily_limit_usd": daily_limit,
        "remaining_usd": round(daily_limit - total, 4),
        "calls": len(today_entries),
        "by_endpoint": {k: {"cost_usd": round(v["cost"], 4), "calls": v["calls"]} for k, v in by_endpoint.items()},
    }
    json.dump(result, sys.stdout, indent=2)


def cmd_config(args):
    """View or update configuration."""
    cfg = _load_config()

    changed = False
    if args.mode:
        if args.mode not in ("always", "threshold", "none"):
            print(json.dumps({"status": "error", "message": "Mode must be: always, threshold, or none"}))
            sys.exit(1)
        cfg["mode"] = args.mode
        changed = True
    if args.threshold is not None:
        cfg["threshold"] = args.threshold
        changed = True
    if args.daily_limit is not None:
        cfg["daily_limit"] = args.daily_limit
        changed = True

    if changed:
        _save_config(cfg)

    result = {
        "status": "updated" if changed else "current",
        "config": cfg,
    }
    json.dump(result, sys.stdout, indent=2)


def cmd_reset(args):
    """Reset today's ledger entries (requires --confirm)."""
    if not args.confirm:
        result = {
            "status": "blocked",
            "message": "Reset requires --confirm flag. This clears today's cost entries.",
        }
        json.dump(result, sys.stdout, indent=2)
        return

    today = _today_str()
    # One lock across the whole read-modify-write, so a concurrent log is either
    # cleared by this reset or survives it, never silently discarded.
    with _locked_ledger(write=True) as ledger:
        today_entries = [e for e in ledger["entries"] if e["timestamp"].startswith(today)]
        removed_total = sum(e["cost"] for e in today_entries)
        removed_count = len(today_entries)

        ledger["entries"] = [e for e in ledger["entries"] if not e["timestamp"].startswith(today)]

        # Immutable audit entry for the reset itself
        ledger["entries"].append({
            "timestamp": datetime.now().isoformat(),
            "endpoint": "_audit_reset",
            "cost": 0,
            "note": f"Reset cleared {removed_count} entries totaling ${removed_total:.4f}",
        })

    result = {
        "status": "reset",
        "date": today,
        "entries_removed": removed_count,
        "amount_cleared_usd": round(removed_total, 4),
    }
    json.dump(result, sys.stdout, indent=2)


def _non_negative_int(value):
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("must be 0 or greater")
    return n


def main():
    parser = argparse.ArgumentParser(
        description="DataForSEO API cost estimation and budget tracking"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # estimate
    p_est = sub.add_parser("estimate", help="Estimate cost for an API call")
    endpoint_help = "v3 path (/v3/serp/google/organic/live/advanced) or 2.8.10 tool name"
    items_help = (
        "Items/results per call: the request's limit or depth. "
        f"Default: one block for SERP-style endpoints, {DEFAULT_ITEMS} for per-item endpoints"
    )
    p_est.add_argument("endpoint", help=endpoint_help)
    p_est.add_argument("--count", type=int, default=1, help="Number of calls")
    p_est.add_argument("--items", type=_non_negative_int, help=items_help)

    # check
    p_chk = sub.add_parser("check", help="Check if call should proceed")
    p_chk.add_argument("endpoint", help=endpoint_help)
    p_chk.add_argument("--count", type=int, default=1, help="Number of calls")
    p_chk.add_argument("--items", type=_non_negative_int, help=items_help)

    # log
    p_log = sub.add_parser("log", help="Log a completed API call cost")
    p_log.add_argument("endpoint", help=endpoint_help)
    p_log.add_argument("cost", type=float, help="Actual cost in USD")
    p_log.add_argument("--note", help="Optional note")

    # summary
    p_sum = sub.add_parser("summary", help="Show spending summary")
    p_sum.add_argument("--days", type=int, default=7, help="Number of days")

    # today
    sub.add_parser("today", help="Show today's spending")

    # config
    p_cfg = sub.add_parser("config", help="View or update configuration")
    p_cfg.add_argument("--mode", choices=["always", "threshold", "none"])
    p_cfg.add_argument("--threshold", type=float)
    p_cfg.add_argument("--daily-limit", type=float, dest="daily_limit")

    # reset
    p_reset = sub.add_parser("reset", help="Reset today's ledger entries")
    p_reset.add_argument("--confirm", action="store_true", help="Confirm reset (required)")

    args = parser.parse_args()
    dispatch = {
        "estimate": cmd_estimate,
        "check": cmd_check,
        "log": cmd_log,
        "summary": cmd_summary,
        "today": cmd_today,
        "config": cmd_config,
        "reset": cmd_reset,
    }
    try:
        dispatch[args.command](args)
    except LedgerError as exc:
        # Fail closed and loudly. Callers parse stdout as JSON, so keep the
        # contract even on the error path.
        json.dump({"status": "error", "message": str(exc)}, sys.stdout, indent=2)
        sys.exit(1)


if __name__ == "__main__":
    main()
