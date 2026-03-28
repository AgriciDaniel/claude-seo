#!/usr/bin/env python3
"""DataForSEO Cost Estimator and Tracker for Claude SEO.

Estimates API costs before calls, enforces approval workflows, tracks spending,
and manages cost configuration. Mirrors the pattern from Banana's cost_tracker.py.

Usage:
    dataforseo_costs.py init                          # Create default config
    dataforseo_costs.py config                        # Show current config
    dataforseo_costs.py config --set key=value        # Update config
    dataforseo_costs.py estimate --command CMD [opts] # Estimate cost for a command
    dataforseo_costs.py check --command CMD [opts]    # Estimate + check approval
    dataforseo_costs.py log --command CMD --cost AMT  # Log actual spend
    dataforseo_costs.py summary                       # Show spending summary
    dataforseo_costs.py today                         # Today's spending
    dataforseo_costs.py reset --confirm               # Reset spending ledger
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CONFIG_PATH = Path.home() / ".claude-seo" / "dataforseo-cost-config.json"
LEDGER_PATH = Path.home() / ".claude-seo" / "dataforseo-costs.json"

DEFAULT_CONFIG = {
    "version": 1,
    "approval_mode": "threshold",
    "threshold_usd": 0.50,
    "prefer_standard_queue": True,
    "default_limits": {
        "serp_depth": 10,
        "keyword_limit": 20,
        "backlink_limit": 50,
        "review_depth": 20,
        "content_limit": 10,
        "grid_size": 5,
    },
    "session_budget_usd": None,
    "warn_modules": ["BACKLINKS", "AI_OPTIMIZATION"],
}

# Per-task base costs in USD (live mode unless noted)
PRICING = {
    # SERP
    "serp_organic_live": 0.002,
    "serp_organic_standard": 0.0006,
    "serp_organic_priority": 0.0012,
    "serp_youtube_live": 0.002,
    "serp_youtube_video_info": 0.006,
    "serp_youtube_video_comments": 0.006,
    "serp_youtube_video_subtitles": 0.006,
    "serp_maps_live": 0.002,
    "serp_maps_standard": 0.0006,
    "serp_screenshot": 0.004,
    "serp_autocomplete": 0.002,
    # Keywords Data
    "kw_search_volume_live": 0.001,  # + $0.0001/keyword
    "kw_search_volume_standard": 0.05,  # batch up to 1k
    "kw_similar": 0.01,  # + $0.0001/keyword
    "kw_suggestions_basic": 0.075,
    "kw_trends_explore": 0.002,
    # DataForSEO Labs
    "labs_keyword_ideas": 0.075,
    "labs_keyword_suggestions": 0.01,  # + $0.0001/keyword
    "labs_related_keywords": 0.01,  # + $0.0001/keyword
    "labs_bulk_keyword_difficulty": 0.001,  # + $0.0001/keyword
    "labs_search_intent": 0.001,  # + $0.0001/keyword
    "labs_ranked_keywords": 0.01,  # + $0.0001/target
    "labs_competitors_domain": 0.01,  # + $0.0001/target
    "labs_domain_rank_overview": 0.01,  # + $0.0001/target
    "labs_domain_intersection": 0.01,  # + $0.0001/target
    "labs_bulk_traffic_estimation": 0.002,  # per domain
    "labs_subdomains": 0.01,  # + $0.0001/target
    "labs_top_searches": 0.01,  # + $0.0001/target
    "labs_relevant_pages": 0.01,  # + $0.0001/target
    "labs_keyword_overview": 0.01,
    "labs_historical_serp": 0.01,
    "labs_serp_competitors": 0.01,
    # Backlinks (requires $100/mo commitment)
    "backlinks_summary": 0.02,  # + $0.00003/row
    "backlinks_list": 0.02,  # + $0.00003/row
    "backlinks_anchors": 0.02,  # + $0.00003/row
    "backlinks_referring_domains": 0.02,  # + $0.00003/row
    "backlinks_bulk_spam_score": 0.02,  # + $0.00003/target
    "backlinks_timeseries": 0.02,  # + $0.00003/row
    "backlinks_domain_intersection": 0.02,  # + $0.00003/row
    # On-Page
    "onpage_instant_basic": 0.000125,
    "onpage_instant_js": 0.00125,
    "onpage_instant_browser": 0.00425,
    "onpage_content_parsing": 0.000125,
    "onpage_lighthouse": 0.00425,
    "onpage_screenshot": 0.004,
    # Domain Analytics
    "domain_technologies": 0.101,  # $0.10 + $0.001
    "domain_whois": 0.101,  # $0.10 + $0.001
    # Business Data
    "business_info_standard": 0.0015,
    "business_info_live": 0.0054,
    "business_reviews_placeid": 0.00075,  # per 20 reviews
    "business_reviews_keyword": 0.003,  # per 10 reviews
    "business_listings": 0.01,  # + $0.0003/item
    "business_tripadvisor": 0.00075,
    "business_trustpilot": 0.00075,
    # Content Analysis
    "content_search": 0.02,  # + $0.00003/row
    "content_summary": 0.02,  # + $0.00003/row
    "content_phrase_trends": 0.02,  # + $0.00003/row
    # AI Optimization
    "ai_llm_mentions_search": 0.10,  # + $0.001/row
    "ai_llm_mentions_top_domains": 0.10,  # + $0.001/row
    "ai_llm_mentions_top_pages": 0.10,  # + $0.001/row
    "ai_llm_mentions_aggregate": 0.10,  # + $0.001/row
    "ai_chatgpt_scraper_live": 0.004,
    "ai_chatgpt_scraper_standard": 0.0012,
    "ai_keyword_data": 0.01,  # + $0.0001/keyword
}

# Per-row costs for endpoints that charge by row
ROW_COSTS = {
    "backlinks": 0.00003,
    "content_analysis": 0.00003,
    "ai_llm_mentions": 0.001,
    "labs_per_keyword": 0.0001,
    "labs_per_target": 0.0001,
    "kw_per_keyword": 0.0001,
    "business_listings_per_item": 0.0003,
}

# Maps command names to (list of pricing keys, row_cost_key, default_rows)
COMMAND_ESTIMATES = {
    "serp": {
        "calls": [("serp_organic_live", 1)],
        "standard_calls": [("serp_organic_standard", 1)],
        "module": "SERP",
    },
    "serp-youtube": {
        "calls": [("serp_youtube_live", 1)],
        "standard_calls": [("serp_organic_standard", 1)],
        "module": "SERP",
    },
    "youtube": {
        "calls": [
            ("serp_youtube_video_info", 1),
            ("serp_youtube_video_comments", 1),
            ("serp_youtube_video_subtitles", 1),
        ],
        "module": "SERP",
    },
    "keywords": {
        "calls": [
            ("labs_keyword_ideas", 1),
            ("labs_keyword_suggestions", 1),
            ("labs_related_keywords", 1),
        ],
        "module": "DATAFORSEO_LABS",
    },
    "volume": {
        "calls": [("kw_search_volume_live", 1)],
        "standard_calls": [("kw_search_volume_standard", 1)],
        "row_cost_key": "kw_per_keyword",
        "rows_param": "keywords",
        "module": "KEYWORDS_DATA",
    },
    "difficulty": {
        "calls": [("labs_bulk_keyword_difficulty", 1)],
        "row_cost_key": "labs_per_keyword",
        "rows_param": "keywords",
        "module": "DATAFORSEO_LABS",
    },
    "intent": {
        "calls": [("labs_search_intent", 1)],
        "row_cost_key": "labs_per_keyword",
        "rows_param": "keywords",
        "module": "DATAFORSEO_LABS",
    },
    "trends": {
        "calls": [("kw_trends_explore", 1)],
        "module": "KEYWORDS_DATA",
    },
    "backlinks": {
        "calls": [
            ("backlinks_summary", 1),
            ("backlinks_list", 1),
            ("backlinks_anchors", 1),
            ("backlinks_referring_domains", 1),
            ("backlinks_bulk_spam_score", 1),
            ("backlinks_timeseries", 1),
        ],
        "row_cost_key": "backlinks",
        "rows_param": "limit",
        "module": "BACKLINKS",
    },
    "competitors": {
        "calls": [
            ("labs_competitors_domain", 1),
            ("labs_domain_rank_overview", 1),
            ("labs_bulk_traffic_estimation", 1),
        ],
        "module": "DATAFORSEO_LABS",
    },
    "ranked": {
        "calls": [
            ("labs_ranked_keywords", 1),
            ("labs_relevant_pages", 1),
        ],
        "row_cost_key": "labs_per_target",
        "rows_param": "limit",
        "module": "DATAFORSEO_LABS",
    },
    "intersection": {
        "calls": [
            ("labs_domain_intersection", 1),
            ("backlinks_domain_intersection", 1),
        ],
        "row_cost_key": "backlinks",
        "rows_param": "limit",
        "module": "DATAFORSEO_LABS",
    },
    "traffic": {
        "calls": [("labs_bulk_traffic_estimation", 1)],
        "rows_param": "domains",
        "module": "DATAFORSEO_LABS",
    },
    "subdomains": {
        "calls": [("labs_subdomains", 1)],
        "row_cost_key": "labs_per_target",
        "rows_param": "limit",
        "module": "DATAFORSEO_LABS",
    },
    "top-searches": {
        "calls": [("labs_top_searches", 1)],
        "row_cost_key": "labs_per_target",
        "rows_param": "limit",
        "module": "DATAFORSEO_LABS",
    },
    "onpage": {
        "calls": [
            ("onpage_instant_basic", 1),
            ("onpage_content_parsing", 1),
            ("onpage_lighthouse", 1),
        ],
        "module": "ONPAGE",
    },
    "tech": {
        "calls": [("domain_technologies", 1)],
        "module": "DOMAIN_ANALYTICS",
    },
    "whois": {
        "calls": [("domain_whois", 1)],
        "module": "DOMAIN_ANALYTICS",
    },
    "content": {
        "calls": [
            ("content_search", 1),
            ("content_summary", 1),
            ("content_phrase_trends", 1),
        ],
        "row_cost_key": "content_analysis",
        "rows_param": "limit",
        "module": "CONTENT_ANALYSIS",
    },
    "listings": {
        "calls": [("business_listings", 1)],
        "row_cost_key": "business_listings_per_item",
        "rows_param": "limit",
        "module": "BUSINESS_DATA",
    },
    "ai-scrape": {
        "calls": [("ai_chatgpt_scraper_live", 1)],
        "standard_calls": [("ai_chatgpt_scraper_standard", 1)],
        "module": "AI_OPTIMIZATION",
    },
    "ai-mentions": {
        "calls": [
            ("ai_llm_mentions_search", 1),
            ("ai_llm_mentions_top_domains", 1),
            ("ai_llm_mentions_top_pages", 1),
            ("ai_llm_mentions_aggregate", 1),
        ],
        "row_cost_key": "ai_llm_mentions",
        "rows_param": "limit",
        "module": "AI_OPTIMIZATION",
    },
    "geo-grid": {
        "calls": [("serp_maps_live", 1)],
        "standard_calls": [("serp_maps_standard", 1)],
        "rows_param": "grid_points",
        "module": "SERP",
    },
}


def _load_config():
    """Load cost config from disk, or return defaults."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        merged = {**DEFAULT_CONFIG, **cfg}
        merged["default_limits"] = {
            **DEFAULT_CONFIG["default_limits"],
            **cfg.get("default_limits", {}),
        }
        return merged
    return dict(DEFAULT_CONFIG)


def _save_config(cfg):
    """Save cost config to disk."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def _load_ledger():
    """Load the spending ledger."""
    if not LEDGER_PATH.exists():
        return {"total_cost": 0.0, "total_calls": 0, "entries": [], "daily": {}}
    with open(LEDGER_PATH) as f:
        return json.load(f)


def _save_ledger(ledger):
    """Save the spending ledger."""
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2)


def _estimate_command_cost(command, keywords=0, domains=0, limit=0,
                           grid_points=0, use_standard=False):
    """Calculate estimated cost for a command.

    Returns (estimated_cost, breakdown_lines, module).
    """
    spec = COMMAND_ESTIMATES.get(command)
    if not spec:
        return 0.0, [f"Unknown command: {command}"], "UNKNOWN"

    use_std = use_standard and "standard_calls" in spec
    calls = spec.get("standard_calls" if use_std else "calls", spec["calls"])

    total = 0.0
    breakdown = []
    queue_label = "standard" if use_std else "live"

    for pricing_key, count in calls:
        base = PRICING.get(pricing_key, 0.0)
        subtotal = base * count
        breakdown.append(f"  {pricing_key} x{count}: ${subtotal:.4f} ({queue_label})")
        total += subtotal

    row_key = spec.get("row_cost_key")
    rows_param = spec.get("rows_param", "")
    actual_rows = 0
    if rows_param == "keywords":
        actual_rows = keywords
    elif rows_param == "domains":
        actual_rows = domains
    elif rows_param == "limit":
        actual_rows = limit
    elif rows_param == "grid_points":
        actual_rows = grid_points

    if command == "geo-grid" and actual_rows > 0:
        base_per_point = PRICING.get(
            "serp_maps_standard" if use_std else "serp_maps_live", 0.002
        )
        grid_cost = base_per_point * actual_rows
        total = grid_cost
        breakdown = [
            f"  maps_serp x{actual_rows} points: "
            f"${grid_cost:.4f} ({queue_label})"
        ]
    elif row_key and actual_rows > 0:
        per_row = ROW_COSTS.get(row_key, 0.0)
        if command == "backlinks":
            row_cost_all = per_row * actual_rows * len(calls)
            breakdown.append(
                f"  + {actual_rows} rows x {len(calls)} endpoints: "
                f"${row_cost_all:.4f}"
            )
            total += row_cost_all
        else:
            row_cost = per_row * actual_rows
            breakdown.append(f"  + {actual_rows} rows @ ${per_row}/row: ${row_cost:.4f}")
            total += row_cost

    return round(total, 4), breakdown, spec.get("module", "UNKNOWN")


def cmd_init(args):
    """Create default config file."""
    if CONFIG_PATH.exists() and not getattr(args, "force", False):
        print(json.dumps({"status": "exists", "path": str(CONFIG_PATH)}))
        return
    _save_config(DEFAULT_CONFIG)
    print(json.dumps({
        "status": "created",
        "path": str(CONFIG_PATH),
        "config": DEFAULT_CONFIG,
    }, default=str))


def cmd_config(args):
    """Show or update config."""
    cfg = _load_config()

    if args.set:
        for pair in args.set:
            if "=" not in pair:
                print(f"Error: Invalid format '{pair}'. Use key=value.", file=sys.stderr)
                sys.exit(1)
            key, val = pair.split("=", 1)

            if key == "approval_mode":
                if val not in ("always", "threshold", "none"):
                    print("Error: approval_mode must be always|threshold|none",
                          file=sys.stderr)
                    sys.exit(1)
                cfg["approval_mode"] = val
            elif key == "threshold_usd":
                cfg["threshold_usd"] = float(val)
            elif key == "prefer_standard_queue":
                cfg["prefer_standard_queue"] = val.lower() in ("true", "1", "yes")
            elif key == "session_budget_usd":
                cfg["session_budget_usd"] = None if val.lower() == "none" else float(val)
            elif key.startswith("default_limits."):
                subkey = key.split(".", 1)[1]
                cfg["default_limits"][subkey] = int(val)
            elif key == "warn_modules":
                cfg["warn_modules"] = [m.strip() for m in val.split(",")]
            else:
                print(f"Error: Unknown config key '{key}'", file=sys.stderr)
                sys.exit(1)

        _save_config(cfg)
        print(json.dumps({"status": "updated", "config": cfg}, default=str))
    else:
        print(json.dumps({"config": cfg, "path": str(CONFIG_PATH)}, default=str))


def cmd_estimate(args):
    """Estimate cost for a DataForSEO command."""
    cfg = _load_config()
    limits = cfg["default_limits"]

    keywords = getattr(args, "keywords", 0) or limits.get("keyword_limit", 20)
    domains = getattr(args, "domains", 0) or 1
    limit = getattr(args, "limit", 0) or limits.get("backlink_limit", 50)
    grid_size = getattr(args, "grid_size", 0) or limits.get("grid_size", 5)
    grid_points = grid_size * grid_size
    use_standard = cfg.get("prefer_standard_queue", True)

    cost, breakdown, module = _estimate_command_cost(
        args.command,
        keywords=keywords,
        domains=domains,
        limit=limit,
        grid_points=grid_points,
        use_standard=use_standard,
    )

    result = {
        "command": args.command,
        "estimated_cost_usd": cost,
        "module": module,
        "queue": "standard" if use_standard else "live",
        "breakdown": breakdown,
        "parameters": {
            "keywords": keywords,
            "domains": domains,
            "limit": limit,
            "grid_size": grid_size,
        },
    }
    print(json.dumps(result, indent=2))


def cmd_check(args):
    """Estimate cost and determine if approval is needed."""
    cfg = _load_config()
    limits = cfg["default_limits"]

    keywords = getattr(args, "keywords", 0) or limits.get("keyword_limit", 20)
    domains = getattr(args, "domains", 0) or 1
    limit = getattr(args, "limit", 0) or limits.get("backlink_limit", 50)
    grid_size = getattr(args, "grid_size", 0) or limits.get("grid_size", 5)
    grid_points = grid_size * grid_size
    use_standard = cfg.get("prefer_standard_queue", True)

    cost, breakdown, module = _estimate_command_cost(
        args.command,
        keywords=keywords,
        domains=domains,
        limit=limit,
        grid_points=grid_points,
        use_standard=use_standard,
    )

    mode = cfg.get("approval_mode", "threshold")
    threshold = cfg.get("threshold_usd", 0.50)
    warn_modules = cfg.get("warn_modules", [])

    needs_approval = False
    approval_reason = None

    if mode == "always":
        needs_approval = True
        approval_reason = "approval_mode is 'always'"
    elif mode == "threshold" and cost >= threshold:
        needs_approval = True
        approval_reason = f"estimated cost ${cost:.4f} >= threshold ${threshold:.2f}"
    elif module in warn_modules:
        needs_approval = True
        approval_reason = f"module {module} is in warn_modules list"

    # Check session budget
    session_budget = cfg.get("session_budget_usd")
    if session_budget is not None:
        ledger = _load_ledger()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily = ledger.get("daily", {}).get(today, {"cost": 0.0})
        remaining = session_budget - daily["cost"]
        if cost > remaining:
            needs_approval = True
            approval_reason = (
                f"would exceed session budget "
                f"(${daily['cost']:.2f} spent + ${cost:.4f} = "
                f"${daily['cost'] + cost:.4f} > ${session_budget:.2f} budget)"
            )

    result = {
        "command": args.command,
        "estimated_cost_usd": cost,
        "module": module,
        "approval_mode": mode,
        "needs_approval": needs_approval,
        "approval_reason": approval_reason,
        "threshold_usd": threshold,
        "breakdown": breakdown,
    }
    print(json.dumps(result, indent=2))


def cmd_log(args):
    """Log actual API spend."""
    ledger = _load_ledger()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    cost = args.cost

    entry = {
        "ts": now,
        "command": args.command,
        "cost": cost,
        "note": getattr(args, "note", "") or "",
    }
    ledger["entries"].append(entry)
    ledger["total_cost"] = round(ledger["total_cost"] + cost, 4)
    ledger["total_calls"] += 1

    if today not in ledger["daily"]:
        ledger["daily"][today] = {"count": 0, "cost": 0.0}
    ledger["daily"][today]["count"] += 1
    ledger["daily"][today]["cost"] = round(ledger["daily"][today]["cost"] + cost, 4)

    _save_ledger(ledger)
    print(json.dumps({
        "logged": True,
        "cost": cost,
        "total_cost": ledger["total_cost"],
        "total_calls": ledger["total_calls"],
        "today_cost": ledger["daily"][today]["cost"],
    }))


def cmd_summary(args):
    """Show spending summary."""
    ledger = _load_ledger()
    cfg = _load_config()

    output = {
        "total_calls": ledger["total_calls"],
        "total_cost_usd": ledger["total_cost"],
        "approval_mode": cfg.get("approval_mode"),
        "threshold_usd": cfg.get("threshold_usd"),
    }

    daily = ledger.get("daily", {})
    if daily:
        sorted_days = sorted(daily.keys(), reverse=True)[:7]
        output["last_7_days"] = {
            d: daily[d] for d in sorted_days
        }

    print(json.dumps(output, indent=2))


def cmd_today(args):
    """Show today's spending."""
    ledger = _load_ledger()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily = ledger.get("daily", {}).get(today, {"count": 0, "cost": 0.0})
    cfg = _load_config()

    result = {
        "date": today,
        "calls": daily["count"],
        "cost_usd": daily["cost"],
        "session_budget_usd": cfg.get("session_budget_usd"),
    }
    if cfg.get("session_budget_usd") is not None:
        result["remaining_usd"] = round(
            cfg["session_budget_usd"] - daily["cost"], 4
        )
    print(json.dumps(result, indent=2))


def cmd_reset(args):
    """Reset the spending ledger."""
    if not args.confirm:
        print("Error: Pass --confirm to reset.", file=sys.stderr)
        sys.exit(1)
    _save_ledger({"total_cost": 0.0, "total_calls": 0, "entries": [], "daily": {}})
    print(json.dumps({"status": "reset"}))


def main():
    parser = argparse.ArgumentParser(
        description="DataForSEO Cost Estimator and Tracker"
    )
    sub = parser.add_subparsers(dest="command_name", required=True)

    # init
    p_init = sub.add_parser("init", help="Create default config")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing")

    # config
    p_cfg = sub.add_parser("config", help="Show/update config")
    p_cfg.add_argument(
        "--set", nargs="+", metavar="KEY=VALUE",
        help="Set config values (e.g. approval_mode=always threshold_usd=1.00)"
    )

    # estimate
    p_est = sub.add_parser("estimate", help="Estimate command cost")
    p_est.add_argument("--command", required=True, help="DataForSEO command name")
    p_est.add_argument("--keywords", type=int, default=0, help="Number of keywords")
    p_est.add_argument("--domains", type=int, default=0, help="Number of domains")
    p_est.add_argument("--limit", type=int, default=0, help="Row limit")
    p_est.add_argument("--grid-size", type=int, default=0, help="Grid dimension (NxN)")

    # check
    p_chk = sub.add_parser("check", help="Estimate + check approval")
    p_chk.add_argument("--command", required=True, help="DataForSEO command name")
    p_chk.add_argument("--keywords", type=int, default=0, help="Number of keywords")
    p_chk.add_argument("--domains", type=int, default=0, help="Number of domains")
    p_chk.add_argument("--limit", type=int, default=0, help="Row limit")
    p_chk.add_argument("--grid-size", type=int, default=0, help="Grid dimension (NxN)")

    # log
    p_log = sub.add_parser("log", help="Log actual spend")
    p_log.add_argument("--command", required=True, help="Command that was run")
    p_log.add_argument("--cost", required=True, type=float, help="Actual cost in USD")
    p_log.add_argument("--note", default="", help="Optional note")

    # summary
    sub.add_parser("summary", help="Spending summary")

    # today
    sub.add_parser("today", help="Today's spending")

    # reset
    p_reset = sub.add_parser("reset", help="Reset ledger")
    p_reset.add_argument("--confirm", action="store_true", help="Confirm reset")

    args = parser.parse_args()
    cmds = {
        "init": cmd_init,
        "config": cmd_config,
        "estimate": cmd_estimate,
        "check": cmd_check,
        "log": cmd_log,
        "summary": cmd_summary,
        "today": cmd_today,
        "reset": cmd_reset,
    }
    cmds[args.command_name](args)


if __name__ == "__main__":
    main()
