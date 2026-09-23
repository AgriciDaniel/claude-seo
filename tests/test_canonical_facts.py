"""Known-wrong statements that must not come back (audit of 2026-09-23).

Each pair is a phrase that was found in the skill text, and the primary source
that disproved it. The scan covers every instruction file a model loads:
skills, agents, extension skills and agents, and the shared references.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = [*ROOT.glob("skills/**/*.md"), *ROOT.glob("agents/*.md"),
         *ROOT.glob("extensions/*/skills/**/*.md"), *ROOT.glob("extensions/*/agents/*.md")]

WRONG = [
    # (regex, why it is wrong, primary source)
    (r"\|\s*Book Actions\s*\|\s*Deprecated", "Book actions banner removed 2025-11-05",
     "developers.google.com/search/updates"),
    (r"LCP [Ss]ubparts \(February 2025", "January 2025 CrUX release, published 2025-02-11",
     "developer.chrome.com/docs/crux/release-notes"),
    (r"(?i)resource load time", "the subpart is 'resource load duration'",
     "web.dev/articles/optimize-lcp"),
    (r"GA4 4\.x", "GA4 has no 4.x version", "developers.google.com/tag-platform"),
    (r"eu_data_collection_disabled", "no such GA4 field", "GA4 Admin API reference"),
    (r"Sept 2025 QRG addition", "generative-AI guidance predates the Sept 2025 QRG",
     "guidelines.raterhub.com"),
    (r"Rolling out to a subset of properties", "gen-AI report reached all sites 2026-08-31",
     "developers.google.com/search/blog/2026/06/gen-ai-performance-reports"),
    (r"AEO and GEO are rebranded labels", "not a quote from Google's guide",
     "developers.google.com/search/docs/fundamentals/ai-optimization-guide"),
    (r"The guide also covers \*\*WebMCP", "the AI optimization guide never mentions WebMCP",
     "developers.google.com/search/docs/fundamentals/ai-optimization-guide"),
    (r"Privacy Sandbox APIs are still available", "most were retired 2025-10-17",
     "privacysandbox.google.com/blog"),
    (r"GBP Q&A is active where available", "Q&A API discontinued 2025-11-03",
     "developers.google.com/my-business/content/sunset-dates"),
    (r"Content API for Shopping sunsets August 18, 2026", "it was sunset; requests now fail",
     "developers.google.com/merchant/api/guides/compatibility/overview"),
    (r"custom version of Gemini 2\.5", "AI Mode default is Gemini 3.5 Flash since 2026-05-19",
     "blog.google/products-and-platforms/products/search/search-io-2026"),
    (r"(?i)optimal passage length", "a third-party heuristic, not a Google rule",
     "developers.google.com/search/docs/fundamentals/ai-optimization-guide"),
    (r"AI crawlers do NOT execute JavaScript", "Googlebot renders JS and feeds AI features",
     "developers.google.com/search/docs/crawling-indexing/javascript"),
    (r"(?i)(aggregator|supplier) units?[^.;|]*(South Africa|Turkiye|Türkiye)|(South Africa|Turkiye|Türkiye)[^.;|]*(aggregator|supplier) units?", "aggregator and supplier units are EEA-only",
     "developers.google.com/search/docs/appearance/aggregator-features"),
    (r"ignore robots\.txt by design", "Google's docs say 'generally ignore robots.txt rules'",
     "developers.google.com/crawling/docs/crawlers-fetchers/google-user-triggered-fetchers"),
    (r"(?i)M157|milestone 157", "no WebMCP ship milestone is announced", "chromestatus 5117755740913664"),
    (r"Google (has said it )?does not act on (Content-Signal|it)", "no Google statement exists",
     "developers.google.com/crawling/docs/robots-txt/robots-txt-spec"),
    (r"ucp\.dev lists (\*\*)?2026-04-08(\*\*)? as the latest", "ucp.dev latest is 2026-08-25", "ucp.dev/versions.json"),
    (r"GBP Q&A remains available", "Q&A API discontinued 2025-11-03",
     "developers.google.com/my-business/content/sunset-dates"),
    (r"Project Mariner\)", "Mariner's status is secondary-only; describe Google-Agent by function",
     "developers.google.com/crawling"),
]


@pytest.mark.parametrize("pattern,why,source", WRONG)
def test_known_wrong_statement_is_absent(pattern: str, why: str, source: str) -> None:
    rx = re.compile(pattern)
    hits = [f"{p.relative_to(ROOT)}:{n}"
            for p in FILES
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if rx.search(line)]
    assert not hits, f"{why} ({source}): {hits}"


def test_notebooklm_is_only_named_as_the_former_token() -> None:
    hits = [f"{p.relative_to(ROOT)}:{n}"
            for p in FILES
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if "Google-NotebookLM" in line and not re.search(r"formerly|replaced|former", line)]
    assert not hits, f"use Google-GeminiNotebook (renamed 2026-07-16): {hits}"
