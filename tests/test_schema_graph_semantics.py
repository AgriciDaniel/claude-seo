"""A `@graph` document must be read the same way by the seo-schema path and by
the post-edit hook.

`hooks/validate-schema.py` already treats a top-level `@graph` container as a
container rather than an entity: the container needs no `@type`, and its
entries inherit the `@context` the document declares (see
`test_valid_top_level_graph_does_not_require_container_type` in
`tests/test_schema_hook_policy.py`).

The seo-schema path did not agree. `scripts/parse_html.py` flattened the
graph and dropped the document's `@context`, so every entry came out as a
block with an `@type` but no `@context`, and the skill and the agent told
Claude to flag exactly that as broken markup. A valid graph document was
reported as broken on every one of its entries.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from parse_html import parse_html  # noqa: E402

SKILL = REPO_ROOT / "skills" / "seo-schema" / "SKILL.md"
AGENT = REPO_ROOT / "agents" / "seo-schema.md"
HOOK = REPO_ROOT / "hooks" / "validate-schema.py"

GRAPH_HTML = (
    "<html><head><title>t</title>"
    '<script type="application/ld+json">'
    '{"@context":"https://schema.org","@graph":['
    '{"@type":"Organization","@id":"#org","name":"Acme"},'
    '{"@type":"WebSite","name":"Acme","publisher":{"@id":"#org"}}'
    "]}</script></head><body><h1>x</h1></body></html>"
)


def _load_hook():
    """Import the hook module, whose filename cannot be used as an import name."""
    spec = importlib.util.spec_from_file_location("validate_schema", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _norm(text: str) -> str:
    """Collapse whitespace runs, so a rewrap of the prose does not break a match.

    Doc prose gets rewrapped whenever a nearby line is edited; asserting
    against the literal wrapped string breaks on every unrelated reflow.
    Matching at sentence level, over normalised whitespace, survives that
    churn while still failing if the actual claim goes missing.
    """
    return re.sub(r"\s+", " ", text).lower()


def _schema_blocks(entries: list) -> str:
    """Rebuild the HTML of the entries parse_html reported, one block each."""
    return (
        "<html><head>"
        + "".join(
            '<script type="application/ld+json">'
            + json.dumps(entry, ensure_ascii=False)
            + "</script>"
            for entry in entries
        )
        + "</head></html>"
    )


def test_graph_entries_inherit_the_document_context() -> None:
    """The flattened entries keep the @context the @graph document declared."""
    result = parse_html(GRAPH_HTML)
    assert [entry["@type"] for entry in result["schema"]] == ["Organization", "WebSite"]
    assert all(entry["@context"] == "https://schema.org" for entry in result["schema"])


def test_graph_entry_keeps_its_own_context() -> None:
    html = (
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@graph":['
        '{"@type":"Organization","@context":"https://example.org/ctx"}]}'
        "</script>"
    )
    result = parse_html(html)
    assert result["schema"] == [
        {"@type": "Organization", "@context": "https://example.org/ctx"}
    ]


def test_graph_document_without_context_is_not_given_one() -> None:
    """A document that declares no @context still has to be reportable."""
    html = (
        '<script type="application/ld+json">'
        '{"@graph":[{"@type":"Organization","name":"Acme"}]}'
        "</script>"
    )
    result = parse_html(html)
    assert result["schema"] == [{"@type": "Organization", "name": "Acme"}]


def test_non_graph_schema_blocks_are_untouched() -> None:
    html = (
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"Article","headline":"h"}'
        "</script>"
    )
    result = parse_html(html)
    assert result["schema"] == [
        {"@context": "https://schema.org", "@type": "Article", "headline": "h"}
    ]


def test_reported_graph_entries_pass_the_post_edit_hook() -> None:
    """What the seo-schema path reports has to satisfy the hook that accepts graphs."""
    hook = _load_hook()
    result = parse_html(GRAPH_HTML)
    assert hook.validate_jsonld(_schema_blocks(result["schema"])) == []


def test_seo_schema_skill_states_the_graph_rule() -> None:
    text = _norm(SKILL.read_text(encoding="utf-8"))
    assert "@graph" in text
    assert "not an entity" in text
    assert "inherit" in text


def test_seo_schema_agent_states_the_graph_rule() -> None:
    text = _norm(AGENT.read_text(encoding="utf-8"))
    assert "@graph" in text
    assert "inherit" in text
