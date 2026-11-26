"""Above-fold findings require an intersecting element, not the first match."""

from __future__ import annotations

import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("playwright.sync_api")
import analyze_visual as visual  # noqa: E402


class Element:
    def __init__(self, box, visible=True, src="hero.png"):
        self.box, self.visible, self.src = box, visible, src

    def bounding_box(self):
        return self.box

    def is_visible(self):
        return self.visible

    def get_attribute(self, name):
        return self.src if name == "src" else None


def box(x=10, y=10, width=100, height=40):
    return {"x": x, "y": y, "width": width, "height": height}


def audit_elements(monkeypatch, elements):
    page = SimpleNamespace(
        route=lambda *_a: None,
        goto=lambda *_a, **_k: None,
        query_selector=lambda selector: next(iter(elements.get(selector, [])), None),
        query_selector_all=lambda selector: elements.get(selector, []),
        evaluate=lambda *_a: 16,
    )
    context = SimpleNamespace(new_page=lambda: page, close=lambda: None)
    monkeypatch.setattr(visual, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(visual, "sync_playwright", lambda: nullcontext(SimpleNamespace(chromium=None)))
    monkeypatch.setattr(visual, "guarded_chromium", lambda *_a: nullcontext(object()))
    monkeypatch.setattr(visual, "chromium_sandboxed", lambda *_a: None)
    monkeypatch.setattr(visual, "new_guarded_context", lambda *_a, **_k: context)
    monkeypatch.setattr(visual, "require_public_page", lambda *_a: None)
    result = visual.analyze_visual("https://example.com/")
    assert result["error"] is None
    return result["above_fold"]


@pytest.mark.parametrize("rectangle,expected", [
    (box(x=-100), False),
    (box(x=1920), False),
    (box(y=-40), False),
    (box(y=1080), False),
    (box(width=0), False),
    (box(height=0), False),
    (box(), True),
    (box(x=-50), True),
    (box(y=-20), True),
    (box(x=1910), True),
    (box(y=1070), True),
    (None, False),
])
def test_heading_requires_positive_viewport_overlap(monkeypatch, rectangle, expected):
    result = audit_elements(monkeypatch, {"h1": [Element(rectangle)]})

    assert result["h1_visible"] is expected


@pytest.mark.parametrize("selector,key", [
    ("h1", "h1_visible"), (".cta", "cta_visible"), (".hero img", "hero_image"),
])
def test_later_visible_matches_are_not_masked_by_the_first(monkeypatch, selector, key):
    elements = [Element(None), Element(box(y=1200)), Element(box(), src="visible.png")]
    result = audit_elements(monkeypatch, {selector: elements})

    assert result[key] == ("visible.png" if key == "hero_image" else True)


@pytest.mark.parametrize("selector,key", [
    ("h1", "h1_visible"), (".cta", "cta_visible"), (".hero img", "hero_image"),
])
def test_hidden_boxes_are_not_reported_as_above_fold(monkeypatch, selector, key):
    result = audit_elements(monkeypatch, {selector: [Element(box(), visible=False)]})

    assert result[key] is (None if key == "hero_image" else False)


def test_visible_hero_without_src_does_not_mask_a_later_image(monkeypatch):
    result = audit_elements(monkeypatch, {".hero img": [Element(box(), src=None), Element(box())]})

    assert result["hero_image"] == "hero.png"


@pytest.fixture(scope="module")
def browser():
    import browser_proxy
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).exists():
            pytest.skip("Playwright Chromium is not installed")
        with browser_proxy.guarded_chromium(playwright.chromium) as instance:
            yield instance


def audit_dom(monkeypatch, browser, markup):
    original_context = visual.new_guarded_context

    def fixture_context(instance, handler, **options):
        context = original_context(instance, handler, **options)
        new_page = context.new_page

        def fixture_page():
            page = new_page()
            # Controlled HTML exercises actual Chromium layout without a server.
            # Only fixture navigation/public-page checks are replaced; every
            # attempted resource request is aborted and the browser is guarded.
            page.goto = lambda *_a, **_k: page.set_content(
                '<style>body{margin:0;font-size:16px}h1,.cta,img{margin:0;display:block;'
                'position:absolute;width:100px;height:40px;left:10px;top:10px}</style>' + markup
            )
            return page

        context.new_page = fixture_page
        return context

    monkeypatch.setattr(visual, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(visual, "sync_playwright", lambda: nullcontext(SimpleNamespace(chromium=None)))
    monkeypatch.setattr(visual, "guarded_chromium", lambda *_a: nullcontext(browser))
    monkeypatch.setattr(visual, "new_guarded_context", fixture_context)
    monkeypatch.setattr(visual, "require_public_page", lambda *_a: None)
    monkeypatch.setattr(visual, "make_safe_playwright_route_handler", lambda: lambda route: route.abort())
    result = visual.analyze_visual("https://example.com/")
    assert result["error"] is None
    return result["above_fold"]


@pytest.mark.parametrize("markup,key,expected", [
    ('<h1 style="left:-100px">Outside</h1>', "h1_visible", False),
    ('<h1 style="left:1920px">Outside</h1>', "h1_visible", False),
    ('<h1 style="top:-40px">Outside</h1>', "h1_visible", False),
    ('<h1 style="top:1080px">Outside</h1>', "h1_visible", False),
    ('<h1 style="left:-50px">Partial</h1>', "h1_visible", True),
    ('<h1 style="top:-20px">Partial</h1>', "h1_visible", True),
    ('<h1 style="display:none">Hidden</h1><h1>Visible</h1>', "h1_visible", True),
    ('<h1 style="visibility:hidden">Hidden</h1>', "h1_visible", False),
    ('<a class="cta" style="top:1200px">Below</a><a class="cta">Visible</a>', "cta_visible", True),
    ('<a class="cta" style="left:-100px">Outside</a>', "cta_visible", False),
    ('<div class="hero"><img src="data:,outside" style="left:-100px"></div>', "hero_image", None),
    ('<div class="hero"><img src="data:,below" style="top:1200px">'
     '<img src="data:,visible"></div>', "hero_image", "data:,visible"),
])
def test_actual_chromium_layout_drives_above_fold_findings(browser, monkeypatch, markup, key, expected):
    result = audit_dom(monkeypatch, browser, markup)

    assert result[key] == expected
