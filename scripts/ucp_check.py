#!/usr/bin/env python3
"""
UCP (Universal Commerce Protocol) profile auditor.

Fetches a site's ``/.well-known/ucp`` business profile, validates it against
the UCP specification (ucp.dev; profile shape verified 2026-09-23 against the
2026-08-25 spec and a live Shopify profile), enumerates declared services and
capabilities, and optionally probes each service endpoint. Output is JSON.

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
Service endpoints declared as private-IP, loopback, or metadata-IP
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
import re
import sys
from urllib.parse import urljoin, urlparse

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from url_safety import (  # noqa: E402
    URLSafetyError,
    decode_response_text,
    safe_requests_get,
    validate_url_strict,
)

KNOWN_CAPABILITIES = {
    "dev.ucp.shopping.checkout": "Initiate checkout, return totals + payment intent",
    "dev.ucp.shopping.fulfillment": "Quote shipping options + delivery windows",
    "dev.ucp.shopping.discount": "Apply promo codes / loyalty discounts",
    "dev.ucp.shopping.cart": "Add / remove / update items in agent-managed carts",
    "dev.ucp.shopping.catalog": "Search / list products via agent queries",
    "dev.ucp.shopping.catalog.search": "Catalog search",
    "dev.ucp.shopping.catalog.lookup": "Catalog lookup by product ID",
    "dev.ucp.common.identity_linking": "Account and identity linking",
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


UCP_TRANSPORTS = {"rest", "mcp", "a2a", "embedded"}
UCP_VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_profile(payload: str) -> dict:
    """Parse a UCP business profile and report structural findings.

    Shape (https://ucp.dev/latest/specification/overview/, verified 2026-09-23):
    everything sits under a root ``ucp`` object with a date ``version``;
    ``services`` and ``capabilities`` are objects keyed by reverse-domain name,
    each holding a list of version variants. A capability variant needs
    ``version``, ``spec`` and ``schema``; a service variant also needs a
    ``transport`` (rest, mcp, a2a or embedded) and usually an ``endpoint``.
    """
    report: dict = {
        "valid_json": False,
        "version": None,
        "supported_versions": [],
        "services": [],
        "capabilities": [],
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

    ucp = data.get("ucp")
    if not isinstance(ucp, dict):
        report["issues"].append("missing-ucp-root")
        if "capabilities" in data or "merchant" in data:
            report["issues"].append(
                "flat-profile: not the UCP spec shape (fields must sit under a root 'ucp' object)")
        return report

    version = ucp.get("version")
    if not isinstance(version, str) or not UCP_VERSION_RE.match(version):
        report["issues"].append("version-missing-or-not-a-date")
    else:
        report["version"] = version
    supported = ucp.get("supported_versions")
    if isinstance(supported, dict):
        report["supported_versions"] = sorted(supported)

    services = ucp.get("services")
    if not isinstance(services, dict) or not services:
        report["issues"].append("missing-services")
    else:
        for name, variants in services.items():
            if not isinstance(variants, list):
                report["issues"].append(f"service-{name}-not-a-list")
                continue
            for variant in variants:
                if not isinstance(variant, dict):
                    report["issues"].append(f"service-{name}-variant-not-object")
                    continue
                entry = {"id": name, "version": variant.get("version"),
                         "transport": variant.get("transport"),
                         "endpoint": variant.get("endpoint"), "issues": []}
                if variant.get("transport") not in UCP_TRANSPORTS:
                    entry["issues"].append("unknown-transport")
                if not variant.get("version"):
                    entry["issues"].append("missing-version")
                if variant.get("transport") in ("rest", "mcp", "a2a") and not variant.get("endpoint"):
                    entry["issues"].append("missing-endpoint")
                report["services"].append(entry)

    caps = ucp.get("capabilities")
    if not isinstance(caps, dict) or not caps:
        report["issues"].append("missing-capabilities")
    else:
        for name, variants in caps.items():
            if name not in KNOWN_CAPABILITIES:
                report["unknown_capabilities"].append(name)
            if not isinstance(variants, list):
                report["issues"].append(f"capability-{name}-not-a-list")
                continue
            for variant in variants:
                if not isinstance(variant, dict):
                    report["issues"].append(f"capability-{name}-variant-not-object")
                    continue
                entry = {"id": name, "version": variant.get("version"),
                         "extends": variant.get("extends"), "issues": []}
                for field in ("version", "spec", "schema"):
                    if not variant.get(field):
                        entry["issues"].append(f"missing-{field}")
                report["capabilities"].append(entry)
    return report


def probe_endpoint(url: str, *, timeout: int = 10) -> dict:
    """GET-probe a declared service endpoint via url_safety (any status below 500 counts as reachable)."""
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
    parsed = parse_profile(decode_response_text(resp))
    report["parse"] = parsed

    if probe_endpoints:
        for endpoint in sorted({svc["endpoint"] for svc in parsed.get("services") or []
                                if svc.get("endpoint")}):
            report["endpoint_probes"].append(probe_endpoint(endpoint, timeout=timeout))

    n_caps = len({cap["id"] for cap in parsed.get("capabilities") or []})
    n_issues = len(parsed.get("issues") or []) + sum(
        len(item["issues"]) for item in (parsed.get("capabilities") or [])
        + (parsed.get("services") or []))
    report["summary"] = (f"profile-found: UCP {parsed.get('version')}, {n_caps} capabilities, "
                         f"{n_issues} structural issues")
    return report


def _cli() -> None:
    parser = argparse.ArgumentParser(description="UCP profile auditor")
    parser.add_argument("site", help="Site root URL (e.g. https://store.example.com)")
    parser.add_argument(
        "--probe-endpoints",
        action="store_true",
        help="Probe each declared service endpoint",
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
        for svc in parsed.get("services") or []:
            print(f"  service {svc.get('id')} (v{svc.get('version')}, {svc.get('transport')}) -> {svc.get('endpoint')}")
        print(f"Capabilities ({len(parsed.get('capabilities') or [])}):")
        for cap in parsed.get("capabilities") or []:
            print(f"  - {cap.get('id')} (v{cap.get('version')})")
        if parsed.get("issues"):
            print(f"Structural issues: {', '.join(parsed['issues'])}")


if __name__ == "__main__":
    _cli()
