"""Mixed-content findings use the resource URL after document-base resolution."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import page_checks  # noqa: E402

PAGE = "https://example.com/articles/page"
HTTP_BASE = '<base href="http://cdn.example.org/assets/">'


def _html(resource, base=HTTP_BASE):
    return f'<!doctype html><html><head>{base}{resource}</head><body><main>Page</main></body></html>'


def _mixed(html, page=PAGE):
    return [f for f in page_checks.run_checks(html, page)["findings"]
            if f["id"] == "mixed-content"]


@pytest.mark.parametrize("resource,expected", [
    ('<script src="app.js"></script>', "http://cdn.example.org/assets/app.js"),
    ('<iframe src="/frame.html"></iframe>', "http://cdn.example.org/frame.html"),
    ('<video src="//media.example.org/movie.mp4"></video>', "http://media.example.org/movie.mp4"),
    ('<link rel="stylesheet" href="style.css">', "http://cdn.example.org/assets/style.css"),
    ('<link rel="preload" as="script" href="//static.example.org/app.js">', "http://static.example.org/app.js"),
])
def test_http_document_base_exposes_insecure_resources(resource, expected):
    findings = _mixed(_html(resource))
    assert len(findings) == 1
    assert findings[0]["severity"] == "High"
    assert findings[0]["count"] == 1
    assert expected in findings[0]["evidence"]


@pytest.mark.parametrize("base,resource", [
    ("", '<script src="app.js"></script>'),
    ('<base href="https://cdn.example.org/">', '<script src="//static.example.org/app.js"></script>'),
    ('<base href="/assets/">', '<link rel="stylesheet" href="style.css">'),
    (HTTP_BASE, '<script src="https://cdn.example.org/app.js"></script>'),
    (HTTP_BASE, '<script>window.x = 1;</script><img><link rel="stylesheet" href="">'),
    (HTTP_BASE, '<img src="data:image/png;base64,aGVsbG8=">'),
    ('<base href="https://cdn.example.org/">' + HTTP_BASE, '<script src="app.js"></script>'),
])
def test_secure_and_non_resource_controls_do_not_add_mixed_content(base, resource):
    assert _mixed(_html(resource, base)) == []


def test_http_document_is_not_reported_as_mixed_content():
    assert _mixed(_html('<script src="app.js"></script>'), "http://example.com/page") == []


def test_saved_page_cli_reports_resolved_resource(tmp_path, monkeypatch, capsys):
    page = tmp_path / "page.html"
    page.write_text(_html('<script src="app.js"></script>'), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["page_checks.py", "--file", str(page), "--base-url", PAGE])
    result = page_checks.main()
    assert result == 0
    output = json.loads(capsys.readouterr().out)
    finding = next(f for f in output["findings"] if f["id"] == "mixed-content")
    assert "http://cdn.example.org/assets/app.js" in finding["evidence"]
