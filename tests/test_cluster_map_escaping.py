"""The cluster map template escapes every SERP-derived field it puts in HTML.

Titles, keywords, statuses and link ids come from search results the user
does not control; the template builds markup by string concatenation and
assigns it to innerHTML, so each such field must go through escapeHtml (or
be coerced to a number or checked against an allowlist).
"""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "skills" / "seo-cluster" / "templates" / "cluster-map.html"
SKILL = TEMPLATE.parents[1] / "SKILL.md"
DATA_FIELD = re.compile(r"\b(?:link|info|post|cluster|data\.pillar)\.[A-Za-z]+")


def _concatenated_expressions(text: str) -> list[str]:
    """Every expression spliced between two string pieces: '...' + EXPR + '...'."""
    marked = re.sub(r"'[^'\n]*'", "\x00", text)  # each single-quoted literal -> one marker
    return [m.strip() for m in re.findall(r"(?=\x00\s*\+\s*([^\x00]+?)\s*\+\s*\x00)", marked)]


def test_every_data_field_in_markup_is_escaped_or_coerced() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    unsafe = [
        expr for expr in _concatenated_expressions(text)
        if DATA_FIELD.search(expr) and not expr.startswith(("escapeHtml(", "(Number("))
    ]
    assert unsafe == []


def test_escape_helper_covers_attribute_quotes() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    body = text[text.index("function escapeHtml"):text.index("function safeColor")]
    for entity in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
        assert entity in body


def test_colors_and_link_types_are_allowlisted() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "safeColor(cluster.color" in text
    assert "/^#[0-9a-fA-F]{6}$/" in text
    assert 'LINK_TYPES.indexOf(link.type)' in text
    assert '"link-line " + link.type' not in text


def test_skill_tells_the_model_to_escape_less_than_in_the_data() -> None:
    assert "\\u003c" in SKILL.read_text(encoding="utf-8")
