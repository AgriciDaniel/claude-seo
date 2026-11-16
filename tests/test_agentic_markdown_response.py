"""A successful non-HTML response is not necessarily a Markdown document."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import agentic_check as checker  # noqa: E402


def response(content_type, text="# Page\n\nSome content.", status=200):
    return {"status": status, "headers": {"content-type": content_type, "vary": "Accept"}, "text": text}


def audit_response(monkeypatch, rec, route):
    url = "https://example.com/page"
    alternate = "https://example.com/version.md"
    fallback = response("text/html", "<html><body>Page</body></html>")
    missing = response("text/plain", "", 404)

    def fetch(target, headers=None):
        if headers:
            return rec if route == "negotiation" else fallback
        if target == alternate:
            return rec
        return rec if route == "sibling" else missing

    monkeypatch.setattr(checker, "fetch", fetch)
    page = {"soup_links": {"markdown_alternates": [alternate] if route == "alternate" else []}}
    return checker.audit_markdown(url, page)


@pytest.mark.parametrize("route", ["alternate", "sibling"])
@pytest.mark.parametrize("content_type", [
    "application/json", "application/xhtml+xml", "image/png", "application/pdf",
])
def test_non_markdown_media_cannot_pass(monkeypatch, route, content_type):
    checks, data = audit_response(monkeypatch, response(content_type), route)
    assert checks[0]["status"] == "info"
    candidate = data["alternates"][0] if route == "alternate" else data["md_sibling"]
    assert candidate["ok"] is False


@pytest.mark.parametrize("route", ["negotiation", "alternate", "sibling"])
@pytest.mark.parametrize("body", ["", "  \n\t"])
def test_empty_document_cannot_pass(monkeypatch, route, body):
    checks, _ = audit_response(monkeypatch, response("text/markdown", body), route)
    assert checks[0]["status"] == "info"


def test_negotiation_requires_exact_markdown_media_type(monkeypatch):
    checks, _ = audit_response(monkeypatch, response("application/x-text/markdown"), "negotiation")
    assert checks[0]["status"] == "info"


@pytest.mark.parametrize("route", ["negotiation", "alternate", "sibling"])
def test_markdown_with_parameters_passes(monkeypatch, route):
    checks, _ = audit_response(monkeypatch, response("Text/Markdown; charset=UTF-8"), route)
    assert checks[0]["status"] == "pass"


@pytest.mark.parametrize("route", ["alternate", "sibling"])
@pytest.mark.parametrize("content_type", ["text/plain", "text/x-markdown"])
def test_plain_text_and_legacy_markdown_alternates_remain_supported(monkeypatch, route, content_type):
    checks, _ = audit_response(monkeypatch, response(content_type), route)
    assert checks[0]["status"] == "pass"


def test_negotiation_still_warns_without_vary_accept(monkeypatch):
    rec = response("text/markdown")
    rec["headers"].pop("vary")
    checks, _ = audit_response(monkeypatch, rec, "negotiation")
    assert checks[0]["status"] == "warn"
    assert "Vary: Accept" in checks[0]["fix"]
