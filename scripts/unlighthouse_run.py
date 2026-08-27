#!/usr/bin/env python3
"""
Thin wrapper around the Unlighthouse CLI (https://unlighthouse.dev).

Unlighthouse is an MIT-licensed OSS Lighthouse runner that crawls an
entire site and outputs a single aggregate report. It's the closest
free-tier equivalent to running PageSpeed against every URL on a site
and aggregating the results — a workflow PSI's API quota does not
support without a paid Google Cloud bill.

This wrapper:
  - Validates the target via url_safety before any subprocess starts.
  - Invokes ``npx --yes unlighthouse@0.13.5 …`` with sensible
    defaults (mobile form factor, 8 parallel workers, JSON output).
  - Captures the JSON summary the CLI writes and returns it parsed
    so claude-seo agents can ingest the result without re-running
    Lighthouse.

Prerequisites
=============
Node.js 18+ available on ``$PATH``. The first run downloads
unlighthouse; subsequent runs use the npx cache.

Usage::

    python scripts/unlighthouse_run.py https://example.com
    python scripts/unlighthouse_run.py https://example.com --json
    python scripts/unlighthouse_run.py https://example.com --device desktop --max-routes 50
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from url_safety import URLSafetyError, validate_url_strict  # noqa: E402

UNLIGHTHOUSE_PIN = "unlighthouse@0.13.5"


def _check_node() -> str | None:
    """Return None if Node is OK, else an error message."""
    npx = shutil.which("npx")
    if not npx:
        return ("npx not found on PATH. Install Node.js 18+ "
                "(https://nodejs.org) and re-run.")
    return None


def run(
    target: str,
    *,
    device: str = "mobile",
    max_routes: int | None = 200,
    output_dir: str | None = None,
    timeout: int = 600,
) -> dict:
    try:
        target, _ = validate_url_strict(target)
    except URLSafetyError as exc:
        return {"ok": False, "error": f"url_safety: {exc}"}

    node_err = _check_node()
    if node_err:
        return {"ok": False, "error": node_err}

    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(
        prefix="claude-seo-unlighthouse-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "npx", "--yes", "--package", UNLIGHTHOUSE_PIN, "unlighthouse-ci",
        "--site", target,
        "--device", device,
        "--output-path", str(out_dir),
        # Reasonable defaults for a one-shot audit; callers can override.
        "--build-static-files",
    ]
    if max_routes is not None:
        cmd.extend(["--scanner", json.dumps({"maxRoutes": max_routes})])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"unlighthouse timed out after {timeout}s",
                "output_dir": str(out_dir)}
    except FileNotFoundError as exc:
        return {"ok": False, "error": f"npx invocation failed: {exc}"}

    summary_path = out_dir / "ci-result.json"
    summary: dict = {}
    if summary_path.is_file():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"ci-result.json invalid JSON: {exc}",
                    "output_dir": str(out_dir)}

    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "target": target,
        "output_dir": str(out_dir),
        "summary": summary,
        "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Unlighthouse (multi-page Lighthouse) on a site."
    )
    parser.add_argument("target", help="Site URL to crawl (https://example.com).")
    parser.add_argument(
        "--device", choices=("mobile", "desktop"), default="mobile",
    )
    parser.add_argument(
        "--max-routes", type=int, default=200,
        help="Cap the crawl at N URLs (default 200).",
    )
    parser.add_argument(
        "--output-dir", help="Directory for the HTML/JSON report (default temp).",
    )
    parser.add_argument(
        "--timeout", type=int, default=600,
        help="Subprocess timeout in seconds (default 600).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run(
        args.target,
        device=args.device,
        max_routes=args.max_routes,
        output_dir=args.output_dir,
        timeout=args.timeout,
    )

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        status = "OK" if result["ok"] else "FAIL"
        print(f"Unlighthouse: {status}")
        print(f"  Target:     {result.get('target', args.target)}")
        print(f"  Output dir: {result.get('output_dir')}")
        if result.get("error"):
            print(f"  Error:      {result['error']}")
        elif result.get("summary"):
            scores = result["summary"].get("scores") or result["summary"].get("score") or {}
            if scores:
                for k, v in scores.items():
                    print(f"  {k:14s} {v}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
