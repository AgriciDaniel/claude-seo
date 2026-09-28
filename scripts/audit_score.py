#!/usr/bin/env python3
"""
Coverage-aware SEO Health Score and verification gate for audit-data.json.

A composite score built from categories nobody measured is a guess wearing a
number. This script scores only the categories that carry a measured score,
renormalises the weights over them, and reports how much of the weighted
model that covers. Below ``--min-coverage`` (default 0.70) it withholds the
composite score entirely rather than extrapolate.

It also enforces the audit's verification step: every Critical or High
finding must carry ``verification.status == "verified"`` before the report
ships. Findings marked ``disproved`` are moved out of the categories into a
top-level ``corrections`` list, so a rejected claim can never reach the
client report while the audit trail keeps it.

Category shape (inside ``categories[]``)::

    {"name": "Technical SEO", "score": 62, "measured": true, "findings": [...]}

A category is measured when ``score`` is a number and ``measured`` is not
false. ``score: null`` or ``measured: false`` means "not measured", never 0.

Category names map to the seven scoring buckets by exact name, then by
keyword ("Performance (Core Web Vitals)" -> performance, "Sitemap &
Indexation" -> technical). ``"scoring_category": "<bucket>"`` overrides the
mapping. Several categories in one bucket are averaged. Every mapping is
reported, so a surprising one is visible rather than silent.

Finding verification shape::

    "verification": {"status": "verified|unverified|disproved",
                     "method": "direct fetch of /blog, rendered",
                     "evidence": "10 /post/ links vs 368 in sitemap"}

Usage::

    python scripts/audit_score.py audit-data.json            # text summary
    python scripts/audit_score.py audit-data.json --json
    python scripts/audit_score.py audit-data.json --write    # update summary in place
    python scripts/audit_score.py audit-data.json --strict   # exit 2 on unverified Critical/High
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

# Mirrors the "Scoring Weights" table in skills/seo-audit/SKILL.md.
# tests/test_audit_score.py keeps the two in sync.
WEIGHTS = {
    "technical seo": 22,
    "content quality": 23,
    "on-page seo": 20,
    "schema / structured data": 10,
    "performance (cwv)": 10,
    "ai search readiness": 10,
    "images": 5,
}

ALIASES = {
    "technical": "technical seo",
    "content": "content quality",
    "on-page": "on-page seo",
    "onpage seo": "on-page seo",
    "schema": "schema / structured data",
    "structured data": "schema / structured data",
    "schema & structured data": "schema / structured data",
    "performance": "performance (cwv)",
    "core web vitals": "performance (cwv)",
    "cwv": "performance (cwv)",
    "geo": "ai search readiness",
    "ai search": "ai search readiness",
    "image": "images",
}

# Checked in order after exact names and aliases; first match wins.
KEYWORD_RULES = (
    (re.compile(r"schema|structured data"), "schema / structured data"),
    (re.compile(r"performance|web vitals|\bcwv\b|page ?speed"), "performance (cwv)"),
    (re.compile(r"\bai\b|\bgeo\b|generative|answer engine|llm"), "ai search readiness"),
    (re.compile(r"image"), "images"),
    (re.compile(r"on-?\s?page"), "on-page seo"),
    (re.compile(r"content|e-e-a-t|eeat"), "content quality"),
    (re.compile(r"technical|crawl|index|sitemap|robots|security|redirect"), "technical seo"),
)

DEFAULT_MIN_COVERAGE = 0.70
GATED_SEVERITIES = {"critical", "high"}
VERIFICATION_STATUSES = {"verified", "unverified", "disproved"}


def _normalise(name: object) -> str:
    return " ".join(str(name or "").lower().split())


def canonical_category(name: object, override: object = None) -> str | None:
    """Map a category name (or explicit ``scoring_category``) to a scoring bucket."""
    if override:
        key = _normalise(override)
        key = ALIASES.get(key, key)
        return key if key in WEIGHTS else None
    key = _normalise(name)
    for candidate in (key, re.sub(r"\s*\(.*?\)\s*", " ", key).strip()):
        candidate = ALIASES.get(candidate, candidate)
        if candidate in WEIGHTS:
            return candidate
    for pattern, bucket in KEYWORD_RULES:
        if pattern.search(key):
            return bucket
    return None


def _measured_score(category: dict) -> float | None:
    if category.get("measured") is False:
        return None
    score = category.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    if not math.isfinite(score) or not 0 <= score <= 100:
        return None
    return float(score)


def _verification_status(finding: dict) -> str:
    verification = finding.get("verification")
    if isinstance(verification, dict):
        status = str(verification.get("status", "")).strip().lower()
    elif isinstance(verification, str):
        status = verification.strip().lower()
    else:
        status = ""
    return status if status in VERIFICATION_STATUSES else "unverified"


def compute(data: dict, min_coverage: float = DEFAULT_MIN_COVERAGE) -> dict:
    """Score measured categories and audit verification. Pure; never mutates ``data``."""
    categories = data.get("categories") if isinstance(data.get("categories"), list) else []

    bucket_scores: dict[str, list[float]] = {}
    mapping: dict[str, str] = {}
    unknown: list[str] = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        name = str(category.get("name", ""))
        key = canonical_category(name, category.get("scoring_category"))
        if key is None:
            unknown.append(name)
            continue
        mapping[name] = key
        score = _measured_score(category)
        if score is not None:
            bucket_scores.setdefault(key, []).append(score)
    measured = {k: sum(v) / len(v) for k, v in bucket_scores.items()}

    measured_weight = sum(WEIGHTS[k] for k in measured)
    total_weight = sum(WEIGHTS.values())
    coverage = measured_weight / total_weight

    health_score = None
    withheld_reason = None
    if not measured:
        withheld_reason = "no category carries a measured score"
    elif coverage + 1e-9 < min_coverage:
        withheld_reason = (
            f"measured categories cover {coverage:.0%} of the scoring weight, "
            f"below the {min_coverage:.0%} minimum"
        )
    else:
        health_score = round(sum(WEIGHTS[k] * s for k, s in measured.items()) / measured_weight)

    unverified: list[dict] = []
    disproved: list[dict] = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        for finding in category.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            status = _verification_status(finding)
            ref = {"category": str(category.get("name", "")), "title": str(finding.get("title", ""))}
            if status == "disproved":
                disproved.append(ref)
            elif status == "unverified" and str(finding.get("severity", "")).lower() in GATED_SEVERITIES:
                unverified.append({**ref, "severity": str(finding.get("severity"))})

    return {
        "health_score": health_score,
        "coverage": round(coverage, 3),
        "min_coverage": min_coverage,
        "withheld_reason": withheld_reason,
        "measured": {k: round(measured[k], 1) for k in WEIGHTS if k in measured},
        "category_mapping": mapping,
        "unmeasured": [k for k in WEIGHTS if k not in measured],
        "unknown_categories": unknown,
        "unverified_high_severity": unverified,
        "disproved": disproved,
    }


def apply(data: dict, result: dict) -> dict:
    """Write the result into ``data['summary']`` and move disproved findings to ``corrections``."""
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    data["summary"] = summary
    if result["health_score"] is None:
        summary.pop("health_score", None)
        summary["health_score_withheld"] = result["withheld_reason"]
    else:
        summary["health_score"] = result["health_score"]
        summary.pop("health_score_withheld", None)
    summary["score_coverage"] = result["coverage"]
    summary["unmeasured_categories"] = result["unmeasured"]

    corrections = data.get("corrections") if isinstance(data.get("corrections"), list) else []
    for category in data.get("categories") or []:
        if not isinstance(category, dict) or not isinstance(category.get("findings"), list):
            continue
        kept = []
        for finding in category["findings"]:
            if isinstance(finding, dict) and _verification_status(finding) == "disproved":
                verification = finding.get("verification") if isinstance(finding.get("verification"), dict) else {}
                corrections.append({
                    "category": str(category.get("name", "")),
                    "claim": str(finding.get("title", "")),
                    "source": str(finding.get("source", "")),
                    "disproof": str(verification.get("evidence", "")),
                })
            else:
                kept.append(finding)
        category["findings"] = kept
    if corrections:
        data["corrections"] = corrections
    return data


def _write_atomic(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _format_text(result: dict) -> str:
    lines = []
    if result["health_score"] is None:
        lines.append(f"Health score: WITHHELD ({result['withheld_reason']})")
    else:
        lines.append(f"Health score: {result['health_score']}/100")
    lines.append(f"Coverage: {result['coverage']:.0%} of scoring weight measured")
    for name, score in result["measured"].items():
        lines.append(f"  measured    {name:<26} {score:g}  (weight {WEIGHTS[name]})")
    for name in result["unmeasured"]:
        lines.append(f"  NOT MEASURED {name:<25}     (weight {WEIGHTS[name]})")
    remapped = {n: b for n, b in result["category_mapping"].items() if _normalise(n) != b}
    for name, bucket in remapped.items():
        lines.append(f"  mapped: {name!r} -> {bucket}")
    for name in result["unknown_categories"]:
        lines.append(f"  ignored (not a scoring category): {name}")
    if result["unverified_high_severity"]:
        lines.append(f"Unverified Critical/High findings: {len(result['unverified_high_severity'])}")
        for item in result["unverified_high_severity"]:
            lines.append(f"  [{item['severity']}] {item['category']}: {item['title']}")
    if result["disproved"]:
        lines.append(f"Disproved findings (moved to corrections on --write): {len(result['disproved'])}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("data", help="path to audit-data.json")
    parser.add_argument("--min-coverage", type=float, default=DEFAULT_MIN_COVERAGE,
                        help="minimum weighted coverage (0-1) to issue a composite score")
    parser.add_argument("--write", action="store_true",
                        help="update summary in place and move disproved findings to corrections")
    parser.add_argument("--strict", action="store_true",
                        help="exit 2 when any Critical/High finding is not verified")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    if not 0 < args.min_coverage <= 1:
        parser.error("--min-coverage must be in (0, 1]")

    path = Path(args.data)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Cannot read {path.name}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print(f"{path.name} is not a JSON object", file=sys.stderr)
        return 1

    result = compute(data, args.min_coverage)
    if args.write:
        _write_atomic(path, apply(data, result))

    print(json.dumps(result, indent=2) if args.json else _format_text(result))
    if args.strict and result["unverified_high_severity"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
