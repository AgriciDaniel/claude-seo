#!/usr/bin/env python3
"""
Backlink report validation for Claude SEO.

Programmatically validates backlink analysis data before it is presented to
the user. Catches common false findings, inconsistencies, and misleading
claims that instruction-based checklists might miss.

Usage:
    python validate_backlink_report.py --report report.json --json
    python validate_backlink_report.py --report report.json

Input: JSON file with backlink analysis data containing keys:
  - cc_data: Common Crawl results
  - verify_data: Verification crawler results
  - parsed_data: Homepage parse_html results
  - moz_data: Moz API results (optional)
  - bing_data: Bing Webmaster results (optional)
"""

import argparse
import json
import sys
from typing import Optional


def validate_schema_claims(parsed_data: dict) -> list:
    """Check schema findings for false positives."""
    issues = []
    schemas = parsed_data.get("schema", [])

    for i, s in enumerate(schemas):
        if not isinstance(s, dict):
            issues.append({
                "severity": "warning",
                "field": f"schema[{i}]",
                "message": "Schema block is not a dict — may be unparseable JSON-LD",
            })
            continue

        if "@type" not in s:
            # Check if it's a @graph wrapper that wasn't flattened
            if "@graph" in s:
                issues.append({
                    "severity": "error",
                    "field": f"schema[{i}]",
                    "message": "Schema uses @graph wrapper but was not flattened. "
                               "This is valid JSON-LD, NOT malformed. "
                               "parse_html.py should flatten @graph into individual @type entries.",
                    "fix": "Update parse_html.py to flatten @graph schemas",
                })
            else:
                issues.append({
                    "severity": "warning",
                    "field": f"schema[{i}]",
                    "message": f"Schema block missing @type. Keys present: {list(s.keys())[:5]}",
                })

        schema_type = s.get("@type", "")
        if isinstance(schema_type, list):
            # @type arrays like ["Product", "ItemPage"] are valid
            pass
        elif schema_type in ("HowTo",):
            issues.append({
                "severity": "error",
                "field": f"schema[{i}]",
                "message": "HowTo schema detected — deprecated Sept 2023. Never recommend.",
            })

    return issues


def validate_verification_results(verify_data: dict) -> list:
    """Check verification findings for false negatives and inconsistencies."""
    issues = []

    if not verify_data or not verify_data.get("data"):
        return issues

    results = verify_data["data"].get("results", [])
    summary = verify_data["data"].get("summary", {})

    # Check summary matches actual results
    counted = {}
    for r in results:
        status = r.get("status", "unknown")
        counted[status] = counted.get(status, 0) + 1

    for status, count in counted.items():
        if summary.get(status, 0) != count:
            issues.append({
                "severity": "error",
                "field": "verify_data.summary",
                "message": f"Summary says {status}={summary.get(status, 0)} but actual count is {count}",
            })

    # Check for social media pages reported as "link_removed" (should be "unverifiable_js")
    social_domains = ["instagram.com", "facebook.com", "twitter.com", "x.com",
                      "tiktok.com", "linkedin.com", "pinterest.com", "youtube.com"]

    for r in results:
        source = r.get("source_url", "")
        status = r.get("status", "")
        from urllib.parse import urlparse
        source_domain = urlparse(source).netloc.lower()

        if status == "link_removed" and any(sd in source_domain for sd in social_domains):
            # Social media page marked as link_removed — likely false negative
            http_status = r.get("http_status", 0)
            if http_status == 200:
                issues.append({
                    "severity": "error",
                    "field": f"verify[{source}]",
                    "message": f"Social media page ({source_domain}) returned 200 but marked 'link_removed'. "
                               "Most social platforms are JS-rendered — should be 'unverifiable_js'.",
                })

    return issues


def validate_h1_claims(parsed_data: dict) -> list:
    """Check H1 findings for misleading data."""
    issues = []
    h1_list = parsed_data.get("h1", [])
    h1_suspicious = parsed_data.get("h1_suspicious", [])

    if not h1_list:
        # No H1 is a real finding — just ensure it's stated clearly
        return issues

    # Check if ALL H1s are suspicious (likely no real heading)
    if h1_suspicious and len(h1_suspicious) == len(h1_list):
        issues.append({
            "severity": "warning",
            "field": "h1",
            "message": "All H1 tags are suspicious (short/numeric). The page may have no real H1 heading. "
                       "Report should say 'No semantic H1 found (only counter/stat elements)'.",
        })

    return issues


def validate_cc_claims(cc_data: dict) -> list:
    """Check Common Crawl findings for misleading interpretations."""
    issues = []

    if not cc_data or not cc_data.get("data"):
        return issues

    data = cc_data["data"]
    in_crawl = data.get("in_crawl")
    in_rankings = data.get("in_rankings")

    if in_crawl is False and in_rankings is False:
        # Domain not in CC at all — ensure report doesn't claim "low authority"
        issues.append({
            "severity": "info",
            "field": "cc_data",
            "message": "Domain not found in Common Crawl. Do NOT interpret as 'low authority' — "
                       "it means CC hasn't crawled it yet. Could be new, niche, or geo-specific (.ro, .jp, etc.).",
        })

    if in_crawl is True and in_rankings is False:
        issues.append({
            "severity": "info",
            "field": "cc_data",
            "message": "Domain in CC crawl but not in rankings. Report as 'below ranking threshold' — "
                       "not 'domain has no authority'.",
        })

    return issues


def validate_reciprocal_links(parsed_data: dict, verify_data: dict) -> list:
    """Detect reciprocal link patterns (A links to B and B links back)."""
    issues = []

    if not verify_data or not verify_data.get("data") or not parsed_data:
        return issues

    # Get outbound domains from homepage
    outbound_domains = set()
    for link in parsed_data.get("links", {}).get("external", []):
        from urllib.parse import urlparse
        href = link.get("href", "")
        if href:
            domain = urlparse(href).netloc.lower()
            if domain:
                outbound_domains.add(domain.replace("www.", ""))

    # Get verified inbound source domains
    inbound_domains = set()
    for r in verify_data["data"].get("results", []):
        if r.get("status") == "verified":
            from urllib.parse import urlparse
            source = r.get("source_url", "")
            domain = urlparse(source).netloc.lower().replace("www.", "")
            if domain:
                inbound_domains.add(domain)

    # Find intersection = reciprocal patterns
    reciprocal = outbound_domains & inbound_domains
    if reciprocal:
        issues.append({
            "severity": "warning",
            "field": "reciprocal_links",
            "message": f"Reciprocal link pattern detected with {len(reciprocal)} domain(s): "
                       f"{', '.join(sorted(reciprocal))}. "
                       "The site links TO these domains AND they link back. Flag in report.",
            "domains": sorted(reciprocal),
        })

    return issues


def validate_health_score(scoring_factors: dict) -> list:
    """Validate health score data sufficiency."""
    issues = []

    if not scoring_factors:
        return issues

    total_factors = scoring_factors.get("total_factors", 7)
    factors_with_data = scoring_factors.get("factors_with_data", 0)
    score = scoring_factors.get("score")

    if factors_with_data < 4 and score is not None:
        issues.append({
            "severity": "error",
            "field": "health_score",
            "message": f"Numeric score ({score}/100) produced with only {factors_with_data}/{total_factors} "
                       "factors having data. This is misleading. Report INSUFFICIENT DATA instead.",
        })

    return issues


# Sources that can support a numeric backlink health score. Common Crawl is
# deliberately absent: it provides rank/presence signals only, not the
# referring-domain quality, anchor, or toxicity data a score implies.
SCOREABLE_SOURCES = ("moz_data", "bing_data", "dataforseo_data")

# Finding sources that mean "we did not measure this".
UNMEASURED_SOURCES = ("not-assessed", "not_assessed")


def _is_numeric_score(value) -> bool:
    """True when value is a real number (bool excluded) or a numeric string."""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value.strip())
        except (TypeError, ValueError):
            return False
        return True
    return False


def _scoreable_sources_present(report_data: dict) -> list:
    """Return the scoreable sources that actually carry data in this report."""
    present = []
    for key in SCOREABLE_SOURCES:
        value = report_data.get(key)
        if isinstance(value, dict):
            if value and not value.get("error"):
                present.append(key)
        elif value:
            present.append(key)
    return present


def validate_source_score_consistency(report_data: dict) -> list:
    """Enforce: never emit a numeric score for data that was not measured.

    Two failure modes, both observed in real audits despite the instruction
    already existing in the skill:

    1. Common Crawl is the only source available, but a numeric health score is
       still produced.
    2. A finding is marked `source: not-assessed` yet carries a score.
    """
    issues = []

    scoring_factors = report_data.get("scoring_factors") or {}
    score = scoring_factors.get("score") if isinstance(scoring_factors, dict) else None

    scoreable = _scoreable_sources_present(report_data)
    has_cc = bool(report_data.get("cc_data"))

    if _is_numeric_score(score) and not scoreable:
        detail = (
            "Common Crawl was the only source available"
            if has_cc else "no backlink data source was available"
        )
        issues.append({
            "severity": "error",
            "field": "health_score",
            "message": (
                f"Numeric score ({score}) produced when {detail}. Common Crawl "
                "supplies rank/presence signals only and MUST NOT be scored. "
                "Report 'Not Assessed' with no numeric value."
            ),
            "fix": "Set the score to null and report Not Assessed.",
        })

    findings = report_data.get("findings")
    if isinstance(findings, list):
        for i, finding in enumerate(findings):
            if not isinstance(finding, dict):
                continue
            source = str(finding.get("source", "")).strip().lower()
            if source not in UNMEASURED_SOURCES:
                continue
            for field in ("score", "value", "health_score"):
                if _is_numeric_score(finding.get(field)):
                    issues.append({
                        "severity": "error",
                        "field": f"findings[{i}].{field}",
                        "message": (
                            f"Finding '{finding.get('title', 'untitled')}' is "
                            f"source: not-assessed but carries a numeric "
                            f"{field} ({finding[field]}). A not-assessed finding "
                            "MUST NOT be scored."
                        ),
                        "fix": f"Omit {field} or set it to null.",
                    })

    return issues


def validate_report(report_data: dict) -> dict:
    """
    Run all validations on a backlink report.

    Args:
        report_data: Dictionary with keys: cc_data, verify_data, parsed_data,
                     moz_data (optional), bing_data (optional), scoring_factors (optional)

    Returns:
        Validation result with status, issues list, and pass/fail per category.
    """
    all_issues = []

    # Run each validator
    if report_data.get("parsed_data"):
        all_issues.extend(validate_schema_claims(report_data["parsed_data"]))
        all_issues.extend(validate_h1_claims(report_data["parsed_data"]))

    if report_data.get("verify_data"):
        all_issues.extend(validate_verification_results(report_data["verify_data"]))

    if report_data.get("cc_data"):
        all_issues.extend(validate_cc_claims(report_data["cc_data"]))

    if report_data.get("parsed_data") and report_data.get("verify_data"):
        all_issues.extend(validate_reciprocal_links(
            report_data["parsed_data"], report_data["verify_data"]
        ))

    if report_data.get("scoring_factors"):
        all_issues.extend(validate_health_score(report_data["scoring_factors"]))

    # Always run: this gate must fire even when the agent supplies no
    # scoring_factors block at all.
    all_issues.extend(validate_source_score_consistency(report_data))

    # Classify
    errors = [i for i in all_issues if i["severity"] == "error"]
    warnings = [i for i in all_issues if i["severity"] == "warning"]
    infos = [i for i in all_issues if i["severity"] == "info"]

    status = "FAIL" if errors else ("REVIEW" if warnings else "PASS")

    return {
        "status": status,
        "data": {
            "total_issues": len(all_issues),
            "errors": len(errors),
            "warnings": len(warnings),
            "infos": len(infos),
            "issues": all_issues,
        },
        "error": None,
        "metadata": {
            "source": "validate_backlink_report",
            "checks_run": [
                "schema_claims", "verification_results", "h1_claims",
                "cc_claims", "reciprocal_links", "health_score",
                "source_score_consistency",
            ],
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate backlink report data before presenting to user"
    )
    parser.add_argument(
        "--report",
        required=True,
        help="JSON file with report data (or '-' for stdin)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    try:
        if args.report == "-":
            report_data = json.load(sys.stdin)
        else:
            with open(args.report, "r") as f:
                report_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading report: {e}", file=sys.stderr)
        sys.exit(1)

    result = validate_report(report_data)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Validation: {result['status']}")
        print(f"  Errors:   {result['data']['errors']}")
        print(f"  Warnings: {result['data']['warnings']}")
        print(f"  Info:     {result['data']['infos']}")
        for issue in result["data"]["issues"]:
            severity = issue["severity"].upper()
            print(f"\n  [{severity}] {issue['field']}: {issue['message']}")


if __name__ == "__main__":
    main()
