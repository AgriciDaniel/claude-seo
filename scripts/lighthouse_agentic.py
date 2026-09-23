#!/usr/bin/env python3
"""
Lighthouse Agentic Browsing category reader.

Runs the ``agentic-browsing`` category through the PageSpeed Insights v5 API
(or reads a saved Lighthouse / PSI JSON file) and explains the result the way
the Lighthouse report renderer computes it.

The category uses ``categoryScoreDisplayMode: "fraction"``: the report shows
"X of N passed", not a 0-100 score. The fraction below reproduces
``ReportUtils.calculateCategoryFraction`` from Lighthouse 13.5.0
(report/renderer/report-utils.js):

- ``notApplicable``, ``manual`` and hidden-group audits are skipped.
- ``informative`` audits are never counted; a failing one only raises
  ``numInformative``.
- Every other audit (``binary``, ``numeric``, ``error``) counts toward N and
  passes when its score is at least 0.9.

Category audits in Lighthouse 13.5.0 (core/config/default-config.js):
``agent-accessibility-tree``, ``webmcp-form-coverage``,
``webmcp-registered-tools``, ``webmcp-schema-validity``,
``cumulative-layout-shift``, ``llms-txt``, ``ard-schema``. The script never
assumes that list: it reads ``auditRefs`` from the result, so a renamed or new
audit is reported rather than dropped.

Source-verified behaviour the explanations rely on (Lighthouse 13.5.0):

- ``webmcp-form-coverage`` is informative while any form lacks both
  ``toolname`` and ``tooldescription``, and becomes a counted binary pass once
  every form has one of them. It is N/A with no forms or no WebMCP support.
- ``webmcp-registered-tools`` is always informative (never counted).
- ``webmcp-schema-validity`` is N/A without WebMCP support, or when no tools
  and no schema issues exist.
- ``llms-txt`` is N/A on a 4xx, fails on a 5xx or fetch error, and otherwise
  needs an H1, at least one Markdown link, and 50 or more characters.
- ``ard-schema`` is N/A unless an ``ai-catalog.json`` is signalled
  (robots.txt ``Agentmap:``, ``<link rel="ai-catalog">``, an HTTP ``Link``
  header) or ``/.well-known/ai-catalog.json`` answers 200.

CLI
===
    python lighthouse_agentic.py https://example.com --json
    python lighthouse_agentic.py https://example.com --strategy both --json
    python lighthouse_agentic.py --from-json lighthouse-report.json --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

CATEGORY_ID = "agentic-browsing"
PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
PASS_MIN_SCORE = 0.9  # RATINGS.PASS.minScore in the Lighthouse report renderer
VERIFIED_LIGHTHOUSE = "13.5.0"

AUDIT_NOTES = {
    "agent-accessibility-tree": (
        "Binary. Fails when any of 33 axe rules fails (names and labels, ARIA "
        "validity, tree structure, tabindex, autocomplete). Fix the listed rules."
    ),
    "webmcp-form-coverage": (
        "Informative while any form lacks both toolname and tooldescription; "
        "counts as a binary pass once every form has one. N/A with no forms or "
        "no WebMCP support in the testing browser."
    ),
    "webmcp-registered-tools": (
        "Always informative. Lists declarative and imperative tools seen during "
        "the page load. Never changes the fraction."
    ),
    "webmcp-schema-validity": (
        "Scores 0 on errors (missing tool name or description, a required "
        "parameter without a name) and 0.5 on warnings, so both count as a "
        "failure. N/A when no tools and no issues exist."
    ),
    "cumulative-layout-shift": (
        "Numeric lab CLS. Passes at score 0.9 or higher (about CLS 0.1 or less)."
    ),
    "llms-txt": (
        "Binary. /llms.txt needs an H1, one Markdown link, and 50+ characters. "
        "A 4xx makes it N/A; a 5xx or fetch error fails it."
    ),
    "ard-schema": (
        "Validates ai-catalog.json (Agentic Resource Discovery). N/A unless a "
        "catalog is signalled or /.well-known/ai-catalog.json returns 200."
    ),
}


def classify_audit(audit_ref: dict, audit: dict) -> str:
    """Return how one auditRef contributes to the fraction.

    One of ``pass``, ``fail`` (both counted), ``informative`` (never
    counted, whatever it lists), ``not-applicable``, ``manual``, ``hidden``,
    ``missing``.
    """
    if not audit:
        return "missing"
    mode = audit.get("scoreDisplayMode")
    if audit_ref.get("group") == "hidden":
        return "hidden"
    if mode == "manual":
        return "manual"
    if mode == "notApplicable":
        return "not-applicable"
    if mode == "informative":
        # showAsPassed() returns False for every informative audit, so the
        # renderer counts each one in numInformative regardless of score.
        return "informative"
    score = audit.get("score")
    if mode == "error" or score is None:
        return "fail"
    try:
        return "pass" if float(score) >= PASS_MIN_SCORE else "fail"
    except (TypeError, ValueError):
        return "fail"


def calculate_fraction(lhr: dict) -> dict:
    """Reproduce ReportUtils.calculateCategoryFraction for agentic-browsing."""
    category = (lhr.get("categories") or {}).get(CATEGORY_ID)
    if not category:
        return {"available": False}
    audits = lhr.get("audits") or {}
    num_passed = num_passable = num_informative = 0
    for ref in category.get("auditRefs", []):
        audit = audits.get(ref.get("id"), {})
        mode = audit.get("scoreDisplayMode")
        if ref.get("group") == "hidden" or mode in ("manual", "notApplicable") or not audit:
            continue
        if mode == "informative":
            num_informative += 1
            continue
        num_passable += 1
        if classify_audit(ref, audit) == "pass":
            num_passed += 1
    return {
        "available": True,
        "passed": num_passed,
        "counted": num_passable,
        "informative": num_informative,
        "display": f"{num_passed}/{num_passable}",
        "category_score": category.get("score"),
    }


def _failed_axe_rules(audit: dict) -> list:
    rules = []
    for section in (audit.get("details") or {}).get("items", []):
        value = section.get("value") if isinstance(section, dict) else None
        for item in (value or {}).get("items", []) if isinstance(value, dict) else []:
            node = item.get("node") or {}
            rules.append({
                "rule": item.get("description", ""),
                "selector": node.get("selector", ""),
                "snippet": (node.get("snippet") or "")[:200],
            })
    return rules


def _registered_tools(audit: dict) -> list:
    tools = []
    for section in (audit.get("details") or {}).get("items", []):
        if not isinstance(section, dict):
            continue
        kind = "imperative" if "Imperative" in str(section.get("title", "")) else "declarative"
        value = section.get("value")
        for item in value.get("items", []) if isinstance(value, dict) else []:
            tools.append({
                "name": item.get("tool"),
                "kind": kind,
                "description": item.get("description"),
            })
    return tools


def _table_rows(audit: dict, keys: tuple) -> list:
    rows = []
    for item in (audit.get("details") or {}).get("items", []):
        if not isinstance(item, dict):
            continue
        row = {}
        for key in keys:
            val = item.get(key)
            if isinstance(val, dict):
                val = val.get("selector") or val.get("snippet") or val.get("nodeLabel")
            if val is not None:
                row[key] = val
        if row:
            rows.append(row)
    return rows


def explain(lhr: dict) -> dict:
    """Build a per-audit explanation plus the paths that change the fraction."""
    category = (lhr.get("categories") or {}).get(CATEGORY_ID) or {}
    audits = lhr.get("audits") or {}
    rows = []
    for ref in category.get("auditRefs", []):
        audit_id = ref.get("id")
        audit = audits.get(audit_id, {})
        status = classify_audit(ref, audit)
        row = {
            "id": audit_id,
            "group": ref.get("group"),
            "title": audit.get("title"),
            "mode": audit.get("scoreDisplayMode"),
            "score": audit.get("score"),
            "status": status,
            "counted": status in ("pass", "fail"),
            "display_value": audit.get("displayValue"),
            "explanation": audit.get("explanation"),
            "note": AUDIT_NOTES.get(audit_id, "Audit not documented for "
                                    f"Lighthouse {VERIFIED_LIGHTHOUSE}; read its description."),
        }
        if audit_id == "agent-accessibility-tree":
            row["failed_rules"] = _failed_axe_rules(audit)
        elif audit_id == "webmcp-registered-tools":
            row["tools"] = _registered_tools(audit)
        elif audit_id == "webmcp-form-coverage":
            row["forms_missing_annotations"] = _table_rows(audit, ("node",))
        elif audit_id in ("webmcp-schema-validity", "ard-schema"):
            row["issues"] = _table_rows(audit, ("element", "issue", "severity"))
        elif audit_id == "llms-txt":
            row["issues"] = _table_rows(audit, ("message",))
        rows.append(row)
    return {"audits": rows, "paths": denominator_paths(rows)}


def denominator_paths(rows: list) -> list:
    """Describe what would add a counted audit or turn a failure into a pass."""
    by_id = {r["id"]: r for r in rows}
    paths = []
    for row in rows:
        if row["status"] == "fail":
            paths.append({"audit": row["id"], "change": "fail -> pass",
                          "how": row["note"]})
    form = by_id.get("webmcp-form-coverage")
    if form and form["status"] == "informative":
        paths.append({
            "audit": "webmcp-form-coverage",
            "change": "adds one counted audit",
            "how": "Give every <form> a toolname or tooldescription attribute. "
                   "Only annotate forms whose submission is safe for an agent to "
                   "trigger; this is a Chrome-only declarative API in origin trial. "
                   "Annotated forms become tools, so webmcp-schema-validity may start "
                   "counting too, and it fails if any parameter lacks a description.",
        })
    ard = by_id.get("ard-schema")
    if ard and ard["status"] == "not-applicable":
        paths.append({
            "audit": "ard-schema",
            "change": "adds one counted audit",
            "how": "Publish a valid /.well-known/ai-catalog.json only if you have "
                   "agent resources to list (MCP server, A2A agent, skills). An "
                   "invalid catalog adds a counted failure instead.",
        })
    llms = by_id.get("llms-txt")
    if llms and llms["status"] == "not-applicable":
        paths.append({
            "audit": "llms-txt",
            "change": "adds one counted audit",
            "how": "Serve /llms.txt with an H1, a summary, and Markdown links.",
        })
    return paths


def summarize(lhr: dict, source: str) -> dict:
    """Return the full structured report for one Lighthouse result."""
    fraction = calculate_fraction(lhr)
    result = {
        "source": source,
        "requested_url": lhr.get("requestedUrl"),
        "final_url": lhr.get("finalDisplayedUrl") or lhr.get("finalUrl"),
        "lighthouse_version": lhr.get("lighthouseVersion"),
        "fetch_time": lhr.get("fetchTime"),
        "form_factor": (lhr.get("configSettings") or {}).get("formFactor"),
        "host_user_agent": (lhr.get("environment") or {}).get("hostUserAgent"),
        "fraction": fraction,
        "error": None,
    }
    if not fraction.get("available"):
        result["error"] = ("No agentic-browsing category in this result. Lighthouse "
                           "13.2+ is required; rerun with the category enabled.")
        return result
    result.update(explain(lhr))
    version = str(lhr.get("lighthouseVersion") or "")
    if version and version != VERIFIED_LIGHTHOUSE:
        result["version_note"] = (
            f"Audit notes were verified against Lighthouse {VERIFIED_LIGHTHOUSE}; "
            f"this result is {version}. The fraction is still read from auditRefs.")
    return result


def extract_lhr(data: dict) -> dict:
    """Accept either a raw Lighthouse result or a PSI v5 response.

    Anything malformed (a null lighthouseResult, non-object audits) is reduced
    to what can be read, so callers report "no category" instead of crashing.
    """
    lhr = data.get("lighthouseResult", data) if isinstance(data, dict) else {}
    if not isinstance(lhr, dict):
        return {}
    audits = lhr.get("audits")
    categories = lhr.get("categories")
    clean_categories = {}
    for cid, cat in (categories or {}).items() if isinstance(categories, dict) else []:
        if not isinstance(cat, dict):
            continue
        refs = cat.get("auditRefs")
        clean_categories[cid] = {**cat, "auditRefs": [
            r for r in refs if isinstance(r, dict) and isinstance(r.get("id"), str)]
            if isinstance(refs, list) else []}
    return {**lhr,
            "audits": {k: v for k, v in (audits or {}).items() if isinstance(v, dict)}
            if isinstance(audits, dict) else {},
            "categories": clean_categories}


def run_psi(url: str, strategy: str, api_key: Optional[str], timeout: int = 180) -> dict:
    """Run the agentic-browsing category through PSI v5 and return the LHR."""
    import requests
    from google_auth import google_api_key_headers, redact_google_api_key, validate_url

    if not validate_url(url):
        raise ValueError("Invalid URL. Only http/https URLs to public hosts are accepted.")
    params = {"url": url, "strategy": strategy.upper(), "category": "AGENTIC_BROWSING"}
    headers = google_api_key_headers(api_key) if api_key else None
    try:
        resp = requests.get(PSI_ENDPOINT, params=params, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(redact_google_api_key(f"PSI request failed: {exc}")) from None
    if resp.status_code != 200:
        try:
            body = resp.json()
            error = body.get("error") if isinstance(body, dict) else None
            message = error.get("message", "") if isinstance(error, dict) else str(body)[:300]
        except (ValueError, RecursionError):
            message = resp.text[:300]
        hint = ""
        if resp.status_code == 429 or "Quota" in message:
            hint = " Configure a Google API key (see /seo google setup)."
        raise RuntimeError(redact_google_api_key(
            f"PSI returned HTTP {resp.status_code}: {message[:300]}{hint}"))
    try:
        data = resp.json()
    except (ValueError, RecursionError):
        raise RuntimeError("PSI returned a body that is not usable JSON.") from None
    return extract_lhr(data)


def _print_text(report: dict) -> None:
    print(f"URL: {report.get('final_url') or report.get('requested_url')}")
    print(f"Lighthouse {report.get('lighthouse_version')} "
          f"({report.get('form_factor') or report.get('source')})")
    if report.get("error"):
        print(f"Error: {report['error']}")
        return
    frac = report["fraction"]
    print(f"Agentic Browsing: {frac['display']} passed "
          f"({frac['informative']} informative, not counted)")
    for row in report.get("audits", []):
        print(f"  [{row['status']:>19}] {row['id']}: {row.get('display_value') or ''}")
    if report.get("paths"):
        print("What changes the fraction:")
        for path in report["paths"]:
            print(f"  - {path['audit']} ({path['change']}): {path['how']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lighthouse Agentic Browsing reader")
    parser.add_argument("url", nargs="?", help="URL to test through PSI")
    parser.add_argument("--from-json", help="Read a saved Lighthouse or PSI JSON file instead")
    parser.add_argument("--strategy", choices=["mobile", "desktop", "both"], default="mobile")
    parser.add_argument("--api-key", help="Google API key (overrides config/env)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not args.url and not args.from_json:
        parser.error("give a URL or --from-json")

    reports = []
    if args.from_json:
        try:
            with open(args.from_json, encoding="utf-8-sig") as fh:  # PowerShell writes a BOM
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            parser.exit(1, f"Could not read {args.from_json}: {exc}\n")
        if not isinstance(data, dict):
            parser.exit(1, f"{args.from_json} is not a Lighthouse or PSI JSON object\n")
        reports.append(summarize(extract_lhr(data), "file"))
    else:
        from google_auth import get_api_key
        api_key = args.api_key or get_api_key()
        strategies = ["mobile", "desktop"] if args.strategy == "both" else [args.strategy]
        for strategy in strategies:
            try:
                reports.append(summarize(run_psi(args.url, strategy, api_key), f"psi-{strategy}"))
            except (RuntimeError, ValueError) as exc:
                reports.append({"source": f"psi-{strategy}", "requested_url": args.url,
                                "error": str(exc)})

    output = reports[0] if len(reports) == 1 else {"results": reports}
    if args.json:
        print(json.dumps(output, indent=2))
    else:
        for report in reports:
            _print_text(report)
            print()
    sys.exit(1 if all(r.get("error") for r in reports) else 0)


if __name__ == "__main__":
    main()
