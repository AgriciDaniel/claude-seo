"""Regression guards for crawler-gated structured data guidance (issue #518).

Some hosted e-commerce platforms serve Product/Offer structured data only to
verified search-engine crawlers (checked by IP / reverse DNS), so browser
fetches, third-party validators, and spoofed Googlebot/YandexBot User-Agent
headers see navigation markup only.

The seo-schema skill and agent, seo-audit's Schema & Structured Data section,
and seo-ecommerce's schema-completeness scoring must instruct the auditor to
verify with a search-engine-operated fetcher before reporting markup as absent
and to report "not visible to non-crawler fetches; unverified for crawlers"
until then.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SEO_SCHEMA_SKILL = REPO_ROOT / "skills" / "seo-schema" / "SKILL.md"
SEO_SCHEMA_AGENT = REPO_ROOT / "agents" / "seo-schema.md"
SEO_AUDIT_SKILL = REPO_ROOT / "skills" / "seo-audit" / "SKILL.md"
SEO_ECOMMERCE_SKILL = REPO_ROOT / "skills" / "seo-ecommerce" / "SKILL.md"
SEO_ECOMMERCE_AGENT = REPO_ROOT / "agents" / "seo-ecommerce.md"

UNVERIFIED_STATUS = "not visible to non-crawler fetches; unverified for crawlers"


def _norm(text: str) -> str:
    """Collapse whitespace runs so prose rewraps do not break assertions."""
    return re.sub(r"\s+", " ", text).lower()


def _section(text: str, heading: str, next_heading: str) -> str:
    start = text.index(heading)
    end = text.index(next_heading, start + len(heading))
    return _norm(text[start:end])


def test_seo_schema_detection_guards_against_crawler_gated_false_positives() -> None:
    raw = SEO_SCHEMA_SKILL.read_text(encoding="utf-8")
    detection = _section(raw, "## Detection", "## Validation")
    assert "hosted e-commerce" in detection
    assert "bot-only" in detection
    assert "search console url inspection" in detection
    assert "rich results test" in detection
    assert UNVERIFIED_STATUS in detection
    assert "user-agent spoofing is not a substitute" in detection


def test_seo_schema_error_handling_mirrors_crawler_gated_caveat() -> None:
    raw = SEO_SCHEMA_SKILL.read_text(encoding="utf-8")
    error_handling = _section(raw, "## Error Handling", "## Security")
    assert UNVERIFIED_STATUS in error_handling
    assert "user-agent spoofing is not a substitute" in error_handling


def test_seo_schema_agent_mirrors_crawler_gated_caveat() -> None:
    text = _norm(SEO_SCHEMA_AGENT.read_text(encoding="utf-8"))
    assert "hosted e-commerce" in text
    assert "search console url inspection" in text
    assert "rich results test" in text
    assert UNVERIFIED_STATUS in text
    assert "user-agent spoofing" in text


def test_seo_audit_schema_category_mirrors_crawler_gated_caveat() -> None:
    raw = SEO_AUDIT_SKILL.read_text(encoding="utf-8")
    schema_section = _section(raw, "### Schema & Structured Data", "### Performance")
    assert "hosted e-commerce" in schema_section
    assert "search console url inspection" in schema_section
    assert "rich results test" in schema_section
    assert UNVERIFIED_STATUS in schema_section
    assert "user-agent spoofing is not a substitute" in schema_section


def test_seo_ecommerce_schema_scoring_mirrors_crawler_gated_caveat() -> None:
    raw = SEO_ECOMMERCE_SKILL.read_text(encoding="utf-8")
    scoring = _section(raw, "### Schema Scoring", "## Cross-Skill Integration")
    assert "hosted e-commerce" in scoring
    assert "search console url inspection" in scoring
    assert "rich results test" in scoring
    assert UNVERIFIED_STATUS in scoring
    assert "user-agent spoofing is not a substitute" in scoring

    error_handling = _section(raw, "## Error Handling", "## Output Template")
    assert UNVERIFIED_STATUS in error_handling


def test_seo_ecommerce_agent_mirrors_crawler_gated_caveat() -> None:
    text = _norm(SEO_ECOMMERCE_AGENT.read_text(encoding="utf-8"))
    assert "hosted e-commerce" in text
    assert "search console url inspection" in text
    assert "rich results test" in text
    assert UNVERIFIED_STATUS in text
    assert "user-agent spoofing is not a substitute" in text
