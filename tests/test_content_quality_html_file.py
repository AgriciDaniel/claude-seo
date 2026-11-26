"""The HTML file mode scores document text rather than markup and metadata."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import content_quality  # noqa: E402


def run_file(path):
    result = subprocess.run(
        [sys.executable, content_quality.__file__, str(path), "--json", "--threshold", "0"],
        capture_output=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("suffix", [".html", ".htm", ".HTML", ".xhtml"])
def test_html_file_excludes_markup_and_non_content_text(tmp_path, suffix):
    page = tmp_path / ("article" + suffix)
    page.write_text(
        "<!doctype html><html><head><title>Unrelated Metadata</title>"
        "<style>.widget { color: red; }</style>"
        "<script>When it comes to SEO, leverage the power of optimization.</script>"
        "</head><body><p>Customers saved <strong>25 percent</strong> in 2026.</p>"
        "<template><p>In today's fast-paced world</p></template>"
        "<noscript>Fallback navigation</noscript></body></html>",
        encoding="utf-8",
    )
    assert run_file(page) == content_quality.analyse(
        "Customers saved 25 percent in 2026."
    )


def test_html_entities_are_scored_as_text(tmp_path):
    page = tmp_path / "article.html"
    page.write_text(
        "<p>It&#39;s important to note that growth reached 25&nbsp;percent.</p>",
        encoding="utf-8",
    )
    assert run_file(page) == content_quality.analyse(
        "It's important to note that growth reached 25\u00a0percent."
    )


def test_plain_text_file_is_not_interpreted_as_html(tmp_path):
    page = tmp_path / "literal.txt"
    text = "A <widget> example documents 25 new fields without changing the literal."
    page.write_text(text, encoding="utf-8")
    assert run_file(page) == content_quality.analyse(text)


def test_omitted_head_end_tag_keeps_body_content(tmp_path):
    page = tmp_path / "article.html"
    page.write_text(
        "<!doctype html><html><head><title>Metadata only</title>"
        "<body><p>Customers saved 25 percent in 2026.</p></body></html>",
        encoding="utf-8",
    )
    assert run_file(page) == content_quality.analyse("Customers saved 25 percent in 2026.")


def test_html_parser_fallback_when_lxml_is_unavailable(tmp_path, monkeypatch, capsys):
    import bs4

    page = tmp_path / "article.html"
    page.write_text("<p>Customers saved 25 percent in 2026.</p>", encoding="utf-8")
    parse = bs4.BeautifulSoup
    parsers = []

    def without_lxml(markup, parser):
        parsers.append(parser)
        if parser == "lxml":
            raise bs4.FeatureNotFound("lxml is unavailable")
        return parse(markup, parser)

    monkeypatch.setattr(bs4, "BeautifulSoup", without_lxml)
    monkeypatch.setattr(sys, "argv", [content_quality.__file__, str(page), "--json", "--threshold", "0"])
    assert content_quality.main() == 0
    assert json.loads(capsys.readouterr().out) == content_quality.analyse(
        "Customers saved 25 percent in 2026."
    )
    assert parsers == ["lxml", "html.parser"]
