#!/usr/bin/env python3
"""
Shared headless renderer for claude-seo.

Every subagent that fetches HTML for analysis (technical, content, schema,
geo, local, ecommerce, hreflang, images) calls this module instead of
``fetch_page.py`` whenever JS execution might change what an audit can see.
Built on Playwright Chromium with trafilatura for boilerplate-free content
extraction and htmldate for publication-date detection.

Why
===
Before v2.0.0 only ``seo-visual`` used Playwright. Every other agent
fetched raw HTML, which produces false negatives on SPAs (empty
``<div id="root">``, no schema in source, no content in source). The
gap analysis (see ``compass_artifact_*.md``) ranks "headless rendering
across all subagents" as the single highest-impact v2 change. This module
delivers it as a shared subsystem so the change is one foundation, not
eight retrofits.

Modes
=====
- ``auto``   : raw fetch first; render only when an SPA shell is detected
               (see ``_is_spa``). Default. Cheapest correct behaviour.
- ``always`` : always render with Playwright, even for static HTML.
- ``never``  : raw HTML only. Equivalent to legacy ``fetch_page.py``.

Result shape
============
A dict with::

    url               final URL after redirects
    status_code       HTTP status of the main document
    content           HTML after JS execution (post-render DOM)
    raw_content       HTML before JS execution (server response)
    is_spa            True iff raw_content looks like a hydration shell
    extracted_text    trafilatura main-content extraction (or None)
    publication_date  htmldate ISO 8601 string (or None)
    accessibility_tree Chromium accessibility-tree snapshot (or None)
    accessibility_error capture failure detail (or None)
    accessibility_partial True when the accessibility result is incomplete
    headers           response headers from the main document
    redirect_chain    list of {url, status_code}
    console_errors    list of browser console error strings
    render_diagnostics list of non-fatal render degradation messages
    render_engine     'playwright-chromium' or None
    render_ms         elapsed wall-clock for the render step
    mode_used         'rendered' or 'raw'
    too_large         True when the raw body hit the size cap (MAX_PAGE_BYTES)
    js_gap            raw-versus-rendered difference (see below), or None
                      when no render happened (or the HTML was too large
                      to compare, which render_diagnostics then says)
    sandbox           True when Chromium ran with its sandbox, False when
                      it ran without (unavailable on this system, root, or
                      opted out), None when no browser was launched
    error             str or None

JavaScript content gap
======================
When a page is rendered, ``js_gap`` compares the HTML as served with the
DOM after JavaScript ran (:func:`js_gap`, a pure function over two HTML
strings)::

    raw, rendered     per version: words, links, schema_types, h1, title,
                      canonical, canonical_all, meta_robots
    diff              words_only_rendered and links_only_rendered with their
                      *_share of the rendered total (0 to 1),
                      schema_types_only_rendered, h1_only_rendered,
                      title_changed, canonical_changed, meta_robots_changed
    raw_truncated     True when the raw body was cut at the size cap, so
                      the gap may be overstated
    significant       True when ``reasons`` is not empty
    reasons           plain-language findings; empty when nothing stands out

Words are every text token outside script, style, noscript, template and
head; hidden elements are not detected. The share limits (``JS_GAP_*``) are
this tool's heuristics, not Google rules.

Every string in ``js_gap`` that comes from the page (schema type names,
title, canonical, robots directives, H1 text, and what ``reasons`` quotes)
has its whitespace collapsed and is cut at a ``JS_GAP_MAX_*`` length, and
every list has an item limit. ``--max-text`` does not apply to ``js_gap``;
these limits keep the whole object to about 24,000 characters of JSON.

SSRF
====
The URL is validated via :func:`url_safety.validate_url_strict` before
Playwright sees it. Chromium is launched through
:func:`browser_proxy.guarded_chromium`: sandboxed where the host can start
the Chromium sandbox (``sandbox`` in the result says so), with every connection
(redirect hops included) forced through a local proxy that validates and
pins the destination. A ``route()`` handler also aborts requests whose
hostname resolves to a non-public IP, as defence in depth. A render that
ends on a blank, failed or refused page is an error with the raw fetch
kept (``raw_fallback_available``). The limits are documented in
SECURITY.md. Where the sandbox cannot start (Ubuntu 23.10 and later, most
containers, root) the browser runs without it, with a warning on stderr and
``sandbox: false``; ``CLAUDE_SEO_CHROMIUM_REQUIRE_SANDBOX=1`` makes that an
error and ``CLAUDE_SEO_CHROMIUM_NO_SANDBOX=1`` skips the sandbox attempt.

CLI
===
    python render_page.py https://nuxt.com --mode always
    python render_page.py https://example.com --mode auto --json
    python render_page.py https://store.example.com --block image --block font
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from typing import Any, Optional

from bs4 import BeautifulSoup

# Optional native dependencies. Each is checked lazily so callers that
# only need raw-mode (mode='never') don't pay the import cost.
try:
    from playwright.sync_api import (
        TimeoutError as PlaywrightTimeout,
    )
    from playwright.sync_api import (
        sync_playwright,
    )
except ImportError:  # pragma: no cover - exercised in environments without playwright
    sync_playwright = None
    PlaywrightTimeout = Exception  # type: ignore[assignment,misc]

try:
    import trafilatura
except ImportError:  # pragma: no cover
    trafilatura = None

try:
    from htmldate import find_date
except ImportError:  # pragma: no cover
    find_date = None

# Reuse the canonical safety module.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from browser_proxy import (  # noqa: E402
    PageNotLoadedError,
    chromium_sandboxed,
    guarded_chromium,
    require_public_page,
)
from url_safety import (  # noqa: E402  (sys.path massage above is intentional)
    MAX_PAGE_BYTES,
    URLSafetyError,
    decode_body,
    make_safe_playwright_route_handler,
    new_guarded_context,
    read_bounded,
    safe_requests_get,
    validate_url_strict,
)

VIEWPORTS: dict[str, dict[str, int]] = {
    "desktop": {"width": 1920, "height": 1080, "device_scale": 1},
    "laptop": {"width": 1366, "height": 768, "device_scale": 1},
    "tablet": {"width": 768, "height": 1024, "device_scale": 1},
    "mobile": {"width": 375, "height": 812, "device_scale": 2},
}

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.7871.115 Safari/537.36 ClaudeSEO/2.0"
)

# Hydration-shell signatures. A marker is actionable only while meaningful
# body text is sparse, because SSR/SSG framework pages legitimately retain
# the same root and hydration markers after serving complete HTML.
_SPA_SHELL_PATTERNS = (
    '<div id="root"></div>',
    '<div id="__next">',
    '<div id="app"></div>',
    '<div id="__nuxt">',
    'data-svelte-h=',
    '<astro-island ',
    'you need to enable javascript',
    'please enable javascript',
)

# Builder markers are supporting evidence only. Wix, Webflow, and Squarespace
# can all serve complete HTML, so auto-render requires multiple same-builder
# markers plus sparse meaningful body text.
_BUILDER_FINGERPRINT_GROUPS = (
    ("wix-warmup-data", "static.parastorage.com", 'content="wix.com'),
    ("data-wf-page", "data-wf-site"),
    ('content="squarespace', "static1.squarespace.com"),
)

_TAG_STRIP = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_NON_VISIBLE_STRIP = re.compile(
    r"<(script|style|template|noscript)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_BUILDER_SPARSE_TEXT_MAX = 400

JSON_LD_MAX_BLOCKS = 50
JSON_LD_MAX_BLOCK_BYTES = 256 * 1024
JSON_LD_MAX_TOTAL_BYTES = 1024 * 1024
JSON_LD_MAX_NODES = 10_000
JSON_LD_MAX_DEPTH = 40
ACCESSIBILITY_MAX_NODES = 10_000
ACCESSIBILITY_MAX_DEPTH = 50

# JavaScript content gap. These limits decide when a raw-versus-rendered
# difference is called "significant". They are this tool's heuristics, not
# Google rules: Google publishes no threshold for either.
JS_GAP_WORDS_SHARE = 0.30  # share of rendered words that exist only after JS
JS_GAP_WORDS_MIN = 25      # and at least this many such words
JS_GAP_LINKS_SHARE = 0.30  # share of rendered links that exist only after JS
JS_GAP_LINKS_MIN = 3       # and at least this many such links
# Output bounds, so a hostile page cannot inflate the JSON.
JS_GAP_MAX_ITEMS = 12      # schema types, H1 texts, robots directives
JS_GAP_MAX_CANONICALS = 5
JS_GAP_MAX_TEXT = 300      # characters kept per title, H1 or canonical
JS_GAP_MAX_NAME = 80       # characters kept per schema type name or robots directive
JS_GAP_REASON_TEXT = 80    # characters of page text quoted inside a reason
JS_GAP_REASON_ITEMS = 5    # schema type names listed inside a reason
# The comparison parses both versions again. Past this size it is skipped
# (js_gap stays None, with a render diagnostic) so a huge DOM cannot stall it.
JS_GAP_MAX_HTML_CHARS = 5_000_000

_WORD = re.compile(r"\w+")
_NON_VISIBLE_TAGS = ("script", "style", "noscript", "template", "head", "title")
_NON_LINK_HREF = ("#", "javascript:", "mailto:", "tel:", "data:")


def _visible_body_text(lower_html: str) -> str:
    body_start = lower_html.find("<body")
    body_end = lower_html.rfind("</body>")
    if body_start == -1 or body_end <= body_start:
        return ""
    body = _NON_VISIBLE_STRIP.sub(" ", lower_html[body_start:body_end])
    return _WHITESPACE.sub(" ", _TAG_STRIP.sub(" ", body)).strip()


def _schema_types(data: object) -> tuple[list[str], bool]:
    """Collect bounded @type values without recursive attacker-controlled calls."""
    types: set[str] = set()
    stack: list[tuple[object, int]] = [(data, 0)]
    visited = 0
    truncated = False
    while stack:
        value, depth = stack.pop()
        visited += 1
        if visited > JSON_LD_MAX_NODES or depth > JSON_LD_MAX_DEPTH:
            truncated = True
            break
        if isinstance(value, dict):
            schema_type = value.get("@type")
            if isinstance(schema_type, str):
                types.add(schema_type)
            elif isinstance(schema_type, list):
                types.update(item for item in schema_type if isinstance(item, str))
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)
    return sorted(types)[:100], truncated or len(types) > 100


def _extract_json_ld(
    html: Optional[str],
    *,
    include_full: bool = False,
    soup: Optional[BeautifulSoup] = None,
) -> dict:
    """Extract full-page JSON-LD with strict block, byte, and traversal bounds.

    ``soup`` lets a caller that already parsed ``html`` skip a second parse.
    """
    result = {
        "block_count": 0,
        "processed_count": 0,
        "total_bytes": 0,
        "truncated": False,
        "blocks": [],
    }
    if not html:
        return result

    if soup is None:
        soup = BeautifulSoup(html, "html.parser")
    scripts = [
        script for script in soup.find_all("script")
        if str(script.get("type", "")).strip().lower() == "application/ld+json"
    ]
    result["block_count"] = len(scripts)

    for index, script in enumerate(scripts):
        if index >= JSON_LD_MAX_BLOCKS:
            result["truncated"] = True
            break
        raw = script.string if script.string is not None else script.get_text()
        raw = str(raw or "").strip()
        size_bytes = len(raw.encode("utf-8"))
        if result["total_bytes"] + size_bytes > JSON_LD_MAX_TOTAL_BYTES:
            result["truncated"] = True
            break
        result["total_bytes"] += size_bytes
        result["processed_count"] += 1

        entry = {"index": index + 1, "size_bytes": size_bytes}
        if size_bytes > JSON_LD_MAX_BLOCK_BYTES:
            entry.update({
                "valid": None,
                "error": "block exceeds the JSON-LD per-block byte limit",
            })
            result["truncated"] = True
            result["blocks"].append(entry)
            continue

        try:
            parsed = json.loads(raw)
            types, types_truncated = _schema_types(parsed)
            entry.update({
                "valid": True,
                "types": types,
                "types_truncated": types_truncated,
            })
            if include_full:
                entry["data"] = parsed
        except (json.JSONDecodeError, RecursionError) as exc:
            entry.update({
                "valid": False,
                "error": f"{type(exc).__name__}: {exc}",
            })
            if include_full:
                entry["raw"] = raw
        result["blocks"].append(entry)
    return result


def _is_spa(raw_html: Optional[str]) -> bool:
    """Detect sparse hydration shells without flagging complete SSR/SSG pages."""
    if not raw_html:
        return True
    lc = raw_html.lower()
    visible_text = _visible_body_text(lc)
    if (
        len(visible_text) < _BUILDER_SPARSE_TEXT_MAX
        and any(pattern in lc for pattern in _SPA_SHELL_PATTERNS)
    ):
        return True
    if len(visible_text) < _BUILDER_SPARSE_TEXT_MAX:
        for markers in _BUILDER_FINGERPRINT_GROUPS:
            if sum(marker in lc for marker in markers) >= 2:
                return True
    # Very thin <body> suggests JS-rendered content even without a shell.
    # Threshold (100 chars) sits between typical SPA shells (0-50 chars of
    # body text) and minimal informational pages like example.com (~125
    # chars). Tuned conservatively to avoid false positives that would
    # force a redundant Playwright render in auto mode.
    body_start = lc.find("<body")
    body_end = lc.rfind("</body>")
    if body_start != -1 and body_end > body_start:
        if len(visible_text) < 100:
            return True
    return False


def _clean_text(value: object, limit: Optional[int] = None) -> str:
    """Page text for js_gap: whitespace collapsed, cut at ``limit`` characters."""
    return _WHITESPACE.sub(" ", str(value or "")).strip()[:limit or JS_GAP_MAX_TEXT]


def _gap_signals(html: str) -> tuple[dict, dict]:
    """Collect one version's SEO signals for :func:`js_gap`.

    Returns the published signals plus the word and link multisets used to
    work out what exists only after rendering. Raw and rendered HTML go
    through the same code, so the two sides are counted the same way.
    """
    soup = BeautifulSoup(html or "", "html.parser")

    # Dicts keep first-seen order and make de-duplication linear, so a page
    # with a huge number of distinct values cannot slow the comparison down.
    # A type name is page text like any other: cleaned and cut before it is
    # kept, so a huge @type value cannot ride into the output.
    schema_types: dict[str, None] = {}
    for block in _extract_json_ld(html, soup=soup)["blocks"]:
        for name in block.get("types") or []:
            name = _clean_text(name, JS_GAP_MAX_NAME)
            if name:
                schema_types[name] = None

    # An <svg><title> is an accessible name, not the document title.
    title = None
    for tag in soup.find_all("title"):
        if tag.find_parent("svg") is None:
            title = _clean_text(tag.get_text(" ")) or None
            break

    canonicals: dict[str, None] = {}
    for tag in soup.find_all("link"):
        rel = tag.get("rel") or []
        rel = rel.split() if isinstance(rel, str) else rel
        href = _clean_text(tag.get("href"))
        if href and any(str(item).lower() == "canonical" for item in rel):
            canonicals[href] = None

    # Several robots meta tags combine, so their directives are merged.
    robots: dict[str, None] = {}
    for tag in soup.find_all("meta"):
        if str(tag.get("name") or "").strip().lower() != "robots":
            continue
        for directive in str(tag.get("content") or "").lower().split(","):
            directive = _clean_text(directive, JS_GAP_MAX_NAME)
            if directive:
                robots[directive] = None

    for tag in soup(list(_NON_VISIBLE_TAGS)):
        tag.decompose()

    h1: dict[str, None] = {}
    for tag in soup.find_all("h1"):
        text = _clean_text(tag.get_text(" ", strip=True))
        if text:
            h1[text] = None

    hrefs: Counter = Counter()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if href and not href.lower().startswith(_NON_LINK_HREF):
            hrefs[href] += 1

    words = Counter(_WORD.findall(soup.get_text(" ", strip=True).lower()))

    signals = {
        "words": sum(words.values()),
        "links": sum(hrefs.values()),
        "schema_types": list(schema_types)[:JS_GAP_MAX_ITEMS],
        "h1": list(h1)[:JS_GAP_MAX_ITEMS],
        "title": title,
        "canonical": next(iter(canonicals), None),
        "canonical_all": list(canonicals)[:JS_GAP_MAX_CANONICALS],
        "meta_robots": ", ".join(list(robots)[:JS_GAP_MAX_ITEMS]) or None,
    }
    return signals, {"words": words, "hrefs": hrefs}


def _only_after(raw: Counter, rendered: Counter) -> tuple[int, float]:
    """Items in ``rendered`` with no counterpart in ``raw``: count and share."""
    total = sum(rendered.values())
    added = sum((rendered - raw).values())
    return added, (round(added / total, 3) if total else 0.0)


def js_gap(
    raw_html: Optional[str],
    rendered_html: Optional[str],
    *,
    raw_truncated: bool = False,
) -> Optional[dict]:
    """Compare the HTML as served with the DOM after JavaScript ran.

    Pure: two HTML strings in, a JSON-ready dict out, no browser or network.
    Returns None when either version is missing (no render happened). An
    empty string is a real, empty document and is compared.

    Title, canonical and meta robots are reported as changed when the raw
    and rendered values differ in any way (added, removed or replaced). A
    mismatch between the two is the case Google's JavaScript SEO guidance
    warns about.
    """
    if raw_html is None or rendered_html is None:
        return None
    raw, raw_sets = _gap_signals(raw_html)
    rendered, rendered_sets = _gap_signals(rendered_html)
    words_added, words_share = _only_after(raw_sets["words"], rendered_sets["words"])
    links_added, links_share = _only_after(raw_sets["hrefs"], rendered_sets["hrefs"])
    gap: dict = {
        "raw": raw,
        "rendered": rendered,
        "diff": {
            "words_only_rendered": words_added,
            "words_only_rendered_share": words_share,
            "links_only_rendered": links_added,
            "links_only_rendered_share": links_share,
            "schema_types_only_rendered": [
                name for name in rendered["schema_types"]
                if name not in raw["schema_types"]
            ],
            "h1_only_rendered": [text for text in rendered["h1"] if text not in raw["h1"]],
            "title_changed": raw["title"] != rendered["title"],
            "canonical_changed": (
                set(raw["canonical_all"]) != set(rendered["canonical_all"])
            ),
            "meta_robots_changed": (
                set((raw["meta_robots"] or "").split(", "))
                != set((rendered["meta_robots"] or "").split(", "))
            ),
        },
        "raw_truncated": bool(raw_truncated),
    }
    gap["reasons"] = js_gap_reasons(gap)
    gap["significant"] = bool(gap["reasons"])
    return gap


def _quoted(value: object) -> str:
    """Page text for a reason line: bounded, or 'none' when absent."""
    if isinstance(value, list):
        value = " | ".join(str(item) for item in value)
    text = str(value or "")
    if not text:
        return "none"
    if len(text) > JS_GAP_REASON_TEXT:
        text = text[:JS_GAP_REASON_TEXT] + "..."
    return f"'{text}'"


def js_gap_reasons(gap: Optional[dict]) -> list[str]:
    """Plain-language reasons a :func:`js_gap` result matters. Empty when none do."""
    if not gap:
        return []
    raw, rendered, diff = gap["raw"], gap["rendered"], gap["diff"]
    reasons: list[str] = []
    if (
        diff["words_only_rendered_share"] >= JS_GAP_WORDS_SHARE
        and diff["words_only_rendered"] >= JS_GAP_WORDS_MIN
    ):
        reasons.append(
            f"{round(diff['words_only_rendered_share'] * 100)}% of visible words appear "
            f"only after JavaScript runs ({raw['words']} raw, {rendered['words']} rendered)"
        )
    if (
        diff["links_only_rendered_share"] >= JS_GAP_LINKS_SHARE
        and diff["links_only_rendered"] >= JS_GAP_LINKS_MIN
    ):
        reasons.append(
            f"{diff['links_only_rendered']} of {rendered['links']} links appear only "
            f"after JavaScript runs ({raw['links']} in the raw HTML)"
        )
    if diff["schema_types_only_rendered"]:
        reasons.append(
            "structured data appears only after JavaScript: "
            + ", ".join(
                _quoted(name)
                for name in diff["schema_types_only_rendered"][:JS_GAP_REASON_ITEMS]
            )
        )
    if diff["h1_only_rendered"]:
        reasons.append(
            "the H1 changes after JavaScript" if raw["h1"]
            else "the H1 appears only after JavaScript"
        )
    for flag, label, key in (
        ("title_changed", "title", "title"),
        ("canonical_changed", "canonical URL", "canonical_all"),
        ("meta_robots_changed", "meta robots value", "meta_robots"),
    ):
        if diff[flag]:
            reasons.append(
                f"the {label} is not the same before and after JavaScript "
                f"(raw: {_quoted(raw[key])}, rendered: {_quoted(rendered[key])})"
            )
    return reasons


def _wait_for_dom_stability(page, timeout_ms: int) -> bool:  # type: ignore[no-untyped-def]
    """Wait up to five seconds for meaningful body text and a stable DOM."""
    budget_ms = max(250, min(timeout_ms, 5000))
    previous = None
    stable_samples = 0
    elapsed_ms = 0
    while elapsed_ms < budget_ms:
        try:
            signature = tuple(page.evaluate(
                "() => ["
                "(document.body && document.body.innerText || '').trim().length,"
                "document.querySelectorAll('*').length"
                "]"
            ))
        except Exception:
            return False
        if signature == previous and signature[0] >= 100:
            stable_samples += 1
            if stable_samples >= 2:
                return True
        else:
            stable_samples = 0
        previous = signature
        page.wait_for_timeout(250)
        elapsed_ms += 250
    return False


def _ax_value(node: dict[str, Any], key: str) -> str:
    value = node.get(key)
    if isinstance(value, dict):
        raw = value.get("value")
        return str(raw) if raw is not None else ""
    return str(value) if value is not None else ""


def _accessibility_tree_from_cdp(nodes: object) -> tuple[Optional[dict], bool]:
    """Convert Chrome's flat AXNode array into the tree used by the auditor."""
    if not isinstance(nodes, list) or not nodes:
        return None, False

    usable = [node for node in nodes if isinstance(node, dict)]
    truncated = len(usable) > ACCESSIBILITY_MAX_NODES
    usable = usable[:ACCESSIBILITY_MAX_NODES]
    by_id = {
        str(node["nodeId"]): node
        for node in usable
        if node.get("nodeId") is not None
    }
    if not by_id:
        return None, truncated

    known_children = {
        str(child_id)
        for node in by_id.values()
        for child_id in (node.get("childIds") or [])
        if str(child_id) in by_id
    }
    root_id = next((node_id for node_id in by_id if node_id not in known_children), None)
    if root_id is None:
        return None, True

    def build(node_id: str, depth: int, ancestors: frozenset[str]) -> dict:
        nonlocal truncated
        node = by_id[node_id]
        result = {
            "role": _ax_value(node, "role"),
            "name": _ax_value(node, "name"),
            "ignored": bool(node.get("ignored", False)),
        }
        child_ids = [
            str(child_id)
            for child_id in (node.get("childIds") or [])
            if str(child_id) in by_id
        ]
        if depth >= ACCESSIBILITY_MAX_DEPTH:
            if child_ids:
                truncated = True
            return result
        children = []
        for child_id in child_ids:
            if child_id in ancestors:
                truncated = True
                continue
            children.append(build(child_id, depth + 1, ancestors | {child_id}))
        if children:
            result["children"] = children
        return result

    return build(root_id, 0, frozenset({root_id})), truncated


def _capture_accessibility_tree(context: Any, page: Any) -> tuple[Optional[dict], bool]:
    """Capture the Chromium AX tree through Playwright's supported CDP seam."""
    session = context.new_cdp_session(page)
    try:
        session.send("Accessibility.enable")
        payload = session.send(
            "Accessibility.getFullAXTree", {"depth": ACCESSIBILITY_MAX_DEPTH}
        )
        return _accessibility_tree_from_cdp(payload.get("nodes"))
    finally:
        try:
            session.send("Accessibility.disable")
        except Exception:
            pass
        detach = getattr(session, "detach", None)
        if detach:
            try:
                detach()
            except Exception:
                pass


def render_page(
    url: str,
    *,
    mode: str = "auto",
    viewport: str = "desktop",
    timeout_ms: int = 15000,
    block_resources: Optional[list[str]] = None,
    extract_content: bool = True,
    extract_accessibility: bool = False,
    user_agent: Optional[str] = None,
) -> dict:
    """Render or fetch ``url`` per the chosen mode. See module docstring.

    ``extract_accessibility``: when True and the page is rendered (mode
    'always' or 'auto'+SPA), the Chromium accessibility tree is captured via
    a Playwright CDP session and attached to ``result['accessibility_tree']``. Used by
    ``agent_ux_check.py`` for agent-friendliness scoring (Google AI
    optimization guide / web.dev agent UX criteria).
    """
    result: dict = {
        "url": url,
        "status_code": None,
        "content": None,
        "raw_content": None,
        "is_spa": None,
        "extracted_text": None,
        "publication_date": None,
        "accessibility_tree": None,
        "accessibility_error": None,
        "accessibility_partial": False,
        "headers": {},
        "redirect_chain": [],
        "console_errors": [],
        "render_diagnostics": [],
        "render_engine": None,
        "render_ms": None,
        "mode_used": None,
        "too_large": False,
        "js_gap": None,
        # True or False once a browser was launched (False: no Chromium
        # sandbox on this system); None when nothing was rendered.
        "sandbox": None,
        "error": None,
    }

    if mode not in ("auto", "always", "never"):
        result["error"] = f"Invalid mode: {mode!r}"
        return result
    if viewport not in VIEWPORTS:
        result["error"] = f"Invalid viewport: {viewport!r}"
        return result

    # Pre-flight SSRF check.
    try:
        norm_url, _pinned_ip = validate_url_strict(url)
        result["url"] = norm_url
    except URLSafetyError as exc:
        result["error"] = f"url_safety: {exc}"
        return result

    # Step 1: raw fetch (always; needed for SPA detection and as a baseline).
    try:
        resp = safe_requests_get(norm_url, timeout=30, allow_redirects=True, stream=True)
        # Streamed so the body is read under the cap; .content must not be
        # read after this.
        try:
            raw, result["too_large"] = read_bounded(resp, MAX_PAGE_BYTES)
        finally:
            resp.close()
        result["raw_content"] = decode_body(raw, resp.headers.get("Content-Type", ""))
        if result["too_large"]:
            result["render_diagnostics"].append(
                "raw body exceeded the size cap; raw_content holds the part read before it"
            )
        if resp.history:
            result["redirect_chain"] = [
                {"url": r.url, "status_code": r.status_code} for r in resp.history
            ]
        raw_status = resp.status_code
        raw_headers = dict(resp.headers)
        final_raw_url = resp.url
    except Exception as exc:
        result["error"] = f"raw fetch failed: {exc}"
        return result

    result["is_spa"] = _is_spa(result["raw_content"])
    should_render = mode == "always" or (mode == "auto" and result["is_spa"])

    if not should_render:
        result["mode_used"] = "raw"
        result["url"] = final_raw_url
        result["status_code"] = raw_status
        result["headers"] = raw_headers
        result["content"] = result["raw_content"]
    else:
        result["mode_used"] = "rendered"

        def _keep_raw_on_render_failure() -> None:
            # The render failed, but the raw fetch succeeded: keep its status,
            # headers and URL so callers still see what the server answered.
            result["url"] = final_raw_url
            result["status_code"] = raw_status
            result["headers"] = raw_headers
            result["raw_fallback_available"] = True

        if sync_playwright is None:
            result["error"] = (
                "playwright is required for rendered mode. "
                "Install: pip install -r requirements.txt "
                "&& playwright install chromium"
            )
            _keep_raw_on_render_failure()
            return result

        vp = VIEWPORTS[viewport]
        blocked = set(block_resources or [])
        route_handler = make_safe_playwright_route_handler(blocked)
        start = time.monotonic()

        try:
            with sync_playwright() as p, guarded_chromium(p.chromium, norm_url) as browser:
                result["sandbox"] = chromium_sandboxed(browser)
                context = new_guarded_context(
                    browser,
                    route_handler,
                    viewport={"width": vp["width"], "height": vp["height"]},
                    device_scale_factor=vp["device_scale"],
                    user_agent=user_agent or USER_AGENT,
                )
                page = context.new_page()

                def _on_console(msg):  # type: ignore[no-untyped-def]
                    if msg.type == "error":
                        result["console_errors"].append(msg.text)

                page.on("console", _on_console)
                page.route("**/*", route_handler)

                try:
                    response = page.goto(
                        norm_url, wait_until="domcontentloaded", timeout=timeout_ms
                    )
                except PlaywrightTimeout:
                    response = None
                    result["render_diagnostics"].append(
                        f"DOMContentLoaded timed out after {timeout_ms}ms; "
                        "captured the available DOM"
                    )
                if not _wait_for_dom_stability(page, timeout_ms):
                    result["render_diagnostics"].append(
                        "DOM did not reach the bounded stability threshold; "
                        "captured the available DOM"
                    )

                # Raises when the browser holds no public document: a blank
                # or error page (PageNotLoadedError) or a page reached through
                # a refused redirect (URLSafetyError). Neither is reported as
                # the rendered site; the raw fetch stays available.
                require_public_page(page)
                result["url"] = page.url
                result["content"] = page.content()
                result["status_code"] = response.status if response else raw_status
                result["headers"] = (
                    dict(response.all_headers()) if response else raw_headers
                )
                result["render_engine"] = "playwright-chromium"

                if extract_accessibility:
                    try:
                        (
                            result["accessibility_tree"],
                            result["accessibility_partial"],
                        ) = _capture_accessibility_tree(context, page)
                        if result["accessibility_tree"] is None:
                            result["accessibility_partial"] = True
                            result["accessibility_error"] = (
                                "Chromium returned no accessibility nodes"
                            )
                        elif result["accessibility_partial"]:
                            result["accessibility_error"] = (
                                "accessibility tree exceeded the capture bounds"
                            )
                    except Exception as exc:
                        result["accessibility_tree"] = None
                        result["accessibility_partial"] = True
                        result["accessibility_error"] = (
                            f"accessibility capture failed: {type(exc).__name__}: {exc}"
                        )
                        result["render_diagnostics"].append(
                            result["accessibility_error"]
                        )

        except URLSafetyError as exc:
            result["error"] = f"url_safety: {exc}"
            _keep_raw_on_render_failure()
            return result
        except PageNotLoadedError as exc:
            result["error"] = f"render failed: {exc}"
            _keep_raw_on_render_failure()
            return result
        except Exception as exc:
            result["error"] = f"playwright error: {exc}"
            _keep_raw_on_render_failure()
            return result
        finally:
            result["render_ms"] = (time.monotonic() - start) * 1000.0

        # Both versions exist: measure what only JavaScript provides.
        try:
            largest = max(len(result["raw_content"] or ""), len(result["content"] or ""))
            if largest > JS_GAP_MAX_HTML_CHARS:
                result["render_diagnostics"].append(
                    f"js_gap skipped: HTML is larger than {JS_GAP_MAX_HTML_CHARS} characters"
                )
            else:
                result["js_gap"] = js_gap(
                    result["raw_content"],
                    result["content"],
                    raw_truncated=result["too_large"],
                )
        except Exception as exc:
            # The comparison is best-effort; never block the audit on it.
            result["render_diagnostics"].append(
                f"js_gap comparison failed: {type(exc).__name__}: {exc}"
            )

    # Step 2: content extraction (works on either raw or rendered HTML).
    if extract_content and result["content"]:
        if trafilatura is not None:
            try:
                result["extracted_text"] = trafilatura.extract(
                    result["content"],
                    include_comments=False,
                    include_tables=True,
                    favor_recall=False,
                )
            except Exception:
                # Extraction is best-effort; never block the audit on it.
                pass
        if find_date is not None:
            try:
                result["publication_date"] = find_date(result["content"])
            except Exception:
                pass

    return result


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def _json_summary(result: dict, *, max_text: int = 0) -> dict:
    """Return an explicit, machine-readable JSON output contract.

    ``max_text=0`` preserves every textual field. Positive values truncate
    content fields and record the original and returned character counts.
    """
    summary = dict(result)
    full_content = result.get("content") or result.get("raw_content") or ""
    summary["structured_data"] = _extract_json_ld(full_content)
    truncation = {"limit": max_text or None, "fields": {}}
    for field in ("content", "raw_content", "extracted_text"):
        value = summary.get(field)
        if not isinstance(value, str):
            continue
        original_chars = len(value)
        truncated = max_text > 0 and original_chars > max_text
        if truncated:
            summary[field] = value[:max_text]
        truncation["fields"][field] = {
            "original_chars": original_chars,
            "returned_chars": len(summary[field]),
            "truncated": truncated,
        }
    summary["truncation"] = truncation
    return summary


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="claude-seo shared headless renderer (Playwright + trafilatura)"
    )
    parser.add_argument("url", help="URL to render")
    parser.add_argument(
        "--mode",
        choices=("auto", "always", "never"),
        default="auto",
        help="auto: render only when SPA detected; always: always render; "
             "never: raw HTML only (default: auto)",
    )
    parser.add_argument(
        "--viewport", choices=list(VIEWPORTS), default="desktop"
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=15000,
        help="Playwright navigation timeout in ms (default: 15000)",
    )
    parser.add_argument(
        "--block",
        action="append",
        default=[],
        choices=("image", "media", "font", "stylesheet"),
        help="resource types to block during render (faster, less accurate)",
    )
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="skip trafilatura and htmldate post-processing",
    )
    parser.add_argument(
        "--a11y-tree",
        action="store_true",
        help="capture Playwright accessibility-tree snapshot (forces render)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON with full content fields unless --max-text is set",
    )
    parser.add_argument(
        "--max-text",
        type=_non_negative_int,
        default=0,
        help=(
            "maximum characters returned for each JSON content field; "
            "0 keeps full text (default: 0)"
        ),
    )
    parser.add_argument(
        "--json-ld-output",
        help=(
            "write bounded full JSON-LD extraction to a UTF-8 JSON file; "
            "normal --json output contains summaries only"
        ),
    )
    parser.add_argument("--output", "-o", help="write HTML content to file")
    args = parser.parse_args()

    effective_mode = "always" if args.a11y_tree else args.mode
    res = render_page(
        args.url,
        mode=effective_mode,
        viewport=args.viewport,
        timeout_ms=args.timeout_ms,
        block_resources=args.block or None,
        extract_content=not args.no_extract,
        extract_accessibility=args.a11y_tree,
    )

    full_content = res.get("content") or res.get("raw_content") or ""
    if args.json_ld_output:
        extraction = _extract_json_ld(full_content, include_full=True)
        with open(args.json_ld_output, "w", encoding="utf-8") as fh:
            json.dump(extraction, fh, indent=2, ensure_ascii=False)

    output_written = False
    if args.output and not res["error"]:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(res["content"] or "")
        output_written = True

    if args.json:
        summary = _json_summary(res, max_text=args.max_text)
        summary["output_written"] = output_written
        print(json.dumps(summary, indent=2, default=str))
        sys.exit(1 if res["error"] else 0)

    if res["error"]:
        print(f"Error: {res['error']}", file=sys.stderr)
        sys.exit(1)

    if output_written:
        print(f"saved to {args.output}", file=sys.stderr)
    else:
        print(res["content"])

    print(
        f"\nFinal URL: {res['url']}\n"
        f"Status: {res['status_code']} | mode={res['mode_used']} | "
        f"is_spa={res['is_spa']}",
        file=sys.stderr,
    )
    if res["render_ms"]:
        print(
            f"Render: {res['render_ms']:.0f}ms via {res['render_engine']}",
            file=sys.stderr,
        )
    if res["publication_date"]:
        print(f"Publication date: {res['publication_date']}", file=sys.stderr)
    for reason in (res.get("js_gap") or {}).get("reasons", []):
        print(f"JS gap: {reason}", file=sys.stderr)
    if res["console_errors"]:
        print(
            f"Console errors ({len(res['console_errors'])}):", file=sys.stderr
        )
        for err in res["console_errors"][:5]:
            print(f"  - {err}", file=sys.stderr)


if __name__ == "__main__":
    _cli()
