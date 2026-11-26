"""A charset declaration must belong to a meta start tag in the byte prescan."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from parse_html import parse_html  # noqa: E402
from url_safety import _extract_meta_charset, decode_body  # noqa: E402


@pytest.mark.parametrize(
    "prefix",
    [
        "<!-- <meta charset=windows-1252> -->",
        "<!-- previous declaration > <META charset=windows-1252> -->",
        '<script data-example="<meta charset=windows-1252>"></script>',
        "<link data-example='<meta charset=windows-1252>'>",
        '<meta name=description content="Example: <meta charset=windows-1252>">',
        "<meta-widget charset=windows-1252>",
        "<meta:example charset=windows-1252>",
        "</div data-example='<meta charset=windows-1252>'>",
        "<me\u00e9ta charset=windows-1252>",
    ],
)
def test_declarations_inside_comments_attributes_or_other_tag_names_are_ignored(prefix):
    html = prefix + '<meta charset=utf-8><title>Café 日本語</title>'
    decoded = decode_body(html.encode("utf-8"), "text/html")
    assert decoded == html
    assert _extract_meta_charset(html.encode("utf-8")) == "utf-8"


def test_a_commented_declaration_does_not_replace_the_utf8_fallback():
    html = '<!-- <meta charset=windows-1252> --><title>Café 日本語</title>'
    assert _extract_meta_charset(html.encode("utf-8")) is None
    assert decode_body(html.encode("utf-8"), "text/html") == html


@pytest.mark.parametrize(
    "meta",
    [
        '<meta data-note=">" charset=windows-1252>',
        "<meta data-note='>' charset=windows-1252>",
        '<meta data-note="<example>" http-equiv=content-type content="text/html; charset=windows-1252">',
        '<meta content="text/html; charset=windows-1252" data-note=">" http-equiv=content-type>',
    ],
)
def test_greater_than_inside_a_quoted_attribute_does_not_end_the_meta_tag(meta):
    html = meta + '<title>Café “menu”</title>'
    raw = html.encode("windows-1252")
    assert _extract_meta_charset(raw) == "windows-1252"
    assert decode_body(raw, "text/html") == html


@pytest.mark.parametrize(
    "prefix",
    [
        "<!-- unfinished <meta charset=windows-1252>",
        '<link data-example="unfinished <meta charset=windows-1252>',
        "<meta data-example='unfinished > <meta charset=windows-1252>",
        "<!--" + "x" * 4080 + "--><meta charset=windows-1252>",
    ],
)
def test_unterminated_or_cut_off_context_does_not_expose_a_nested_declaration(prefix):
    raw = (prefix + "Café").encode("utf-8")
    assert _extract_meta_charset(raw) is None
    assert decode_body(raw, "text/html").endswith("Café")


def test_shared_decoder_preserves_seo_metadata_after_a_commented_old_encoding():
    html = (
        '<!-- migration note: <meta charset=windows-1252> -->'
        '<meta charset=utf-8><title>Café 日本語</title>'
        '<meta name=description content="École de français">'
        '<link rel=canonical href="https://example.com/café">'
    )
    parsed = parse_html(decode_body(html.encode("utf-8"), "text/html"))
    assert parsed["title"] == "Café 日本語"
    assert parsed["meta_description"] == "École de français"
    assert parsed["canonical"] == "https://example.com/café"


@pytest.mark.parametrize("separator", ["\t", "\n", "\f", "\r", " ", "/"])
def test_meta_start_accepts_each_ascii_prescan_delimiter(separator):
    raw = f"<MeTa{separator}charset=windows-1252>".encode("ascii")
    assert _extract_meta_charset(raw) == "windows-1252"


def test_empty_comment_closes_at_its_first_arrow():
    raw = b"<!--><meta charset=windows-1252>"
    assert _extract_meta_charset(raw) == "windows-1252"


@pytest.mark.parametrize(
    "markup",
    [
        "<link data-note=it's><meta charset=windows-1252>",
        "<meta data-note=it's charset=windows-1252>",
        '<link data-note=he"said><meta charset=windows-1252>',
        '<meta data-note=he"said charset=windows-1252>',
        "<link data'quoted=example><meta charset=windows-1252>",
        "<meta data'quoted=example charset=windows-1252>",
    ],
)
def test_quotes_inside_names_or_unquoted_values_do_not_open_quoted_values(markup):
    # HTML's prescan treats a quote specially only at the beginning of a
    # value after '='. Malformed-but-readable attributes cannot swallow a
    # following declaration that the existing decoder already recognized.
    html = markup + "<title>Café “menu”</title>"
    raw = html.encode("windows-1252")
    assert _extract_meta_charset(raw) == "windows-1252"
    assert decode_body(raw, "text/html") == html


@pytest.mark.parametrize("non_ascii", [b"\x85", b"\xa0"])
@pytest.mark.parametrize("prefix", [b"<meta data", b"<meta data=example"])
def test_non_ascii_bytes_cannot_split_attribute_names_or_unquoted_values(non_ascii, prefix):
    raw = (
        prefix + non_ascii + b"charset=windows-1252><meta charset=utf-8>"
        + "<title>Café 日本語</title>".encode("utf-8")
    )
    assert _extract_meta_charset(raw) == "utf-8"
    assert decode_body(raw, "text/html").endswith("<title>Café 日本語</title>")
