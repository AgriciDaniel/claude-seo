#!/usr/bin/env python3
"""
Fetch Google Shopping and Amazon marketplace data via DataForSEO API.

Supports product search, seller analysis, and cross-marketplace comparison.
Uses task/poll pattern for standard queue (60-80% cost savings vs live).

Usage:
    python dataforseo_merchant.py search <keyword> [--marketplace google|amazon] [--location 2840]
    python dataforseo_merchant.py sellers <keyword> [--location 2840]
    python dataforseo_merchant.py compare <keyword> [--location 2840]

Environment: DATAFORSEO_USERNAME, DATAFORSEO_PASSWORD
Output: JSON with normalized product data.

Original concept: Matej Marjanovic (Pro Hub Challenge)
"""

import argparse
import base64
import json
import os
import sys
import time
from typing import Any, Optional
from urllib.parse import urlparse

# Add scripts directory to path for sibling imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import requests
except ImportError:
    print(
        json.dumps({"error": "requests library required. Install with: pip install requests"}),
        file=sys.stdout,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE = "https://api.dataforseo.com/v3"

ENDPOINTS = {
    "google_products": "/merchant/google/products/task_post",
    "google_products_get": "/merchant/google/products/task_get/advanced",
    "google_sellers": "/merchant/google/sellers/task_post",
    "google_sellers_get": "/merchant/google/sellers/task_get/advanced",
    "amazon_products": "/merchant/amazon/products/task_post",
    "amazon_products_get": "/merchant/amazon/products/task_get/advanced",
}

COST_ENDPOINTS = {
    "google_products": "merchant_google_products_search",
    "google_sellers": "merchant_google_sellers_search",
    "amazon_products": "merchant_amazon_products_search",
}

# Default polling configuration
POLL_INITIAL_DELAY = 2.0
POLL_MAX_DELAY = 60.0
POLL_MULTIPLIER = 2.0
POLL_MAX_ATTEMPTS = 15


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _get_credentials() -> tuple[str, str]:
    """Read DataForSEO credentials from environment variables."""
    username = os.environ.get("DATAFORSEO_USERNAME", "")
    password = os.environ.get("DATAFORSEO_PASSWORD", "")
    if not username or not password:
        print(
            "Error: DATAFORSEO_USERNAME and DATAFORSEO_PASSWORD environment "
            "variables must be set.",
            file=sys.stderr,
        )
        result = {
            "error": "missing_credentials",
            "message": (
                "DataForSEO credentials not found. Set DATAFORSEO_USERNAME and "
                "DATAFORSEO_PASSWORD environment variables."
            ),
        }
        json.dump(result, sys.stdout, indent=2)
        sys.exit(1)
    return username, password


def _auth_header(username: str, password: str) -> dict[str, str]:
    """Build HTTP Basic Auth header."""
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _post_task(
    endpoint_key: str,
    payload: list[dict[str, Any]],
    headers: dict[str, str],
) -> dict[str, Any]:
    """POST a task to DataForSEO and return the response."""
    url = f"{API_BASE}{ENDPOINTS[endpoint_key]}"
    print(f"Posting task to {endpoint_key}...", file=sys.stderr)

    resp = requests.post(url, json=payload, headers=headers, timeout=30, verify=True)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status_code") != 20000:
        return {
            "error": "api_error",
            "status_code": data.get("status_code"),
            "message": data.get("status_message", "Unknown API error"),
        }
    return data


def _poll_results(
    endpoint_key: str,
    task_id: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    """Poll for task results with exponential backoff."""
    get_key = f"{endpoint_key}_get"
    url = f"{API_BASE}{ENDPOINTS[get_key]}/{task_id}"

    delay = POLL_INITIAL_DELAY
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        print(
            f"Polling attempt {attempt}/{POLL_MAX_ATTEMPTS} "
            f"(waiting {delay:.1f}s)...",
            file=sys.stderr,
        )
        time.sleep(delay)

        resp = requests.get(url, headers=headers, timeout=30, verify=True)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status_code")
        if status == 20000:
            tasks = data.get("tasks", [])
            if tasks and tasks[0].get("status_code") == 20000:
                return data
            # Task not ready yet
            task_status = tasks[0].get("status_code") if tasks else None
            if task_status and task_status != 40601:
                # 40601 = "Task In Queue" -- keep polling
                # Other errors: return the error
                return data

        delay = min(delay * POLL_MULTIPLIER, POLL_MAX_DELAY)

    return {
        "error": "poll_timeout",
        "message": f"Task {task_id} did not complete after {POLL_MAX_ATTEMPTS} attempts.",
    }


def _extract_task_id(response: dict[str, Any]) -> Optional[str]:
    """Extract task ID from POST response."""
    tasks = response.get("tasks", [])
    if tasks and "id" in tasks[0]:
        return tasks[0]["id"]
    return None


def _extract_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract result items from DataForSEO response envelope."""
    items = []
    for task in response.get("tasks", []):
        for result in task.get("result", []):
            task_items = result.get("items")
            if task_items:
                items.extend(task_items)
    return items


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _normalize_price(raw_price: Any) -> Optional[float]:
    """Normalize price to float."""
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return round(float(raw_price), 2)
    if isinstance(raw_price, str):
        cleaned = raw_price.replace("$", "").replace(",", "").replace(" ", "").strip()
        try:
            return round(float(cleaned), 2)
        except ValueError:
            return None
    return None


def _normalize_availability(raw: Any) -> str:
    """Normalize availability to enum."""
    if not raw:
        return "unknown"
    text = str(raw).lower().strip()
    if "in_stock" in text or "in stock" in text:
        return "in_stock"
    if "out_of_stock" in text or "out of stock" in text:
        return "out_of_stock"
    if "preorder" in text or "pre-order" in text or "pre_order" in text:
        return "preorder"
    return "unknown"


def _normalize_product(item: dict[str, Any], marketplace: str) -> dict[str, Any]:
    """Normalize a single product item."""
    return {
        "marketplace": marketplace,
        "title": item.get("title", ""),
        "price": _normalize_price(item.get("price")),
        "currency": item.get("currency", "USD"),
        "seller": item.get("seller", item.get("seller_name", "")),
        "rating": round(float(item.get("rating", {}).get("value", 0) or 0), 1)
            if isinstance(item.get("rating"), dict)
            else round(float(item.get("rating", 0) or 0), 1),
        "reviews_count": int(item.get("reviews_count", 0) or 0),
        "url": item.get("url", ""),
        "image_url": item.get("image_url", item.get("marketplace_url", "")),
        "availability": _normalize_availability(item.get("availability")),
    }


def _normalize_seller(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single seller item."""
    return {
        "seller_name": item.get("seller_name", item.get("title", "")),
        "seller_rating": round(float(item.get("seller_rating", 0) or 0), 1),
        "seller_reviews_count": int(item.get("seller_reviews_count", 0) or 0),
        "price": _normalize_price(item.get("price")),
        "delivery_info": item.get("delivery_info", ""),
        "url": item.get("url", ""),
    }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_search(args):
    """Search for products on Google Shopping or Amazon."""
    username, password = _get_credentials()
    headers = _auth_header(username, password)
    marketplace = args.marketplace

    endpoint_key = (
        "google_products" if marketplace == "google" else "amazon_products"
    )

    payload = [
        {
            "keyword": args.keyword,
            "location_code": args.location,
            "language_code": args.language,
            "depth": args.depth,
        }
    ]
    if args.sort_by:
        payload[0]["sort_by"] = args.sort_by
    if args.price_min is not None:
        payload[0]["price_min"] = args.price_min
    if args.price_max is not None:
        payload[0]["price_max"] = args.price_max

    # Post task
    post_resp = _post_task(endpoint_key, payload, headers)
    if "error" in post_resp:
        json.dump(post_resp, sys.stdout, indent=2)
        return

    task_id = _extract_task_id(post_resp)
    if not task_id:
        json.dump(
            {"error": "no_task_id", "message": "No task ID in response."},
            sys.stdout,
            indent=2,
        )
        return

    # Poll for results
    result_resp = _poll_results(endpoint_key, task_id, headers)
    if "error" in result_resp:
        json.dump(result_resp, sys.stdout, indent=2)
        return

    # Extract and normalize
    items = _extract_items(result_resp)
    normalized = [_normalize_product(item, marketplace) for item in items]

    # Compute summary statistics
    prices = [p["price"] for p in normalized if p["price"] is not None]
    ratings = [p["rating"] for p in normalized if p["rating"] > 0]

    output = {
        "status": "success",
        "marketplace": marketplace,
        "keyword": args.keyword,
        "location_code": args.location,
        "total_results": len(normalized),
        "summary": {
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
            "price_median": sorted(prices)[len(prices) // 2] if prices else None,
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "avg_reviews": (
                round(
                    sum(p["reviews_count"] for p in normalized) / len(normalized), 1
                )
                if normalized
                else None
            ),
        },
        "products": normalized,
    }
    json.dump(output, sys.stdout, indent=2)


def cmd_sellers(args):
    """Search for sellers on Google Shopping."""
    username, password = _get_credentials()
    headers = _auth_header(username, password)

    payload = [
        {
            "keyword": args.keyword,
            "location_code": args.location,
            "language_code": args.language,
        }
    ]

    post_resp = _post_task("google_sellers", payload, headers)
    if "error" in post_resp:
        json.dump(post_resp, sys.stdout, indent=2)
        return

    task_id = _extract_task_id(post_resp)
    if not task_id:
        json.dump(
            {"error": "no_task_id", "message": "No task ID in response."},
            sys.stdout,
            indent=2,
        )
        return

    result_resp = _poll_results("google_sellers", task_id, headers)
    if "error" in result_resp:
        json.dump(result_resp, sys.stdout, indent=2)
        return

    items = _extract_items(result_resp)
    normalized = [_normalize_seller(item) for item in items]

    # Seller dominance analysis
    seller_counts: dict[str, int] = {}
    for s in normalized:
        name = s["seller_name"]
        seller_counts[name] = seller_counts.get(name, 0) + 1

    top_sellers = sorted(seller_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    output = {
        "status": "success",
        "keyword": args.keyword,
        "location_code": args.location,
        "total_sellers": len(normalized),
        "top_sellers": [{"name": n, "listings": c} for n, c in top_sellers],
        "sellers": normalized,
    }
    json.dump(output, sys.stdout, indent=2)


def cmd_compare(args):
    """Cross-marketplace comparison: Google Shopping vs Amazon."""
    username, password = _get_credentials()
    headers = _auth_header(username, password)

    results = {}

    for marketplace, endpoint_key in [("google", "google_products"), ("amazon", "amazon_products")]:
        print(f"Fetching {marketplace} data...", file=sys.stderr)
        payload = [
            {
                "keyword": args.keyword,
                "location_code": args.location,
                "language_code": args.language,
                "depth": args.depth,
            }
        ]

        post_resp = _post_task(endpoint_key, payload, headers)
        if "error" in post_resp:
            results[marketplace] = {"error": post_resp.get("message", "API error")}
            continue

        task_id = _extract_task_id(post_resp)
        if not task_id:
            results[marketplace] = {"error": "No task ID returned"}
            continue

        result_resp = _poll_results(endpoint_key, task_id, headers)
        if "error" in result_resp:
            results[marketplace] = {"error": result_resp.get("message", "Poll error")}
            continue

        items = _extract_items(result_resp)
        normalized = [_normalize_product(item, marketplace) for item in items]
        prices = [p["price"] for p in normalized if p["price"] is not None]
        ratings = [p["rating"] for p in normalized if p["rating"] > 0]

        results[marketplace] = {
            "total_results": len(normalized),
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
            "price_median": sorted(prices)[len(prices) // 2] if prices else None,
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "avg_reviews": (
                round(sum(p["reviews_count"] for p in normalized) / len(normalized), 1)
                if normalized
                else None
            ),
            "products": normalized[:20],  # Top 20 per marketplace for context size
        }

    output = {
        "status": "success",
        "keyword": args.keyword,
        "location_code": args.location,
        "comparison": results,
    }
    json.dump(output, sys.stdout, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch marketplace data via DataForSEO Merchant API"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Shared arguments
    def add_common(p):
        p.add_argument("keyword", help="Product search keyword")
        p.add_argument(
            "--location", type=int, default=2840, help="Location code (default: 2840 = US)"
        )
        p.add_argument(
            "--language", default="en", help="Language code (default: en)"
        )

    # search
    p_search = sub.add_parser("search", help="Search products on a marketplace")
    add_common(p_search)
    p_search.add_argument(
        "--marketplace",
        choices=["google", "amazon"],
        default="google",
        help="Marketplace to search (default: google)",
    )
    p_search.add_argument("--depth", type=int, default=100, help="Number of results")
    p_search.add_argument("--sort-by", dest="sort_by", help="Sort order")
    p_search.add_argument("--price-min", dest="price_min", type=float, help="Minimum price filter")
    p_search.add_argument("--price-max", dest="price_max", type=float, help="Maximum price filter")

    # sellers
    p_sellers = sub.add_parser("sellers", help="Search sellers on Google Shopping")
    add_common(p_sellers)

    # compare
    p_compare = sub.add_parser(
        "compare", help="Cross-marketplace comparison (Google vs Amazon)"
    )
    add_common(p_compare)
    p_compare.add_argument("--depth", type=int, default=100, help="Number of results")

    args = parser.parse_args()

    dispatch = {
        "search": cmd_search,
        "sellers": cmd_sellers,
        "compare": cmd_compare,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
