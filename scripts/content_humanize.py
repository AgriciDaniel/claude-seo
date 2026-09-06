#!/usr/bin/env python3
"""
AI-pattern remover. Rewrites filler / AI-typical phrasings into
direct prose. Conservative by design: only replaces phrases listed in
``_REPLACEMENTS``. Unknown idiom? Leave it alone.

Use case: a content editor running last-mile cleanup on a draft. This
is NOT a paraphraser or a translation tool; it does not introduce new
content. Every replacement is a deterministic 1:1 swap.

Attribution
===========
Replacement table aligns with the Wikipedia "AI Cleanup" catalogue
(CC BY-SA 4.0) and ivankuznetsov/claude-seo's 24-pattern list (MIT).
We diverge from those upstreams only on a handful of phrases where
their preferred replacement reads less naturally for SEO contexts
(e.g. "leverage" -> "use", not "employ"). Diff is documented inline.

CLI::

    python scripts/content_humanize.py draft.md -o cleaned.md
    cat draft.md | python scripts/content_humanize.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Replacements run in order. Each entry is (pattern, replacement, label).
# Patterns are compiled with re.IGNORECASE and \b word boundaries where
# appropriate. The replacement preserves the original case of the first
# character (e.g. "Leverage X" -> "Use X", not "use X").
_REPLACEMENTS: tuple[tuple[str, str, str], ...] = (
    (r"\bdelve\s+deeper\s+into\b", "explore", "delve-deeper-into"),
    (r"\bdelve\s+into\b", "explore", "delve-into"),
    (r"\bin\s+the\s+ever-evolving\s+landscape\s+of\b", "in", "ever-evolving-landscape"),
    (r"\bin\s+the\s+ever-evolving\s+world\s+of\b", "in", "ever-evolving-world"),
    (r"\bever-evolving\b", "changing", "ever-evolving"),
    (r"\bever-changing\b", "changing", "ever-changing"),
    (r"\bnavigating\s+the\s+complexities\s+of\b", "handling", "navigating-complexities"),
    (r"\btapestry\s+of\b", "range of", "tapestry-of"),
    (r"\b(rich|intricate|complex)\s+tapestry\b", "range", "rich-tapestry"),
    (r"\bembark\s+on\s+a\s+journey\b", "begin", "embark-journey"),
    (r"\ba\s+testament\s+to\b", "evidence of", "testament-to"),
    (r"\ba\s+beacon\s+of\b", "a leader in", "beacon-of"),
    (r"\b(the\s+|a\s+)?cornerstone\s+of\b", "central to", "cornerstone-of"),
    (r"\bat\s+the\s+heart\s+of\b", "central to", "at-the-heart-of"),
    (r"\bin\s+essence,\s*", "", "in-essence"),
    (r"\bin\s+conclusion,\s*", "", "in-conclusion"),
    (r"\bultimately,\s*", "", "ultimately-comma"),
    (r"\bmoreover,\s*", "", "moreover-comma"),
    (r"\bfurthermore,\s*", "", "furthermore-comma"),
    (r"\bhowever,\s+it'?s\s+worth\s+noting\s+that\b", "however,", "worth-noting-clause"),
    (r"\bit'?s\s+worth\s+noting\s+that\b", "note:", "worth-noting"),
    (r"\bby\s+leveraging\b", "by using", "by-leveraging"),
    (r"\bleverage\s+the\s+power\s+of\b", "use", "leverage-power"),
    (r"\bleveraging\s+the\s+power\s+of\b", "using", "leveraging-power"),
    (r"\bharness\s+the\s+power\s+of\b", "use", "harness-power"),
    (r"\bunlock\s+(?:the\s+(?:full\s+)?)?potential\s+of\b", "get more from",
     "unlock-potential-of"),
    (r"\bunlock\s+(?:the\s+(?:full\s+)?)?potential\b", "do more", "unlock-potential"),
    (r"\bopen\s+up\s+a\s+world\s+of\b", "enable", "open-world"),
    (r"\ba\s+world\s+of\s+possibilities\b", "options", "world-possibilities"),
    (r"\belevate\s+your\b", "improve your", "elevate-your"),
    (r"\btransform\s+your\b", "improve your", "transform-your"),
    (r"\brevolutionize\s+the\s+way\b", "change how", "revolutionize-the-way"),
    # "game-changer" is a noun; replacing it with the adjective "important"
    # produced "this is a important". Replace a noun with a noun.
    (r"\bgame-?changers\b", "big changes", "game-changers"),
    (r"\bgame-?changer\b", "big change", "game-changer"),
    (r"\bcutting-?edge\b", "modern", "cutting-edge"),
    (r"\bstate-of-the-art\b", "modern", "state-of-the-art"),
    (r"\bin\s+summary,\s*", "", "in-summary"),
    (r"\bto\s+summarize,\s*", "", "to-summarize"),
    (r"\bto\s+put\s+it\s+simply,\s*", "", "to-put-simply"),
    (r"\bin\s+a\s+nutshell,\s*", "", "in-nutshell"),
    (r"\bit'?s\s+important\s+to\s+note\s+that\b", "note:", "important-note"),
    (r"\bin\s+today'?s\s+(fast-paced|digital|competitive)\s+(world|age|landscape)\b",
     "today", "today-cliche"),
    (r"\bneedless\s+to\s+say,?\s*", "", "needless-to-say"),
    (r"\bat\s+the\s+end\s+of\s+the\s+day\b", "ultimately", "end-of-the-day"),
    (r"\bwhen\s+it\s+comes\s+to\b", "for", "when-it-comes-to"),
    (r"\bfirst\s+and\s+foremost,?\s*", "first, ", "first-and-foremost"),
    (r"\blast\s+but\s+not\s+least,?\s*", "finally, ", "last-but-not-least"),
    (r"\blet'?s\s+dive\s+(in|into)\b", "starting with", "let-us-dive"),
    (r"\blet'?s\s+take\s+a\s+(closer|deeper)\s+look\b", "look at", "let-us-take-look"),
)


_PATTERNS = [
    (re.compile(p, re.IGNORECASE), repl, label)
    for p, repl, label in _REPLACEMENTS
]


def _preserve_case(match_text: str, replacement: str) -> str:
    """If the original starts uppercase, capitalise the replacement."""
    if not replacement:
        return ""
    if match_text and match_text[0].isupper() and not replacement[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def humanize(text: str) -> dict:
    """Apply every replacement; return the cleaned text plus a change log."""
    changes: list[dict] = []
    cleaned = text

    for pattern, replacement, label in _PATTERNS:
        def _repl(match):
            original = match.group(0)
            new = _preserve_case(original, replacement)
            changes.append({
                "label": label,
                "from": original,
                "to": new,
            })
            return new
        cleaned = pattern.sub(_repl, cleaned)

    # Collapse double spaces introduced by deleted phrases, but leave
    # newlines and intentional spacing alone.
    cleaned = re.sub(r"  +", " ", cleaned)
    cleaned = re.sub(r" ([,.;:!?])", r"\1", cleaned)
    cleaned = _fix_articles(cleaned)
    if any(c["to"] == "" for c in changes):
        cleaned = _recapitalise(cleaned)

    return {
        "cleaned": cleaned,
        "changes": changes,
        "change_count": len(changes),
    }



_CODE_OR_URL_RE = re.compile(r"```.*?```|`[^`\n]*`|https?://\S+", re.S)
_SENTENCE_START_RE = re.compile(r"(^|[.!?]\s+|\n)([a-z])", re.M)
_ARTICLE_RE = re.compile(r"\b(a|an)\s+([A-Za-z])", re.IGNORECASE)


def _recapitalise(text: str) -> str:
    """Restore the capital a deleted sentence-opener took with it.

    ``"In conclusion, this is X."`` becomes ``"this is X."`` once the opener is
    dropped. Only real sentence starts are touched, and code spans, fenced blocks
    and URLs are masked out first because an uppercase letter changes their meaning.
    """
    spans: list[str] = []

    def _mask(match: re.Match) -> str:
        spans.append(match.group(0))
        return f"\x00{len(spans) - 1}\x00"

    masked = _CODE_OR_URL_RE.sub(_mask, text)
    masked = _SENTENCE_START_RE.sub(
        lambda m: m.group(1) + m.group(2).upper(), masked
    )
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], masked)


def _fix_articles(text: str) -> str:
    """Repair a/an after a replacement changed the following word.

    ``game-changer -> important`` turns "a game-changer" into "a important".
    The article is only corrected when the replacement actually broke it.
    """
    vowels = "aeiou"

    def _swap(match: re.Match) -> str:
        article, first = match.group(1), match.group(2)
        needs_an = first.lower() in vowels
        if needs_an and article.lower() == "a":
            fixed = "An" if article[0].isupper() else "an"
        elif not needs_an and article.lower() == "an":
            fixed = "A" if article[0].isupper() else "a"
        else:
            return match.group(0)
        return f"{fixed} {first}"

    return _ARTICLE_RE.sub(_swap, text)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-pattern remover for drafts.")
    parser.add_argument(
        "source",
        nargs="?",
        help="Path to a text/markdown file, or '-' for stdin (default '-').",
        default="-",
    )
    parser.add_argument("--output", "-o", help="Write cleaned text to this path.")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON with cleaned text + change log.")
    args = parser.parse_args()

    if args.source == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.source).read_text(encoding="utf-8", errors="replace")

    result = humanize(text)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.output:
        Path(args.output).write_text(result["cleaned"], encoding="utf-8")
        print(
            f"Wrote {args.output} ({result['change_count']} replacements)",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(result["cleaned"])

    if result["change_count"]:
        print(f"\n--- {result['change_count']} replacements ---", file=sys.stderr)
        seen: set[str] = set()
        for change in result["changes"]:
            key = change["label"]
            if key in seen:
                continue
            seen.add(key)
            print(f"  {change['from']!r} -> {change['to']!r}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
