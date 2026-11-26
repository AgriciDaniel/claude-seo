"""Canonical drift compares the target resolved by the document base URL."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import drift_baseline  # noqa: E402
import parse_html as parser  # noqa: E402
from drift_compare import rule_02_canonical_changed  # noqa: E402

PAGE = "https://example.com/articles/draft"


@pytest.mark.parametrize("html_parser", ["lxml", "html.parser"])
@pytest.mark.parametrize(("base", "href", "expected"), [
    ("", "/guide", "https://example.com/guide"),
    ("", "guide", "https://example.com/articles/guide"),
    ("", "//other.example/guide", "https://other.example/guide"),
    ('<base href="/published/">', "guide", "https://example.com/published/guide"),
    ('<base href="https://other.example/docs/">', "../guide", "https://other.example/guide"),
    ('<base href="/first/"><base href="/second/">', "guide", "https://example.com/first/guide"),
    ('<base href="http://[invalid">', "guide", "https://example.com/articles/guide"),
    ('<base href="/published/">', "https://other.example/guide", "https://other.example/guide"),
])
def test_canonical_uses_the_document_base(monkeypatch, html_parser, base, href, expected):
    monkeypatch.setattr(parser, "_HTML_PARSER", html_parser)
    html = f'<html><head>{base}<link rel="canonical" href="{href}"></head></html>'
    result = parser.parse_html(html, PAGE)
    assert result["canonical"] == expected
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("href", ["", "  ", "http://[invalid", "mailto:editor@example.com"])
def test_empty_or_unusable_canonicals_remain_visible(href):
    result = parser.parse_html(f'<link rel="canonical" href="{href}">', PAGE)
    assert result["canonical"] == href


def test_relative_canonical_without_a_base_is_retained():
    assert parser.parse_html('<link rel="canonical" href="guide">')["canonical"] == "guide"
    assert parser.parse_html('<link rel="canonical">', PAGE)["canonical"] is None


def test_drift_detects_a_changed_base_for_the_same_relative_canonical():
    old = parser.parse_html('<base href="/before/"><link rel="canonical" href="guide">', PAGE)
    new = parser.parse_html('<base href="/after/"><link rel="canonical" href="guide">', PAGE)
    finding = rule_02_canonical_changed(old, new)
    assert finding["triggered"]
    assert finding["old_value"] == "https://example.com/before/guide"
    assert finding["new_value"] == "https://example.com/after/guide"


def test_drift_ignores_equivalent_relative_and_absolute_canonicals():
    old = parser.parse_html('<link rel="canonical" href="/guide">', PAGE)
    new = parser.parse_html('<link rel="canonical" href="https://example.com/guide">', PAGE)
    assert not rule_02_canonical_changed(old, new)["triggered"]


def test_fetch_parse_handoff_uses_the_final_page_url(monkeypatch):
    real_run = subprocess.run

    def fetch_fixture_or_run_parser(command, **kwargs):
        if command[1].endswith("fetch_page.py"):
            Path(command[command.index("--output") + 1]).write_text(
                '<html><head><link rel="canonical" href="guide"></head></html>',
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr=(
                "Status: 200\nURL: https://example.com/published/article\n"
            ))
        return real_run(command, **kwargs)

    monkeypatch.setattr(drift_baseline.subprocess, "run", fetch_fixture_or_run_parser)
    result = drift_baseline.fetch_page_data(PAGE)
    assert result["error"] is None
    assert result["parsed"]["canonical"] == "https://example.com/published/guide"
