#!/usr/bin/env python3
"""
Templated-metadata detector.

Finds machine-generated ``<title>`` / ``<meta name="description">`` pairs.
The signature is narrow and deterministic: a description that opens by
restating its own title verbatim and then closes with a stock call to
action ("Try it free now.", "Start free!", "Learn more now!").

Why this matters
================
Bulk metadata jobs (a CSV column piped into a template, an LLM asked for
"a description for each of these titles") emit that exact shape across
every page of a site at once. Under Google's spam policies and QRG
§4.6.5, site-wide templated metadata reads as scaled content abuse, and
it does so **independently of body-copy quality** — a site whose article
text is entirely original can still be demoted on the metadata alone.

Existing content checks do not catch this. ``content_quality.py`` scores
body text; the ``seo-programmatic`` uniqueness gate measures unique body
words per page. A site with fully unique body copy passes both while
carrying an identical templated description shape on every URL.

Detection
=========
Four deterministic string comparisons, no model and no inference about
authorship:

  1. ``templated_metadata`` (high)
        Description opens with the title, then ends in a stock CTA.
  2. ``description_echoes_title`` (medium)
        Description opens with the title but adds real information.
  3. ``brand_suffix_in_description`` (low)
        The title's brand suffix was concatenated into the description
        body — a generation artefact, not a written sentence.
  4. ``description_duplicates_title`` (medium)
        Description and title are the same string.

Only titles of a reasonable length are compared, so short titles that a
sentence can legitimately open with ("Word Counter" beginning a sentence
about a word counter) are never flagged.

Output (JSON when ``--json`` is set)::

    {
      "pages": [
        {
          "url": "https://example.com/tool",
          "title": "...",
          "description": "...",
          "templated": true,
          "severity": "high",
          "cta_phrase": "try it free now",
          "flags": ["templated-metadata"],
          "signals": [{"id", "severity", "message", "recommendation"}]
        }
      ],
      "pages_checked":    int,
      "templated_count":  int,
      "templated_ratio":  0.0..1.0,
      "shared_cta_phrases": {"try it free now": 26},
      "site_flags":       ["site-wide-templated-metadata", ...],
      "site_risk":        "high" | "medium" | "low"
    }

A single pair scores as one page; ``--pairs-file`` scores a whole site,
which is the unit the spam signal actually operates on.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

# Stock closers that bulk metadata jobs append. Each entry must match at
# the very end of the description remainder (after the echoed title has
# been removed), so a page that genuinely ends on a call to action
# without echoing its title is never flagged. Adding to this list should
# require seeing the phrase in real generated metadata, not intuition.
_CTA_TAIL_PATTERNS = (
    # "Try it free now.", "Try free!", "Try it today."
    r"try (?:it )?(?:free|now)(?: now)?",
    r"try (?:it )?today",
    # "Start free.", "Start now.", "Start your free scan now.", "Start your audit now!"
    r"start (?:your |the )?(?:\w+ ){0,3}(?:free|now)",
    # "Learn more now.", "Read more now.", "Find out now."
    r"(?:learn|read|find out|see) (?:more )?now",
    # "Get started.", "Get started now.", "Get started free."
    r"get started(?: (?:now|free|today))?",
    # "Check it out now.", "Check your score now."
    r"check (?:it out|your \w+) now",
    # "Boost your rankings now.", "Improve your writing score now."
    r"(?:boost|improve|upgrade) (?:your )?(?:\w+ ){0,3}now",
    # "Sign up free.", "Sign up today."
    r"sign up (?:free|now|today)",
)
_CTA_TAIL_RE = re.compile(
    r"(" + "|".join(_CTA_TAIL_PATTERNS) + r")[.!]*\s*$", re.IGNORECASE
)

# "Page Title | Brand", "Page Title - Brand", en/em dash variants.
_BRAND_SEPARATOR_RE = re.compile(r"\s[|–—-]\s")

_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]+")

# A title shorter than this (normalised) is too generic to treat an echo
# as evidence of templating.
_MIN_TITLE_CHARS = 25
# Compare at most this many leading characters, so a long title whose
# tail was truncated in the description still matches.
_ECHO_PREFIX_CHARS = 60
# Brand suffixes outside this range are almost certainly a mis-split.
_BRAND_MIN_CHARS = 2
_BRAND_MAX_CHARS = 30

# Site-level gates. The signal is scaled content abuse, so it needs both
# an absolute count (one templated page is an oversight) and a share of
# the sampled pages (three out of three hundred is not a pattern).
_SITE_MIN_TEMPLATED_PAGES = 3
_SITE_HIGH_RATIO = 0.30
_SITE_MEDIUM_RATIO = 0.10


def _normalise(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace.

    Two strings that differ only in casing or separators compare equal.
    """
    return " ".join(_NON_ALNUM_RE.sub(" ", text.lower()).split())


def _title_core(title: str) -> str:
    """The claim the title makes, without its brand suffix.

    "Keyword Density Checker | Credify" -> "Keyword Density Checker".
    """
    return _BRAND_SEPARATOR_RE.split(title)[0].strip()


def _finding(signal_id: str, severity: str, message: str, recommendation: str) -> dict:
    return {
        "id": signal_id,
        "severity": severity,
        "message": message,
        "recommendation": recommendation,
    }


def _echo_remainder(core: str, description: str) -> str:
    """What the description says after it finishes restating the title."""
    return description[len(core):].strip(" -–—:|.")


def analyse(title: str, description: str, url: str | None = None) -> dict:
    """Score one title/description pair for templating signals."""
    title = (title or "").strip()
    description = (description or "").strip()

    result: dict = {
        "url": url,
        "title": title,
        "description": description,
        "templated": False,
        "severity": "none",
        "cta_phrase": None,
        "flags": [],
        "signals": [],
    }
    if not title or not description:
        result["flags"].append("missing-metadata")
        return result

    core = _title_core(title)
    core_n = _normalise(core)
    title_n = _normalise(title)
    description_n = _normalise(description)
    signals: list[dict] = result["signals"]

    # 1. Description opens by restating the title.
    echoes_title = (
        len(core_n) >= _MIN_TITLE_CHARS
        and description_n.startswith(core_n[:_ECHO_PREFIX_CHARS])
    )
    if echoes_title:
        cta_match = _CTA_TAIL_RE.search(_echo_remainder(core, description))
        if cta_match:
            result["templated"] = True
            result["cta_phrase"] = _normalise(cta_match.group(1))
            result["flags"].append("templated-metadata")
            signals.append(_finding(
                "templated_metadata", "high",
                "Meta description repeats the title verbatim and then closes with a "
                "stock call to action. Bulk metadata jobs emit this shape on every "
                "page at once, and site-wide templated metadata reads as scaled "
                "content abuse even when the body copy is original.",
                "Rewrite the description to say what the title does not: what the page "
                "does, for whom, and what makes it different. 150-160 characters, no "
                "stock CTA.",
            ))
        else:
            result["flags"].append("description-echoes-title")
            signals.append(_finding(
                "description_echoes_title", "medium",
                "Meta description opens with the exact text of the title, so the SERP "
                "snippet says the same thing twice.",
                "Open the description with information the title does not already "
                "carry.",
            ))

    # 2. Brand suffix concatenated into the description body.
    parts = _BRAND_SEPARATOR_RE.split(title)
    if len(parts) > 1:
        brand = parts[-1].strip()
        brand_n = _normalise(brand)
        if (
            _BRAND_MIN_CHARS <= len(brand) <= _BRAND_MAX_CHARS
            and brand_n
            and brand_n in description_n
            and not description.startswith(brand)
        ):
            result["flags"].append("brand-suffix-in-description")
            signals.append(_finding(
                "brand_suffix_in_description", "low",
                f"The title's brand suffix {brand!r} was concatenated into the meta "
                "description body. That is a generation artefact rather than a "
                "written sentence, and it spends SERP characters on your own name.",
                f"Remove {brand!r} from the description body; the title already "
                "carries it.",
            ))

    # 3. Description and title are the same string.
    if len(title_n) >= _MIN_TITLE_CHARS and description_n == title_n:
        result["flags"].append("description-duplicates-title")
        signals.append(_finding(
            "description_duplicates_title", "medium",
            "Meta description is identical to the title tag. Google has two SERP "
            "slots and both currently say the same thing.",
            "Write a description that expands on the title instead of repeating it.",
        ))

    order = {"high": 3, "medium": 2, "low": 1}
    if signals:
        result["severity"] = max((s["severity"] for s in signals), key=lambda s: order[s])
    return result


def analyse_pairs(pairs: Iterable[dict]) -> dict:
    """Roll single-page results up to the site level.

    ``pairs`` yields mappings with ``title`` and ``description`` keys and
    an optional ``url``. The site view is the operational unit: one
    templated description is an oversight, the same shape on a third of
    the site is the pattern Google's spam systems act on.
    """
    pages = [
        analyse(p.get("title", ""), p.get("description", ""), p.get("url"))
        for p in pairs
    ]
    templated = [p for p in pages if p["templated"]]
    checked = len(pages)
    ratio = len(templated) / checked if checked else 0.0

    shared: dict[str, int] = {}
    for page in templated:
        phrase = page["cta_phrase"]
        if phrase:
            shared[phrase] = shared.get(phrase, 0) + 1
    shared = dict(sorted(shared.items(), key=lambda kv: (-kv[1], kv[0])))

    site_flags: list[str] = []
    site_risk = "low"
    if len(templated) >= _SITE_MIN_TEMPLATED_PAGES and ratio >= _SITE_HIGH_RATIO:
        site_flags.append("site-wide-templated-metadata")
        site_risk = "high"
    elif len(templated) >= _SITE_MIN_TEMPLATED_PAGES and ratio >= _SITE_MEDIUM_RATIO:
        site_flags.append("templated-metadata-cluster")
        site_risk = "medium"
    elif templated:
        site_flags.append("templated-metadata-isolated")
    if any(count >= _SITE_MIN_TEMPLATED_PAGES for count in shared.values()):
        site_flags.append("shared-cta-tail")

    return {
        "pages": pages,
        "pages_checked": checked,
        "templated_count": len(templated),
        "templated_ratio": round(ratio, 3),
        "shared_cta_phrases": shared,
        "site_flags": site_flags,
        "site_risk": site_risk,
    }


def _load_pairs(path: str) -> list[dict]:
    """Read a JSON list of {url, title, description} objects.

    Also accepts ``parse_html.py`` output shape, where the description
    key is ``meta_description``.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("pages", [data])
    pairs = []
    for row in data:
        pairs.append({
            "url": row.get("url"),
            "title": row.get("title") or "",
            "description": row.get("description") or row.get("meta_description") or "",
        })
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Templated-metadata detector (title echo + stock CTA)."
    )
    parser.add_argument("--title", help="Title tag of a single page.")
    parser.add_argument("--description", help="Meta description of a single page.")
    parser.add_argument("--url", help="URL to label the single-page result with.")
    parser.add_argument(
        "--pairs-file",
        help="JSON list of {url, title, description} objects (parse_html.py "
             "output with meta_description is also accepted).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout.")
    parser.add_argument(
        "--fail-on",
        choices=("none", "any", "site"),
        default="none",
        help="Exit non-zero on any templated page ('any'), on a site-level "
             "flag ('site'), or never (default 'none').",
    )
    args = parser.parse_args()

    if args.pairs_file:
        pairs = _load_pairs(args.pairs_file)
    elif args.title is not None or args.description is not None:
        pairs = [{
            "url": args.url,
            "title": args.title or "",
            "description": args.description or "",
        }]
    else:
        print(
            "Error: pass --title/--description for one page, or --pairs-file "
            "for a site.",
            file=sys.stderr,
        )
        return 2

    result = analyse_pairs(pairs)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Pages checked:   {result['pages_checked']}")
        print(f"Templated pages: {result['templated_count']} "
              f"({result['templated_ratio']:.0%})")
        print(f"Site risk:       {result['site_risk']}")
        if result["site_flags"]:
            print(f"Site flags:      {', '.join(result['site_flags'])}")
        for phrase, count in result["shared_cta_phrases"].items():
            print(f"  shared CTA tail: {phrase!r} on {count} page(s)")
        print()
        for page in result["pages"]:
            if not page["signals"]:
                continue
            label = page["url"] or page["title"][:60]
            print(f"  {label}  [{page['severity']}]")
            for signal in page["signals"]:
                print(f"    {signal['severity']:<6} {signal['id']}")
                print(f"           {signal['message']}")

    if args.fail_on == "any" and result["templated_count"]:
        return 1
    if args.fail_on == "site" and result["site_risk"] in ("high", "medium"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
