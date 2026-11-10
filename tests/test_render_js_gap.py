"""render_page.js_gap: what a page only has after JavaScript ran.

js_gap is a pure function over two HTML strings (raw as served, rendered
DOM), so every test here runs without a browser or the network. The first
test is ported from web-obs (scripts/verify-browser-audit.py), where the
comparison was first written.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

pytest.importorskip("requests")
import render_page  # noqa: E402
from render_page import js_gap, js_gap_reasons  # noqa: E402

SHELL = "<html><head><title>App</title></head><body><p>one two</p></body></html>"
HYDRATED = (
    "<html><head><title>App</title>"
    '<script type="application/ld+json">{"@type": ["Organization", "Brand"]}</script></head>'
    "<body><h1>Title here</h1>"
    + "<p>word word word word word</p>" * 10
    + '<a href="/a">a</a>' * 6
    + "</body></html>"
)


def _page(head: str = "", body: str = "") -> str:
    filler = "<p>" + "steady server rendered copy " * 20 + "</p>"
    return f"<html><head>{head}</head><body>{filler}{body}</body></html>"


def test_js_gap_measures_words_links_schema_and_h1() -> None:
    gap = js_gap(SHELL, HYDRATED)
    assert gap["raw"]["words"] == 2
    assert gap["rendered"]["words"] == 58
    assert gap["rendered"]["links"] == 6
    assert gap["rendered"]["schema_types"] == ["Brand", "Organization"]
    diff = gap["diff"]
    assert diff["words_only_rendered"] == 58
    assert diff["words_only_rendered_share"] == 1.0
    assert diff["links_only_rendered"] == 6
    assert diff["links_only_rendered_share"] == 1.0
    assert diff["schema_types_only_rendered"] == ["Brand", "Organization"]
    assert diff["h1_only_rendered"] == ["Title here"]
    assert diff["title_changed"] is False
    assert gap["significant"] is True
    assert len(gap["reasons"]) == 4, gap["reasons"]
    assert gap["reasons"][0].startswith("100% of visible words appear only after JavaScript")
    assert gap["reasons"] == js_gap_reasons(gap)
    json.dumps(gap)  # the object goes straight into the CLI JSON


def test_identical_html_has_no_gap_and_no_reasons() -> None:
    gap = js_gap(HYDRATED, HYDRATED)
    assert gap["diff"]["words_only_rendered"] == 0
    assert gap["diff"]["words_only_rendered_share"] == 0.0
    assert gap["diff"]["links_only_rendered"] == 0
    assert gap["reasons"] == []
    assert gap["significant"] is False


def test_missing_side_means_no_render_and_returns_none() -> None:
    assert js_gap(None, HYDRATED) is None
    assert js_gap(SHELL, None) is None
    assert js_gap_reasons(None) == []


def test_empty_raw_body_is_compared_not_skipped() -> None:
    gap = js_gap("", HYDRATED)
    assert gap["raw"] == {
        "words": 0, "links": 0, "schema_types": [], "h1": [], "title": None,
        "canonical": None, "canonical_all": [], "meta_robots": None,
    }
    assert gap["diff"]["words_only_rendered_share"] == 1.0
    assert gap["diff"]["title_changed"] is True


def test_title_canonical_and_robots_changes_are_flagged() -> None:
    raw = _page(
        "<title>Server title</title>"
        '<link rel="canonical" href="https://shop.example/a">'
        '<meta name="robots" content="noindex">'
    )
    rendered = _page(
        "<title>Client title</title>"
        '<link rel="canonical" href="https://shop.example/b">'
        '<meta name="robots" content="index, follow">'
    )
    gap = js_gap(raw, rendered)
    assert gap["raw"]["canonical"] == "https://shop.example/a"
    assert gap["rendered"]["canonical"] == "https://shop.example/b"
    assert gap["raw"]["meta_robots"] == "noindex"
    assert gap["rendered"]["meta_robots"] == "index, follow"
    assert gap["diff"]["title_changed"] is True
    assert gap["diff"]["canonical_changed"] is True
    assert gap["diff"]["meta_robots_changed"] is True
    # Same words and links on both sides: only the three head tags differ.
    assert gap["diff"]["words_only_rendered"] == 0
    assert gap["significant"] is True
    assert gap["reasons"] == [
        "the title is not the same before and after JavaScript "
        "(raw: 'Server title', rendered: 'Client title')",
        "the canonical URL is not the same before and after JavaScript "
        "(raw: 'https://shop.example/a', rendered: 'https://shop.example/b')",
        "the meta robots value is not the same before and after JavaScript "
        "(raw: 'noindex', rendered: 'index, follow')",
    ]


def test_head_tags_added_only_by_javascript_count_as_changed() -> None:
    rendered = _page(
        "<title>Client title</title>"
        '<link rel="canonical" href="https://shop.example/b">'
        '<meta name="robots" content="noindex">'
    )
    gap = js_gap(_page(), rendered)
    assert gap["diff"]["title_changed"] is True
    assert gap["diff"]["canonical_changed"] is True
    assert gap["diff"]["meta_robots_changed"] is True
    assert "(raw: none, rendered: 'noindex')" in gap["reasons"][-1]


def test_second_canonical_injected_by_javascript_is_a_change() -> None:
    first = '<link rel="canonical" href="https://shop.example/a">'
    gap = js_gap(
        _page(first),
        _page(first + '<link href="https://shop.example/b" rel="alternate CANONICAL">'),
    )
    assert gap["rendered"]["canonical"] == "https://shop.example/a"
    assert gap["rendered"]["canonical_all"] == [
        "https://shop.example/a", "https://shop.example/b",
    ]
    assert gap["diff"]["canonical_changed"] is True
    assert "'https://shop.example/a | https://shop.example/b'" in gap["reasons"][0]


def test_robots_directive_order_case_and_split_tags_are_not_a_change() -> None:
    raw = _page('<meta name="ROBOTS" content="NOINDEX,nofollow">')
    rendered = _page(
        '<meta name="robots" content="nofollow"><meta name="robots" content=" noindex ">'
    )
    gap = js_gap(raw, rendered)
    assert gap["raw"]["meta_robots"] == "noindex, nofollow"
    assert gap["rendered"]["meta_robots"] == "nofollow, noindex"
    assert gap["diff"]["meta_robots_changed"] is False
    assert gap["reasons"] == []


def test_replaced_copy_counts_even_when_the_word_total_is_equal() -> None:
    raw = "<html><body><p>" + "loading " * 40 + "</p></body></html>"
    rendered = "<html><body><p>" + "product " * 40 + "</p></body></html>"
    gap = js_gap(raw, rendered)
    assert gap["raw"]["words"] == gap["rendered"]["words"] == 40
    assert gap["diff"]["words_only_rendered"] == 40
    assert gap["significant"] is True


def test_links_are_matched_by_href_and_non_links_are_ignored() -> None:
    raw = _page(body='<a href="/a">a</a><a href="/b">b</a>')
    rendered = _page(
        body='<a href="/a">a</a><a href="/b">b</a><a href="/c">c</a>'
        '<a href="#top">top</a><a href="javascript:void(0)">x</a>'
        '<a href="mailto:a@b.example">m</a><a>no href</a>'
    )
    gap = js_gap(raw, rendered)
    assert gap["raw"]["links"] == 2
    assert gap["rendered"]["links"] == 3
    assert gap["diff"]["links_only_rendered"] == 1
    assert gap["diff"]["links_only_rendered_share"] == 0.333


def test_significance_thresholds_are_the_named_constants(monkeypatch) -> None:
    raw = "<html><body><p>" + "base " * 100 + "</p></body></html>"
    rendered = (
        "<html><body><p>" + "base " * 100 + "extra " * 20 + "</p>"
        '<a href="/1">1</a><a href="/2">2</a></body></html>'
    )
    gap = js_gap(raw, rendered)
    # 22 of 122 words (18%) and 2 links: under every default limit.
    assert gap["diff"]["words_only_rendered"] == 22
    assert gap["reasons"] == []

    monkeypatch.setattr(render_page, "JS_GAP_WORDS_SHARE", 0.10)
    monkeypatch.setattr(render_page, "JS_GAP_WORDS_MIN", 10)
    monkeypatch.setattr(render_page, "JS_GAP_LINKS_MIN", 2)
    reasons = js_gap_reasons(gap)
    assert len(reasons) == 2
    assert reasons[0].startswith("18% of visible words")
    assert reasons[1].startswith("2 of 2 links appear only after JavaScript")


def test_a_few_new_words_on_a_tiny_page_are_not_significant() -> None:
    gap = js_gap(
        "<html><body><p>hello</p></body></html>",
        "<html><body><p>hello there dear visitor</p></body></html>",
    )
    assert gap["diff"]["words_only_rendered_share"] == 0.75
    assert gap["significant"] is False


def test_non_visible_markup_is_not_counted_as_words_links_or_title() -> None:
    html = (
        "<html><head><title>Real title</title><style>.a{color:red}</style></head><body>"
        "<svg><title>Icon name</title></svg>"
        "<script>var hidden = 'one two three';</script>"
        '<noscript><h1>No script</h1><a href="/ns">enable js</a></noscript>'
        '<template><h1>Tpl</h1><a href="/tpl">tpl</a></template>'
        "<h1>Seen</h1><p>four visible words here</p></body></html>"
    )
    signals = js_gap(html, html)["raw"]
    assert signals["title"] == "Real title"
    assert signals["h1"] == ["Seen"]
    assert signals["links"] == 0
    assert signals["words"] == 5


def test_svg_title_alone_is_not_a_document_title() -> None:
    signals = js_gap("<body><svg><title>Icon</title></svg></body>", "")["raw"]
    assert signals["title"] is None


def test_h1_change_and_removed_tags_are_reported() -> None:
    gap = js_gap(
        _page("<title>T</title>", "<h1>Old heading</h1>"),
        _page("", "<h1>New   heading</h1>"),
    )
    assert gap["diff"]["h1_only_rendered"] == ["New heading"]
    assert gap["reasons"] == [
        "the H1 changes after JavaScript",
        "the title is not the same before and after JavaScript (raw: 'T', rendered: none)",
    ]


def test_output_is_bounded_for_hostile_pages() -> None:
    hostile = (
        "<html><head><title>" + "t" * 5000 + "</title>"
        + "".join(f'<link rel="canonical" href="https://x.example/{i}">' for i in range(40))
        + '<meta name="robots" content="' + ",".join(f"d{i}" for i in range(500)) + '">'
        + '<script type="application/ld+json">['
        + ",".join('{"@type":"T%d"}' % i for i in range(60))
        + "]</script></head><body>"
        + "".join(f"<h1>Heading {i}</h1>" for i in range(60))
        + "</body></html>"
    )
    gap = js_gap("", hostile, raw_truncated=True)
    rendered = gap["rendered"]
    assert len(rendered["title"]) == render_page.JS_GAP_MAX_TEXT
    assert len(rendered["h1"]) == render_page.JS_GAP_MAX_ITEMS
    assert len(rendered["schema_types"]) == render_page.JS_GAP_MAX_ITEMS
    assert len(rendered["canonical_all"]) == render_page.JS_GAP_MAX_CANONICALS
    assert len(rendered["meta_robots"].split(", ")) == render_page.JS_GAP_MAX_ITEMS
    assert gap["raw_truncated"] is True
    assert all(len(reason) < 400 for reason in gap["reasons"])


def test_malformed_json_ld_and_markup_do_not_raise() -> None:
    broken = (
        '<html><head><script type="application/ld+json">{"@type": </script>'
        "<link rel=canonical><meta name=robots><title></title></head>"
        "<body><h1></h1><a href=''>x</a><p>unclosed"
    )
    gap = js_gap(broken, broken)
    assert gap["raw"]["schema_types"] == []
    assert gap["raw"]["canonical"] is None
    assert gap["raw"]["meta_robots"] is None
    assert gap["raw"]["title"] is None
    assert gap["reasons"] == []
