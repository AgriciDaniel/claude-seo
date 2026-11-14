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
verdict: modern generative tools can produce content that passes
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
      "unique_tokens":          int,
      "coverage":               present only when a signal was not fully
                                 computed for the dominant script, e.g.
                                 {"script": "cjk"|"non_latin_alphabetic"
                                            |"unsegmented",
                                  "entity_density": "not_computed",
                                  "phrase_lists": "english_only"}: the
                                 filler/AI-pattern phrase lists and the
                                 capitalisation-based entity heuristic are
                                 English-only, so a score in one of those
                                 scripts is not directly comparable to a
                                 Latin-script one. "unsegmented" (Thai, Lao,
                                 Khmer, Myanmar) also carries
                                 "tokenisation": "low_confidence": see below.
    }

Tokenisation coverage
=====================
Supported (a token is a word): Latin including accented letters in NFC or
NFD form, and the other scripts that put spaces between words: Greek,
Cyrillic, Armenian, Georgian, Hebrew, Arabic, Devanagari and the other
space-delimited Indic scripts. Combining marks stay with their word.
Supported (a token is a unit of the script): Korean (a run of Hangul
syllables), Chinese and Japanese (one ideograph or kana each).
Low confidence: Thai, Lao, Khmer and Myanmar are written without spaces and
need a dictionary to segment, which this script does not have. A run between
spaces or punctuation counts as one token, so ``tokens``, ``unique_tokens``,
``repetition_score`` and the thin-content flag are rough for them.
Not supported: every other script written without word spaces.

Attribution
===========
The AI-pattern list draws from the Wikipedia "AI Cleanup" project's
catalogue of LLM-typical phrasings (CC BY-SA 4.0). The same list is
used by ivankuznetsov/claude-seo (MIT) and we cite both upstreams in
the comment block. Patterns are kept conservative: only phrases that
appear disproportionately in LLM output and rarely in human writing
are included.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
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


# East Asian blocks the generic word rule must never claim: Hangul, kana,
# CJK ideographs and their compatibility and extension blocks. The dedicated
# alternatives in _TOKEN_RE own the parts of them that are tokenised.
_EAST_ASIAN_RANGES: tuple[tuple[int, int], ...] = (
    (0x1100, 0x11FF),    # Hangul Jamo
    (0x2E80, 0x33FF),    # CJK radicals and symbols, kana, Bopomofo, compatibility
    (0x3400, 0x4DBF),    # CJK Extension A
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0xA960, 0xA97F),    # Hangul Jamo Extended-A
    (0xAC00, 0xD7FF),    # Hangul syllables, Jamo Extended-B
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0xFF66, 0xFFDC),    # Halfwidth katakana and Hangul
    (0x16FE0, 0x18D8F),  # Ideographic symbols, Tangut, Khitan
    (0x1AFF0, 0x1B2FF),  # Kana extensions, Nushu
)
# Every letter from U+20000 up is a CJK ideograph, and the only marks there
# are ideographic variation selectors, so the scan stops below it.
_CLASS_SCAN_LIMIT = 0x20000


def _is_east_asian(codepoint: int) -> bool:
    return any(low <= codepoint <= high for low, high in _EAST_ASIAN_RANGES)


def _char_class(wanted) -> str:
    """Build the body of a regex character class from a code point test.

    The ``re`` module has no Unicode property classes, so the letter and
    combining-mark classes come from ``unicodedata`` once at import.
    """
    parts: list[str] = []
    start = None
    for codepoint in range(_CLASS_SCAN_LIMIT + 1):
        inside = codepoint < _CLASS_SCAN_LIMIT and wanted(codepoint)
        if inside and start is None:
            start = codepoint
        elif not inside and start is not None:
            end = codepoint - 1
            parts.append(f"\\U{start:08x}" if start == end else f"\\U{start:08x}-\\U{end:08x}")
            start = None
    return "".join(parts)


# Letters (Unicode categories L*) outside the East Asian blocks. For ASCII
# input this is exactly [A-Za-z].
_LETTER_CLASS = _char_class(
    lambda cp: unicodedata.category(chr(cp))[0] == "L" and not _is_east_asian(cp)
)
# Combining marks (Mn, Mc): accents on decomposed Latin, Arabic and Hebrew
# points, Indic vowel signs and viramas. They are not ``\w`` letters, so a
# plain letter run breaks "हिन्दी" into single consonants.
_MARK_CLASS = _char_class(
    lambda cp: unicodedata.category(chr(cp)) in ("Mn", "Mc") and not _is_east_asian(cp)
)

# A word in any script that puts spaces between words, then Hangul eojeol,
# then kana and CJK ideographs. The word rule is a letter followed by letters,
# combining marks, apostrophes, hyphens and the zero-width joiners that Indic
# and Persian text uses inside a word; on ASCII text it is the same rule as
# the original [A-Za-z][A-Za-z'\-]*. Korean is space delimited so a run of
# syllables is one token; Chinese and Japanese are unspaced, so one ideograph
# or kana counts as one token. The four alternatives match disjoint
# characters, so a word never runs on into Hangul, kana or CJK.
# Thai, Lao, Khmer and Myanmar are unspaced too, and segmenting them needs a
# dictionary. They fall under the word rule as a low-confidence fallback (a
# run between spaces or punctuation is one token), which analyse() reports
# in "coverage". See "Tokenisation coverage" in the module docstring.
_TOKEN_RE = re.compile(
    rf"[{_LETTER_CLASS}][{_LETTER_CLASS}{_MARK_CLASS}'\-\u200c\u200d]*"
    r"|[\uac00-\ud7a3]+"
    r"|[\u3041-\u3096\u30a1-\u30fa\u30fc]"
    r"|[\u3400-\u4dbf\u4e00-\u9fff]"
)


def _tokenise(text: str) -> list[str]:
    """Split text into tokens (see "Tokenisation coverage" in the docstring).

    The text is composed to NFC first, so "café" typed with a combining
    accent is the same token as the precomposed spelling.
    """
    return _TOKEN_RE.findall(unicodedata.normalize("NFC", text))


_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?(?:%|st|nd|rd|th)?\b")
# Capitalised multi-word names: rough proper-noun heuristic. Two or more
# capitalised tokens in a row count as one entity. Latin-cased only: Greek,
# Cyrillic and other cased scripts are not recognised here either (see the
# non_latin_alphabetic coverage note below).
_ENTITY_RE = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
# NOTE: CJK scripts have no letter case, so this heuristic finds no entities
# in Korean/Japanese/Chinese text. Density for those languages therefore rests
# on _NUMBER_RE alone and skews low. Tokenisation (above) is the load-bearing
# fix; CJK named-entity detection needs a real model, not a regex.

# Same character classes as the CJK branches of _TOKEN_RE, used only to guess
# whether a text is CJK-dominant so we can flag which signals below are not
# meaningfully computed for it. Not a language detector.
_CJK_CHAR_RE = re.compile(
    r"[가-힣ぁ-ゖァ-ヺー㐀-䶿一-鿿]"
)
# ASCII letters plus the accented Latin blocks (Latin-1, Extended-A and B,
# Extended Additional), so French or Vietnamese text counts as Latin.
_LATIN_CHAR_RE = re.compile(
    r"[A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u024f\u1e00-\u1eff]"
)
# Any Unicode "letter" character (word character that is not a digit or
# underscore). Used only to size up how much of the text is alphabetic in
# a script that is neither Latin nor CJK/Hangul/kana: Greek, Cyrillic,
# Arabic, Hebrew, Armenian, Georgian, Thai, Devanagari, etc. Not a language
# detector: it cannot say *which* script, only that it is "other".
_ALPHA_CHAR_RE = re.compile(r"[^\W\d_]")
# Letters of the scripts written without spaces between words that
# _TOKEN_RE cannot segment: Thai, Lao, Myanmar (with extensions) and Khmer.
_UNSEGMENTED_CHAR_RE = re.compile(
    r"(?=[\u0e00-\u0eff\u1000-\u109f\u1780-\u17ff\ua9e0-\ua9ff\uaa60-\uaa7f])[^\W\d_]"
)


def _detect_script(text: str) -> str | None:
    """Return the dominant script when a signal is not fully computed for it.

    "cjk" when CJK/Hangul/kana characters dominate. "unsegmented" when Thai,
    Lao, Khmer or Myanmar dominates: those are tokenised only as a
    low-confidence fallback. "non_latin_alphabetic" when another non-Latin
    alphabetic script (Greek, Cyrillic, Arabic, Hebrew, Devanagari, ...)
    dominates: ``_TOKEN_RE`` splits those into words, but the filler and
    AI-pattern phrase lists and the capitalisation-based ``_ENTITY_RE``
    heuristic are English/Latin only, so those signals are not meaningful
    for any of the three.

    ``None`` covers Latin-script and any other text; the coverage note is
    only added when the score's known-unreliable signals apply.
    """
    cjk_chars = len(_CJK_CHAR_RE.findall(text))
    latin_chars = len(_LATIN_CHAR_RE.findall(text))
    if cjk_chars and cjk_chars >= latin_chars:
        return "cjk"
    other_alpha_chars = len(_ALPHA_CHAR_RE.findall(text)) - cjk_chars - latin_chars
    if other_alpha_chars > 0 and other_alpha_chars >= latin_chars:
        unsegmented_chars = len(_UNSEGMENTED_CHAR_RE.findall(text))
        if unsegmented_chars * 2 >= other_alpha_chars:
            return "unsegmented"
        return "non_latin_alphabetic"
    return None


def _count_phrase_hits(text: str, patterns: Iterable[str]) -> list[str]:
    """Return the patterns that appear at least once as a whole phrase.

    Matching is case-insensitive. The phrase must not continue into another
    word, so ``let's dive in`` is not also a hit inside ``let's dive into``.
    Counting that prefix made one sentence two filler hits, which moved
    ``filler_score`` from 25 to 50 and raised the filler flag.
    """
    lowered = text.lower()
    hits = []
    for pattern in patterns:
        if re.search(rf"(?<!\w){re.escape(pattern)}(?!\w)", lowered):
            hits.append(pattern)
    return hits


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

    tokens = [t.lower() for t in _tokenise(text)]
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

    result = {
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

    # The filler/AI-pattern phrase lists and the capitalisation-based entity
    # heuristic are English-only; they are silently near-zero for CJK and for
    # other non-Latin scripts (Greek, Cyrillic, Thai, ...) rather than
    # reporting "no filler found". Flag that explicitly so a score in one of
    # those scripts is never read as comparable to a Latin-script one.
    # Latin/other output is unchanged: no "coverage" key is added when every
    # signal was actually computed.
    script = _detect_script(text)
    if script in ("cjk", "non_latin_alphabetic", "unsegmented"):
        result["coverage"] = {
            "script": script,
            "entity_density": "not_computed",
            "phrase_lists": "english_only",
        }
        if script == "unsegmented":
            # Thai, Lao, Khmer and Myanmar are not segmented into words, so
            # every token-based number above is a rough fallback.
            result["coverage"]["tokenisation"] = "low_confidence"

    return result


def _configure_utf8() -> None:
    """Read stdin and write stdout as UTF-8 regardless of the console codec.

    Windows consoles default to a legacy code page, which cannot encode CJK
    text and would raise UnicodeEncodeError on the first non-Latin character.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main() -> int:
    _configure_utf8()
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
        if result.get("coverage"):
            script_label = {
                "cjk": "CJK",
                "non_latin_alphabetic": "non-Latin-script",
                "unsegmented": "unsegmented-script (Thai, Lao, Khmer or Myanmar)",
            }.get(result["coverage"]["script"], result["coverage"]["script"])
            print(
                f"  Note: {script_label} text detected, entity-density and "
                "phrase-list signals are English-only heuristics here, so "
                "this score is not directly comparable to a Latin-script "
                "page."
            )
            if result["coverage"].get("tokenisation") == "low_confidence":
                print(
                    "  Note: this script is written without spaces between "
                    "words and is not segmented here, so the token counts "
                    "and repetition score are low confidence."
                )

    return 0 if result["overall_quality"] >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
