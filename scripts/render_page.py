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
    error             str or None

SSRF
====
The URL is validated via :func:`url_safety.validate_url_strict` before
Playwright sees it. Inside Playwright a ``route()`` handler intercepts
every subresource and aborts requests whose hostname resolves to a
non-public IP. This is defence in depth against DNS rebinding inside
Chromium's resolver. The residual rebinding risk for browser fetches
is documented in SECURITY.md.

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
from url_safety import (  # noqa: E402  (sys.path massage above is intentional)
    URLSafetyError,
    make_safe_playwright_route_handler,
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


def _extract_json_ld(html: Optional[str], *, include_full: bool = False) -> dict:
    """Extract full-page JSON-LD with strict block, byte, and traversal bounds."""
    result = {
        "block_count": 0,
        "processed_count": 0,
        "total_bytes": 0,
        "truncated": False,
        "blocks": [],
    }
    if not html:
        return result

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

    # Step 1 — raw fetch (always; needed for SPA detection and as a baseline).
    try:
        resp = safe_requests_get(norm_url, timeout=30, allow_redirects=True)
        result["raw_content"] = resp.text
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
        if sync_playwright is None:
            result["error"] = (
                "playwright is required for rendered mode. "
                "Install: pip install -r requirements.txt "
                "&& playwright install chromium"
            )
            return result

        vp = VIEWPORTS[viewport]
        blocked = set(block_resources or [])
        route_handler = make_safe_playwright_route_handler(blocked)
        start = time.monotonic()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
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

                browser.close()
        except Exception as exc:
            result["error"] = f"playwright error: {exc}"
            return result
        finally:
            result["render_ms"] = (time.monotonic() - start) * 1000.0

    # Step 2 — content extraction (works on either raw or rendered HTML).
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
    if res["console_errors"]:
        print(
            f"Console errors ({len(res['console_errors'])}):", file=sys.stderr
        )
        for err in res["console_errors"][:5]:
            print(f"  - {err}", file=sys.stderr)


if __name__ == "__main__":
    _cli()
