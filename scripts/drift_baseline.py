#!/usr/bin/env python3
"""
Capture an SEO baseline snapshot of a page's critical elements.

Stores title, meta tags, canonical, headings, schema/JSON-LD, OG tags,
and Core Web Vitals as a "known good" state in SQLite.

Usage:
    python drift_baseline.py <url> [--skip-cwv]

Output: JSON with baseline ID, timestamp, and captured elements.
Storage: ~/.cache/claude-seo/drift/baselines.db
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse, urlunparse, urlencode

# ---------------------------------------------------------------------------
# Path setup — resolve scripts/ directory relative to this file
# ---------------------------------------------------------------------------
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from google_auth import validate_url  # noqa: E402

DB_DIR = os.path.expanduser("~/.cache/claude-seo/drift")
DB_PATH = os.path.join(DB_DIR, "baselines.db")

# UTM parameters to strip during URL normalization
UTM_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """
    Normalize a URL for consistent baseline matching.

    - Lowercase scheme and host
    - Strip default ports (80 for http, 443 for https)
    - Sort query parameters
    - Remove UTM parameters
    - Strip trailing slash (except bare domain)
    """
    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()

    # Strip default ports
    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    netloc = hostname
    if port:
        netloc = f"{hostname}:{port}"

    # Sort query params and strip UTM
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in sorted(query_params.items()) if k not in UTM_PARAMS}
    query = urlencode(filtered, doseq=True)

    # Strip trailing slash (but keep "/" for bare domain)
    path = parsed.path.rstrip("/") or "/"

    return urlunparse((scheme, netloc, path, "", query, ""))


def url_hash(url: str) -> str:
    """SHA-256 hash of normalized URL, truncated to 16 hex chars."""
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    """Initialize the SQLite database and return a connection."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            url_hash TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            title TEXT,
            meta_description TEXT,
            canonical TEXT,
            robots TEXT,
            h1 TEXT,
            h2_json TEXT,
            h3_json TEXT,
            schema_json TEXT,
            og_json TEXT,
            cwv_json TEXT,
            html_hash TEXT,
            schema_hash TEXT,
            status_code INTEGER
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_url_hash ON baselines(url_hash)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            url_hash TEXT NOT NULL,
            baseline_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            results_json TEXT NOT NULL,
            critical_count INTEGER DEFAULT 0,
            warning_count INTEGER DEFAULT 0,
            info_count INTEGER DEFAULT 0,
            FOREIGN KEY (baseline_id) REFERENCES baselines(id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_comp_url_hash ON comparisons(url_hash)
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Page fetching via existing scripts (SSRF-protected)
# ---------------------------------------------------------------------------

def fetch_page_data(url: str) -> dict:
    """
    Fetch and parse a page using the project's existing scripts.

    Returns dict with keys: status_code, html, parsed, error
    """
    result = {"status_code": None, "html": None, "parsed": None, "error": None}

    # Step 1: Fetch the page via fetch_page.py
    fetch_script = os.path.join(SCRIPTS_DIR, "fetch_page.py")
    try:
        proc = subprocess.run(
            [sys.executable, fetch_script, url, "--output", "/dev/stdout"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        result["error"] = "Page fetch timed out after 60 seconds"
        return result

    if proc.returncode != 0:
        error_msg = proc.stderr.strip() if proc.stderr else "Unknown fetch error"
        result["error"] = f"Fetch failed: {error_msg}"
        return result

    html_content = proc.stdout

    # Extract status code from stderr output (fetch_page.py prints "Status: NNN")
    status_match = re.search(r"Status:\s*(\d+)", proc.stderr or "")
    result["status_code"] = int(status_match.group(1)) if status_match else 200
    result["html"] = html_content

    # Step 2: Parse the HTML via parse_html.py
    parse_script = os.path.join(SCRIPTS_DIR, "parse_html.py")
    try:
        proc = subprocess.run(
            [sys.executable, parse_script, "--url", url, "--json"],
            input=html_content,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        result["error"] = "HTML parsing timed out after 30 seconds"
        return result

    if proc.returncode != 0:
        error_msg = proc.stderr.strip() if proc.stderr else "Unknown parse error"
        result["error"] = f"Parse failed: {error_msg}"
        return result

    try:
        result["parsed"] = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        result["error"] = f"Failed to parse JSON output: {e}"

    return result


def fetch_cwv_data(url: str) -> dict | None:
    """
    Fetch Core Web Vitals via pagespeed_check.py.

    Returns CWV dict or None on failure.
    """
    psi_script = os.path.join(SCRIPTS_DIR, "pagespeed_check.py")
    try:
        proc = subprocess.run(
            [sys.executable, psi_script, url, "--psi-only", "--strategy", "mobile", "--json"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return None

    if proc.returncode != 0:
        return None

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None

    # Extract the key metrics
    psi = data.get("psi", {}).get("mobile", {})
    if psi.get("error"):
        return None

    cwv = {
        "performance_score": psi.get("lighthouse_scores", {}).get("performance"),
        "lab_metrics": psi.get("lab_metrics", {}),
        "field_metrics": psi.get("field_metrics", {}),
    }
    return cwv


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_content(content: str) -> str:
    """SHA-256 hash of content string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Main baseline capture
# ---------------------------------------------------------------------------

def capture_baseline(url: str, skip_cwv: bool = False) -> dict:
    """
    Capture a full SEO baseline for a URL.

    Args:
        url: The URL to baseline.
        skip_cwv: If True, skip Core Web Vitals fetch.

    Returns:
        Dict with baseline data or error.
    """
    # Validate URL (SSRF protection)
    if not validate_url(url):
        return {"error": "URL rejected: only public http/https URLs are accepted (SSRF protection)"}

    # Fetch and parse the page
    page_data = fetch_page_data(url)
    if page_data["error"]:
        return {"error": page_data["error"]}

    parsed = page_data["parsed"]
    if not parsed:
        return {"error": "No parsed data returned from HTML parser"}

    # Fetch CWV (optional)
    cwv_data = None
    if not skip_cwv:
        cwv_data = fetch_cwv_data(url)

    # Compute hashes
    html_content_hash = hash_content(page_data["html"]) if page_data["html"] else None
    schema_content = json.dumps(parsed.get("schema", []), sort_keys=True)
    schema_content_hash = hash_content(schema_content) if parsed.get("schema") else None

    # Prepare baseline record
    now = datetime.now(timezone.utc).isoformat()
    norm_url = normalize_url(url)
    uhash = url_hash(url)

    h1_list = parsed.get("h1", [])
    h1_text = h1_list[0] if h1_list else None

    baseline = {
        "url": norm_url,
        "url_hash": uhash,
        "timestamp": now,
        "title": parsed.get("title"),
        "meta_description": parsed.get("meta_description"),
        "canonical": parsed.get("canonical"),
        "robots": parsed.get("meta_robots"),
        "h1": h1_text,
        "h2_json": json.dumps(parsed.get("h2", [])),
        "h3_json": json.dumps(parsed.get("h3", [])),
        "schema_json": json.dumps(parsed.get("schema", [])),
        "og_json": json.dumps(parsed.get("open_graph", {})),
        "cwv_json": json.dumps(cwv_data) if cwv_data else None,
        "html_hash": html_content_hash,
        "schema_hash": schema_content_hash,
        "status_code": page_data["status_code"],
    }

    # Store in SQLite
    conn = init_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO baselines (
                url, url_hash, timestamp, title, meta_description, canonical,
                robots, h1, h2_json, h3_json, schema_json, og_json, cwv_json,
                html_hash, schema_hash, status_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                baseline["url"],
                baseline["url_hash"],
                baseline["timestamp"],
                baseline["title"],
                baseline["meta_description"],
                baseline["canonical"],
                baseline["robots"],
                baseline["h1"],
                baseline["h2_json"],
                baseline["h3_json"],
                baseline["schema_json"],
                baseline["og_json"],
                baseline["cwv_json"],
                baseline["html_hash"],
                baseline["schema_hash"],
                baseline["status_code"],
            ),
        )
        conn.commit()
        baseline_id = cursor.lastrowid
    finally:
        conn.close()

    # Build summary output
    h2_count = len(parsed.get("h2", []))
    h3_count = len(parsed.get("h3", []))
    schema_count = len(parsed.get("schema", []))
    og_count = len(parsed.get("open_graph", {}))

    output = {
        "status": "ok",
        "baseline_id": baseline_id,
        "url": norm_url,
        "timestamp": now,
        "summary": {
            "title": baseline["title"],
            "meta_description": (
                baseline["meta_description"][:80] + "..."
                if baseline["meta_description"] and len(baseline["meta_description"]) > 80
                else baseline["meta_description"]
            ),
            "canonical": baseline["canonical"],
            "robots": baseline["robots"],
            "h1": baseline["h1"],
            "h2_count": h2_count,
            "h3_count": h3_count,
            "schema_count": schema_count,
            "og_tag_count": og_count,
            "cwv_captured": cwv_data is not None,
            "status_code": baseline["status_code"],
            "html_hash": html_content_hash[:12] + "..." if html_content_hash else None,
        },
    }

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Capture an SEO baseline snapshot for drift monitoring"
    )
    parser.add_argument("url", help="URL to baseline")
    parser.add_argument(
        "--skip-cwv",
        action="store_true",
        help="Skip Core Web Vitals fetch (faster, uses less API quota)",
    )

    args = parser.parse_args()
    result = capture_baseline(args.url, skip_cwv=args.skip_cwv)

    print(json.dumps(result, indent=2))

    if result.get("error"):
        sys.exit(1)


if __name__ == "__main__":
    main()
