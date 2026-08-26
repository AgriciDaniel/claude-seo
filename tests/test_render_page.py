"""
Tests for scripts/render_page.py.

Focus areas:
  - SPA heuristic (covers React/Next/Vue/Nuxt/Svelte/Astro shells + the
    thin-body fallback tuned against the example.com false-positive).
  - Mode dispatch (never / auto / always) without spinning up Chromium.
  - SSRF pre-flight delegation to url_safety.
  - Defensive returns for invalid mode / invalid viewport / raw-fetch
    failure / Playwright-missing.
  - Content extraction graceful degradation when trafilatura / htmldate
    aren't installed.

Tests that would launch Chromium are skipped automatically when
Playwright is not available in the test environment. The skip marker
documents the limitation so CI shows "skipped" rather than "failed".
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import render_page  # noqa: E402

# ---------------------------------------------------------------------------
# _is_spa: SPA shell detector
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    [
        # Empty input is treated as "render to be safe".
        "",
        # React CRA / Vite / Remix
        '<html><body><div id="root"></div></body></html>',
        # Next.js
        '<html><body><div id="__next"><div></div></div></body></html>',
        # Vue / Generic JS apps
        '<html><body><div id="app"></div></body></html>',
        # Nuxt
        '<html><body><div id="__nuxt"></div></body></html>',
        # Svelte
        '<html><body><div data-svelte-h="abc"></div></body></html>',
        # Astro islands
        '<html><body><astro-island uid="x"></astro-island></body></html>',
        # noscript banners
        '<html><body><noscript>You need to enable JavaScript to run this app.</noscript></body></html>',
        # Thin body (<100 chars text)
        "<html><body><h1>Hi</h1></body></html>",
    ],
)
def test_is_spa_positive(html: str) -> None:
    assert render_page._is_spa(html) is True


@pytest.mark.parametrize(
    "html",
    [
        # Rich content page.
        "<html><body><article>"
        + ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 5)
        + "</article></body></html>",
        # example.com-style minimal informational page (~125 chars body) —
        # the threshold was specifically tuned not to flag this.
        '<html><body><div><h1>Example Domain</h1>'
        '<p>This domain is for use in illustrative examples in documents. '
        'You may use this domain in literature without prior coordination '
        'or asking for permission.</p>'
        '<p><a href="https://www.iana.org/domains/example">More information...</a></p>'
        '</div></body></html>',
    ],
)
def test_is_spa_negative(html: str) -> None:
    assert render_page._is_spa(html) is False


def test_is_spa_detects_sparse_builder_shell_with_multiple_markers() -> None:
    html = (
        '<html><head><meta content="Wix.com Website Builder">'
        '<script src="https://static.parastorage.com/app.js"></script></head>'
        '<body><script id="wix-warmup-data">{}</script><main>Loading</main></body></html>'
    )
    assert render_page._is_spa(html) is True


def test_is_spa_does_not_render_complete_builder_page() -> None:
    html = (
        '<html data-wf-page="page" data-wf-site="site"><body><main>'
        + ("Complete server rendered product information. " * 20)
        + "</main></body></html>"
    )
    assert render_page._is_spa(html) is False


@pytest.mark.parametrize(
    "marker",
    (
        '<div id="root">',
        '<div id="__next">',
        '<div id="app">',
        '<div id="__nuxt">',
        '<main data-svelte-h="abc">',
        '<astro-island uid="x">',
    ),
)
def test_is_spa_does_not_flag_complete_server_rendered_framework_page(
    marker: str,
) -> None:
    html = (
        "<html><body>"
        + marker
        + ("Complete server-rendered product details and specifications. " * 12)
        + "</main></div></astro-island></body></html>"
    )
    assert render_page._is_spa(html) is False


def test_is_spa_ignores_large_inline_script_as_visible_text() -> None:
    html = (
        "<html><body><script>"
        + ("window.payload = 'large';" * 100)
        + "</script><div>Loading</div></body></html>"
    )
    assert render_page._is_spa(html) is True


# ---------------------------------------------------------------------------
# Bounded JSON-LD extraction
# ---------------------------------------------------------------------------


def test_extract_json_ld_parses_full_html_before_summary_truncation() -> None:
    html = (
        "<html><head>"
        "<script nonce='x' TYPE='application/ld+json'>"
        '{"@context":"https://schema.org","@graph":['
        '{"@type":"Organization"},{"@type":["WebSite","Thing"]}]}'
        "</script></head><body>ok</body></html>"
    )
    result = render_page._extract_json_ld(html)
    assert result["block_count"] == 1
    assert result["blocks"][0]["valid"] is True
    assert result["blocks"][0]["types"] == ["Organization", "Thing", "WebSite"]
    assert "data" not in result["blocks"][0]


def test_extract_json_ld_full_data_is_explicit_opt_in() -> None:
    html = '<script type="application/ld+json">{"@type":"Caf\u00e9"}</script>'
    summary = render_page._extract_json_ld(html)
    full = render_page._extract_json_ld(html, include_full=True)
    assert "data" not in summary["blocks"][0]
    assert full["blocks"][0]["data"]["@type"] == "Caf\u00e9"


def test_extract_json_ld_malformed_content_is_full_output_only() -> None:
    malformed = '{"private_fragment":"not valid"'
    html = f'<script type="application/ld+json">{malformed}</script>'

    summary = render_page._extract_json_ld(html)
    full = render_page._extract_json_ld(html, include_full=True)

    summary_block = summary["blocks"][0]
    assert summary_block["valid"] is False
    assert "raw" not in summary_block
    assert "preview" not in summary_block
    assert malformed not in json.dumps(summary)
    assert full["blocks"][0]["raw"] == malformed


def test_extract_json_ld_enforces_block_and_count_limits(monkeypatch) -> None:
    monkeypatch.setattr(render_page, "JSON_LD_MAX_BLOCK_BYTES", 20)
    monkeypatch.setattr(render_page, "JSON_LD_MAX_BLOCKS", 2)
    html = (
        '<script type="application/ld+json">{"value":"' + ("x" * 30) + '"}</script>'
        '<script type="application/ld+json">{"@type":"Two"}</script>'
        '<script type="application/ld+json">{"@type":"Three"}</script>'
    )
    result = render_page._extract_json_ld(html, include_full=True)
    assert result["block_count"] == 3
    assert result["processed_count"] == 2
    assert result["truncated"] is True
    assert result["blocks"][0]["valid"] is None
    assert "data" not in result["blocks"][0]


class _StabilityPage:
    def __init__(self, signatures):
        self.signatures = list(signatures)
        self.last = self.signatures[-1]
        self.waits = []

    def evaluate(self, _expression):
        if self.signatures:
            self.last = self.signatures.pop(0)
        return self.last

    def wait_for_timeout(self, milliseconds):
        self.waits.append(milliseconds)


def test_wait_for_dom_stability_handles_late_hydration() -> None:
    page = _StabilityPage([(0, 5), (80, 10), (240, 20), (240, 20), (240, 20)])
    assert render_page._wait_for_dom_stability(page, 2000) is True


def test_wait_for_dom_stability_is_bounded() -> None:
    page = _StabilityPage([(0, 5)])
    assert render_page._wait_for_dom_stability(page, 750) is False
    assert sum(page.waits) == 750


# ---------------------------------------------------------------------------
# render_page — argument validation
# ---------------------------------------------------------------------------


def test_render_page_rejects_invalid_mode() -> None:
    result = render_page.render_page("https://example.com/", mode="banana")
    assert result["error"] and "Invalid mode" in result["error"]
    assert result["content"] is None


def test_render_page_rejects_invalid_viewport() -> None:
    result = render_page.render_page("https://example.com/", viewport="hologram")
    assert result["error"] and "Invalid viewport" in result["error"]


# ---------------------------------------------------------------------------
# render_page — SSRF pre-flight delegation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.7/",
        "http://169.254.169.254/latest/meta-data/",
        "http://2130706433/",          # obfuscated 127.0.0.1
        "https://metadata.google.internal./",  # FQDN bypass
    ],
)
def test_render_page_blocks_ssrf(url: str) -> None:
    result = render_page.render_page(url, mode="never")
    assert result["error"], f"expected error for {url}"
    assert result["error"].startswith("url_safety:")
    assert result["content"] is None


# ---------------------------------------------------------------------------
# render_page — raw mode (mode='never') is the cheap, network-touching path
# ---------------------------------------------------------------------------


def test_render_page_never_mode_against_example_com() -> None:
    """Single live-network check. example.com is the canonical IETF-reserved
    test target — stable, public, low-traffic, no auth required."""
    result = render_page.render_page("https://example.com/", mode="never")
    assert result["error"] is None
    assert result["status_code"] == 200
    assert result["mode_used"] == "raw"
    assert result["is_spa"] is False  # tuned threshold passes example.com
    assert result["render_engine"] is None
    assert result["content"] is not None
    assert "Example Domain" in result["content"]


# ---------------------------------------------------------------------------
# render_page — auto mode decision logic (mocked, no real network for SPA path)
# ---------------------------------------------------------------------------


def _fake_response(text: str, status: int = 200, url: str = "https://x.example/"):
    return SimpleNamespace(
        text=text, status_code=status, headers={"Content-Type": "text/html"},
        url=url, history=[],
    )


def _mock_validate_strict(url: str) -> tuple[str, str]:
    """Skip the real DNS resolution that validate_url_strict does."""
    return (url, "1.2.3.4")


class _FakeBrowserResponse:
    status = 200

    @staticmethod
    def all_headers():
        return {"content-type": "text/html"}


class _FakeBrowserPage(_StabilityPage):
    def __init__(self, signatures, *, navigation_timeout=False):
        super().__init__(signatures)
        self.navigation_timeout = navigation_timeout
        self.goto_options = None
        self.url = "https://app.example/"

    def on(self, *_args):
        return None

    def route(self, *_args):
        return None

    def goto(self, _url, **kwargs):
        self.goto_options = kwargs
        if self.navigation_timeout:
            raise render_page.PlaywrightTimeout("timeout")
        return _FakeBrowserResponse()

    @staticmethod
    def content():
        return "<html><body>" + ("hydrated content " * 20) + "</body></html>"


class _FakePlaywrightManager:
    def __init__(self, page):
        class _Session:
            def __init__(self):
                self.commands = []

            def send(self, method, params=None):
                self.commands.append((method, params))
                if method == "Accessibility.getFullAXTree":
                    return {
                        "nodes": [
                            {
                                "nodeId": "1",
                                "role": {"value": "RootWebArea"},
                                "name": {"value": "Example"},
                                "childIds": ["2"],
                            },
                            {
                                "nodeId": "2",
                                "parentId": "1",
                                "role": {"value": "button"},
                                "name": {"value": "Submit"},
                            },
                        ]
                    }
                return {}

            def detach(self):
                return None

        context = SimpleNamespace(
            new_page=lambda: page,
            new_cdp_session=lambda _page: _Session(),
        )
        browser = SimpleNamespace(
            new_context=lambda **_kwargs: context,
            close=lambda: None,
        )
        self.playwright = SimpleNamespace(
            chromium=SimpleNamespace(launch=lambda **_kwargs: browser)
        )

    def __enter__(self):
        return self.playwright

    def __exit__(self, *_args):
        return False


def _render_with_fake_browser(page, *, extract_accessibility=False):
    spa_html = '<html><body><div id="root"></div></body></html>'
    with patch.object(render_page, "validate_url_strict", side_effect=_mock_validate_strict), \
         patch.object(render_page, "safe_requests_get", return_value=_fake_response(spa_html)), \
         patch.object(render_page, "sync_playwright", lambda: _FakePlaywrightManager(page)):
        return render_page.render_page(
            "https://app.example/",
            mode="auto",
            timeout_ms=1000,
            extract_accessibility=extract_accessibility,
        )


def test_render_uses_domcontentloaded_for_persistent_socket_pages() -> None:
    page = _FakeBrowserPage([(200, 20), (200, 20), (200, 20)])
    result = _render_with_fake_browser(page)
    assert result["error"] is None
    assert page.goto_options["wait_until"] == "domcontentloaded"
    assert result["render_diagnostics"] == []


def test_render_navigation_timeout_returns_degraded_dom() -> None:
    page = _FakeBrowserPage(
        [(200, 20), (200, 20), (200, 20)], navigation_timeout=True
    )
    result = _render_with_fake_browser(page)
    assert result["error"] is None
    assert result["content"].startswith("<html>")
    assert result["status_code"] == 200
    assert any("DOMContentLoaded timed out" in item for item in result["render_diagnostics"])


def test_render_captures_accessibility_tree_through_cdp() -> None:
    page = _FakeBrowserPage([(200, 20), (200, 20), (200, 20)])
    result = _render_with_fake_browser(page, extract_accessibility=True)
    assert result["accessibility_error"] is None
    assert result["accessibility_partial"] is False
    assert result["accessibility_tree"]["role"] == "RootWebArea"
    assert result["accessibility_tree"]["children"][0] == {
        "role": "button",
        "name": "Submit",
        "ignored": False,
    }


def test_render_surfaces_accessibility_capture_failure() -> None:
    page = _FakeBrowserPage([(200, 20), (200, 20), (200, 20)])
    with patch.object(
        render_page,
        "_capture_accessibility_tree",
        side_effect=RuntimeError("CDP unavailable"),
    ):
        result = _render_with_fake_browser(page, extract_accessibility=True)
    assert result["error"] is None
    assert result["accessibility_tree"] is None
    assert result["accessibility_partial"] is True
    assert "CDP unavailable" in result["accessibility_error"]
    assert result["accessibility_error"] in result["render_diagnostics"]


def test_render_page_auto_stays_raw_for_static_html() -> None:
    """auto mode + non-SPA raw HTML → no Playwright invocation."""
    rich_html = "<html><body>" + ("hello world. " * 20) + "</body></html>"
    with patch.object(render_page, "validate_url_strict", side_effect=_mock_validate_strict), \
         patch.object(render_page, "safe_requests_get",
                      return_value=_fake_response(rich_html)):
        result = render_page.render_page("https://safe.example/", mode="auto")
    assert result["error"] is None
    assert result["mode_used"] == "raw"
    assert result["is_spa"] is False
    assert result["render_engine"] is None


def test_render_page_never_mode_skips_render_even_for_spa_shell() -> None:
    spa_html = '<html><body><div id="root"></div></body></html>'
    with patch.object(render_page, "validate_url_strict", side_effect=_mock_validate_strict), \
         patch.object(render_page, "safe_requests_get",
                      return_value=_fake_response(spa_html)):
        result = render_page.render_page("https://app.example/", mode="never")
    assert result["error"] is None
    assert result["mode_used"] == "raw"
    assert result["is_spa"] is True  # detected, but mode says don't render
    assert result["render_engine"] is None


def test_render_page_always_mode_errors_when_playwright_missing() -> None:
    """When Playwright is uninstalled, always-mode returns a clear error."""
    rich_html = "<html><body>" + ("a" * 1000) + "</body></html>"
    with patch.object(render_page, "validate_url_strict", side_effect=_mock_validate_strict), \
         patch.object(render_page, "safe_requests_get",
                      return_value=_fake_response(rich_html)), \
         patch.object(render_page, "sync_playwright", None):
        result = render_page.render_page("https://x.example/", mode="always")
    assert result["error"] is not None
    assert "playwright" in result["error"].lower()


def test_render_page_auto_errors_for_spa_when_playwright_missing() -> None:
    spa_html = '<html><body><div id="__next"></div></body></html>'
    with patch.object(render_page, "validate_url_strict", side_effect=_mock_validate_strict), \
         patch.object(render_page, "safe_requests_get",
                      return_value=_fake_response(spa_html)), \
         patch.object(render_page, "sync_playwright", None):
        result = render_page.render_page("https://app.example/", mode="auto")
    assert result["error"] is not None
    assert "playwright" in result["error"].lower()


def test_render_page_raw_fetch_failure_surfaces_clean_error() -> None:
    """When safe_requests_get raises, render_page returns an informative
    error rather than crashing."""
    import requests

    with patch.object(render_page, "validate_url_strict", side_effect=_mock_validate_strict), \
         patch.object(render_page, "safe_requests_get",
                      side_effect=requests.exceptions.ConnectionError("nope")):
        result = render_page.render_page("https://x.example/", mode="auto")
    assert result["error"] is not None
    assert "raw fetch failed" in result["error"]


# ---------------------------------------------------------------------------
# render_page — content-extraction graceful degradation
# ---------------------------------------------------------------------------


def test_render_page_extraction_skips_when_trafilatura_missing() -> None:
    rich_html = "<html><body>" + ("hello world. " * 20) + "</body></html>"
    with patch.object(render_page, "validate_url_strict", side_effect=_mock_validate_strict), \
         patch.object(render_page, "safe_requests_get",
                      return_value=_fake_response(rich_html)), \
         patch.object(render_page, "trafilatura", None), \
         patch.object(render_page, "find_date", None):
        result = render_page.render_page("https://x.example/", mode="never",
                                         extract_content=True)
    assert result["error"] is None
    assert result["extracted_text"] is None
    assert result["publication_date"] is None
    # Core fields still populated.
    assert result["content"] is not None


def test_render_page_extraction_disabled_by_flag() -> None:
    rich_html = "<html><body>" + ("hello world. " * 20) + "</body></html>"
    with patch.object(render_page, "validate_url_strict", side_effect=_mock_validate_strict), \
         patch.object(render_page, "safe_requests_get",
                      return_value=_fake_response(rich_html)):
        result = render_page.render_page("https://x.example/", mode="never",
                                         extract_content=False)
    assert result["error"] is None
    assert result["extracted_text"] is None
    assert result["publication_date"] is None


# ---------------------------------------------------------------------------
# render_page — result-shape contract
# ---------------------------------------------------------------------------


def test_render_page_result_dict_has_all_documented_fields() -> None:
    """Every caller (8 subagents) destructures this dict; the shape is the API."""
    rich_html = "<html><body>" + ("hello world. " * 20) + "</body></html>"
    with patch.object(render_page, "validate_url_strict", side_effect=_mock_validate_strict), \
         patch.object(render_page, "safe_requests_get",
                      return_value=_fake_response(rich_html)):
        result = render_page.render_page("https://x.example/", mode="never")
    expected_fields = {
        "url", "status_code", "content", "raw_content", "is_spa",
        "extracted_text", "publication_date", "accessibility_tree",
        "accessibility_error", "accessibility_partial",
        "headers", "redirect_chain", "console_errors", "render_engine",
        "render_diagnostics", "render_ms", "mode_used", "error",
    }
    assert set(result.keys()) == expected_fields


def test_cdp_accessibility_nodes_are_bounded_and_rebuilt(monkeypatch) -> None:
    monkeypatch.setattr(render_page, "ACCESSIBILITY_MAX_NODES", 2)
    nodes = [
        {
            "nodeId": "1",
            "role": {"value": "RootWebArea"},
            "name": {"value": "Page"},
            "childIds": ["2", "3"],
        },
        {
            "nodeId": "2",
            "parentId": "1",
            "role": {"value": "link"},
            "name": {"value": "Home"},
        },
        {
            "nodeId": "3",
            "parentId": "1",
            "role": {"value": "button"},
            "name": {"value": "Buy"},
        },
    ]
    tree, partial = render_page._accessibility_tree_from_cdp(nodes)
    assert partial is True
    assert tree["children"] == [
        {"role": "link", "name": "Home", "ignored": False}
    ]


def test_cdp_detach_failure_does_not_discard_captured_tree() -> None:
    class Session:
        def send(self, method: str, _params: object = None) -> dict:
            if method == "Accessibility.getFullAXTree":
                return {
                    "nodes": [
                        {
                            "nodeId": "1",
                            "role": {"value": "RootWebArea"},
                            "name": {"value": "Page"},
                        }
                    ]
                }
            return {}

        def detach(self) -> None:
            raise RuntimeError("already detached")

    class Context:
        def new_cdp_session(self, _page: object) -> Session:
            return Session()

    tree, partial = render_page._capture_accessibility_tree(Context(), object())
    assert tree == {"role": "RootWebArea", "name": "Page", "ignored": False}
    assert partial is False


def test_json_summary_is_full_by_default_and_explicit_when_bounded() -> None:
    result = {
        "content": "c" * 12,
        "raw_content": "r" * 8,
        "extracted_text": "word " * 5,
    }
    full = render_page._json_summary(result)
    assert full["content"] == result["content"]
    assert full["truncation"]["limit"] is None
    assert full["truncation"]["fields"]["content"]["truncated"] is False

    bounded = render_page._json_summary(result, max_text=5)
    assert bounded["content"] == "ccccc"
    assert bounded["extracted_text"] == "word "
    assert bounded["truncation"]["fields"]["content"] == {
        "original_chars": 12,
        "returned_chars": 5,
        "truncated": True,
    }


def test_json_and_output_are_composable(tmp_path, monkeypatch, capsys) -> None:
    output = tmp_path / "rendered.html"
    result = {
        "url": "https://example.test/",
        "content": "<html><body>complete output</body></html>",
        "raw_content": "<html></html>",
        "extracted_text": "complete output",
        "error": None,
    }
    monkeypatch.setattr(render_page, "render_page", lambda *_args, **_kwargs: result)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "render_page.py",
            "https://example.test/",
            "--json",
            "--max-text",
            "8",
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        render_page._cli()
    assert exc.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["output_written"] is True
    assert payload["content"] == "<html><b"
    assert payload["truncation"]["fields"]["content"]["truncated"] is True
    assert output.read_text(encoding="utf-8") == result["content"]
