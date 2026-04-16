#!/usr/bin/env python3
"""
CrUX History API for Core Web Vitals trends over time.

Fetches up to 25 weekly data points from the Chrome UX Report History API
and identifies improving, stable, or degrading trends per metric.

Usage:
    python crux_history.py https://example.com
    python crux_history.py https://example.com --form-factor PHONE --json
    python crux_history.py https://example.com --origin
"""

import argparse
import json
import sys
from typing import Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

try:
    from google_auth import get_api_key, validate_url
except ImportError:
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from google_auth import get_api_key, validate_url

CRUX_HISTORY_ENDPOINT = "https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord"

CWV_THRESHOLDS = {
    "largest_contentful_paint": {"good": 2500, "poor": 4000, "label": "LCP", "unit": "ms"},
    "interaction_to_next_paint": {"good": 200, "poor": 500, "label": "INP", "unit": "ms"},
    "cumulative_layout_shift": {"good": 0.1, "poor": 0.25, "label": "CLS", "unit": ""},
    "first_contentful_paint": {"good": 1800, "poor": 3000, "label": "FCP", "unit": "ms"},
    "experimental_time_to_first_byte": {"good": 800, "poor": 1800, "label": "TTFB", "unit": "ms"},
}


def query_history(
    url_or_origin: str,
    api_key: str,
    form_factor: Optional[str] = None,
) -> dict:
    """
    Query CrUX History API for weekly CWV trends.

    Args:
        url_or_origin: Full URL or origin.
        api_key: Google API key.
        form_factor: DESKTOP, PHONE, or TABLET. None for all.

    Returns:
        Dictionary with metrics timeseries, collection periods, and trend analysis.
    """
    result = {
        "target": url_or_origin,
        "form_factor": form_factor or "ALL",
        "metrics": {},
        "collection_periods": [],
        "trends": {},
        "error": None,
    }

    if not validate_url(url_or_origin):
        result["error"] = "Invalid URL. Only http/https URLs to public hosts are accepted."
        return result

    parsed = urlparse(url_or_origin)
    is_origin = parsed.path in ("", "/") and not parsed.query

    body = {}
    if is_origin:
        body["origin"] = f"{parsed.scheme}://{parsed.netloc}"
    else:
        body["url"] = url_or_origin

    if form_factor:
        body["formFactor"] = form_factor.upper()

    try:
        resp = requests.post(
            f"{CRUX_HISTORY_ENDPOINT}?key={api_key}",
            json=body,
            timeout=30,
        )

        if resp.status_code == 404:
            target_type = "origin" if is_origin else "URL"
            result["error"] = (
                f"No CrUX history data for this {target_type}. "
                "Insufficient Chrome traffic volume for eligibility."
            )
            return result

        if resp.status_code == 429:
            result["error"] = "CrUX API rate limit exceeded (150 QPM shared). Wait and retry."
            return result

        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        result["error"] = f"CrUX History API request failed: {e}"
        return result

    record = data.get("record", {})

    # Collection periods
    periods = record.get("collectionPeriods", [])
    for period in periods:
        first = period.get("firstDate", {})
        last = period.get("lastDate", {})
        result["collection_periods"].append({
            "first": f"{first.get('year')}-{first.get('month', 0):02d}-{first.get('day', 0):02d}",
            "last": f"{last.get('year')}-{last.get('month', 0):02d}-{last.get('day', 0):02d}",
        })

    # Metrics timeseries
    for metric_name, metric_data in record.get("metrics", {}).items():
        if metric_name not in CWV_THRESHOLDS:
            continue

        thresholds = CWV_THRESHOLDS[metric_name]
        p75s_data = metric_data.get("percentilesTimeseries", {})
        p75s_raw = p75s_data.get("p75s", [])

        # Parse p75 values (CLS is string-encoded)
        p75s = []
        for val in p75s_raw:
            if val is None:
                p75s.append(None)
            elif metric_name == "cumulative_layout_shift":
                try:
                    p75s.append(float(str(val)))
                except (ValueError, TypeError):
                    p75s.append(None)
            else:
                try:
                    p75s.append(int(val))
                except (ValueError, TypeError):
                    try:
                        p75s.append(float(val))
                    except (ValueError, TypeError):
                        p75s.append(None)

        # Distributions timeseries
        histogram_ts = metric_data.get("histogramTimeseries", [])
        good_pcts = []
        if len(histogram_ts) >= 3:
            good_densities = histogram_ts[0].get("densities", [])
            for d in good_densities:
                if d is None or str(d) == "NaN":
                    good_pcts.append(None)
                else:
                    try:
                        good_pcts.append(round(float(d) * 100, 1))
                    except (ValueError, TypeError):
                        good_pcts.append(None)

        # Extract needs_improvement (bin 1) and poor (bin 2) percentages
        ni_pcts = []
        poor_pcts = []
        if len(histogram_ts) >= 3:
            for bin_idx, target_list in [(1, ni_pcts), (2, poor_pcts)]:
                bin_densities = histogram_ts[bin_idx].get("densities", [])
                for d in bin_densities:
                    if d is None or str(d) == "NaN":
                        target_list.append(None)
                    else:
                        try:
                            target_list.append(round(float(d) * 100, 1))
                        except (ValueError, TypeError):
                            target_list.append(None)

        result["metrics"][metric_name] = {
            "label": thresholds["label"],
            "unit": thresholds["unit"],
            "p75_values": p75s,
            "good_percentages": good_pcts,
            "needs_improvement_percentages": ni_pcts,
            "poor_percentages": poor_pcts,
            "latest_p75": p75s[-1] if p75s and p75s[-1] is not None else None,
            "good_threshold": thresholds["good"],
            "poor_threshold": thresholds["poor"],
        }

    # Trend analysis
    result["trends"] = detect_trends(result["metrics"])

    return result


def detect_trends(metrics: dict) -> dict:
    """
    Analyze p75 timeseries to detect trends.

    Compares the average of the last 4 weeks to the average of the first 4 weeks.

    Returns:
        Dictionary mapping metric names to trend info:
        direction (improving/stable/degrading), change_pct, latest, earliest.
    """
    trends = {}

    for metric_name, data in metrics.items():
        p75s = data.get("p75_values", [])
        valid = [v for v in p75s if v is not None]

        if len(valid) < 8:
            trends[metric_name] = {
                "direction": "insufficient_data",
                "label": data.get("label", metric_name),
            }
            continue

        # First 4 valid vs last 4 valid
        first_4 = valid[:4]
        last_4 = valid[-4:]
        avg_first = sum(first_4) / len(first_4)
        avg_last = sum(last_4) / len(last_4)

        if avg_first == 0:
            change_pct = 0
        else:
            change_pct = ((avg_last - avg_first) / avg_first) * 100

        # For CWV, lower is better (except CLS where lower is also better)
        # So a negative change_pct means improvement
        if abs(change_pct) < 5:
            direction = "stable"
        elif change_pct < 0:
            direction = "improving"
        else:
            direction = "degrading"

        trends[metric_name] = {
            "direction": direction,
            "change_pct": round(change_pct, 1),
            "earliest_avg": round(avg_first, 3) if data.get("unit") == "" else round(avg_first),
            "latest_avg": round(avg_last, 3) if data.get("unit") == "" else round(avg_last),
            "label": data.get("label", metric_name),
            "data_points": len(valid),
        }

    return trends


def main():
    parser = argparse.ArgumentParser(
        description="CrUX History API - Core Web Vitals trends over time"
    )
    parser.add_argument("url", help="URL or origin to analyze")
    parser.add_argument(
        "--form-factor",
        choices=["PHONE", "DESKTOP", "TABLET"],
        help="Filter by form factor",
    )
    parser.add_argument(
        "--api-key",
        help="Google API key (overrides config/env)",
    )
    parser.add_argument(
        "--origin",
        action="store_true",
        help="Force origin-level query (strip path/query)",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    api_key = args.api_key or get_api_key()
    if not api_key:
        print("Error: API key required. Use --api-key or configure GOOGLE_API_KEY.", file=sys.stderr)
        sys.exit(1)

    target = args.url
    if args.origin:
        parsed = urlparse(target)
        target = f"{parsed.scheme}://{parsed.netloc}"

    result = query_history(target, api_key, form_factor=args.form_factor)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("error"):
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

        print(f"=== CrUX History ({result.get('form_factor', 'ALL')}) ===")
        print(f"Target: {result.get('target')}")

        periods = result.get("collection_periods", [])
        if periods:
            print(f"Range: {periods[0]['first']} to {periods[-1]['last']} ({len(periods)} weeks)")

        print("\nTrend Analysis:")
        for name, trend in result.get("trends", {}).items():
            label = trend.get("label", name)
            direction = trend.get("direction", "?")
            if direction == "insufficient_data":
                print(f"  {label}: Insufficient data")
                continue

            arrow = {"improving": "IMPROVING", "stable": "STABLE", "degrading": "DEGRADING"}.get(direction, "?")
            change = trend.get("change_pct", 0)
            earliest = trend.get("earliest_avg")
            latest = trend.get("latest_avg")
            print(f"  {label}: {arrow} ({change:+.1f}%) | {earliest} -> {latest}")


if __name__ == "__main__":
    main()
