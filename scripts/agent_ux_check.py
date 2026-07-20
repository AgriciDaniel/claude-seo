#!/usr/bin/env python3
"""
Agent-friendly page auditor.

Scores a page against the checklist in
``skills/seo-technical/references/agent-friendly-pages.md`` — the
web.dev-sourced criteria Google's AI optimization guide references for
agent UX. Findings cover the three channels agents use:

1. Accessibility-tree quality (the cleanest signal)
2. Raw HTML semantics (real ``<button>`` / ``<a>`` vs ``<div onclick>``)
3. Layout / interactive-element sizing

Audit posture
=============
Findings are surfaced as **opportunities**, not failures. The scoring
exists to give the audit a quantitative axis without making it a hard
SEO gate.

NOTE: this score is a local 0-100 heuristic and is **distinct** from
Google's Lighthouse "Agentic Browsing" category, which reports a
**fractional pass-ratio (X of N), not a 0-100 score** (Chrome 150+).
Do not present this heuristic as the official Lighthouse agentic score.
See ``skills/seo-technical/references/agent-friendly-pages.md``.

Implementation
==============
Calls ``render_page.render_page`` with ``extract_accessibility=True``
to get both the rendered HTML and the Playwright accessibility-tree
snapshot. Then walks both for the checklist items.

CLI
===
    python agent_ux_check.py https://example.com
    python agent_ux_check.py https://example.com --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Optional

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from render_page import render_page  # noqa: E402


_ONCLICK_DIV_RE = re.compile(
    r"<div\b[^>]*\bonclick\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE
)
_INPUT_WITHOUT_LABEL_RE = re.compile(
    r"<input\b(?![^>]*\baria-label\s*=)(?![^>]*\baria-labelledby\s*=)[^>]*>",
    re.IGNORECASE,
)
_LABEL_FOR_RE = re.compile(r'<label\b[^>]*\bfor\s*=\s*[\"\']([^\"\']+)[\"\']', re.IGNORECASE)
_INPUT_ID_RE = re.compile(r'<input\b[^>]*\bid\s*=\s*[\"\']([^\"\']+)[\"\']', re.IGNORECASE)
_BUTTON_RE = re.compile(r"<button\b", re.IGNORECASE)
_ANCHOR_HREF_RE = re.compile(r"<a\b[^>]*\bhref\s*=", re.IGNORECASE)
_SEMANTIC_LANDMARK_RE = re.compile(
    r"<(?:nav|main|article|section|aside|header|footer)\b", re.IGNORECASE
)


def _walk_tree(node: Optional[dict]):
    """Yield every node in a Playwright accessibility snapshot."""
    if not node:
        return
    yield node
    for child in node.get("children") or []:
        yield from _walk_tree(child)


def analyze_html(html: str) -> dict:
    """Walk raw rendered HTML for the agent-UX checklist."""
    findings: dict = {
        "real_buttons": len(_BUTTON_RE.findall(html)),
        "real_anchors": len(_ANCHOR_HREF_RE.findall(html)),
        "div_onclick_widgets": len(_ONCLICK_DIV_RE.findall(html)),
        "semantic_landmarks": len(_SEMANTIC_LANDMARK_RE.findall(html)),
        "inputs_without_aria": 0,
        "inputs_without_label": 0,
    }

    # Inputs without ARIA labels — first cut, then check label[for] coverage.
    aria_less = _INPUT_WITHOUT_LABEL_RE.findall(html)
    findings["inputs_without_aria"] = len(aria_less)

    label_targets = set(_LABEL_FOR_RE.findall(html))
    input_ids = _INPUT_ID_RE.findall(html)
    unlabeled = [iid for iid in input_ids if iid not in label_targets]
    findings["inputs_without_label"] = len(unlabeled)

    return findings


def analyze_accessibility_tree(tree: Optional[dict]) -> dict:
    """Walk a Playwright accessibility snapshot for the checklist items."""
    findings: dict = {
        "tree_present": tree is not None,
        "total_nodes": 0,
        "interactive_nodes": 0,
        "role_button": 0,
        "role_link": 0,
        "role_generic": 0,
        "unnamed_interactive": 0,
    }
    if tree is None:
        return findings
    interactive_roles = {"button", "link", "textbox", "checkbox", "radio",
                          "combobox", "menuitem", "tab"}
    for node in _walk_tree(tree):
        findings["total_nodes"] += 1
        role = (node.get("role") or "").lower()
        name = (node.get("name") or "").strip()
        if role == "button":
            findings["role_button"] += 1
        elif role == "link":
            findings["role_link"] += 1
        elif role == "generic":
            findings["role_generic"] += 1
        if role in interactive_roles:
            findings["interactive_nodes"] += 1
            if not name:
                findings["unnamed_interactive"] += 1
    return findings


def score(html_findings: dict, a11y_findings: dict) -> dict:
    """Combine HTML + a11y-tree findings into a 0-100 agent-UX score."""
    score = 100
    issues: list[str] = []

    if html_findings["div_onclick_widgets"] > 0:
        deduction = min(20, html_findings["div_onclick_widgets"] * 5)
        score -= deduction
        issues.append(
            f"{html_findings['div_onclick_widgets']} div onclick widget(s) "
            f"(-{deduction})"
        )
    if html_findings["semantic_landmarks"] == 0:
        score -= 10
        issues.append("no semantic landmarks (nav/main/article/...) (-10)")
    if html_findings["inputs_without_label"] > 0:
        deduction = min(20, html_findings["inputs_without_label"] * 4)
        score -= deduction
        issues.append(
            f"{html_findings['inputs_without_label']} input(s) without label[for] "
            f"(-{deduction})"
        )

    if a11y_findings["tree_present"]:
        if a11y_findings["unnamed_interactive"] > 0:
            deduction = min(20, a11y_findings["unnamed_interactive"] * 3)
            score -= deduction
            issues.append(
                f"{a11y_findings['unnamed_interactive']} interactive node(s) "
                f"without accessible name (-{deduction})"
            )
        # A high role=generic ratio suggests broken semantics (lots of divs).
        total = a11y_findings["total_nodes"] or 1
        generic_ratio = a11y_findings["role_generic"] / total
        if generic_ratio > 0.5:
            score -= 10
            issues.append(
                f"role=generic dominates the a11y tree "
                f"({generic_ratio:.0%}) (-10)"
            )

    return {"score": max(0, score), "issues": issues}


def audit(url: str, *, timeout_ms: int = 15000) -> dict:
    """Audit a URL for agent-friendliness. Forces rendered mode."""
    page = render_page(
        url,
        mode="always",
        timeout_ms=timeout_ms,
        extract_content=False,
        extract_accessibility=True,  # type: ignore[call-arg]
    )
    report: dict = {
        "url": page.get("url"),
        "status_code": page.get("status_code"),
        "render_error": page.get("error"),
        "html_findings": {},
        "a11y_findings": {},
        "score": None,
        "issues": [],
    }
    if page.get("error"):
        return report
    html = page.get("content") or ""
    a11y = page.get("accessibility_tree")

    report["html_findings"] = analyze_html(html)
    report["a11y_findings"] = analyze_accessibility_tree(a11y)
    scored = score(report["html_findings"], report["a11y_findings"])
    report["score"] = scored["score"]
    report["issues"] = scored["issues"]
    return report


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Agent-friendly page auditor (semantic HTML + a11y tree)"
    )
    parser.add_argument("url")
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = audit(args.url, timeout_ms=args.timeout_ms)
    if args.json:
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["score"] is not None else 1)

    if report["render_error"]:
        print(f"Render error: {report['render_error']}", file=sys.stderr)
        sys.exit(1)

    print(f"URL: {report['url']}")
    print(f"Status: {report['status_code']}")
    print(f"Agent-UX score: {report['score']}/100")
    if report["issues"]:
        print("Issues:")
        for issue in report["issues"]:
            print(f"  - {issue}")
    print("\nHTML findings:")
    for k, v in report["html_findings"].items():
        print(f"  {k}: {v}")
    print("\nA11y tree findings:")
    for k, v in report["a11y_findings"].items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    _cli()
