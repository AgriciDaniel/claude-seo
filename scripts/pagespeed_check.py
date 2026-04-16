#!/usr/bin/env python3
"""
PageSpeed Insights v5 + CrUX API combined checker.

Runs Lighthouse lab analysis via PSI and fetches real Chrome UX field data
via the CrUX API. Merges both perspectives into a single report.

Usage:
    python pagespeed_check.py https://example.com
    python pagespeed_check.py https://example.com --strategy mobile
    python pagespeed_check.py https://example.com --crux-only
    python pagespeed_check.py https://example.com --psi-only --json
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

# Import credential helper (same directory)
try:
    from google_auth import get_api_key, load_config, validate_url
except ImportError:
    # Fallback: try relative import from scripts/
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from google_auth import get_api_key, load_config, validate_url

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CRUX_ENDPOINT = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"

# Core Web Vitals thresholds (March 2026)
CWV_THRESHOLDS = {
    "largest_contentful_paint": {"good": 2500, "poor": 4000, "unit": "ms", "label": "LCP"},
    "interaction_to_next_paint": {"good": 200, "poor": 500, "unit": "ms", "label": "INP"},
    "cumulative_layout_shift": {"good": 0.1, "poor": 0.25, "unit": "", "label": "CLS"},
    "first_contentful_paint": {"good": 1800, "poor": 3000, "unit": "ms", "label": "FCP"},
    "experimental_time_to_first_byte": {"good": 800, "poor": 1800, "unit": "ms", "label": "TTFB"},
}

PSI_METRIC_MAP = {
    "LARGEST_CONTENTFUL_PAINT_MS": "largest_contentful_paint",
    "INTERACTION_TO_NEXT_PAINT": "interaction_to_next_paint",
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": "cumulative_layout_shift",
    "FIRST_CONTENTFUL_PAINT_MS": "first_contentful_paint",
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE": "experimental_time_to_first_byte",
}


def rate_metric(metric_name: str, value: float) -> str:
    """Rate a CWV metric as good/needs-improvement/poor."""
    thresholds = CWV_THRESHOLDS.get(metric_name)
    if not thresholds:
        return "unknown"
    if value <= thresholds["good"]:
        return "good"
    elif value <= thresholds["poor"]:
        return "needs-improvement"
    else:
        return "poor"


def run_pagespeed(
    url: str,
    strategy: str = "mobile",
    api_key: Optional[str] = None,
    categories: Optional[list] = None,
) -> dict:
    """
    Run PageSpeed Insights v5 analysis.

    Args:
        url: URL to analyze.
        strategy: 'mobile' or 'desktop'.
        api_key: Google API key (optional but recommended for quota).
        categories: List of categories: PERFORMANCE, ACCESSIBILITY, BEST_PRACTICES, SEO.

    Returns:
        Dictionary with lighthouse scores, lab metrics, field data (if available),
        and opportunities. Error in 'error' field on failure.
    """
    result = {
        "url": url,
        "strategy": strategy,
        "lighthouse_scores": {},
        "lab_metrics": {},
        "field_metrics": {},
        "opportunities": [],
        "diagnostics": [],
        "failed_audits": [],
        "passed_audits_count": 0,
        "seo_audits": [],
        "accessibility_audits": [],
        "analysis_timestamp": None,
        "error": None,
    }

    if not validate_url(url):
        result["error"] = "Invalid URL. Only http/https URLs to public hosts are accepted."
        return result

    if categories is None:
        categories = ["PERFORMANCE", "ACCESSIBILITY", "BEST_PRACTICES", "SEO"]

    params = {
        "url": url,
        "strategy": strategy.upper(),
    }
    for cat in categories:
        params.setdefault("category", [])
        if isinstance(params["category"], list):
            params["category"].append(cat)

    if api_key:
        params["key"] = api_key

    try:
        resp = requests.get(PSI_ENDPOINT, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        result["error"] = "PageSpeed Insights request timed out (120s). The target page may be very slow."
        return result
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 429:
            result["error"] = "PSI rate limit exceeded (240 QPM / 25,000 QPD). Wait and retry."
        elif resp.status_code == 400:
            result["error"] = f"Invalid URL or parameters: {resp.text}"
        else:
            result["error"] = f"PSI API error {resp.status_code}: {e}"
        return result
    except requests.exceptions.RequestException as e:
        result["error"] = f"Request failed: {e}"
        return result

    result["analysis_timestamp"] = data.get("analysisUTCTimestamp")

    # Lighthouse scores
    lr = data.get("lighthouseResult", {})
    for cat_key, cat_data in lr.get("categories", {}).items():
        result["lighthouse_scores"][cat_key] = round(cat_data.get("score", 0) * 100)

    # Lab metrics from Lighthouse audits
    audits = lr.get("audits", {})
    lab_audit_ids = [
        "first-contentful-paint", "largest-contentful-paint",
        "total-blocking-time", "cumulative-layout-shift",
        "speed-index", "interactive",
    ]
    for audit_id in lab_audit_ids:
        audit = audits.get(audit_id, {})
        if audit.get("numericValue") is not None:
            result["lab_metrics"][audit_id] = {
                "value": audit["numericValue"],
                "display": audit.get("displayValue", ""),
                "score": audit.get("score"),
            }

    # Field data from PSI (loading experience)
    for exp_key in ["loadingExperience", "originLoadingExperience"]:
        exp = data.get(exp_key, {})
        metrics = exp.get("metrics", {})
        if metrics:
            field_source = "url" if exp_key == "loadingExperience" else "origin"
            for psi_name, crux_name in PSI_METRIC_MAP.items():
                metric_data = metrics.get(psi_name, {})
                if metric_data:
                    p75 = metric_data.get("percentile")
                    category = metric_data.get("category", "NONE")
                    if p75 is not None:
                        # CLS from PSI is already numeric
                        if crux_name == "cumulative_layout_shift":
                            p75_val = p75 / 100 if p75 > 1 else p75
                        else:
                            p75_val = p75
                        result["field_metrics"][f"{field_source}_{crux_name}"] = {
                            "p75": p75_val,
                            "rating": category.lower().replace("_", "-"),
                            "source": f"PSI {field_source}-level",
                        }

    # Opportunities
    for audit_id, audit in audits.items():
        if audit.get("details", {}).get("type") == "opportunity":
            savings = audit.get("details", {}).get("overallSavingsMs")
            if savings and savings > 0:
                result["opportunities"].append({
                    "id": audit_id,
                    "title": audit.get("title", audit_id),
                    "savings_ms": savings,
                    "description": audit.get("description", ""),
                })

    result["opportunities"].sort(key=lambda x: x["savings_ms"], reverse=True)

    # Diagnostics (performance bottlenecks)
    diagnostic_ids = [
        "dom-size", "render-blocking-resources", "uses-long-cache-ttl",
        "total-byte-weight", "mainthread-work-breakdown", "bootup-time",
        "font-display", "third-party-summary", "largest-contentful-paint-element",
        "layout-shifts", "long-tasks", "duplicated-javascript",
        "legacy-javascript", "unused-javascript", "unused-css-rules",
    ]
    for diag_id in diagnostic_ids:
        audit = audits.get(diag_id, {})
        if audit:
            score = audit.get("score")
            result["diagnostics"].append({
                "id": diag_id,
                "title": audit.get("title", diag_id),
                "display": audit.get("displayValue", ""),
                "score": score,
                "description": audit.get("description", ""),
            })

    # Failed and warning audits (score < 0.9, excluding opportunities already captured)
    opportunity_ids = {o["id"] for o in result["opportunities"]}
    passed_count = 0
    for audit_id, audit in audits.items():
        score = audit.get("score")
        if score is None:
            continue
        if score >= 0.9:
            passed_count += 1
            continue
        if audit_id in opportunity_ids:
            continue
        result["failed_audits"].append({
            "id": audit_id,
            "title": audit.get("title", audit_id),
            "score": score,
            "display": audit.get("displayValue", ""),
            "description": audit.get("description", ""),
        })
    result["passed_audits_count"] = passed_count
    result["failed_audits"].sort(key=lambda x: x.get("score", 1))

    # SEO audits from the SEO category
    seo_cat = lr.get("categories", {}).get("seo", {})
    for ref in seo_cat.get("auditRefs", []):
        audit = audits.get(ref.get("id"), {})
        if audit and audit.get("score") is not None:
            result["seo_audits"].append({
                "id": ref["id"],
                "title": audit.get("title", ref["id"]),
                "score": audit["score"],
                "pass": audit["score"] >= 0.9,
            })

    # Accessibility audits from the accessibility category
    a11y_cat = lr.get("categories", {}).get("accessibility", {})
    for ref in a11y_cat.get("auditRefs", []):
        audit = audits.get(ref.get("id"), {})
        if audit and audit.get("score") is not None and audit["score"] < 0.9:
            result["accessibility_audits"].append({
                "id": ref["id"],
                "title": audit.get("title", ref["id"]),
                "score": audit["score"],
                "display": audit.get("displayValue", ""),
            })

    # Audit details: extract top items from audits with details.items[]
    # This captures WHICH specific resources are problems (e.g., "hero.jpg is 2MB")
    for audit_id, audit in audits.items():
        details = audit.get("details", {})
        items = details.get("items", [])
        headings = details.get("headings", [])
        if items and headings:
            heading_keys = [h.get("key", "") for h in headings if h.get("key")]
            extracted_items = []
            for item in items[:5]:
                row = {}
                for key in heading_keys:
                    val = item.get(key)
                    if isinstance(val, dict):
                        row[key] = val.get("url") or val.get("text") or str(val)[:200]
                    elif val is not None:
                        row[key] = val
                if row:
                    extracted_items.append(row)
            if extracted_items:
                result["audit_details"][audit_id] = {
                    "title": audit.get("title", audit_id),
                    "headings": heading_keys,
                    "items": extracted_items,
                    "total_items": len(items),
                }

    return result


def query_crux(
    url_or_origin: str,
    api_key: str,
    form_factor: Optional[str] = None,
) -> dict:
    """
    Query the CrUX API for field data (28-day rolling average).

    Args:
        url_or_origin: Full URL or origin (e.g., https://example.com).
        api_key: Google API key.
        form_factor: DESKTOP, PHONE, or TABLET. None for all form factors.

    Returns:
        Dictionary with p75 metrics, distributions, collection period, and rating.
        Error in 'error' field on failure.
    """
    result = {
        "target": url_or_origin,
        "metrics": {},
        "collection_period": None,
        "form_factor": form_factor or "ALL",
        "error": None,
    }

    if not validate_url(url_or_origin):
        result["error"] = "Invalid URL. Only http/https URLs to public hosts are accepted."
        return result

    parsed = urlparse(url_or_origin)
    # Determine if this is a URL or an origin
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
            f"{CRUX_ENDPOINT}?key={api_key}",
            json=body,
            timeout=30,
        )

        if resp.status_code == 404:
            target_type = "origin" if is_origin else "URL"
            result["error"] = (
                f"No CrUX data for this {target_type}. "
                "The site likely has insufficient Chrome traffic volume for eligibility."
            )
            return result

        if resp.status_code == 429:
            result["error"] = "CrUX API rate limit exceeded (150 QPM shared with History API). Wait and retry."
            return result

        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        result["error"] = f"CrUX API request failed: {e}"
        return result

    record = data.get("record", {})

    # Collection period
    cp = record.get("collectionPeriod", {})
    if cp:
        first = cp.get("firstDate", {})
        last = cp.get("lastDate", {})
        result["collection_period"] = {
            "first": f"{first.get('year')}-{first.get('month', 0):02d}-{first.get('day', 0):02d}",
            "last": f"{last.get('year')}-{last.get('month', 0):02d}-{last.get('day', 0):02d}",
        }

    # Metrics
    for metric_name, metric_data in record.get("metrics", {}).items():
        p75s = metric_data.get("percentiles", {})
        p75 = p75s.get("p75")
        if p75 is None:
            continue

        # CLS is string-encoded in CrUX -- parse carefully
        if metric_name == "cumulative_layout_shift":
            try:
                p75_val = float(str(p75))
            except (ValueError, TypeError):
                p75_val = 0.0
        else:
            try:
                p75_val = int(p75)
            except (ValueError, TypeError):
                try:
                    p75_val = float(p75)
                except (ValueError, TypeError):
                    continue

        rating = rate_metric(metric_name, p75_val)
        thresholds = CWV_THRESHOLDS.get(metric_name, {})

        result["metrics"][metric_name] = {
            "p75": p75_val,
            "rating": rating,
            "label": thresholds.get("label", metric_name),
            "unit": thresholds.get("unit", ""),
            "good_threshold": thresholds.get("good"),
            "poor_threshold": thresholds.get("poor"),
        }

        # Distributions
        histogram = metric_data.get("histogram", [])
        if histogram:
            densities = [bin_data.get("density", 0) for bin_data in histogram]
            if len(densities) >= 3:
                result["metrics"][metric_name]["distribution"] = {
                    "good": round(densities[0] * 100, 1),
                    "needs_improvement": round(densities[1] * 100, 1),
                    "poor": round(densities[2] * 100, 1),
                }

    return result


def combined_check(
    url: str,
    api_key: Optional[str] = None,
    strategy: str = "both",
) -> dict:
    """
    Run combined PSI + CrUX check.

    Args:
        url: URL to analyze.
        api_key: Google API key.
        strategy: 'mobile', 'desktop', or 'both'.

    Returns:
        Dictionary with PSI results (per strategy) and CrUX field data.
    """
    result = {
        "url": url,
        "psi": {},
        "crux": None,
        "error": None,
    }

    strategies = ["mobile", "desktop"] if strategy == "both" else [strategy]

    for strat in strategies:
        psi_result = run_pagespeed(url, strategy=strat, api_key=api_key)
        result["psi"][strat] = psi_result
        if psi_result.get("error"):
            result["error"] = psi_result["error"]

    # CrUX (separate call for accurate field data)
    if api_key:
        crux_result = query_crux(url, api_key)
        result["crux"] = crux_result
        # Also try origin-level if URL-level has no data
        if crux_result.get("error") and "insufficient" in crux_result.get("error", ""):
            parsed = urlparse(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            origin_result = query_crux(origin, api_key)
            if not origin_result.get("error"):
                result["crux"] = origin_result
                result["crux"]["note"] = "URL-level data unavailable; showing origin-level data"

    return result


def main():
    parser = argparse.ArgumentParser(
        description="PageSpeed Insights v5 + CrUX API combined checker"
    )
    parser.add_argument("url", help="URL to analyze")
    parser.add_argument(
        "--strategy", "-s",
        choices=["mobile", "desktop", "both"],
        default="both",
        help="Analysis strategy (default: both)",
    )
    parser.add_argument(
        "--api-key",
        help="Google API key (overrides config/env)",
    )
    parser.add_argument(
        "--crux-only",
        action="store_true",
        help="Only fetch CrUX field data (skip PSI Lighthouse)",
    )
    parser.add_argument(
        "--psi-only",
        action="store_true",
        help="Only run PSI Lighthouse (skip CrUX API)",
    )
    parser.add_argument(
        "--form-factor",
        choices=["PHONE", "DESKTOP", "TABLET"],
        help="CrUX form factor filter",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    api_key = args.api_key or get_api_key()

    if args.crux_only:
        if not api_key:
            print("Error: CrUX API requires an API key. Use --api-key or configure GOOGLE_API_KEY.", file=sys.stderr)
            sys.exit(1)
        result = query_crux(args.url, api_key, form_factor=args.form_factor)
    elif args.psi_only:
        strategies = ["mobile", "desktop"] if args.strategy == "both" else [args.strategy]
        result = {"psi": {}}
        for strat in strategies:
            result["psi"][strat] = run_pagespeed(args.url, strategy=strat, api_key=api_key)
    else:
        result = combined_check(args.url, api_key=api_key, strategy=args.strategy)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Pretty print summary
        if args.crux_only:
            _print_crux_summary(result)
        elif args.psi_only:
            for strat, psi in result.get("psi", {}).items():
                _print_psi_summary(psi)
        else:
            for strat, psi in result.get("psi", {}).items():
                _print_psi_summary(psi)
            if result.get("crux"):
                print()
                _print_crux_summary(result["crux"])

    # Exit with error code if any errors occurred
    if isinstance(result, dict) and result.get("error"):
        sys.exit(1)


def _print_psi_summary(psi: dict):
    """Print PSI results in human-readable format."""
    if psi.get("error"):
        print(f"PSI Error ({psi.get('strategy', '?')}): {psi['error']}")
        return

    print(f"\n=== PageSpeed Insights ({psi.get('strategy', 'unknown')}) ===")
    print(f"URL: {psi.get('url')}")
    print(f"Timestamp: {psi.get('analysis_timestamp', 'N/A')}")

    scores = psi.get("lighthouse_scores", {})
    if scores:
        print("\nLighthouse Scores:")
        for cat, score in scores.items():
            print(f"  {cat}: {score}/100")

    lab = psi.get("lab_metrics", {})
    if lab:
        print("\nLab Metrics:")
        for metric_id, data in lab.items():
            print(f"  {metric_id}: {data.get('display', data.get('value'))}")

    opps = psi.get("opportunities", [])
    if opps:
        print("\nTop Opportunities:")
        for opp in opps[:5]:
            print(f"  - {opp['title']} (save ~{opp['savings_ms']}ms)")

    failed = psi.get("failed_audits", [])
    if failed:
        print(f"\nFailed/Warning Audits ({len(failed)}):")
        for a in failed[:10]:
            score_pct = f"{a['score']:.0%}" if a['score'] is not None else "?"
            print(f"  [{score_pct}] {a['title']} {a.get('display', '')}")

    diags = psi.get("diagnostics", [])
    notable_diags = [d for d in diags if d.get("score") is not None and d["score"] < 0.9]
    if notable_diags:
        print(f"\nDiagnostics (needs attention):")
        for d in notable_diags[:5]:
            score_pct = f"{d['score']:.0%}" if d['score'] is not None else "info"
            print(f"  [{score_pct}] {d['title']}: {d.get('display', '')}")

    seo = psi.get("seo_audits", [])
    seo_failed = [a for a in seo if not a.get("pass")]
    if seo_failed:
        print(f"\nSEO Issues ({len(seo_failed)}):")
        for a in seo_failed:
            print(f"  [FAIL] {a['title']}")
    elif seo:
        print(f"\nSEO: All {len(seo)} checks passed")

    a11y = psi.get("accessibility_audits", [])
    if a11y:
        print(f"\nAccessibility Issues ({len(a11y)}):")
        for a in a11y[:5]:
            print(f"  [{a['score']:.0%}] {a['title']}")

    passed = psi.get("passed_audits_count", 0)
    if passed:
        print(f"\nPassed: {passed} audits")


def _print_crux_summary(crux: dict):
    """Print CrUX results in human-readable format."""
    if crux.get("error"):
        print(f"CrUX Error: {crux['error']}")
        return

    print(f"=== CrUX Field Data ({crux.get('form_factor', 'ALL')}) ===")
    print(f"Target: {crux.get('target')}")

    if crux.get("note"):
        print(f"Note: {crux['note']}")

    cp = crux.get("collection_period", {})
    if cp:
        print(f"Period: {cp.get('first')} to {cp.get('last')}")

    metrics = crux.get("metrics", {})
    if metrics:
        print("\nCore Web Vitals (p75):")
        for name, data in metrics.items():
            label = data.get("label", name)
            p75 = data.get("p75")
            unit = data.get("unit", "")
            rating = data.get("rating", "?")
            good = data.get("good_threshold")

            rating_icon = {"good": "GOOD", "needs-improvement": "NEEDS IMPROVEMENT", "poor": "POOR"}.get(rating, "?")

            if name == "cumulative_layout_shift":
                print(f"  {label}: {p75:.3f} [{rating_icon}] (threshold: <={good})")
            else:
                print(f"  {label}: {p75}{unit} [{rating_icon}] (threshold: <={good}{unit})")

            dist = data.get("distribution")
            if dist:
                print(f"       Good: {dist['good']}% | NI: {dist['needs_improvement']}% | Poor: {dist['poor']}%")


if __name__ == "__main__":
    main()
