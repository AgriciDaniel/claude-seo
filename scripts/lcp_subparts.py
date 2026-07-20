#!/usr/bin/env python3
"""
LCP subparts breakdown via CrUX API.

Since January 2025 CrUX has exposed the four LCP sub-metrics:
  - largest_contentful_paint_image_time_to_first_byte
  - largest_contentful_paint_image_resource_load_delay
  - largest_contentful_paint_image_resource_load_duration
  - largest_contentful_paint_image_element_render_delay

These let you decompose a slow LCP into network, scheduling, fetch,
and render phases — turning "your LCP is 4.2s" into "your TTFB is 1.1s
and your render delay is 2.4s, fix server response and the image
preload sequence". Per the gap analysis, this is the single most
actionable upgrade to claude-seo's CWV reporting.

Usage::

    python scripts/lcp_subparts.py https://example.com/
    python scripts/lcp_subparts.py https://example.com/ --form-factor PHONE --json

Requires the same Google API key used by ``scripts/crux_history.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import urllib.request
import urllib.error

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from url_safety import URLSafetyError, validate_url_strict  # noqa: E402
from google_auth import get_api_key, google_api_key_headers, redact_google_api_key  # noqa: E402


CRUX_ENDPOINT = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"


_LCP_SUBPART_METRICS = [
    "largest_contentful_paint_image_time_to_first_byte",
    "largest_contentful_paint_image_resource_load_delay",
    "largest_contentful_paint_image_resource_load_duration",
    "largest_contentful_paint_image_element_render_delay",
]


def _query_crux(url: str, form_factor: str, api_key: str) -> dict:
    payload = {
        "url": url,
        "formFactor": form_factor,
        "metrics": _LCP_SUBPART_METRICS + ["largest_contentful_paint"],
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", **google_api_key_headers(api_key)}
    request = urllib.request.Request(
        CRUX_ENDPOINT,
        data=body,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {
            "error": (
                f"CrUX HTTP {exc.code}: "
                f"{redact_google_api_key(exc.read().decode('utf-8', 'replace'))}"
            )
        }
    except urllib.error.URLError as exc:
        return {"error": f"CrUX request failed: {redact_google_api_key(exc.reason)}"}


def _percentile(metric: dict) -> float | None:
    p = metric.get("percentiles", {}).get("p75")
    if p is None:
        return None
    try:
        return float(p)
    except (TypeError, ValueError):
        return None


def analyse(url: str, form_factor: str = "PHONE") -> dict:
    try:
        url, _ = validate_url_strict(url)
    except URLSafetyError as exc:
        return {"error": f"url_safety: {exc}"}

    api_key = get_api_key()
    if not api_key:
        return {
            "error": "Google API key not configured. "
                     "Run `python scripts/google_auth.py --setup`.",
        }

    raw = _query_crux(url, form_factor, api_key)
    if "error" in raw:
        return raw

    metrics = raw.get("record", {}).get("metrics", {})
    breakdown: dict[str, float | None] = {}
    for key in _LCP_SUBPART_METRICS:
        m = metrics.get(key)
        breakdown[key] = _percentile(m) if m else None

    overall_lcp = _percentile(metrics.get("largest_contentful_paint", {})) \
        if metrics.get("largest_contentful_paint") else None

    # Identify the dominant subpart. "Dominant" = subpart that contributes
    # >40% of overall LCP, which is where remediation effort pays back.
    dominant: list[dict] = []
    if overall_lcp:
        for key, val in breakdown.items():
            if val is None:
                continue
            share = val / overall_lcp
            if share >= 0.40:
                dominant.append({"metric": key, "p75_ms": val,
                                 "share": round(share, 2)})

    recommendations: list[str] = []
    for d in dominant:
        if d["metric"].endswith("time_to_first_byte"):
            recommendations.append(
                "TTFB dominates LCP. Check origin response time, server-side "
                "compute, CDN edge cache hit rate. Aim for TTFB < 0.8s."
            )
        elif d["metric"].endswith("resource_load_delay"):
            recommendations.append(
                "Resource load delay dominates. The LCP element is discovered "
                "late; preload the hero image with fetchpriority=high or move "
                "it ahead of blocking resources."
            )
        elif d["metric"].endswith("resource_load_duration"):
            recommendations.append(
                "Resource load duration dominates. The LCP image is large. "
                "Serve responsive sizes (srcset), modern formats (AVIF/WebP), "
                "and add async decoding hints."
            )
        elif d["metric"].endswith("element_render_delay"):
            recommendations.append(
                "Element render delay dominates. The element is loaded but "
                "painting is blocked. Reduce render-blocking CSS/JS above the "
                "fold and avoid font-blocking layout shifts."
            )

    return {
        "url": url,
        "form_factor": form_factor,
        "p75_lcp_ms": overall_lcp,
        "subparts_p75_ms": breakdown,
        "dominant_subparts": dominant,
        "recommendations": recommendations,
        "raw": raw,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Decompose LCP into its four subparts via CrUX."
    )
    parser.add_argument("url")
    parser.add_argument(
        "--form-factor",
        choices=("PHONE", "DESKTOP", "TABLET", "ALL_FORM_FACTORS"),
        default="PHONE",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = analyse(args.url, args.form_factor)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if args.json:
        # Strip the noisy CrUX raw response from JSON output by default.
        out = {k: v for k, v in result.items() if k != "raw"}
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"URL: {result['url']}")
        print(f"Form factor: {result['form_factor']}")
        print(f"Overall p75 LCP: {result['p75_lcp_ms']} ms")
        print("Subparts (p75 ms):")
        for k, v in result["subparts_p75_ms"].items():
            label = k.replace("largest_contentful_paint_image_", "")
            print(f"  {label:35s} {v if v is not None else '—'}")
        if result["dominant_subparts"]:
            print("\nDominant subparts (>= 40% of LCP):")
            for d in result["dominant_subparts"]:
                short = d["metric"].replace("largest_contentful_paint_image_", "")
                print(f"  {short} = {d['p75_ms']:.0f} ms ({d['share']*100:.0f}%)")
        if result["recommendations"]:
            print("\nRecommendations:")
            for r in result["recommendations"]:
                print(f"  - {r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
