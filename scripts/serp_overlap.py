#!/usr/bin/env python3
"""Compute reproducible top-ten organic SERP overlap from saved result URLs.

Input: {"serps": [{"keyword": "...", "urls": ["https://...", ...]}]}.
URLs must already be organic results in ranking order; ads, PAA, and other SERP
features are excluded by the collector. An optional "error" records an incomplete
fetch. This script performs no network requests and never executes input data.

Usage:
    ./scripts/claude-seo run serp_overlap.py serp-results.json
    ./scripts/claude-seo run serp_overlap.py - < serp-results.json

Output is JSON with the symmetric ``serp_matrix``, pairwise evidence, and coverage
diagnostics. An incomplete SERP yields null matrix cells and an "inconclusive"
relationship, not evidence that two keywords need separate pages.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote_plus, urlsplit, urlunsplit

import idna

TOP_RESULTS = 10
MAX_KEYWORDS = 200
MAX_INPUT_BYTES = 4 * 1024 * 1024
_TRACKING_KEYS = {"gclid", "dclid", "fbclid", "msclkid", "mc_cid", "mc_eid", "_ga"}
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_PERCENT_ESCAPE = re.compile(r"%([0-9a-fA-F]{2})")


def _normalise_escapes(value: str) -> str:
    def replace(match: re.Match) -> str:
        char = chr(int(match.group(1), 16))
        return char if char in _UNRESERVED else match.group(0).upper()

    return _PERCENT_ESCAPE.sub(replace, value)


def normalise_url(url: str) -> str:
    """Normalize syntax and attribution parameters without merging page identities.

    Keep the scheme, path case, trailing slash, and non-tracking query parameters.
    Their equivalence cannot be established without redirect/canonical evidence.
    """
    if not isinstance(url, str) or not url or "\\" in url:
        raise ValueError("Expected an absolute HTTP(S) URL without whitespace or backslashes")
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url):
        raise ValueError("Expected an absolute HTTP(S) URL without whitespace or backslashes")
    if re.search(r"%(?![0-9a-fA-F]{2})", url):
        raise ValueError("Invalid percent escape")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Expected an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are not accepted")
    host = parsed.hostname
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        host = idna.encode(host, uts46=True).decode("ascii").lower()
    else:
        host = f"[{address.compressed}]" if address.version == 6 else str(address)
    port = parsed.port
    if port is not None and port != {"http": 80, "https": 443}[parsed.scheme]:
        host = f"{host}:{port}"
    path = _normalise_escapes(quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~"))
    parameters = []
    for parameter in parsed.query.split("&") if parsed.query else []:
        name = unquote_plus(parameter.partition("=")[0]).lower()
        if not name.startswith("utm_") and name not in _TRACKING_KEYS:
            parameters.append(_normalise_escapes(quote(parameter, safe="/?%:@!$'()*+,;=-._~")))
    return urlunsplit((parsed.scheme, host, path, "&".join(parameters), ""))


def _relationship(score: int) -> str:
    if score >= 7:
        return "same_post"
    if score >= 4:
        return "same_cluster"
    if score >= 2:
        return "interlink"
    return "separate"


def analyse(payload: dict) -> dict:
    """Compute every pair once from the collected top-ten organic results."""
    if not isinstance(payload, dict) or not isinstance(payload.get("serps"), list):
        raise ValueError('Input must be an object with a "serps" list')
    rows = payload["serps"]
    if not 1 <= len(rows) <= MAX_KEYWORDS:
        raise ValueError(f"Provide between 1 and {MAX_KEYWORDS} keyword SERPs")
    keywords = []
    seen_keywords = set()
    coverage = []
    url_sets = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("keyword"), str):
            raise ValueError(f"SERP {index + 1} needs a keyword string")
        keyword = row["keyword"].strip()
        identity = " ".join(keyword.casefold().split())
        if not identity:
            raise ValueError(f"SERP {index + 1} has an empty keyword")
        if identity in seen_keywords:
            raise ValueError(f"SERP {index + 1} repeats a keyword")
        seen_keywords.add(identity)
        urls = row.get("urls", [])
        error = row.get("error")
        if not isinstance(urls, list) or (error is not None and not isinstance(error, str)):
            raise ValueError(f"SERP {index + 1} needs a URL list and an optional error string")
        normalized = set()
        invalid = []
        duplicates = 0
        # Do not backfill with rank 11 after an invalid or duplicate top-ten URL.
        for rank, url in enumerate(urls[:TOP_RESULTS], 1):
            try:
                normalized_url = normalise_url(url)
            except (ValueError, idna.IDNAError) as exc:
                invalid.append({"rank": rank, "error": str(exc)})
                continue
            if normalized_url in normalized:
                duplicates += 1
            normalized.add(normalized_url)
        complete = len(normalized) == TOP_RESULTS and not error
        keywords.append(keyword)
        url_sets.append(normalized)
        coverage.append({
            "keyword": keyword,
            "provided_results": len(urls),
            "unique_top_ten_urls": len(normalized),
            "duplicate_results": duplicates,
            "invalid_results": invalid,
            "error": error or None,
            "complete": complete,
        })

    scores = [[None for _ in keywords] for _ in keywords]
    pairs = []
    for left in range(len(keywords)):
        if coverage[left]["complete"]:
            scores[left][left] = TOP_RESULTS
        for right in range(left + 1, len(keywords)):
            shared = sorted(url_sets[left] & url_sets[right])
            complete = coverage[left]["complete"] and coverage[right]["complete"]
            score = len(shared) if complete else None
            scores[left][right] = scores[right][left] = score
            pairs.append({
                "keywords": [keywords[left], keywords[right]],
                "score": score,
                "observed_shared_count": len(shared),
                "shared_urls": shared,
                "relationship": _relationship(score) if score is not None else "inconclusive",
                "needs_review": score is None or score in {3, 4},
            })
    return {
        "serp_matrix": {"keywords": keywords, "scores": scores},
        "pairs": pairs,
        "coverage": coverage,
        "complete": all(row["complete"] for row in coverage),
        "comparisons": len(pairs),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Saved organic SERP JSON, or - for stdin")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with Path(args.input).open("rb") as source:
                raw = source.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError(f"Input exceeds {MAX_INPUT_BYTES} bytes")
        result = analyse(json.loads(raw.decode("utf-8-sig")))
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
