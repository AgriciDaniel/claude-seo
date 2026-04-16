#!/usr/bin/env python3
"""
Compare current page state to stored baseline and detect SEO drift.

Applies 17 comparison rules across 3 severity levels (CRITICAL, WARNING, INFO).
Fetches current page state and compares against the most recent baseline.

Usage:
    python drift_compare.py <url> [--skip-cwv] [--baseline-id ID]

Output: JSON with diffs, severity levels, and recommended actions.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from google_auth import validate_url  # noqa: E402
from drift_baseline import (  # noqa: E402
    DB_PATH,
    fetch_cwv_data,
    fetch_page_data,
    hash_content,
    init_db,
    normalize_url,
    url_hash,
)


# ---------------------------------------------------------------------------
# Baseline loading
# ---------------------------------------------------------------------------

def load_baseline(conn: sqlite3.Connection, uhash: str, baseline_id: int | None = None) -> dict | None:
    """
    Load the most recent baseline for a URL hash, or a specific baseline by ID.

    All queries use parameterized placeholders.
    """
    if baseline_id is not None:
        row = conn.execute(
            "SELECT * FROM baselines WHERE id = ? AND url_hash = ?",
            (baseline_id, uhash),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM baselines WHERE url_hash = ? ORDER BY id DESC LIMIT 1",
            (uhash,),
        ).fetchone()

    if not row:
        return None

    columns = [desc[0] for desc in conn.execute("SELECT * FROM baselines LIMIT 0").description]
    return dict(zip(columns, row))


# ---------------------------------------------------------------------------
# Comparison rules
# ---------------------------------------------------------------------------

def _make_finding(rule: str, severity: str, triggered: bool, old_value, new_value, message: str) -> dict:
    """Create a standardized finding dict."""
    return {
        "rule": rule,
        "severity": severity,
        "triggered": triggered,
        "old_value": old_value,
        "new_value": new_value,
        "message": message,
    }


def rule_01_schema_removed(baseline: dict, current: dict) -> dict:
    """CRITICAL: Schema/JSON-LD completely removed."""
    old_schema = json.loads(baseline.get("schema_json") or "[]")
    new_schema = current.get("schema", [])
    triggered = len(old_schema) > 0 and len(new_schema) == 0
    return _make_finding(
        "schema_removed", "CRITICAL", triggered,
        f"{len(old_schema)} schema block(s)",
        "0 schema blocks",
        "All structured data (JSON-LD) has been removed. Rich results will be lost. Restore immediately."
        if triggered else "Schema presence unchanged.",
    )


def rule_02_canonical_changed(baseline: dict, current: dict) -> dict:
    """CRITICAL: Canonical URL changed."""
    old = baseline.get("canonical")
    new = current.get("canonical")
    triggered = old is not None and new is not None and old != new
    return _make_finding(
        "canonical_changed", "CRITICAL", triggered,
        old, new,
        f"Canonical URL changed from '{old}' to '{new}'. Verify this is intentional."
        if triggered else "Canonical URL unchanged.",
    )


def rule_03_canonical_removed(baseline: dict, current: dict) -> dict:
    """CRITICAL: Canonical URL removed."""
    old = baseline.get("canonical")
    new = current.get("canonical")
    triggered = old is not None and (new is None or new == "")
    return _make_finding(
        "canonical_removed", "CRITICAL", triggered,
        old, None,
        "Canonical tag has been removed. Google will guess the canonical, often incorrectly."
        if triggered else "Canonical tag presence unchanged.",
    )


def rule_04_noindex_added(baseline: dict, current: dict) -> dict:
    """CRITICAL: Noindex directive added."""
    old_robots = (baseline.get("robots") or "").lower()
    new_robots = (current.get("meta_robots") or "").lower()
    triggered = "noindex" not in old_robots and "noindex" in new_robots
    return _make_finding(
        "noindex_added", "CRITICAL", triggered,
        baseline.get("robots"), current.get("meta_robots"),
        "A 'noindex' directive has been added. The page will be dropped from search results within days."
        if triggered else "Robots directives unchanged regarding noindex.",
    )


def rule_05_h1_removed(baseline: dict, current: dict) -> dict:
    """CRITICAL: H1 tag removed entirely."""
    old_h1 = baseline.get("h1")
    new_h1_list = current.get("h1", [])
    triggered = old_h1 is not None and old_h1 != "" and len(new_h1_list) == 0
    return _make_finding(
        "h1_removed", "CRITICAL", triggered,
        old_h1, None,
        "H1 heading has been removed. Primary topic signal for search engines is gone."
        if triggered else "H1 presence unchanged.",
    )


def rule_06_h1_changed_significantly(baseline: dict, current: dict) -> dict:
    """CRITICAL: H1 text changed significantly (>50% different)."""
    old_h1 = baseline.get("h1") or ""
    new_h1_list = current.get("h1", [])
    new_h1 = new_h1_list[0] if new_h1_list else ""

    if not old_h1 or not new_h1:
        return _make_finding("h1_changed", "CRITICAL", False, old_h1, new_h1, "H1 comparison skipped (one side empty).")

    ratio = SequenceMatcher(None, old_h1, new_h1).ratio()
    triggered = ratio < 0.5
    return _make_finding(
        "h1_changed", "CRITICAL", triggered,
        old_h1, new_h1,
        f"H1 changed significantly (similarity: {ratio:.0%}). Verify keyword targeting is preserved."
        if triggered else f"H1 text is similar enough (similarity: {ratio:.0%}).",
    )


def rule_07_title_removed(baseline: dict, current: dict) -> dict:
    """CRITICAL: Title tag removed entirely."""
    old = baseline.get("title")
    new = current.get("title")
    triggered = old is not None and old != "" and (new is None or new == "")
    return _make_finding(
        "title_removed", "CRITICAL", triggered,
        old, None,
        "Title tag has been removed. Google will auto-generate one, often poorly."
        if triggered else "Title tag presence unchanged.",
    )


def rule_08_status_code_error(baseline: dict, current_status: int | None) -> dict:
    """CRITICAL: HTTP status code changed to 4xx or 5xx."""
    old = baseline.get("status_code")
    new = current_status
    old_ok = old is not None and 200 <= old < 400
    new_error = new is not None and new >= 400
    triggered = old_ok and new_error
    return _make_finding(
        "status_code_error", "CRITICAL", triggered,
        old, new,
        f"Page now returns HTTP {new} (was {old}). Rankings will drop within days."
        if triggered else f"Status code: {old} -> {new}.",
    )


def rule_09_title_changed(baseline: dict, current: dict) -> dict:
    """WARNING: Title text changed."""
    old = (baseline.get("title") or "").strip()
    new = (current.get("title") or "").strip()
    # Only trigger if both exist and differ (removal is Rule 7)
    triggered = old != "" and new != "" and old != new
    return _make_finding(
        "title_changed", "WARNING", triggered,
        old, new,
        "Title tag text has changed. Monitor CTR in Search Console over 2 weeks."
        if triggered else "Title text unchanged.",
    )


def rule_10_meta_description_changed(baseline: dict, current: dict) -> dict:
    """WARNING: Meta description changed."""
    old = (baseline.get("meta_description") or "").strip()
    new = (current.get("meta_description") or "").strip()
    triggered = old != "" and new != "" and old != new
    return _make_finding(
        "meta_description_changed", "WARNING", triggered,
        old[:120] + ("..." if len(old) > 120 else ""),
        new[:120] + ("..." if len(new) > 120 else ""),
        "Meta description has changed. Verify it includes target keywords and CTA."
        if triggered else "Meta description unchanged.",
    )


def rule_11_cwv_regressed(baseline: dict, current_cwv: dict | None) -> dict:
    """WARNING: Core Web Vitals metric regressed >20%."""
    old_cwv = json.loads(baseline.get("cwv_json") or "null")
    if not old_cwv or not current_cwv:
        return _make_finding("cwv_regressed", "WARNING", False, None, None, "CWV comparison skipped (data unavailable).")

    regressions = []
    old_lab = old_cwv.get("lab_metrics", {})
    new_lab = current_cwv.get("lab_metrics", {})

    for metric_id in ["largest-contentful-paint", "cumulative-layout-shift", "total-blocking-time"]:
        old_val = old_lab.get(metric_id, {}).get("value")
        new_val = new_lab.get(metric_id, {}).get("value")
        if old_val is not None and new_val is not None and old_val > 0:
            pct_change = (new_val - old_val) / old_val
            if pct_change > 0.20:  # >20% worse (higher is worse for all these)
                regressions.append(f"{metric_id}: {old_val:.0f} -> {new_val:.0f} (+{pct_change:.0%})")

    triggered = len(regressions) > 0
    return _make_finding(
        "cwv_regressed", "WARNING", triggered,
        {k: v.get("value") for k, v in old_lab.items()} if old_lab else None,
        {k: v.get("value") for k, v in new_lab.items()} if new_lab else None,
        f"CWV regressions detected: {'; '.join(regressions)}"
        if triggered else "No significant CWV regressions.",
    )


def rule_12_performance_score_dropped(baseline: dict, current_cwv: dict | None) -> dict:
    """WARNING: CWV performance score dropped 10+ points."""
    old_cwv = json.loads(baseline.get("cwv_json") or "null")
    if not old_cwv or not current_cwv:
        return _make_finding("perf_score_dropped", "WARNING", False, None, None, "Performance score comparison skipped.")

    old_score = old_cwv.get("performance_score")
    new_score = current_cwv.get("performance_score")
    if old_score is None or new_score is None:
        return _make_finding("perf_score_dropped", "WARNING", False, old_score, new_score, "Performance score unavailable.")

    drop = old_score - new_score
    triggered = drop >= 10
    return _make_finding(
        "perf_score_dropped", "WARNING", triggered,
        old_score, new_score,
        f"Performance score dropped {drop} points ({old_score} -> {new_score}). Run full PageSpeed analysis."
        if triggered else f"Performance score: {old_score} -> {new_score} (change: {-drop:+d}).",
    )


def rule_13_og_tags_removed(baseline: dict, current: dict) -> dict:
    """WARNING: OG tags removed."""
    old_og = json.loads(baseline.get("og_json") or "{}")
    new_og = current.get("open_graph", {})
    triggered = len(old_og) > 0 and len(new_og) == 0
    return _make_finding(
        "og_tags_removed", "WARNING", triggered,
        list(old_og.keys()),
        [],
        "All Open Graph tags have been removed. Social sharing will show generic previews."
        if triggered else "OG tags presence unchanged.",
    )


def rule_14_schema_modified(baseline: dict, current: dict) -> dict:
    """WARNING: Schema/JSON-LD content modified."""
    old_hash = baseline.get("schema_hash")
    new_schema = current.get("schema", [])
    new_schema_str = json.dumps(new_schema, sort_keys=True)
    new_hash = hash_content(new_schema_str) if new_schema else None

    # Only trigger if schema exists in both and hash differs (removal is Rule 1)
    triggered = (
        old_hash is not None
        and new_hash is not None
        and old_hash != new_hash
    )
    return _make_finding(
        "schema_modified", "WARNING", triggered,
        old_hash[:12] + "..." if old_hash else None,
        new_hash[:12] + "..." if new_hash else None,
        "Schema/JSON-LD content has been modified. Validate with /seo schema."
        if triggered else "Schema content hash unchanged.",
    )


def rule_15_schema_added(baseline: dict, current: dict) -> dict:
    """INFO: New schema/JSON-LD added (positive change)."""
    old_schema = json.loads(baseline.get("schema_json") or "[]")
    new_schema = current.get("schema", [])
    triggered = len(old_schema) == 0 and len(new_schema) > 0
    return _make_finding(
        "schema_added", "INFO", triggered,
        "0 schema blocks",
        f"{len(new_schema)} schema block(s)",
        "New structured data added. Validate with /seo schema."
        if triggered else "No new schema added.",
    )


def rule_16_h2_structure_changed(baseline: dict, current: dict) -> dict:
    """INFO: H2 structure changed."""
    old_h2 = json.loads(baseline.get("h2_json") or "[]")
    new_h2 = current.get("h2", [])
    triggered = old_h2 != new_h2
    return _make_finding(
        "h2_structure_changed", "INFO", triggered,
        f"{len(old_h2)} H2s",
        f"{len(new_h2)} H2s",
        f"H2 heading structure changed ({len(old_h2)} -> {len(new_h2)} headings)."
        if triggered else "H2 structure unchanged.",
    )


def rule_17_content_hash_changed(baseline: dict, current_html_hash: str | None) -> dict:
    """INFO: Content hash changed (catch-all)."""
    old_hash = baseline.get("html_hash")
    triggered = (
        old_hash is not None
        and current_html_hash is not None
        and old_hash != current_html_hash
    )
    return _make_finding(
        "content_hash_changed", "INFO", triggered,
        old_hash[:12] + "..." if old_hash else None,
        current_html_hash[:12] + "..." if current_html_hash else None,
        "Page content has changed (HTML body hash differs from baseline)."
        if triggered else "Page content hash unchanged.",
    )


# ---------------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------------

def run_comparison(url: str, skip_cwv: bool = False, baseline_id: int | None = None) -> dict:
    """
    Compare current page state to stored baseline.

    Args:
        url: The URL to compare.
        skip_cwv: Skip Core Web Vitals fetch.
        baseline_id: Specific baseline ID to compare against (default: most recent).

    Returns:
        Dict with comparison results or error.
    """
    # Validate URL (SSRF protection)
    if not validate_url(url):
        return {"error": "URL rejected: only public http/https URLs are accepted (SSRF protection)"}

    uhash = url_hash(url)
    norm_url = normalize_url(url)

    # Load baseline
    conn = init_db()
    try:
        baseline = load_baseline(conn, uhash, baseline_id)
    except sqlite3.Error as e:
        conn.close()
        return {"error": f"Database error: {e}"}

    if not baseline:
        conn.close()
        msg = f"No baseline found for {norm_url}."
        if baseline_id:
            msg += f" (baseline_id={baseline_id})"
        msg += " Run `drift baseline` first."
        return {"error": msg}

    # Fetch current page state
    page_data = fetch_page_data(url)
    if page_data["error"]:
        conn.close()
        return {"error": page_data["error"]}

    parsed = page_data["parsed"]
    if not parsed:
        conn.close()
        return {"error": "No parsed data returned from HTML parser"}

    # Fetch current CWV (optional)
    current_cwv = None
    if not skip_cwv:
        current_cwv = fetch_cwv_data(url)

    # Compute current hashes
    current_html_hash = hash_content(page_data["html"]) if page_data["html"] else None

    # Run all 17 comparison rules
    findings = [
        # CRITICAL (Rules 1-8)
        rule_01_schema_removed(baseline, parsed),
        rule_02_canonical_changed(baseline, parsed),
        rule_03_canonical_removed(baseline, parsed),
        rule_04_noindex_added(baseline, parsed),
        rule_05_h1_removed(baseline, parsed),
        rule_06_h1_changed_significantly(baseline, parsed),
        rule_07_title_removed(baseline, parsed),
        rule_08_status_code_error(baseline, page_data["status_code"]),
        # WARNING (Rules 9-14)
        rule_09_title_changed(baseline, parsed),
        rule_10_meta_description_changed(baseline, parsed),
        rule_11_cwv_regressed(baseline, current_cwv),
        rule_12_performance_score_dropped(baseline, current_cwv),
        rule_13_og_tags_removed(baseline, parsed),
        rule_14_schema_modified(baseline, parsed),
        # INFO (Rules 15-17)
        rule_15_schema_added(baseline, parsed),
        rule_16_h2_structure_changed(baseline, parsed),
        rule_17_content_hash_changed(baseline, current_html_hash),
    ]

    # Separate triggered and untriggered
    triggered = [f for f in findings if f["triggered"]]
    untriggered = [f for f in findings if not f["triggered"]]

    # Count by severity
    critical_count = sum(1 for f in triggered if f["severity"] == "CRITICAL")
    warning_count = sum(1 for f in triggered if f["severity"] == "WARNING")
    info_count = sum(1 for f in triggered if f["severity"] == "INFO")

    now = datetime.now(timezone.utc).isoformat()

    # Build result
    result = {
        "status": "ok",
        "url": norm_url,
        "baseline_id": baseline["id"],
        "baseline_timestamp": baseline["timestamp"],
        "comparison_timestamp": now,
        "summary": {
            "total_rules": len(findings),
            "triggered": len(triggered),
            "critical": critical_count,
            "warning": warning_count,
            "info": info_count,
        },
        "triggered_findings": triggered,
        "untriggered_findings": untriggered,
        "current_status_code": page_data["status_code"],
        "cwv_compared": current_cwv is not None,
    }

    # Store comparison in database
    try:
        conn.execute(
            """
            INSERT INTO comparisons (
                url, url_hash, baseline_id, timestamp, results_json,
                critical_count, warning_count, info_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                norm_url,
                uhash,
                baseline["id"],
                now,
                json.dumps(result),
                critical_count,
                warning_count,
                info_count,
            ),
        )
        conn.commit()
    except sqlite3.Error as e:
        # Non-fatal: comparison still succeeds even if we can't persist it
        result["db_warning"] = f"Could not save comparison: {e}"
    finally:
        conn.close()

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compare current page state to stored SEO baseline"
    )
    parser.add_argument("url", help="URL to compare against its baseline")
    parser.add_argument(
        "--skip-cwv",
        action="store_true",
        help="Skip Core Web Vitals comparison (faster, uses less API quota)",
    )
    parser.add_argument(
        "--baseline-id",
        type=int,
        default=None,
        help="Compare against a specific baseline ID (default: most recent)",
    )

    args = parser.parse_args()
    result = run_comparison(args.url, skip_cwv=args.skip_cwv, baseline_id=args.baseline_id)

    print(json.dumps(result, indent=2))

    if result.get("error"):
        sys.exit(1)

    # Also print a human-readable summary to stderr
    summary = result.get("summary", {})
    critical = summary.get("critical", 0)
    warning = summary.get("warning", 0)
    info = summary.get("info", 0)

    if critical > 0:
        print(f"\n*** {critical} CRITICAL finding(s) ***", file=sys.stderr)
    if warning > 0:
        print(f"    {warning} WARNING finding(s)", file=sys.stderr)
    if info > 0:
        print(f"    {info} INFO finding(s)", file=sys.stderr)
    if critical == 0 and warning == 0 and info == 0:
        print("\n    No drift detected. Page matches baseline.", file=sys.stderr)


if __name__ == "__main__":
    main()
