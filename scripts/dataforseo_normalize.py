#!/usr/bin/env python3
"""
Normalize DataForSEO API responses for consistent consumption by claude-seo skills.

Provides generic helpers (extract_items, truncate_for_context, format_table) and
per-module normalizers (merchant, social, reviews, etc.).

Usage:
    python dataforseo_normalize.py <input.json> [--module merchant|social|reviews]

Can also be imported as a library:
    from dataforseo_normalize import extract_items, normalize_merchant, truncate_for_context

Original concept: Matej Marjanovic (Pro Hub Challenge)
"""

import argparse
import json
import math
import sys
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def extract_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract data items from a DataForSEO response envelope.

    DataForSEO responses follow a consistent structure:
        { "tasks": [ { "result": [ { "items": [...] } ] } ] }

    This function walks the envelope and collects all items into a flat list.

    Args:
        response: Raw DataForSEO JSON response.

    Returns:
        Flat list of item dicts.
    """
    items: list[dict[str, Any]] = []
    for task in response.get("tasks", []):
        if task.get("status_code") != 20000:
            continue
        for result in task.get("result", []) or []:
            result_items = result.get("items")
            if result_items and isinstance(result_items, list):
                items.extend(result_items)
    return items


def truncate_for_context(
    data: list[dict[str, Any]],
    max_tokens: int = 4000,
    chars_per_token: float = 3.5,
) -> list[dict[str, Any]]:
    """
    Truncate a list of result items to fit within an LLM context budget.

    Uses a simple character-based estimation (avg ~3.5 chars/token for JSON).
    Items are kept in order; the list is sliced when the budget is exceeded.

    Args:
        data: List of normalized item dicts.
        max_tokens: Approximate token budget.
        chars_per_token: Average characters per token for estimation.

    Returns:
        Truncated list that fits within the budget.
    """
    max_chars = int(max_tokens * chars_per_token)
    total_chars = 0
    truncated: list[dict[str, Any]] = []

    for item in data:
        item_str = json.dumps(item, ensure_ascii=False)
        item_chars = len(item_str)
        if total_chars + item_chars > max_chars:
            break
        truncated.append(item)
        total_chars += item_chars

    return truncated


def format_markdown_table(
    items: list[dict[str, Any]],
    columns: list[str],
    headers: Optional[list[str]] = None,
    max_rows: int = 50,
) -> str:
    """
    Format a list of dicts as a Markdown table.

    Args:
        items: List of dicts to tabulate.
        columns: Dict keys to include as columns.
        headers: Human-readable column headers (defaults to column keys).
        max_rows: Maximum number of rows to include.

    Returns:
        Markdown-formatted table string.
    """
    if not items:
        return "_No data available._"

    display_headers = headers or [col.replace("_", " ").title() for col in columns]

    # Header row
    lines = [
        "| " + " | ".join(display_headers) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]

    # Data rows
    for item in items[:max_rows]:
        row_values = []
        for col in columns:
            val = item.get(col, "")
            if val is None:
                val = "--"
            elif isinstance(val, float):
                val = f"{val:.2f}" if not val.is_integer() else f"{int(val)}"
            else:
                val = str(val)
            row_values.append(val)
        lines.append("| " + " | ".join(row_values) + " |")

    if len(items) > max_rows:
        lines.append(f"\n_...and {len(items) - max_rows} more rows (truncated)._")

    return "\n".join(lines)


def compute_statistics(values: list[float]) -> dict[str, Optional[float]]:
    """
    Compute basic descriptive statistics for a list of numeric values.

    Args:
        values: List of floats.

    Returns:
        Dict with min, max, mean, median, p25, p75, std_dev.
    """
    if not values:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "p25": None,
            "p75": None,
            "std_dev": None,
            "count": 0,
        }

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mean = sum(sorted_vals) / n

    def _percentile(data: list[float], p: float) -> float:
        idx = (p / 100) * (len(data) - 1)
        lower = int(math.floor(idx))
        upper = int(math.ceil(idx))
        if lower == upper:
            return data[lower]
        frac = idx - lower
        return data[lower] * (1 - frac) + data[upper] * frac

    variance = sum((x - mean) ** 2 for x in sorted_vals) / n
    std_dev = math.sqrt(variance)

    return {
        "min": round(sorted_vals[0], 2),
        "max": round(sorted_vals[-1], 2),
        "mean": round(mean, 2),
        "median": round(_percentile(sorted_vals, 50), 2),
        "p25": round(_percentile(sorted_vals, 25), 2),
        "p75": round(_percentile(sorted_vals, 75), 2),
        "std_dev": round(std_dev, 2),
        "count": n,
    }


# ---------------------------------------------------------------------------
# Merchant normalizer
# ---------------------------------------------------------------------------

def _normalize_price(raw: Any) -> Optional[float]:
    """Convert various price formats to float."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return round(float(raw), 2)
    if isinstance(raw, str):
        cleaned = raw.replace("$", "").replace(",", "").replace(" ", "").strip()
        try:
            return round(float(cleaned), 2)
        except ValueError:
            return None
    return None


def _normalize_currency(raw: Any) -> str:
    """Normalize currency to ISO 4217 code."""
    if not raw:
        return "USD"
    text = str(raw).upper().strip()
    # Handle common symbols
    symbol_map = {"$": "USD", "EUR": "EUR", "GBP": "GBP", "JPY": "JPY"}
    return symbol_map.get(text, text[:3] if len(text) >= 3 else "USD")


def _normalize_availability(raw: Any) -> str:
    """Normalize availability to enum string."""
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


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert a value to int."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def normalize_merchant(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Normalize Google Shopping and Amazon product data.

    Handles variations in DataForSEO response format:
    - Price as string or number
    - Rating as nested dict or flat float
    - Availability as various string formats

    Args:
        items: Raw item dicts from DataForSEO Merchant API.

    Returns:
        List of normalized product dicts.
    """
    normalized = []
    for item in items:
        # Handle rating as dict or scalar
        rating_raw = item.get("rating")
        if isinstance(rating_raw, dict):
            rating_val = _safe_float(rating_raw.get("value") or rating_raw.get("rating_value"))
        else:
            rating_val = _safe_float(rating_raw)

        product = {
            "title": str(item.get("title", "")),
            "price": _normalize_price(item.get("price")),
            "currency": _normalize_currency(item.get("currency")),
            "seller": str(item.get("seller", item.get("seller_name", ""))),
            "rating": round(rating_val, 1),
            "reviews_count": _safe_int(item.get("reviews_count")),
            "url": str(item.get("url", "")),
            "image_url": str(item.get("image_url", item.get("marketplace_url", ""))),
            "availability": _normalize_availability(item.get("availability")),
        }

        # Amazon-specific fields
        if "asin" in item:
            product["asin"] = item["asin"]
        if "is_prime" in item:
            product["is_prime"] = bool(item["is_prime"])
        if "is_best_seller" in item:
            product["is_best_seller"] = bool(item["is_best_seller"])

        # Google-specific fields
        if "product_id" in item:
            product["product_id"] = item["product_id"]
        if "delivery_info" in item:
            product["delivery_info"] = str(item["delivery_info"])

        normalized.append(product)
    return normalized


# ---------------------------------------------------------------------------
# Social normalizer (placeholder for future seo-social skill)
# ---------------------------------------------------------------------------

def normalize_social(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Normalize social signal data from DataForSEO.

    Placeholder for future seo-social skill integration. Handles social
    media engagement metrics, share counts, and platform-specific data.

    Args:
        items: Raw item dicts from DataForSEO social endpoints.

    Returns:
        List of normalized social signal dicts.
    """
    normalized = []
    for item in items:
        signal = {
            "url": str(item.get("url", "")),
            "title": str(item.get("title", "")),
            "platform": str(item.get("platform", item.get("source", "unknown"))),
            "engagement_count": _safe_int(
                item.get("engagement_count", item.get("social_count", 0))
            ),
            "likes": _safe_int(item.get("likes")),
            "shares": _safe_int(item.get("shares")),
            "comments": _safe_int(item.get("comments")),
            "date": str(item.get("date", item.get("datetime", ""))),
            "sentiment": str(item.get("sentiment", "neutral")),
        }
        normalized.append(signal)
    return normalized


# ---------------------------------------------------------------------------
# Reviews normalizer (placeholder for future expansion)
# ---------------------------------------------------------------------------

def normalize_reviews(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Normalize review data from DataForSEO.

    Handles business listing reviews, product reviews, and Google Maps reviews.

    Args:
        items: Raw item dicts from DataForSEO review endpoints.

    Returns:
        List of normalized review dicts.
    """
    normalized = []
    for item in items:
        review = {
            "author": str(item.get("author", item.get("profile_name", "Anonymous"))),
            "rating": round(_safe_float(item.get("rating")), 1),
            "text": str(item.get("text", item.get("review_text", ""))),
            "date": str(item.get("date", item.get("time_ago", ""))),
            "source": str(item.get("source", "")),
            "verified": bool(item.get("is_verified", False)),
            "helpful_count": _safe_int(item.get("helpful_count", item.get("likes", 0))),
        }
        normalized.append(review)
    return normalized


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Normalize DataForSEO API responses for claude-seo skills"
    )
    parser.add_argument("input", help="Input JSON file (use - for stdin)")
    parser.add_argument(
        "--module",
        choices=["merchant", "social", "reviews"],
        default="merchant",
        help="Normalizer module to use (default: merchant)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=0,
        dest="max_tokens",
        help="Truncate output to fit token budget (0 = no truncation)",
    )
    parser.add_argument(
        "--table",
        action="store_true",
        help="Output as Markdown table instead of JSON",
    )
    parser.add_argument(
        "--columns",
        help="Comma-separated column names for table output",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Include price/rating statistics in output",
    )

    args = parser.parse_args()

    # Read input
    if args.input == "-":
        data = json.load(sys.stdin)
    else:
        with open(args.input) as f:
            data = json.load(f)

    # Extract items from response envelope
    items = extract_items(data) if "tasks" in data else data
    if isinstance(items, dict):
        items = [items]

    # Normalize
    normalizers = {
        "merchant": normalize_merchant,
        "social": normalize_social,
        "reviews": normalize_reviews,
    }
    normalized = normalizers[args.module](items)

    # Truncate if requested
    if args.max_tokens > 0:
        normalized = truncate_for_context(normalized, max_tokens=args.max_tokens)

    # Output
    if args.table:
        columns = (
            args.columns.split(",")
            if args.columns
            else _default_columns(args.module)
        )
        print(format_markdown_table(normalized, columns))
    else:
        output: dict[str, Any] = {
            "module": args.module,
            "total_items": len(normalized),
            "items": normalized,
        }

        if args.stats and args.module == "merchant":
            prices = [p["price"] for p in normalized if p.get("price") is not None]
            ratings = [p["rating"] for p in normalized if p.get("rating", 0) > 0]
            output["price_stats"] = compute_statistics(prices)
            output["rating_stats"] = compute_statistics(ratings)

        json.dump(output, sys.stdout, indent=2)


def _default_columns(module: str) -> list[str]:
    """Return default table columns for each module."""
    defaults = {
        "merchant": ["title", "price", "currency", "seller", "rating", "reviews_count", "availability"],
        "social": ["platform", "title", "engagement_count", "likes", "shares", "date"],
        "reviews": ["author", "rating", "text", "date", "source", "verified"],
    }
    return defaults.get(module, ["title"])


if __name__ == "__main__":
    main()
