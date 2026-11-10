"""A malformed URL in one attribute must not abort the whole parse.

Background: `urljoin` and `urlparse` raise ValueError on an unbalanced IPv6
bracket such as `http://[bad/x`. One such value in any `<img src>` or
`<a href>` used to end the run with a traceback, so the page got no report.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from parse_html import parse_html  # noqa: E402

PAGE = "https://example.com/blog/post"


def test_malformed_img_src_is_kept_raw_and_the_parse_continues():
    html = '<h1>Title</h1><img src="http://[bad/a.jpg" alt="broken"><img src="ok.png" alt="fine">'
    result = parse_html(html, PAGE)
    assert [img["src"] for img in result["images"]] == [
        "http://[bad/a.jpg",
        "https://example.com/blog/ok.png",
    ]
    assert result["images"][0]["alt"] == "broken"
    assert result["h1"] == ["Title"]
    assert result["malformed_urls"] == [{"tag": "img", "value": "http://[bad/a.jpg"}]


def test_malformed_a_href_is_recorded_and_the_parse_continues():
    html = '<a href="http://[bad/x">Bad</a><a href="/ok">Ok</a><a href="https://other.example/">Out</a>'
    result = parse_html(html, PAGE)
    assert [link["href"] for link in result["links"]["internal"]] == ["https://example.com/ok"]
    assert [link["href"] for link in result["links"]["external"]] == ["https://other.example/"]
    assert result["malformed_urls"] == [{"tag": "a", "value": "http://[bad/x"}]


def test_clean_page_has_no_malformed_urls_key():
    result = parse_html('<img src="ok.png"><a href="/ok">Ok</a>', PAGE)
    assert "malformed_urls" not in result
