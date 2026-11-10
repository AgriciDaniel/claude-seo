"""
Tests for whitespace around inline tags in scripts/parse_html.py.

Background: headings, link text and the title were read with
`get_text(strip=True)`. bs4 strips each text node before joining them, so the
spaces next to inline tags such as <em>, <strong>, <a> and <b> disappeared
("for <em>every</em> dollar" became "foreverydollar"), and newlines inside a
multi-line heading were kept. Every consumer of the headings and anchor text
(keyword checks, duplicate-heading detection, drift baselines) saw the glued
text.
"""
import sys
from pathlib import Path

# Make scripts/ importable without requiring it to be a package
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from parse_html import parse_html  # noqa: E402


def test_h1_keeps_spaces_around_inline_emphasis():
    html = "<h1>Free money calculators for <em>every</em> dollar question.</h1>"
    result = parse_html(html)
    assert result["h1"] == ["Free money calculators for every dollar question."]


def test_h2_keeps_spaces_around_strong_and_link():
    html = '<h2>Save <strong>more</strong>, spend <a href="/x">less</a></h2>'
    result = parse_html(html)
    assert result["h2"] == ["Save more, spend less"]


def test_link_text_keeps_spaces_around_inline_tags():
    html = '<a href="/tools/">Browse all <b>46</b> calculators</a>'
    result = parse_html(html, base_url="https://example.com/")
    assert [link["text"] for link in result["links"]["internal"]] == [
        "Browse all 46 calculators"
    ]


def test_multiline_heading_collapses_whitespace():
    html = "<h3>\n  Multi-line\n  heading  </h3>"
    result = parse_html(html)
    assert result["h3"] == ["Multi-line heading"]


def test_multiline_title_collapses_whitespace():
    html = "<html><head><title>\n  Acme\n  Tools  </title></head></html>"
    result = parse_html(html)
    assert result["title"] == "Acme Tools"


def test_link_text_is_still_capped_at_100_characters():
    html = '<a href="/long">' + "word " * 40 + "</a>"
    result = parse_html(html, base_url="https://example.com/")
    text = result["links"]["internal"][0]["text"]
    assert len(text) == 100
    assert text == ("word " * 20)[:100]


def test_br_separates_words_in_headings():
    html = "<h1>Foo<br>Bar</h1><h2>Fast<br/>Cheap<br />Good</h2><h3>One <br> Two</h3>"
    result = parse_html(html)
    assert result["h1"] == ["Foo Bar"]
    assert result["h2"] == ["Fast Cheap Good"]
    assert result["h3"] == ["One Two"]


def test_br_separates_words_in_link_text():
    html = '<a href="/x">Read<br>more</a>'
    result = parse_html(html, base_url="https://example.com/")
    assert result["links"]["internal"][0]["text"] == "Read more"


def test_br_inside_a_nested_inline_tag_still_separates_words():
    html = "<h2><span>Plans<br>and</span> pricing</h2>"
    assert parse_html(html)["h2"] == ["Plans and pricing"]


def test_br_never_shows_as_glued_words_in_the_title():
    # Parsers differ on <title>: some read the <br> as a tag, some as literal
    # text (which is what a browser shows). Neither may glue the two words.
    html = "<html><head><title>Foo<br>Bar</title></head></html>"
    assert parse_html(html)["title"] in ("Foo Bar", "Foo<br>Bar")


def test_inline_tags_without_spaces_still_add_none():
    html = "<h1>Web<span>Obs</span></h1><h2>$<b>99</b> a month</h2>"
    result = parse_html(html)
    assert result["h1"] == ["WebObs"]
    assert result["h2"] == ["$99 a month"]


def test_br_handling_leaves_the_word_count_alone():
    html = "<body><h1>Foo<br>Bar</h1><p>three more words</p></body>"
    assert parse_html(html)["word_count"] == 5
