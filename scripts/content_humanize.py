#!/usr/bin/env python3
"""
AI-pattern remover. Rewrites filler / AI-typical phrasings into
direct prose, and strips invisible Unicode artifacts ("text
watermarks") that AI tools and copy-paste pipelines leave behind:
zero-width characters, directional marks, exotic spaces, and Unicode
tag characters. Conservative by design: only replaces phrases listed
in ``_REPLACEMENTS``, and keeps zero-width joiners / variation
selectors that are part of real emoji sequences. Unknown idiom?
Leave it alone.

Statistical watermarks (e.g. SynthID-style token-probability
watermarks) live in word choice, not codepoints; nothing here — or
anywhere — reliably detects or strips those, so this tool does not
claim to.

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
    (r"\bunlock\s+(?:the\s+(?:full\s+)?)?potential\b", "use", "unlock-potential"),
    (r"\bopen\s+up\s+a\s+world\s+of\b", "enable", "open-world"),
    (r"\ba\s+world\s+of\s+possibilities\b", "options", "world-possibilities"),
    (r"\belevate\s+your\b", "improve your", "elevate-your"),
    (r"\btransform\s+your\b", "improve your", "transform-your"),
    (r"\brevolutionize\s+the\s+way\b", "change how", "revolutionize-the-way"),
    (r"\bgame-?changer\b", "important", "game-changer"),
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
    (r"\bfirst\s+and\s+foremost,?\s*", "first,", "first-and-foremost"),
    (r"\blast\s+but\s+not\s+least,?\s*", "finally,", "last-but-not-least"),
    (r"\blet'?s\s+dive\s+(in|into)\b", "starting with", "let-us-dive"),
    (r"\blet'?s\s+take\s+a\s+(closer|deeper)\s+look\b", "look at", "let-us-take-look"),
)


_PATTERNS = [
    (re.compile(p, re.IGNORECASE), repl, label)
    for p, repl, label in _REPLACEMENTS
]


# Invisible / format characters deleted outright. They render as
# nothing, break regex word boundaries, inflate diffs, and are the
# codepoints used to fingerprint or smuggle hidden text in AI output.
_INVISIBLE_DELETE = {
    "\u00ad": "soft-hyphen",
    "\u180e": "mongolian-vowel-separator",
    "\u200b": "zero-width-space",
    "\u200e": "left-to-right-mark",
    "\u200f": "right-to-left-mark",
    "\u202a": "lre-embedding",
    "\u202b": "rle-embedding",
    "\u202c": "pop-directional",
    "\u202d": "lro-override",
    "\u202e": "rlo-override",
    "\u2060": "word-joiner",
    "\u2061": "function-application",
    "\u2062": "invisible-times",
    "\u2063": "invisible-separator",
    "\u2064": "invisible-plus",
    "\u2066": "lri-isolate",
    "\u2067": "rli-isolate",
    "\u2068": "fsi-isolate",
    "\u2069": "pop-isolate",
    "\u3164": "hangul-filler",
    "\ufeff": "zero-width-no-break-space",
    "\uffa0": "halfwidth-hangul-filler",
}

# Exotic whitespace normalised to a plain equivalent instead of deleted.
_INVISIBLE_SPACE = {
    "\u00a0": ("space", " "),   # no-break space
    "\u2000": ("space", " "),   # en quad
    "\u2001": ("space", " "),   # em quad
    "\u2002": ("space", " "),   # en space
    "\u2003": ("space", " "),   # em space
    "\u2004": ("space", " "),   # three-per-em space
    "\u2005": ("space", " "),   # four-per-em space
    "\u2006": ("space", " "),   # six-per-em space
    "\u2007": ("space", " "),   # figure space
    "\u2008": ("space", " "),   # punctuation space
    "\u2009": ("space", " "),   # thin space
    "\u200a": ("space", " "),   # hair space
    "\u202f": ("space", " "),   # narrow no-break space
    "\u205f": ("space", " "),   # medium mathematical space
    "\u2028": ("newline", "\n"),    # line separator
    "\u2029": ("newline", "\n\n"),  # paragraph separator
}

# Legitimate inside emoji sequences (family/warning/keycap emoji);
# stripped only when nothing emoji-like sits next to them.
_EMOJI_GLUE = {
    "\u200c": "zero-width-non-joiner",
    "\u200d": "zero-width-joiner",
    "\ufe0e": "variation-selector-15",
    "\ufe0f": "variation-selector-16",
}


def _emoji_adjacent(prev: str, nxt: str) -> bool:
    """True when either neighbour is plausibly part of an emoji sequence."""
    for ch in (prev, nxt):
        if ch and (ord(ch) >= 0x2100 or ch == "\u20e3"):
            return True
    return False


def strip_invisible(text: str) -> tuple[str, dict]:
    """Remove invisible watermark characters; return (cleaned, counts)."""
    removed: dict[str, int] = {}
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch in _INVISIBLE_DELETE:
            label = _INVISIBLE_DELETE[ch]
        elif ch in _INVISIBLE_SPACE:
            label, replacement = _INVISIBLE_SPACE[ch]
            out.append(replacement)
        elif ch in _EMOJI_GLUE:
            prev = text[i - 1] if i else ""
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if _emoji_adjacent(prev, nxt):
                out.append(ch)
                continue
            label = _EMOJI_GLUE[ch]
        elif 0xE0000 <= ord(ch) <= 0xE007F:
            label = "unicode-tag-character"
        else:
            out.append(ch)
            continue
        removed[label] = removed.get(label, 0) + 1
    return "".join(out), removed


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
    # Strip invisible characters first: zero-width codepoints inside
    # words would otherwise defeat the \b boundaries below.
    cleaned, invisible_removed = strip_invisible(text)

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

    return {
        "cleaned": cleaned,
        "changes": changes,
        "change_count": len(changes),
        "invisible_removed": invisible_removed,
        "invisible_count": sum(invisible_removed.values()),
    }


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

    if result["invisible_count"]:
        print(
            f"\n--- {result['invisible_count']} invisible characters removed ---",
            file=sys.stderr,
        )
        for label, count in sorted(result["invisible_removed"].items()):
            print(f"  {label}: {count}", file=sys.stderr)

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
