"""JSON-LD permits one node object as the value of @graph."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from parse_html import parse_html  # noqa: E402

spec = importlib.util.spec_from_file_location("singleton_graph_hook", ROOT / "hooks" / "validate-schema.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def html(payload):
    return '<script type="application/ld+json">' + json.dumps(payload) + "</script>"


@pytest.mark.parametrize("graph_as_list", [False, True])
def test_singleton_graph_is_extracted_with_context(graph_as_list):
    node = {"@type": "Organization", "name": "Example"}
    payload = {"@context": "https://schema.org", "@graph": [node] if graph_as_list else node}
    result = parse_html(html(payload))
    assert result["schema"] == [{**node, "@context": "https://schema.org"}]
    assert result["schema_invalid"]["count"] == 0
    assert hook.validate_jsonld(html(payload)) == []


def test_singleton_node_keeps_its_own_context():
    node = {"@type": "Organization", "@context": "https://example.org/context"}
    result = parse_html(html({"@context": "https://schema.org", "@graph": node}))
    assert result["schema"] == [node]


def test_singleton_without_document_context_does_not_gain_one():
    node = {"@type": "Organization"}
    assert parse_html(html({"@graph": node}))["schema"] == [node]


def test_hook_checks_deprecated_type_in_singleton_graph():
    errors = hook.validate_jsonld(html({"@context": "https://schema.org", "@graph": {"@type": "HowTo"}}))
    assert any("HowTo" in error and "deprecated" in error for error in errors)
    assert not any("@graph must" in error or "Missing @context" in error for error in errors)


def test_hook_requires_type_on_singleton_node():
    errors = hook.validate_jsonld(html({"@context": "https://schema.org", "@graph": {"name": "Example"}}))
    assert errors == ["Block 1: Missing @type"]


@pytest.mark.parametrize("invalid", ["Organization", 7, True, None])
def test_invalid_graph_shape_is_reported(invalid):
    payload = {"@context": "https://schema.org", "@graph": invalid}
    result = parse_html(html(payload))
    assert result["schema"] == []
    assert result["schema_invalid"]["count"] == 1
    assert any("@graph must" in error for error in hook.validate_jsonld(html(payload)))
