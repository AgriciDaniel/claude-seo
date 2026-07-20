#!/usr/bin/env python3
"""
Claim extractor + citation-gap detector.

Surfaces *verifiable claims* in a body of text and reports which ones
lack a nearby citation marker. Designed for the v2 ``/seo content
verify`` workflow: a fact-check pass on drafts before publish.

What counts as a claim
======================
- Statistical:  "47% of marketers report …"
- Quantitative: "200 million users", "$3.2 billion in revenue"
- Authority:    "according to a Stanford study"
- Temporal:     "in 2025, …", "by 2030 …"
- Comparative:  "twice as effective", "3x faster"

What counts as a citation marker
================================
- A nearby (`<= 200 chars`) markdown/HTML link: `[Source](https://…)`
- A footnote-style reference: `[^1]` or `[1]`
- An inline attribution to a named source: "Forrester said", "per Gartner"
- A schema.org Citation block (rough detection of nearby `@type`:
  `"Citation"` JSON)

Output JSON::

    {
      "claims": [
        {
          "text": "…",
          "kind": "statistic|quantity|authority|temporal|comparative",
          "position": <char offset>,
          "has_citation": bool,
          "nearby_citation": "…" or None
        },
        …
      ],
      "claim_count": int,
      "uncited_count": int,
      "uncited_ratio": 0..1
    }

The script is *advisory*: it does not check whether a citation actually
exists. The signal is whether the author bothered to anchor each
claim. The uncited_ratio field is this tool's internal heuristic,
inspired by QRG trust expectations, not a Google rater metric.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Claim patterns. Each is (regex, label). Order matters — first match
# wins per substring so a "47% of users" doesn't double-count as both
# statistic and quantity. Trailing-word groups are restricted to
# [a-zA-Z]+ so a greedy match cannot cross a sentence boundary into the
# next claim (e.g. "47% of marketers do X. 60%" must not collapse to a
# single match).
_CLAIM_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\b\d+(?:\.\d+)?\s*%\s+of\s+[a-zA-Z]+(?:\s+[a-zA-Z]+){0,4}",
                re.IGNORECASE),
     "statistic"),
    (re.compile(r"\b\d+(?:\.\d+)?\s*%\b"), "statistic"),
    (re.compile(r"\$\s?\d+(?:\.\d+)?\s*(?:million|billion|trillion|k|M|B)\b",
                re.IGNORECASE), "quantity"),
    (re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\s+\w+", re.IGNORECASE),
     "quantity"),
    (re.compile(r"\b\d+(?:\.\d+)?\s*(?:million|billion|trillion)\b",
                re.IGNORECASE), "quantity"),
    (re.compile(
        r"\baccording\s+to\s+(?:a\s+)?(?:[A-Z][a-z]+\s+){1,4}(?:study|report|survey|analysis|paper)\b"),
     "authority"),
    (re.compile(
        r"\b(?:Forrester|Gartner|McKinsey|Pew|Nielsen|Statista|Deloitte|Edelman|MIT|Stanford|Harvard|Wharton)\s+(?:said|reports?|found|noted)",
        re.IGNORECASE), "authority"),
    (re.compile(r"\bin\s+(?:19|20)\d{2}\b"), "temporal"),
    (re.compile(r"\bby\s+20\d{2}\b"), "temporal"),
    (re.compile(r"\b\d+(?:\.\d+)?\s*(?:x|times)\s+(?:more|less|faster|slower|higher|lower|better|worse)\b",
                re.IGNORECASE), "comparative"),
    (re.compile(r"\b(?:twice|thrice|half)\s+as\s+\w+", re.IGNORECASE),
     "comparative"),
)


# Citation markers we look for in a +/-200 char window around each claim.
# Standalone "see" and "per" are NOT included as triggers because they are
# common English words that produce too many false positives ("see growth",
# "per page"). We require the attribution form ("Source:", "Per Gartner",
# "according to a Stanford study") or an explicit hyperlink / footnote.
_CITATION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\[[^\]]+\]\(https?://[^)]+\)"),  # markdown link
    re.compile(r"<a\s+[^>]*href=[\"']https?://[^\"']+[\"']"),  # HTML link
    re.compile(r"\[\^?\d+\]"),  # footnote-style [1] or [^1]
    re.compile(r"@type\s*:\s*[\"']Citation[\"']"),  # schema.org Citation
    re.compile(
        # "Source:", "Via:", "See also:", "Cited in", "Cited by", or
        # "Per/According to" followed by a Proper Noun.
        r"\b(?:source\s*:|via\s*:|see\s+also\s*:|cited\s+(?:in|by)|"
        r"according\s+to|per)\s+[A-Z]",
        re.IGNORECASE,
    ),
)


def _has_citation_near(text: str, position: int, window: int = 200) -> str | None:
    """Return the matched citation text if any citation pattern hits within
    ``window`` chars of ``position``, otherwise None."""
    start = max(0, position - window)
    end = min(len(text), position + window)
    snippet = text[start:end]
    for pattern in _CITATION_PATTERNS:
        m = pattern.search(snippet)
        if m:
            return m.group(0)[:80]
    return None


def extract_claims(text: str) -> list[dict]:
    """Find every claim-like span; mark whether each has a nearby citation."""
    found_spans: list[tuple[int, int, str]] = []
    for pattern, label in _CLAIM_PATTERNS:
        for m in pattern.finditer(text):
            # Skip if an earlier (more specific) pattern already covered
            # this span — prevents 47% double-counting as statistic + quantity.
            if any(s <= m.start() < e or s < m.end() <= e for s, e, _ in found_spans):
                continue
            found_spans.append((m.start(), m.end(), label))

    claims: list[dict] = []
    for start, end, label in sorted(found_spans):
        cite = _has_citation_near(text, start)
        claims.append({
            "text": text[start:end].strip(),
            "kind": label,
            "position": start,
            "has_citation": cite is not None,
            "nearby_citation": cite,
        })
    return claims


def verify(text: str) -> dict:
    claims = extract_claims(text)
    uncited = [c for c in claims if not c["has_citation"]]
    return {
        "claims": claims,
        "claim_count": len(claims),
        "uncited_count": len(uncited),
        "uncited_ratio": round(len(uncited) / len(claims), 3) if claims else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Claim + citation-gap detector for content drafts."
    )
    parser.add_argument("source", nargs="?", default="-",
                        help="File path or '-' for stdin (default '-').")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.4,
        help="Exit non-zero if uncited_ratio > threshold (default 0.4).",
    )
    args = parser.parse_args()

    text = sys.stdin.read() if args.source == "-" else \
        Path(args.source).read_text(encoding="utf-8", errors="replace")

    result = verify(text)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Claims:          {result['claim_count']}")
        print(f"Uncited:         {result['uncited_count']}")
        print(f"Uncited ratio:   {result['uncited_ratio']:.2f}")
        for c in result["claims"]:
            mark = "✓" if c["has_citation"] else "✗"
            print(f"  [{mark} {c['kind']:<11}] {c['text']!r}")

    return 0 if result["uncited_ratio"] <= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
