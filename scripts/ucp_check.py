#!/usr/bin/env python3
"""
UCP (Universal Commerce Protocol) profile auditor.

Fetches a site's ``/.well-known/ucp`` document, validates its structure
against the early UCP spec (Google + Shopify + Etsy + Walmart + payment
partners), enumerates declared capabilities, and probes each declared
endpoint for reachability. Output is JSON.

Audit posture
=============
Per ``skills/seo-ecommerce/references/ucp-universal-commerce-protocol.md``,
UCP adoption is early. Missing profiles are reported as
**opportunities**, not failures. The scanner exists so claude-seo
audits can surface forward-looking ecommerce signals without making
them a hard scoring gate.

SSRF
====
Both the discovery fetch and every endpoint probe go through
``url_safety.safe_requests_get`` / ``url_safety.validate_url_strict``.
Capability endpoints declared as private-IP, loopback, or metadata-IP
URLs are rejected at validation time and reported as ``ssrf-blocked``.

CLI
===
    python ucp_check.py https://store.example.com
    python ucp_check.py https://store.example.com --json
    python ucp_check.py https://store.example.com --probe-endpoints
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import urljoin, urlparse

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from url_safety import (  # noqa: E402
    URLSafetyError,
    safe_requests_get,
    validate_url_strict,
)

KNOWN_CAPABILITIES = {
    "dev.ucp.shopping.checkout": "Initiate checkout, return totals + payment intent",
    "dev.ucp.shopping.fulfillment": "Quote shipping options + delivery windows",
    "dev.ucp.shopping.discount": "Apply promo codes / loyalty discounts",
    "dev.ucp.shopping.cart": "Add / remove / update items in agent-managed carts",
    "dev.ucp.shopping.catalog": "Search / list products via agent queries",
    "dev.ucp.shopping.order": "Order status, lookup, history",
    "dev.ucp.shopping.returns": "Return initiation + status",
}


def discovery_url_for(site: str) -> str:
    """Return the canonical UCP discovery URL for a site root."""
    parsed = urlparse(site)
    if not parsed.scheme:
        site = "https://" + site
        parsed = urlparse(site)
    base = f"{parsed.scheme}://{parsed.netloc}/"
    return urljoin(base, ".well-known/ucp")


def parse_profile(payload: str) -> dict:
    """Parse a UCP profile JSON document and report structural findings."""
    report: dict = {
        "valid_json": False,
        "version": None,
        "capabilities": [],
        "merchant": None,
        "issues": [],
        "unknown_capabilities": [],
    }
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        report["issues"].append(f"invalid-json: {exc.msg} (line {exc.lineno})")
        return report
    if not isinstance(data, dict):
        report["issues"].append("profile-not-object")
        return report
    report["valid_json"] = True

    version = data.get("version")
    if version is None:
        report["issues"].append("missing-version")
    elif not isinstance(version, str):
        report["issues"].append("version-not-string")
    else:
        report["version"] = version

    merchant = data.get("merchant")
    if merchant is None:
        report["issues"].append("missing-merchant")
    elif isinstance(merchant, dict):
        report["merchant"] = {
            "name": merchant.get("name"),
            "id": merchant.get("id"),
        }
        if not merchant.get("name"):
            report["issues"].append("merchant-name-empty")
    else:
        report["issues"].append("merchant-not-object")

    caps = data.get("capabilities")
    if caps is None:
        report["issues"].append("missing-capabilities")
    elif not isinstance(caps, list):
        report["issues"].append("capabilities-not-array")
    else:
        for idx, cap in enumerate(caps):
            if not isinstance(cap, dict):
                report["issues"].append(f"capability-{idx}-not-object")
                continue
            cap_id = cap.get("id")
            cap_version = cap.get("version")
            cap_endpoint = cap.get("endpoint")
            entry = {
                "id": cap_id,
                "version": cap_version,
                "endpoint": cap_endpoint,
                "issues": [],
            }
            if not cap_id:
                entry["issues"].append("missing-id")
            elif cap_id not in KNOWN_CAPABILITIES:
                report["unknown_capabilities"].append(cap_id)
            if not cap_version:
                entry["issues"].append("missing-version")
            if not cap_endpoint:
                entry["issues"].append("missing-endpoint")
            report["capabilities"].append(entry)

    return report


def probe_endpoint(url: str, *, timeout: int = 10) -> dict:
    """HEAD-probe a declared capability endpoint via url_safety."""
    out: dict = {"url": url, "reachable": False, "status_code": None, "error": None}
    try:
        validate_url_strict(url)
    except URLSafetyError as exc:
        out["error"] = f"ssrf-blocked: {exc}"
        return out
    try:
        resp = safe_requests_get(url, timeout=timeout, allow_redirects=True)
        out["status_code"] = resp.status_code
        out["reachable"] = 200 <= resp.status_code < 500
    except Exception as exc:
        out["error"] = str(exc)
    return out


def audit_site(
    site: str,
    *,
    probe_endpoints: bool = False,
    timeout: int = 10,
) -> dict:
    """Fetch and audit a site's UCP profile. Returns a JSON-serializable dict."""
    discovery = discovery_url_for(site)
    report: dict = {
        "site": site,
        "discovery_url": discovery,
        "profile_present": False,
        "status_code": None,
        "parse": None,
        "endpoint_probes": [],
        "summary": "",
    }
    try:
        validate_url_strict(discovery)
    except URLSafetyError as exc:
        report["summary"] = f"discovery-url-blocked-by-url-safety: {exc}"
        return report
    try:
        resp = safe_requests_get(discovery, timeout=timeout, allow_redirects=True)
    except Exception as exc:
        report["summary"] = f"fetch-failed: {exc}"
        return report
    report["status_code"] = resp.status_code
    if resp.status_code == 404:
        report["summary"] = "no-ucp-profile (forward-looking opportunity)"
        return report
    if resp.status_code >= 400:
        report["summary"] = f"http-{resp.status_code} on discovery"
        return report
    report["profile_present"] = True
    parsed = parse_profile(resp.text)
    report["parse"] = parsed

    if probe_endpoints and parsed.get("capabilities"):
        for cap in parsed["capabilities"]:
            endpoint = cap.get("endpoint")
            if endpoint:
                report["endpoint_probes"].append(probe_endpoint(endpoint, timeout=timeout))

    n_caps = len(parsed.get("capabilities") or [])
    n_issues = len(parsed.get("issues") or [])
    report["summary"] = f"profile-found: {n_caps} capabilities, {n_issues} structural issues"
    return report


def _cli() -> None:
    parser = argparse.ArgumentParser(description="UCP profile auditor")
    parser.add_argument("site", help="Site root URL (e.g. https://store.example.com)")
    parser.add_argument(
        "--probe-endpoints",
        action="store_true",
        help="HEAD-probe each declared capability endpoint",
    )
    parser.add_argument(
        "--timeout", type=int, default=10, help="Per-request timeout (seconds)"
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    report = audit_site(
        args.site, probe_endpoints=args.probe_endpoints, timeout=args.timeout
    )
    if args.json:
        print(json.dumps(report, indent=2))
        sys.exit(0 if report.get("profile_present") else 0)

    print(f"Site: {report['site']}")
    print(f"Discovery: {report['discovery_url']}")
    print(f"Status: {report['status_code']}")
    print(f"Summary: {report['summary']}")
    if report.get("parse"):
        parsed = report["parse"]
        print(f"Version: {parsed.get('version')}")
        print(f"Capabilities ({len(parsed.get('capabilities') or [])}):")
        for cap in parsed.get("capabilities") or []:
            print(f"  - {cap.get('id')} (v{cap.get('version')}) -> {cap.get('endpoint')}")
        if parsed.get("issues"):
            print(f"Structural issues: {', '.join(parsed['issues'])}")


if __name__ == "__main__":
    _cli()
