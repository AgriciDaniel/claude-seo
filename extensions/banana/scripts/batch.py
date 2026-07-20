#!/usr/bin/env python3
"""Claude Banana - CSV Batch Workflow

Parse a CSV file of image generation requests and output a structured plan.
Claude then executes each row via MCP.

Usage:
    batch.py --csv path/to/file.csv --model MODEL [--unit-cost USD]

CSV columns:
    prompt (required), ratio, resolution, model, preset (all optional except prompt)

Example CSV:
    prompt,ratio,resolution
    "coffee shop hero image",16:9,2K
    "team photo placeholder",1:1,1K
    "product shot on marble",4:3,2K
"""

import argparse
import csv
import json
import sys
from pathlib import Path

DEFAULT_RESOLUTION = "1K"
DEFAULT_RATIO = "1:1"


def estimate_cost(unit_cost):
    """Estimate cost for a single image from a user-verified unit cost."""
    return unit_cost


def main():
    parser = argparse.ArgumentParser(description="Parse CSV batch and output generation plan")
    parser.add_argument("--csv", required=True, help="Path to CSV file")
    parser.add_argument("--model", required=True, help="Default model ID for rows without a model")
    parser.add_argument("--unit-cost", type=float, default=None,
                        help="Optional verified current cost per image in USD")
    args = parser.parse_args()

    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        print(json.dumps({"error": True, "message": f"CSV not found: {csv_path}"}))
        sys.exit(1)

    rows = []
    errors = []

    try:
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "prompt" not in reader.fieldnames:
                print(json.dumps({"error": True, "message": "CSV must have a 'prompt' column header"}))
                sys.exit(1)
            for i, row in enumerate(reader, start=2):  # Line 2+ (1 is header)
                prompt = row.get("prompt", "").strip()
                if not prompt:
                    errors.append(f"Row {i}: missing prompt")
                    continue

                rows.append({
                    "row": i,
                    "prompt": prompt,
                    "ratio": row.get("ratio", "").strip() or DEFAULT_RATIO,
                    "resolution": row.get("resolution", "").strip() or DEFAULT_RESOLUTION,
                    "model": row.get("model", "").strip() or args.model,
                    "preset": row.get("preset", "").strip() or None,
                })
    except (csv.Error, UnicodeDecodeError) as e:
        print(json.dumps({"error": True, "message": f"Failed to parse CSV: {e}"}))
        sys.exit(1)

    if errors:
        print("Validation errors:")
        for e in errors:
            print(f"  - {e}")
        if not rows:
            sys.exit(1)
        print()

    # Cost estimate
    unit_cost = estimate_cost(args.unit_cost)
    total_cost = round(unit_cost * len(rows), 3) if unit_cost is not None else None
    pricing_note = ("Approximate estimate from user-provided unit cost"
                    if unit_cost is not None
                    else "No estimate; pass --unit-cost after checking current Google pricing")

    # Output structured JSON for Claude to consume
    print(json.dumps({"rows": rows, "total_count": len(rows),
                       "estimated_cost": total_cost,
                       "pricing_note": pricing_note,
                       "errors": errors}, indent=2))


if __name__ == "__main__":
    main()
