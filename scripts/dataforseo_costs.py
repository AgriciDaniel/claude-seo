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

Usage:
    python dataforseo_costs.py estimate <endpoint> [--count N]
    python dataforseo_costs.py check <endpoint> [--count N]
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
from datetime import datetime, timedelta
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None  # Windows fallback: no locking

# ----- paths -----
CONFIG_DIR = Path.home() / ".config" / "claude-seo"
CONFIG_FILE = CONFIG_DIR / "dataforseo-costs.json"
LEDGER_FILE = CONFIG_DIR / "dataforseo-ledger.json"

# ----- cost table (USD per call, standard queue) -----
# Source: https://dataforseo.com/pricing
# Prices are approximate; actual costs may vary by parameters.
COST_TABLE = {
    # SERP
    "serp_organic_live_advanced": 0.002,
    "serp_organic_live_regular": 0.001,
    "serp_google_images_live_advanced": 0.002,
    "serp_google_images_live_regular": 0.001,
    "serp_youtube_organic_live_advanced": 0.002,
    "serp_youtube_video_info_live_advanced": 0.002,
    "serp_youtube_video_comments_live_advanced": 0.002,
    "serp_youtube_video_subtitles_live_advanced": 0.002,
    # Keywords Data
    "kw_data_google_ads_search_volume": 0.05,
    "kw_data_google_trends_explore": 0.01,
    # DataForSEO Labs
    "dataforseo_labs_google_keyword_ideas": 0.05,
    "dataforseo_labs_google_keyword_suggestions": 0.05,
    "dataforseo_labs_google_related_keywords": 0.05,
    "dataforseo_labs_bulk_keyword_difficulty": 0.01,
    "dataforseo_labs_search_intent": 0.01,
    "dataforseo_labs_google_competitors_domain": 0.05,
    "dataforseo_labs_google_domain_rank_overview": 0.01,
    "dataforseo_labs_bulk_traffic_estimation": 0.01,
    "dataforseo_labs_google_ranked_keywords": 0.05,
    "dataforseo_labs_google_relevant_pages": 0.05,
    "dataforseo_labs_google_domain_intersection": 0.05,
    "dataforseo_labs_google_subdomains": 0.05,
    "dataforseo_labs_google_top_searches": 0.05,
    # On-Page
    "on_page_instant_pages": 0.01,
    "on_page_content_parsing": 0.01,
    "on_page_lighthouse": 0.02,
    # Backlinks
    "backlinks_summary": 0.02,
    "backlinks_backlinks": 0.02,
    "backlinks_anchors": 0.02,
    "backlinks_referring_domains": 0.02,
    "backlinks_bulk_spam_score": 0.01,
    "backlinks_timeseries_summary": 0.02,
    "backlinks_domain_intersection": 0.05,
    # Domain Analytics
    "domain_analytics_technologies_domain_technologies": 0.01,
    "domain_analytics_whois_overview": 0.005,
    # Content Analysis
    "content_analysis_search": 0.02,
    "content_analysis_summary": 0.02,
    "content_analysis_phrase_trends": 0.02,
    # Business Data
    "business_data_business_listings_search": 0.05,
    # AI / GEO
    "ai_optimization_chat_gpt_scraper": 0.05,
    "ai_opt_llm_ment_search": 0.05,
    "ai_opt_llm_ment_top_domains": 0.05,
    "ai_opt_llm_ment_top_pages": 0.05,
    "ai_opt_llm_ment_agg_metrics": 0.05,
    "ai_opt_llm_ment_cross_agg_metrics": 0.05,
    # Merchant (e-commerce)
    "merchant_google_products_search": 0.02,
    "merchant_amazon_products_search": 0.02,
    "merchant_google_sellers_search": 0.02,
}

# Endpoints that always require confirmation regardless of mode
WARN_ENDPOINTS = {
    "backlinks_backlinks",
    "backlinks_domain_intersection",
    "ai_optimization_chat_gpt_scraper",
    "ai_opt_llm_ment_search",
    "merchant_amazon_products_search",
}

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


def _load_ledger():
    """Load spending ledger with file locking."""
    if not LEDGER_FILE.exists():
        return {"entries": []}
    if fcntl:
        lock_path = LEDGER_FILE.with_suffix(".lock")
        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_SH)
            try:
                with open(LEDGER_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {"entries": []}
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
    else:
        with open(LEDGER_FILE) as f:
            return json.load(f)


def _save_ledger(ledger):
    """Save spending ledger with file locking."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if fcntl:
        lock_path = LEDGER_FILE.with_suffix(".lock")
        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                with open(LEDGER_FILE, "w") as f:
                    json.dump(ledger, f, indent=2)
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
    else:
        with open(LEDGER_FILE, "w") as f:
            json.dump(ledger, f, indent=2)


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
    endpoint = args.endpoint
    count = args.count or 1
    unit_cost = COST_TABLE.get(endpoint)

    if unit_cost is None:
        # Try fuzzy match
        matches = [k for k in COST_TABLE if endpoint in k]
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

    total = unit_cost * count
    result = {
        "status": "estimated",
        "endpoint": endpoint,
        "unit_cost_usd": unit_cost,
        "count": count,
        "total_cost_usd": round(total, 4),
    }
    json.dump(result, sys.stdout, indent=2)


def cmd_check(args):
    """Check if an API call should proceed (cost + approval logic)."""
    cfg = _load_config()
    ledger = _load_ledger()
    endpoint = args.endpoint
    count = args.count or 1
    unit_cost = COST_TABLE.get(endpoint)
    if unit_cost is None:
        result = {
            "status": "needs_approval",
            "endpoint": endpoint,
            "approval_reason": "unknown_endpoint",
            "message": f"Unknown endpoint '{endpoint}' — cost not in database. Requires explicit approval.",
            "estimated_cost_usd": 0.05,
        }
        json.dump(result, sys.stdout, indent=2)
        return
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
            "message": f"Daily limit ${daily_limit:.2f} would be exceeded. Today's spend: ${today_total:.2f}, this call: ${total:.2f}."
        }
        json.dump(result, sys.stdout, indent=2)
        return

    # Check approval mode
    needs_approval = False
    approval_reason = None

    if endpoint in cfg.get("warn_endpoints", WARN_ENDPOINTS):
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
        "unit_cost_usd": unit_cost,
        "count": count,
        "total_cost_usd": round(total, 4),
        "today_spend_usd": round(today_total, 4),
        "daily_remaining_usd": round(daily_limit - today_total, 4),
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
    ledger = _load_ledger()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": args.endpoint,
        "cost": args.cost,
    }
    if args.note:
        entry["note"] = args.note
    ledger["entries"].append(entry)
    _save_ledger(ledger)

    result = {
        "status": "logged",
        "entry": entry,
        "today_total_usd": round(_today_spend(ledger), 4),
    }
    json.dump(result, sys.stdout, indent=2)


def cmd_summary(args):
    """Show spending summary for recent days."""
    ledger = _load_ledger()
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
    ledger = _load_ledger()
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

    ledger = _load_ledger()
    today = _today_str()
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

    _save_ledger(ledger)

    result = {
        "status": "reset",
        "date": today,
        "entries_removed": removed_count,
        "amount_cleared_usd": round(removed_total, 4),
    }
    json.dump(result, sys.stdout, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="DataForSEO API cost estimation and budget tracking"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # estimate
    p_est = sub.add_parser("estimate", help="Estimate cost for an API call")
    p_est.add_argument("endpoint", help="DataForSEO MCP tool name")
    p_est.add_argument("--count", type=int, default=1, help="Number of calls")

    # check
    p_chk = sub.add_parser("check", help="Check if call should proceed")
    p_chk.add_argument("endpoint", help="DataForSEO MCP tool name")
    p_chk.add_argument("--count", type=int, default=1, help="Number of calls")

    # log
    p_log = sub.add_parser("log", help="Log a completed API call cost")
    p_log.add_argument("endpoint", help="DataForSEO MCP tool name")
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
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
