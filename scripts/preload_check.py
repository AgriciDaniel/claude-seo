#!/usr/bin/env python3
"""
Speculation Rules / bfcache / prerender2 / preload detector.

Per the v2 gap analysis, **LCP is the binding CWV constraint** as of
2025: 77% of mobile pages pass INP, only 62% pass LCP, and 48% pass
all three. The fastest large LCP win available without a content
rewrite is to wire up **bfcache** and **Speculation Rules** so the
next-navigation paint is effectively instant.

This script audits a page's HTML and response headers for the four
preload mechanisms Google rewards in 2025-2026:

  - ``<script type="speculationrules">`` blocks  (Chrome 121+)
  - ``Speculation-Rules`` HTTP response header   (Chrome 122+)
  - ``<link rel="preload" as="…">``               (legacy but still useful for LCP)
  - ``<link rel="prerender" href="…">``           (deprecated; flag for migration)
  - bfcache hints: ``Cache-Control: no-store`` removed, no
    ``unload`` listeners, no permission-prompting APIs.

The script does NOT measure bfcache eligibility from JS; that requires
a headless browser run with the ``NotRestoredReasons`` API. Instead,
it surfaces the easy static signals so an audit can quickly identify
high-value fixes.

Result JSON::

    {
      "url":                   "<final URL>",
      "speculation_rules": {
        "inline_blocks":       <int>,
        "header_present":      <bool>,
        "actions":             ["prefetch", "prerender", …]
      },
      "preload_hints":         <int>,
      "prerender_links":       <int>,  # deprecated rel=prerender count
      "bfcache_signals": {
        "cache_control_no_store":  <bool>,
        "unload_listener":         <bool>,
        "beforeunload_listener":   <bool>
      },
      "lcp_resource_hints": {
        "preload_lcp_candidate":   <bool>,
        "fetchpriority_high":      <int>
      },
      "score": 0..100,
      "recommendations": ["…"]
    }
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
from url_safety import URLSafetyError, safe_requests_get  # noqa: E402

_SPECULATION_BLOCK_RE = re.compile(
    r'<script\b[^>]*\btype\s*=\s*["\']speculationrules["\'][^>]*>(?P<body>.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_PRELOAD_LINK_RE = re.compile(
    r'<link\b[^>]*\brel\s*=\s*["\']preload["\'][^>]*>', re.IGNORECASE,
)
_PRERENDER_LINK_RE = re.compile(
    r'<link\b[^>]*\brel\s*=\s*["\']prerender["\'][^>]*>', re.IGNORECASE,
)
_FETCHPRIORITY_HIGH_RE = re.compile(
    r'\bfetchpriority\s*=\s*["\']high["\']', re.IGNORECASE,
)
_LCP_IMG_HINT_RE = re.compile(
    r'<(?:img|video|source)\b[^>]*\bfetchpriority\s*=\s*["\']high["\']',
    re.IGNORECASE,
)
_UNLOAD_LISTENER_RE = re.compile(
    r'\b(?:addEventListener|on)\s*\(\s*["\']?unload["\']?', re.IGNORECASE,
)
_BEFOREUNLOAD_LISTENER_RE = re.compile(
    r'\b(?:addEventListener|on)\s*\(\s*["\']?beforeunload["\']?', re.IGNORECASE,
)


def _extract_speculation_actions(body: str) -> list[str]:
    """Pull the unique 'action' field values out of a speculationrules JSON."""
    actions: set[str] = set()
    try:
        payload = json.loads(body.strip())
    except json.JSONDecodeError:
        return []
    for action_kind in ("prefetch", "prerender"):
        if isinstance(payload.get(action_kind), list):
            actions.add(action_kind)
    return sorted(actions)


def analyse(html: str, headers: Optional[dict] = None) -> dict:
    headers = headers or {}
    speculation_blocks = list(_SPECULATION_BLOCK_RE.finditer(html))
    actions: set[str] = set()
    for m in speculation_blocks:
        for a in _extract_speculation_actions(m.group("body")):
            actions.add(a)
    speculation_header = "speculation-rules" in {k.lower() for k in headers}

    preload_count = len(_PRELOAD_LINK_RE.findall(html))
    prerender_count = len(_PRERENDER_LINK_RE.findall(html))
    fetchpriority_count = len(_FETCHPRIORITY_HIGH_RE.findall(html))
    lcp_img_hint = bool(_LCP_IMG_HINT_RE.search(html))

    cc_value = ""
    for key, value in headers.items():
        if key.lower() == "cache-control":
            cc_value = value or ""
            break
    cache_control_no_store = "no-store" in cc_value.lower()

    has_unload = bool(_UNLOAD_LISTENER_RE.search(html))
    has_beforeunload = bool(_BEFOREUNLOAD_LISTENER_RE.search(html))

    # Score: 25 pts each for speculation rules, preload-with-LCP hint,
    # absence of bfcache-killers, and the absence of deprecated prerender.
    score = 0
    recs: list[str] = []
    if speculation_blocks or speculation_header:
        score += 25
    else:
        recs.append(
            "Add <script type=\"speculationrules\"> for prefetch+prerender on "
            "top user-paths. Saves entire next-navigation paint cost."
        )

    if lcp_img_hint:
        score += 25
    else:
        recs.append(
            "Mark the LCP hero image with fetchpriority=\"high\" so the "
            "browser preloads it ahead of other resources."
        )

    if not cache_control_no_store and not has_unload:
        score += 25
    else:
        if cache_control_no_store:
            recs.append(
                "Cache-Control: no-store disqualifies the page from bfcache. "
                "Remove it or scope it to authenticated routes only."
            )
        if has_unload:
            recs.append(
                "An unload listener disqualifies the page from bfcache. "
                "Switch to pagehide or visibilitychange."
            )

    if prerender_count == 0:
        score += 25
    else:
        recs.append(
            f"Found {prerender_count} <link rel=\"prerender\"> (deprecated). "
            "Migrate to speculation rules (rel=prerender was sunset in Chrome 120)."
        )

    return {
        "speculation_rules": {
            "inline_blocks": len(speculation_blocks),
            "header_present": speculation_header,
            "actions": sorted(actions),
        },
        "preload_hints": preload_count,
        "prerender_links": prerender_count,
        "bfcache_signals": {
            "cache_control_no_store": cache_control_no_store,
            "unload_listener": has_unload,
            "beforeunload_listener": has_beforeunload,
        },
        "lcp_resource_hints": {
            "preload_lcp_candidate": lcp_img_hint,
            "fetchpriority_high": fetchpriority_count,
        },
        "score": score,
        "recommendations": recs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit Speculation Rules, bfcache, prerender, and LCP "
                    "preload signals on a single URL."
    )
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        resp = safe_requests_get(args.url, timeout=20, allow_redirects=True)
    except URLSafetyError as exc:
        print(f"Error: url_safety: {exc}", file=sys.stderr)
        return 2

    result = {"url": resp.url, **analyse(resp.text, dict(resp.headers))}

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"URL: {result['url']}")
        print(f"Score: {result['score']}/100")
        sr = result["speculation_rules"]
        print(f"  Speculation Rules:    blocks={sr['inline_blocks']} "
              f"header={sr['header_present']} actions={sr['actions']}")
        print(f"  Preload hints:        {result['preload_hints']}")
        print(f"  Deprecated prerender: {result['prerender_links']}")
        bf = result["bfcache_signals"]
        print(f"  bfcache killers:      no-store={bf['cache_control_no_store']} "
              f"unload={bf['unload_listener']} "
              f"beforeunload={bf['beforeunload_listener']}")
        lr = result["lcp_resource_hints"]
        print(f"  LCP preload:          marked={lr['preload_lcp_candidate']} "
              f"fetchpriority=high count={lr['fetchpriority_high']}")
        if result["recommendations"]:
            print("Recommendations:")
            for r in result["recommendations"]:
                print(f"  - {r}")

    return 0 if result["score"] >= 75 else 1


if __name__ == "__main__":
    sys.exit(main())
