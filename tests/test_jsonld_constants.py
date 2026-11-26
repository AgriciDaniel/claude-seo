"""JSON-LD syntax follows JSON rather than Python's non-finite extensions."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import page_checks  # noqa: E402
import parse_html  # noqa: E402

URL = "https://example.com/products/coffee"


@pytest.fixture(params=["html.parser", "lxml"])
def parser(request, monkeypatch):
    if request.param == "lxml":
        pytest.importorskip("lxml")
    monkeypatch.setattr(page_checks, "_HTML_PARSER", request.param)
    monkeypatch.setattr(parse_html, "_HTML_PARSER", request.param)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_constants_are_invalid_blocks(parser, constant):
    raw = '{"@type":"Product","offers":{"price":' + constant + '}}'
    html = f'<script type="application/ld+json">{raw}</script>'

    parsed = parse_html.parse_html(html, URL)
    assert parsed["schema"] == []
    assert parsed["schema_invalid"]["count"] == 1
    assert parsed["schema_invalid"]["samples"] == [raw]
    json.dumps(parsed, allow_nan=False)

    checked = page_checks.run_checks(html, URL)
    assert checked["facts"]["jsonld_blocks"] == 1
    assert checked["facts"]["jsonld_invalid"] == 1
    assert any(item["id"] == "invalid-jsonld" for item in checked["findings"])


def test_constant_names_inside_strings_remain_valid(parser):
    payload = {"@type": "Product", "name": "NaN Infinity -Infinity", "offers": {"price": 0.0}}
    raw = json.dumps(payload)
    html = f'<script type="application/ld+json">{raw}</script>'

    parsed = parse_html.parse_html(html, URL)
    assert parsed["schema"] == [payload]
    assert parsed["schema_invalid"]["count"] == 0
    assert page_checks.run_checks(html, URL)["facts"]["jsonld_invalid"] == 0


def test_invalid_block_does_not_discard_other_valid_blocks(parser):
    html = ('<script type="application/ld+json">{"value":NaN}</script>'
            '<script type="application/ld+json">{"@type":"Article"}</script>')

    parsed = parse_html.parse_html(html, URL)
    assert parsed["schema"] == [{"@type": "Article"}]
    assert parsed["schema_invalid"]["count"] == 1
    checked = page_checks.run_checks(html, URL)
    assert (checked["facts"]["jsonld_blocks"], checked["facts"]["jsonld_invalid"]) == (2, 1)
