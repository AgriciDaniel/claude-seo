#!/usr/bin/env python3
"""
GBP feature-deprecation linter.

Google sunset two long-running Google Business Profile features:

  - **GBP chat + call history**: fully wound down 2024-07-31. Any page
    that still surfaces a "Message us via Google" CTA or wires up a
    GBP-chat widget is broken.
  - **`*.business.site` GBP websites**: legacy-risk references that need
    manual verification before treating them as inactive.

This script scans HTML for both patterns and emits a structured report
so the seo-local audit can include "remove deprecated GBP references"
with the severity provided by each finding.

Usage::

    python scripts/gbp_deprecation_lint.py https://example.com
    python scripts/gbp_deprecation_lint.py page.html --file
    python scripts/gbp_deprecation_lint.py https://example.com --json

Exit code 0 if no deprecated patterns found, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from url_safety import URLSafetyError, safe_requests_get  # noqa: E402


# Patterns for retired GBP chat. The "Message" / "Chat" CTAs alone are
# common on commercial sites — we only flag when they appear NEAR a
# Google-business-related signal in the same DOM neighbourhood.
_GBP_CHAT_CTAS = re.compile(
    r"\bmessage\s+us\s+(?:on|via|through)\s+google\b"
    r"|\bchat\s+(?:on|via|with)\s+google\s+(?:business|maps)\b"
    r"|\bgoogle\s+business\s+chat\b"
    r"|\bgoogle[-\s]?business[-\s]?messages?\b",
    re.IGNORECASE,
)


# Deprecated GBP-hosted websites: business.site, .business.google.com.
# Both patterns match anywhere in HTML (links, citations, schema sameAs).
_BUSINESS_SITE_URL = re.compile(
    r"https?://[^/\s\"']+\.business\.site(?:/[^\s\"']*)?",
    re.IGNORECASE,
)


def scan(html: str) -> dict:
    """Find every deprecated GBP feature reference in the HTML."""
    chat_matches = sorted(set(_GBP_CHAT_CTAS.findall(html)))
    business_site_matches = sorted(set(_BUSINESS_SITE_URL.findall(html)))

    findings: list[dict] = []
    for hit in chat_matches:
        findings.append({
            "severity": "Critical",
            "feature": "gbp-chat",
            "match": hit[:200],
            "message": "GBP chat / call-history features were fully sunset "
                       "2024-07-31. The CTA does nothing and breaks user "
                       "trust. Remove or replace with a working channel "
                       "(phone, web form, SMS, etc.).",
        })
    for url in business_site_matches:
        findings.append({
            "severity": "Medium",
            "feature": "business-site-url",
            "match": url,
            "message": "Legacy *.business.site URL found. Google shutdown "
                       "status was not confirmed from a live Google page in "
                       "this run; manually verify whether the URL resolves "
                       "and update to your actual site URL if inactive.",
        })

    return {
        "ok": not findings,
        "findings": findings,
        "summary": {
            "critical": sum(1 for f in findings if f["severity"] == "Critical"),
            "high":     sum(1 for f in findings if f["severity"] == "High"),
            "medium":   sum(1 for f in findings if f["severity"] == "Medium"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GBP deprecation linter (chat + business.site)."
    )
    parser.add_argument("source", help="URL, or file path with --file.")
    parser.add_argument("--file", action="store_true",
                        help="Treat source as a local file path, not a URL.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.file:
        html = Path(args.source).read_text(encoding="utf-8", errors="replace")
    else:
        try:
            resp = safe_requests_get(args.source, timeout=20)
            html = resp.text
        except URLSafetyError as exc:
            print(f"Error: url_safety: {exc}", file=sys.stderr)
            return 2

    result = scan(html)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        status = "PASS" if result["ok"] else "FAIL"
        s = result["summary"]
        print(f"GBP deprecation lint: {status} "
              f"({s['critical']} critical, {s['high']} high, {s['medium']} medium)")
        for f in result["findings"]:
            print(f"  [{f['severity']:<8}] {f['feature']}: {f['match']!r}")
            print(f"           {f['message']}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
