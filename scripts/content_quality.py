#!/usr/bin/env python3
"""
QRG-aligned content quality detector.

Scores a block of text against the three lowest-rating triggers from
Google's September 11, 2025 Quality Rater Guidelines:

  - §4.6.5 Scaled content abuse
        "Using automated tools (generative AI or otherwise) as a
         low-effort way to produce many pages that add little-to-no
         value."
  - §4.6.6 Lowest rating triggered when
        "all or almost all MC… copied, paraphrased, [or] AI-generated."
  - §4.6 Filler content
        Padding phrases, generic transitions, no original insight.

The script is *advisory*: it surfaces signals so the caller can decide
whether a page warrants rewriting. It does NOT make a "this is AI"
verdict — modern generative tools can produce content that passes
every heuristic. Pair this with ``content_verify.py`` (claim
verification) for stronger signal.

Output (JSON when ``--json`` is set)::

    {
      "filler_score":           0..100 (higher = more filler-like)
      "ai_pattern_score":       0..100 (higher = more AI-pattern hits)
      "information_density":    0.0..1.0 (entities + numbers per token)
      "repetition_score":       0..100 (higher = more repetition)
      "overall_quality":        0..100 (composite, higher is better)
      "flags": ["filler", "ai-patterns", "low-density", ...],
      "matches": {"filler": [...], "ai_patterns": [...]},
      "tokens":                 int,
      "unique_tokens":          int
    }

Attribution
===========
The AI-pattern list draws from the Wikipedia "AI Cleanup" project's
catalogue of LLM-typical phrasings (CC BY-SA 4.0). The same list is
used by ivankuznetsov/claude-seo (MIT) and we cite both upstreams in
the comment block. Patterns are kept conservative — only phrases that
appear disproportionately in LLM output and rarely in human writing
are included.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable


# Padding / filler phrases that QRG §4.6 flags as "little-to-no value".
# Each phrase scores 1 hit; threshold tuned at ~3 hits per 1000 tokens.
_FILLER_PHRASES: tuple[str, ...] = (
    "it's important to note that",
    "in this article, we'll explore",
    "in this article we will explore",
    "in today's fast-paced world",
    "in today's digital age",
    "in today's competitive landscape",
    "needless to say",
    "at the end of the day",
    "when it comes to",
    "when all is said and done",
    "in the realm of",
    "in the world of",
    "the bottom line is",
    "without further ado",
    "first and foremost",
    "last but not least",
    "for what it's worth",
    "it goes without saying",
    "as we all know",
    "the truth is that",
    "the fact of the matter is",
    "more often than not",
    "let's dive in",
    "let's dive into",
    "let's take a closer look",
    "let's take a deeper look",
)


# LLM-typical phrasings (Wikipedia AI Cleanup catalogue, CC BY-SA 4.0;
# also used by ivankuznetsov/claude-seo, MIT). Conservative selection:
# only phrases that disproportionately appear in LLM output. Adding to
# this list should require corpus evidence, not just intuition.
_AI_PATTERNS: tuple[str, ...] = (
    "delve into",
    "delve deeper into",
    "in the ever-evolving",
    "ever-evolving landscape",
    "ever-changing landscape",
    "in the dynamic landscape",
    "navigating the",
    "navigate the complexities",
    "tapestry of",
    "rich tapestry",
    "intricate tapestry",
    "embark on a journey",
    "embarking on this",
    "a testament to",
    "a beacon of",
    "the cornerstone of",
    "a cornerstone of",
    "at the heart of",
    "at its core",
    "in essence,",
    "in conclusion,",
    "ultimately,",
    "moreover,",
    "furthermore,",
    "however, it's worth noting",
    "it's worth noting that",
    "by leveraging",
    "leverage the power of",
    "leveraging the power of",
    "harness the power of",
    "unlock the potential",
    "unlock the full potential",
    "the realm of possibilities",
    "open up a world of",
    "a world of possibilities",
    "elevate your",
    "transform your",
    "revolutionize the way",
    "game-changer",
    "game-changing",
    "cutting-edge",
    "state-of-the-art",
    "in summary,",
    "to summarize,",
    "to put it simply,",
    "in a nutshell,",
)


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?(?:%|st|nd|rd|th)?\b")
# Capitalised multi-word names: rough proper-noun heuristic. Two or more
# capitalised tokens in a row count as one entity.
_ENTITY_RE = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")


def _count_phrase_hits(text: str, patterns: Iterable[str]) -> list[str]:
    """Return the patterns that appear at least once in ``text`` (case-insensitive)."""
    lowered = text.lower()
    return [p for p in patterns if p in lowered]


def _repetition_score(tokens: list[str]) -> float:
    """Bigram repetition: fraction of bigrams that recur more than once."""
    if len(tokens) < 4:
        return 0.0
    bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]
    counts = Counter(bigrams)
    repeated = sum(1 for v in counts.values() if v > 1)
    return repeated / max(1, len(counts))


def analyse(text: str) -> dict:
    """Score a body of text against the QRG quality heuristics."""
    if not text or not text.strip():
        return {
            "filler_score": 0,
            "ai_pattern_score": 0,
            "information_density": 0.0,
            "repetition_score": 0,
            "overall_quality": 0,
            "flags": ["empty-input"],
            "matches": {"filler": [], "ai_patterns": []},
            "tokens": 0,
            "unique_tokens": 0,
        }

    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    n_tokens = len(tokens)
    unique = len(set(tokens))

    filler_hits = _count_phrase_hits(text, _FILLER_PHRASES)
    ai_hits = _count_phrase_hits(text, _AI_PATTERNS)

    # Density: entities + numbers per 100 tokens. A typical high-density
    # article (case studies, data journalism) lands at ~5+; a generic
    # filler post lands at <2.
    entities = len(_ENTITY_RE.findall(text))
    numbers = len(_NUMBER_RE.findall(text))
    density_per_100 = (entities + numbers) * 100.0 / max(1, n_tokens)
    information_density = min(1.0, density_per_100 / 10.0)

    rep = _repetition_score(tokens)
    rep_score = int(round(rep * 100))

    # Scale to per-1000 tokens so the score is comparable across page lengths.
    scale = max(1.0, n_tokens / 1000.0)
    filler_per_kt = len(filler_hits) / scale
    ai_per_kt = len(ai_hits) / scale

    filler_score = min(100, int(round(filler_per_kt * 25)))
    ai_pattern_score = min(100, int(round(ai_per_kt * 15)))

    flags: list[str] = []
    if filler_score >= 50:
        flags.append("filler")
    if ai_pattern_score >= 40:
        flags.append("ai-patterns")
    if information_density < 0.20:
        flags.append("low-density")
    if rep_score >= 30:
        flags.append("repetitive")
    if n_tokens < 300:
        flags.append("thin-content")

    # Composite: invert penalty signals, weight by impact.
    overall = (
        (100 - filler_score) * 0.25
        + (100 - ai_pattern_score) * 0.25
        + information_density * 100 * 0.25
        + (100 - rep_score) * 0.15
        + min(100, n_tokens / 10.0) * 0.10  # length bonus capped at 1000 tokens
    )

    return {
        "filler_score": filler_score,
        "ai_pattern_score": ai_pattern_score,
        "information_density": round(information_density, 3),
        "repetition_score": rep_score,
        "overall_quality": int(round(overall)),
        "flags": flags,
        "matches": {"filler": filler_hits, "ai_patterns": ai_hits},
        "tokens": n_tokens,
        "unique_tokens": unique,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="QRG-aligned content quality scorer."
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="Path to a text/HTML file, or '-' to read stdin (default '-').",
        default="-",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout.")
    parser.add_argument(
        "--threshold",
        type=int,
        default=60,
        help="Exit non-zero if overall_quality is below this (default 60).",
    )
    args = parser.parse_args()

    if args.source == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.source).read_text(encoding="utf-8", errors="replace")

    result = analyse(text)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Overall quality:       {result['overall_quality']}/100")
        print(f"  Filler score:        {result['filler_score']}/100 (higher = worse)")
        print(f"  AI-pattern score:    {result['ai_pattern_score']}/100 (higher = worse)")
        print(f"  Information density: {result['information_density']:.2f}")
        print(f"  Repetition:          {result['repetition_score']}/100 (higher = worse)")
        print(f"  Tokens:              {result['tokens']} ({result['unique_tokens']} unique)")
        if result["flags"]:
            print(f"  Flags:               {', '.join(result['flags'])}")
        if result["matches"]["filler"]:
            print(f"  Filler hits:         {', '.join(result['matches']['filler'][:5])}"
                  f"{' …' if len(result['matches']['filler']) > 5 else ''}")
        if result["matches"]["ai_patterns"]:
            print(f"  AI-pattern hits:     {', '.join(result['matches']['ai_patterns'][:5])}"
                  f"{' …' if len(result['matches']['ai_patterns']) > 5 else ''}")

    return 0 if result["overall_quality"] >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
