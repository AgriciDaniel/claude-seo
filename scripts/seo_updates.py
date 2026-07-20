#!/usr/bin/env python3
"""
Primary-source Google updates query tool.

Reads ``data/google-updates.json`` and surfaces filtered views of the
confirmed Google ranking / spam / QRG / product / schema updates
since March 2024. Every entry cites a Google-owned URL.

The companion file lists *unverified* third-party claims separately. Those
entries are explicitly NOT used to drive recommendations until they are
confirmed against ``status.search.google.com``.

Usage::

    python scripts/seo_updates.py                  # latest 10
    python scripts/seo_updates.py --since 2025-06  # ISO yyyy or yyyy-mm filter
    python scripts/seo_updates.py --kind core
    python scripts/seo_updates.py --json
    python scripts/seo_updates.py --unverified     # show 3rd-party claims awaiting check
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Iterable


_DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "google-updates.json"


def _load() -> dict:
    with _DATA_FILE.open() as fh:
        return json.load(fh)


def _filter(
    updates: Iterable[dict],
    *,
    since: str | None = None,
    kinds: set[str] | None = None,
) -> list[dict]:
    out = list(updates)
    if since:
        # Accept yyyy or yyyy-mm
        if len(since) == 4:
            since_date = date(int(since), 1, 1)
        elif len(since) == 7:
            y, m = since.split("-")
            since_date = date(int(y), int(m), 1)
        else:
            since_date = date.fromisoformat(since)
        out = [u for u in out if date.fromisoformat(u["date"]) >= since_date]
    if kinds:
        out = [u for u in out if u.get("kind") in kinds]
    out.sort(key=lambda u: u["date"], reverse=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Query the primary-source Google updates changelog."
    )
    parser.add_argument(
        "--since",
        help="ISO date (yyyy, yyyy-mm, or yyyy-mm-dd) to filter from.",
    )
    parser.add_argument(
        "--kind",
        action="append",
        choices=("core", "spam", "core+spam", "policy", "qrg", "product", "schema", "cwv", "discover"),
        help="Filter to one or more kinds (repeatable).",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="Maximum number of entries to show (default 10).",
    )
    parser.add_argument(
        "--unverified",
        action="store_true",
        help="Show only the unverified third-party claims awaiting "
             "confirmation against status.search.google.com.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = _load()

    if args.unverified:
        result = {
            "last_verified": data.get("last_verified"),
            "source_of_truth": data.get("source_of_truth"),
            "unverified": data.get("unverified", []),
        }
        if args.json:
            json.dump(result, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            print(f"Source of truth: {result['source_of_truth']}")
            print(f"Last verified:   {result['last_verified']}")
            print()
            if not result["unverified"]:
                print("(no unverified third-party claims tracked)")
            for entry in result["unverified"]:
                print(f"  {entry['date']}: {entry['claim']}")
                print(f"    status: {entry['status']}")
                for s in entry.get("third_party_sources", []):
                    print(f"    third-party: {s}")
                print(f"    primary-check: {entry['primary_source_check']}")
                print()
        return 0

    kinds = set(args.kind) if args.kind else None
    filtered = _filter(data["updates"], since=args.since, kinds=kinds)[: args.limit]

    if args.json:
        json.dump(
            {
                "source_of_truth": data["source_of_truth"],
                "last_verified": data["last_verified"],
                "filter": {"since": args.since, "kinds": list(kinds or [])},
                "count": len(filtered),
                "updates": filtered,
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    print(f"Source of truth: {data['source_of_truth']}")
    print(f"Last verified:   {data['last_verified']}")
    print(f"Showing {len(filtered)} updates"
          f"{' since ' + args.since if args.since else ''}"
          f"{' kind=' + '/'.join(kinds) if kinds else ''}")
    print()
    for u in filtered:
        print(f"  {u['date']}  [{u['kind']:<10}]  {u['name']}")
        print(f"      source: {u['source']}")
        print(f"      notes:  {u['notes']}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
