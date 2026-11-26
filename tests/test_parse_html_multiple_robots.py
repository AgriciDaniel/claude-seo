"""Separate robots meta tags combine their directives instead of overriding."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("bs4")
pytest.importorskip("requests")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import drift_compare  # noqa: E402
import parse_html  # noqa: E402
import verify_backlinks  # noqa: E402


def _document(values):
    meta = "".join(f'<meta name="robots" content="{value}">' for value in values)
    return (f"<html><head>{meta}</head><body>"
            '<a href="https://target.example/article">A useful article</a></body></html>')


@pytest.mark.parametrize("values,expected", [
    (["noindex", "follow"], "noindex, follow"),
    (["follow", "noindex"], "follow, noindex"),
    (["nofollow", "index"], "nofollow, index"),
    (["none", "max-image-preview: large"], "none, max-image-preview: large"),
    (["noindex", "", "follow"], "noindex, follow"),
    (["", "noindex", ""], "noindex"),
    ([], None),
    ([""], ""),
    ([" index, follow "], " index, follow "),
])
def test_parser_retains_all_generic_robot_directives(values, expected):
    result = parse_html.parse_html(_document(values))
    assert result["meta_robots"] == expected


@pytest.mark.parametrize("values", [["noindex", "follow"], ["follow", "noindex"]])
def test_drift_detects_noindex_regardless_of_meta_order(values):
    parsed = parse_html.parse_html(_document(values))
    result = drift_compare.rule_04_noindex_added({"robots": "index, follow"}, parsed)
    assert result["triggered"] is True
    assert "noindex" in result["new_value"]


@pytest.mark.parametrize("restriction", ["nofollow", "none"])
@pytest.mark.parametrize("later", ["index, follow", "noindex", ""])
def test_backlink_verification_keeps_page_nofollow(monkeypatch, restriction, later):
    source = "https://source.example/post"
    monkeypatch.setattr(verify_backlinks, "validate_url", lambda value: True)
    monkeypatch.setattr(verify_backlinks, "_polite_delay", lambda value: None)
    monkeypatch.setattr(verify_backlinks, "_head_check", lambda *args, **kwargs: {
        "status_code": 200, "exists": True, "redirect_url": None, "error": None,
    })
    monkeypatch.setattr(verify_backlinks, "fetch_page", lambda *args, **kwargs: {
        "url": source, "status_code": 200, "error": None, "headers": {},
        "content": _document([restriction, later]),
    })
    result = verify_backlinks.verify_single_backlink(source, "https://target.example/article")
    assert result["status"] == "verified"
    assert result["match_type"] == "exact_url"
    assert result["page_nofollow"] is True
    assert result["rel_attributes"] == ["follow"]


def test_case_insensitive_generic_tags_do_not_absorb_bot_specific_rules():
    markup = ('<meta name="ROBOTS" content="nofollow">'
              '<meta name="robots" content="max-image-preview: large">'
              '<meta name="googlebot" content="noindex">')
    result = parse_html.parse_html(markup)
    assert result["meta_robots"] == "nofollow, max-image-preview: large"
