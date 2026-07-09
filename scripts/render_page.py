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
    headers           response headers from the main document
    redirect_chain    list of {url, status_code}
    console_errors    list of browser console error strings
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
from typing import Optional

# Optional native dependencies. Each is checked lazily so callers that
# only need raw-mode (mode='never') don't pay the import cost.
try:
    from playwright.sync_api import (
        sync_playwright,
        TimeoutError as PlaywrightTimeout,
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
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 ClaudeSEO/2.0"
)

# Hydration-shell signatures. Any single match flips is_spa to True. These
# cover the dominant SPA frameworks: React (CRA, Vite, Remix), Next.js,
# Vue, Nuxt, Svelte, Astro islands, and the "JS required" noscript pattern.
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

_TAG_STRIP = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


_JSON_LD_BLOCK = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _extract_json_ld(html: Optional[str]) -> list[dict]:
    """Pull every JSON-LD script block out of full HTML, in full.

    Runs on the untruncated content so the --json summary's character
    limit (see _cli) can never silently hide a structured-data block from
    a schema-focused agent. Malformed blocks are still reported (as raw
    text) rather than dropped, so a schema agent can flag invalid JSON-LD
    instead of missing it entirely.
    """
    if not html:
        return []
    blocks: list[dict] = []
    for raw in _JSON_LD_BLOCK.findall(html):
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
            blocks.append({"valid": True, "data": parsed})
        except json.JSONDecodeError as exc:
            blocks.append({"valid": False, "raw": raw, "error": str(exc)})
    return blocks


def _is_spa(raw_html: Optional[str]) -> bool:
    """Heuristic SPA detector. Conservative: any positive signal flips True."""
    if not raw_html:
        return True
    lc = raw_html.lower()
    if any(pattern in lc for pattern in _SPA_SHELL_PATTERNS):
        return True
    # Very thin <body> suggests JS-rendered content even without a shell.
    # Threshold (100 chars) sits between typical SPA shells (0-50 chars of
    # body text) and minimal informational pages like example.com (~125
    # chars). Tuned conservatively to avoid false positives that would
    # force a redundant Playwright render in auto mode.
    body_start = lc.find("<body")
    body_end = lc.rfind("</body>")
    if body_start != -1 and body_end > body_start:
        body = lc[body_start:body_end]
        text = _WHITESPACE.sub(" ", _TAG_STRIP.sub("", body)).strip()
        if len(text) < 100:
            return True
    return False


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
    'always' or 'auto'+SPA), the Playwright accessibility-tree snapshot is
    captured and attached to ``result['accessibility_tree']``. Used by
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
        "headers": {},
        "redirect_chain": [],
        "console_errors": [],
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

                response = page.goto(
                    norm_url, wait_until="networkidle", timeout=timeout_ms
                )
                # Allow late hydration (deferred islands, useEffect chains).
                page.wait_for_timeout(500)

                result["url"] = page.url
                result["content"] = page.content()
                result["status_code"] = response.status if response else raw_status
                result["headers"] = (
                    dict(response.all_headers()) if response else raw_headers
                )
                result["render_engine"] = "playwright-chromium"

                if extract_accessibility:
                    try:
                        result["accessibility_tree"] = page.accessibility.snapshot(
                            interesting_only=False
                        )
                    except Exception:
                        # Accessibility snapshot is best-effort; never block the audit.
                        result["accessibility_tree"] = None

                browser.close()
        except PlaywrightTimeout:
            result["error"] = f"playwright navigation timed out after {timeout_ms}ms"
            return result
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
        help="emit a JSON summary (truncates content fields)",
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

    if args.json:
        summary = dict(res)
        # Structured-data blocks (JSON-LD) are extracted from the full,
        # untruncated content BEFORE truncation below, so a schema check
        # never has to re-fetch full HTML just to rule out a block that
        # got cut off by the character limit. See _extract_json_ld().
        full_content = summary.get("content") or summary.get("raw_content") or ""
        summary["structured_data_blocks"] = _extract_json_ld(full_content)
        # JSON-safe truncation so the CLI is usable from agents without
        # piping megabytes of HTML across stdio.
        for field, limit in (
            ("content", 500),
            ("raw_content", 200),
            ("extracted_text", 500),
        ):
            if summary.get(field):
                value = summary[field]
                summary[field] = (
                    value[:limit] + "..." if len(value) > limit else value
                )
        print(json.dumps(summary, indent=2, default=str))
        sys.exit(1 if res["error"] else 0)

    if res["error"]:
        print(f"Error: {res['error']}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(res["content"] or "")
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
