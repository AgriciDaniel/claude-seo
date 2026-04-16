#!/usr/bin/env python3
"""
Query drift history for a URL from the SQLite database.

Usage:
    python drift_history.py <url> [--limit N]

Output: JSON array of baselines and comparisons for the URL.
"""

import argparse
import json
import os
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from drift_baseline import DB_PATH, init_db, normalize_url, url_hash  # noqa: E402


def get_history(url: str, limit: int = 20) -> dict:
    """
    Retrieve baselines and comparisons for a URL.

    Args:
        url: The URL to query history for.
        limit: Maximum number of baselines to return.

    Returns:
        Dict with baselines and comparisons arrays.
    """
    norm_url = normalize_url(url)
    uhash = url_hash(url)

    if not os.path.exists(DB_PATH):
        return {"url": norm_url, "baselines": [], "comparisons": [], "note": "No database found. Run `drift baseline` first."}

    conn = init_db()
    try:
        # Fetch baselines (all queries parameterized)
        rows = conn.execute(
            """
            SELECT id, url, timestamp, title, canonical, robots, h1,
                   status_code, html_hash, schema_hash,
                   CASE WHEN cwv_json IS NOT NULL THEN 1 ELSE 0 END as has_cwv
            FROM baselines
            WHERE url_hash = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (uhash, limit),
        ).fetchall()

        baselines = []
        for row in rows:
            baselines.append({
                "id": row[0],
                "url": row[1],
                "timestamp": row[2],
                "title": row[3],
                "canonical": row[4],
                "robots": row[5],
                "h1": row[6],
                "status_code": row[7],
                "html_hash": row[8][:12] + "..." if row[8] else None,
                "schema_hash": row[9][:12] + "..." if row[9] else None,
                "has_cwv": bool(row[10]),
            })

        # Fetch comparisons
        comp_rows = conn.execute(
            """
            SELECT id, baseline_id, timestamp, critical_count, warning_count, info_count
            FROM comparisons
            WHERE url_hash = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (uhash, limit),
        ).fetchall()

        comparisons = []
        for row in comp_rows:
            comparisons.append({
                "id": row[0],
                "baseline_id": row[1],
                "timestamp": row[2],
                "critical": row[3],
                "warning": row[4],
                "info": row[5],
            })

    finally:
        conn.close()

    return {
        "url": norm_url,
        "baselines": baselines,
        "comparisons": comparisons,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Query SEO drift history for a URL"
    )
    parser.add_argument("url", help="URL to query history for")
    parser.add_argument(
        "--limit", "-n",
        type=int,
        default=20,
        help="Maximum number of entries to return (default: 20)",
    )

    args = parser.parse_args()
    result = get_history(args.url, limit=args.limit)

    print(json.dumps(result, indent=2))

    if not result["baselines"]:
        print(f"\nNo baselines found for {result['url']}.", file=sys.stderr)
        print("Run `python scripts/drift_baseline.py <url>` to capture the first baseline.", file=sys.stderr)


if __name__ == "__main__":
    main()
