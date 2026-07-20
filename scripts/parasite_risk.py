#!/usr/bin/env python3
"""
Parasite-SEO risk scanner.

Per Google's 2024-11-19 policy clarification, "no amount of first-party
involvement alters the third-party nature" of a section. Section-level
risk is now a Critical finding to surface in any audit of an established
editorial domain.

This scanner crawls a small set of representative URLs on a site,
classifies each into a content "topic", and flags subfolders where
the topic diverges from the site's primary corpus. Three signals:

  1. **Third-party authorship density** — bylines containing words like
     "Partner Content", "Sponsored", "Advertising", "Brand Studio".
  2. **Commercial-intent skew vs. site primary corpus** — affiliate
     code in outbound links, "Buy now" CTAs, price comparison tables,
     coupons.
  3. **Topical drift between subfolders** — root corpus is editorial
     but a single subfolder reads as pure commerce.

The output is **advisory**: the scanner cannot determine the actual
contractual relationship between the site and the content producer.
But it identifies the patterns Google's policy targets so the
audit user can investigate.

Inputs
======
A list of URLs from one host. Typically obtained by sampling
sitemaps or running `seo-sitemap`'s URL extractor.

Output
======
Per-subfolder risk: high/medium/low/unknown plus the contributing
signals. The script does not score the whole site — section-level
risk is the operational unit (per Google's policy).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Iterable
from urllib.parse import urlparse

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from url_safety import URLSafetyError, safe_requests_get  # noqa: E402


# Indicators of third-party authored content. Each adds 1 hit per page.
_THIRD_PARTY_BYLINE_PATTERNS = (
    r"\bPartner\s+Content\b",
    r"\bSponsored\s+Content\b",
    r"\bSponsored\s+by\b",
    r"\bBrand\s+Studio\b",
    r"\bIn\s+Partnership\s+With\b",
    r"\bAdvertisement\b",
    r"\bAdvertorial\b",
    r"\bPaid\s+Post\b",
    r"\bPromoted\b",
    r"\bPaid\s+Content\b",
)
_THIRD_PARTY_RE = re.compile("|".join(_THIRD_PARTY_BYLINE_PATTERNS), re.IGNORECASE)


# Commercial-intent signals. Each adds 1 hit per page.
_COMMERCE_PATTERNS = (
    r"\bBuy\s+Now\b",
    r"\bShop\s+Now\b",
    r"\bAdd\s+to\s+Cart\b",
    r"\bCompare\s+Prices\b",
    r"\bBest\s+\w+\s+Deals?\b",
    r"\bPromo\s+Code\b",
    r"\bCoupon\b",
    r"\bDiscount\s+Code\b",
    r"\bAffiliate\s+Disclosure\b",
)
_COMMERCE_RE = re.compile("|".join(_COMMERCE_PATTERNS), re.IGNORECASE)


# Outbound affiliate-link signatures. Each adds 1 hit per outbound link.
_AFFILIATE_LINK_RE = re.compile(
    r"\b(?:tag=|aff_id=|affid=|partnerid=|ref_=|utm_source=|utm_campaign=)",
    re.IGNORECASE,
)


def _subfolder(url: str) -> str:
    """Return the first path segment of a URL as the section key."""
    path = urlparse(url).path or "/"
    parts = [p for p in path.split("/") if p]
    return f"/{parts[0]}/" if parts else "/"


def _audit_page(url: str, html: str) -> dict:
    third_party_hits = len(_THIRD_PARTY_RE.findall(html))
    commerce_hits = len(_COMMERCE_RE.findall(html))
    affiliate_link_hits = len(_AFFILIATE_LINK_RE.findall(html))
    return {
        "url": url,
        "third_party_hits": third_party_hits,
        "commerce_hits": commerce_hits,
        "affiliate_link_hits": affiliate_link_hits,
    }


def _classify(rows: list[dict]) -> dict:
    """Aggregate signals per subfolder and emit a risk label."""
    by_section: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_section[_subfolder(row["url"])].append(row)

    report: dict[str, dict] = {}
    for section, pages in by_section.items():
        n = len(pages)
        third_party_rate = sum(p["third_party_hits"] for p in pages) / n
        commerce_rate = sum(p["commerce_hits"] for p in pages) / n
        affiliate_rate = sum(p["affiliate_link_hits"] for p in pages) / n

        flags: list[str] = []
        risk = "low"

        if third_party_rate >= 1.0:
            flags.append("third-party-authorship-density")
        if commerce_rate >= 2.0:
            flags.append("commercial-intent-skew")
        if affiliate_rate >= 3.0:
            flags.append("affiliate-density")

        if "third-party-authorship-density" in flags:
            risk = "high"
        elif "commercial-intent-skew" in flags and "affiliate-density" in flags:
            risk = "high"
        elif flags:
            risk = "medium"

        report[section] = {
            "page_count": n,
            "third_party_hits_per_page": round(third_party_rate, 2),
            "commerce_hits_per_page": round(commerce_rate, 2),
            "affiliate_link_hits_per_page": round(affiliate_rate, 2),
            "flags": flags,
            "risk": risk,
            "sample_urls": [p["url"] for p in pages[:3]],
        }

    # Cross-section drift: if one section has > 2x the *mean* commerce
    # rate of the site, flag it as drift even when its own absolute
    # threshold is below. Mean is more useful than median for the
    # common "1 outlier section, N quiet sections" pattern. The
    # absolute threshold above still catches sections that are bad on
    # their own merits.
    rates = [v["commerce_hits_per_page"] for v in report.values() if v["page_count"] > 0]
    if rates:
        mean_rate = sum(rates) / len(rates)
        for section, row in report.items():
            if mean_rate > 0 and row["commerce_hits_per_page"] > 2 * mean_rate:
                if "commercial-intent-drift" not in row["flags"]:
                    row["flags"].append("commercial-intent-drift")
                if row["risk"] == "low":
                    row["risk"] = "medium"

    return report


def scan(urls: Iterable[str], *, timeout: int = 20) -> dict:
    rows: list[dict] = []
    errors: list[dict] = []
    for url in urls:
        try:
            resp = safe_requests_get(url, timeout=timeout, allow_redirects=True)
            rows.append(_audit_page(resp.url, resp.text))
        except URLSafetyError as exc:
            errors.append({"url": url, "error": f"url_safety: {exc}"})
        except Exception as exc:  # noqa: BLE001 — surface every transport error
            errors.append({"url": url, "error": str(exc)})

    sections = _classify(rows)
    severities = Counter(v["risk"] for v in sections.values())
    overall_risk = "high" if severities.get("high", 0) > 0 else (
        "medium" if severities.get("medium", 0) > 0 else "low"
    )

    return {
        "pages_audited": len(rows),
        "errors": errors,
        "by_section": sections,
        "summary": dict(severities),
        "overall_risk": overall_risk,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parasite-SEO risk scanner (Google site-reputation policy)."
    )
    parser.add_argument(
        "urls", nargs="*",
        help="URLs to audit. Mix freely with --urls-file.",
    )
    parser.add_argument(
        "--urls-file",
        help="Path to a file with one URL per line.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    targets: list[str] = list(args.urls)
    if args.urls_file:
        from pathlib import Path
        for line in Path(args.urls_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                targets.append(line)

    if not targets:
        print("Error: pass URLs via positional args or --urls-file.",
              file=sys.stderr)
        return 2

    result = scan(targets)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Overall risk: {result['overall_risk']}")
        print(f"Pages audited: {result['pages_audited']}")
        if result["errors"]:
            print(f"Errors:        {len(result['errors'])}")
        print()
        for section, row in result["by_section"].items():
            print(f"  Section {section}  ({row['page_count']} pages)  "
                  f"risk={row['risk']}")
            print(f"    third-party/page: {row['third_party_hits_per_page']}")
            print(f"    commerce/page:    {row['commerce_hits_per_page']}")
            print(f"    affiliate/page:   {row['affiliate_link_hits_per_page']}")
            if row["flags"]:
                print(f"    flags:            {', '.join(row['flags'])}")

    return 0 if result["overall_risk"] != "high" else 1


if __name__ == "__main__":
    sys.exit(main())
