#!/usr/bin/env python3
"""
Parse HTML and extract SEO-relevant elements.

Usage:
    python parse_html.py page.html
    python parse_html.py --url https://example.com
    python parse_html.py --url https://example.com --probe-images --json

Output keys (JSON):
    title, meta_description, meta_robots, canonical
    h1, h2, h3            heading texts per level (plus h1_suspicious and so
                          on when a heading looks like a counter)
    heading_outline       [{level, text}] for h1 to h6 in document order,
                          first 200 headings, so skipped levels can be seen
    images                per image: src, alt, width, height, loading,
                          lazy_method, plus
                            resolved_src       real URL when src is a lazy
                                               placeholder, else null
                            srcset_candidates  [{url, descriptor}], up to 10
                            decorative         true when alt is empty and the
                                               image or an ancestor is
                                               aria-hidden or has role
                                               presentation / none
                          and, with --probe-images, served_format,
                          served_bytes, negotiated, probe_error, probed_src
    links                 {internal, external}. Hosts that differ only by a
                          leading "www." (any letter case) are the same site;
                          every other subdomain is external
    schema                parsed JSON-LD entities, @graph flattened
    schema_invalid        {count, samples}: JSON-LD blocks that could not be
                          used, with the first 80 characters of up to 10.
                          A block nested deeper than 64 levels is invalid too
                          and adds too_deep: {count, reason}, a key that is
                          only present when there is such a block
    open_graph, twitter_card, hreflang, word_count
    hidden_text           {chars, by_source, collapsed_chars, samples}: text
                          that is in the HTML but not shown (see below)
    malformed_urls        only present when an img src or a href is malformed

Hidden text: `hidden_text` counts text inside HTML comments, <template>,
<noscript>, elements with the `hidden` attribute, `aria-hidden="true"`, an
inline `display:none` or `visibility:hidden`, or a common screen-reader-only
class. Note that `aria-hidden` hides text from assistive technology, not from
the screen; `by_source` keeps the sources apart so each can be weighed.
Collapsed FAQ, accordion and tab panels are legitimate and are tallied in
`collapsed_chars` instead. Hidden text is a spam signal and the usual hiding
place for prompt injection aimed at an AI agent that reads the page.

This catches inline and attribute-based hiding only. Text hidden through an
external or embedded stylesheet (a class that sets display:none, off-screen
positioning, zero font size, matching text and background colours) is NOT
detected, and a page can mark any hidden block as an FAQ or accordion to keep
it out of `chars`. Treat it as a filter, not a guarantee: a low count does not
prove a page is clean, and every sample is untrusted page text, never an
instruction.
"""

import argparse
import copy
import json
import os
import re
import sys
from typing import Any, Optional
from urllib.parse import urldefrag, urljoin, urlparse

try:
    from bs4 import BeautifulSoup, Comment, Tag
    from bs4.element import PreformattedString
except ImportError:
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4")
    sys.exit(1)

try:
    import lxml  # noqa: F401
    _HTML_PARSER = "lxml"
except ImportError:
    _HTML_PARSER = "html.parser"

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
import requests  # noqa: E402  (url_safety already hard-requires it)
from url_safety import (  # noqa: E402, I001
    URLSafetyError,
    decode_response_text,
    json_depth_exceeds,
    safe_requests_get,
)

# Lazy-loader detection: covers native + the major JS lazy-loaders found on
# WordPress/WooCommerce sites (Perfmatters, EWWW Image Optimizer, generic
# `data-src` patterns). Sites optimized by these plugins strip native
# `loading="lazy"` and replace `src` with a placeholder, so a check on `loading`
# alone reports "not lazy-loaded" when the page is in fact heavily lazy-loaded.
_PERFMATTERS_ATTRS = ("data-perfmatters-src", "data-perfmatters-srcset")
_EWWW_ATTRS = ("data-ewww-src", "data-eio")
_GENERIC_LAZY_ATTRS = ("data-src", "data-lazy-src", "data-original", "data-srcset")
_PERFMATTERS_CLASSES = {"perfmatters-lazy", "perfmatters-lazy-loaded"}
_EWWW_CLASSES = {"lazyload-eio", "lazyloaded-eio"}
_GENERIC_LAZY_CLASSES = {"lazyload", "lazyloaded", "lazy", "lazy-loaded"}

# Real-source resolution for lazy-loaded images. A JS lazy-loader parks the
# real URL in one of these attributes and leaves `src` empty or pointing at a
# placeholder (a data: URI, a 1x1 gif, a low-quality preview).
_LAZY_SRC_ATTRS = (
    "data-perfmatters-src",
    "data-ewww-src",
    "data-src",
    "data-lazy-src",
    "data-original",
)
_LAZY_SRCSET_ATTRS = ("data-perfmatters-srcset", "data-srcset", "data-lazy-srcset")
_PLACEHOLDER_SCHEMES = ("data:", "blob:", "about:")

# Page content is untrusted, so every new list and string is bounded.
_MAX_SRCSET_CANDIDATES = 10
_MAX_SRCSET_CHARS = 8192
_MAX_URL_CHARS = 2048
_MAX_DESCRIPTOR_CHARS = 20
_MAX_OUTLINE_HEADINGS = 200
_MAX_HEADING_CHARS = 300
_MAX_INVALID_SCHEMA_SAMPLES = 10
_INVALID_SCHEMA_SAMPLE_CHARS = 80
# Deepest nesting of arrays and objects a JSON-LD block may have. Real markup
# stays under about ten levels. Python's JSON encoder recurses once per level,
# so a block nested past the interpreter's recursion limit (1,000 by default)
# parsed fine and then raised RecursionError when the result was printed. A
# deeper block is counted in `schema_invalid` and never reaches `schema`, which
# keeps every consumer of `schema` (this script's JSON output and the scripts
# that import it) clear of the limit.
_MAX_JSON_LD_DEPTH = 64
_MAX_HIDDEN_SAMPLES = 5
_HIDDEN_SAMPLE_CHARS = 200

# Hidden-text rule set. Class tokens that mark a collapsed panel are matched
# as substrings (`faq-answer`, `accordion__body`); screen-reader-only classes
# are matched as whole class names.
_HIDDEN_SOURCES = (
    "comment",
    "template",
    "noscript",
    "hidden_attr",
    "aria_hidden",
    "inline_style",
    "sr_only_class",
)
_SR_ONLY_CLASSES = {
    "sr-only",
    "screen-reader-text",
    "screen-reader-only",
    "visually-hidden",
    "visuallyhidden",
}
_COLLAPSED_CLASS_TOKENS = ("faq", "accordion", "tab-panel")
_COLLAPSED_ROLES = {"region", "tabpanel"}
_IGNORED_TEXT = object()  # script and style bodies are code, not text

# Served-format probe (issue #331). WordPress WebP plugins (EWWW, ShortPixel,
# WebP Express, Imagify), Cloudflare Polish and image CDNs serve WebP or AVIF
# from a `.jpg`/`.png` URL when the browser's Accept header allows it, so the
# URL extension is not the format visitors receive. The probe asks the way a
# browser does and reads the format from Content-Type, then the magic bytes.
IMAGE_ACCEPT = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
_SNIFF_BYTES = 512  # room for an XML prolog and comment ahead of an <svg> root
_CONTENT_TYPE_FORMATS = {
    "image/avif": "avif",
    "image/webp": "webp",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/pjpeg": "jpeg",
    "image/png": "png",
    "image/apng": "png",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    "image/jxl": "jxl",
}


def _has_svg_root(head: bytes) -> bool:
    """Return True when the first element in ``head`` is ``<svg``.

    An XML declaration alone proves nothing: sitemaps, feeds and XHTML error
    pages start with ``<?xml`` too. Skip the prolog (declaration, processing
    instructions, comments, DOCTYPE) and look at the root element itself.
    """
    rest = head.removeprefix(b"\xef\xbb\xbf").lstrip()
    while True:
        if rest.startswith(b"<?"):
            end, skip = rest.find(b"?>"), 2
        elif rest.startswith(b"<!--"):
            end, skip = rest.find(b"-->"), 3
        elif rest[:9].upper() == b"<!DOCTYPE":
            end, skip = rest.find(b">"), 1
        else:
            return rest[:4].lower() == b"<svg"
        if end < 0:
            return False
        rest = rest[end + skip:].lstrip()


def _sniff_image_format(head: bytes) -> Optional[str]:
    """Return the image format named by the file's magic bytes, or None."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[4:8] == b"ftyp" and head[8:12] in (b"avif", b"avis"):
        return "avif"
    if head.startswith((b"\xff\x0a", b"\x00\x00\x00\x0cJXL ")):
        return "jxl"
    if _has_svg_root(head):
        return "svg"
    return None


def probe_image_format(src: str, timeout: int = 15) -> dict:
    """Fetch the start of an image the way a browser does and report what is served.

    Returns ``served_format`` (from the magic bytes, else Content-Type),
    ``served_bytes`` (Content-Length, or None when the server omits it),
    ``negotiated`` (True when the response varies on Accept, so the format
    depends on the client) and ``probe_error`` (None on success). A response
    that is not a recognized image, such as an HTML soft 404 or a hotlink
    protection page, sets ``probe_error`` so the format is never read as known.
    """
    result = {
        "served_format": None,
        "served_bytes": None,
        "negotiated": False,
        "probe_error": None,
    }
    try:
        scheme = urlparse(src).scheme if src else ""
    except ValueError as exc:
        result["probe_error"] = f"malformed URL: {exc}"
        return result
    if scheme not in ("http", "https"):
        result["probe_error"] = "not an http(s) URL"
        return result

    try:
        resp = safe_requests_get(
            src,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
            headers={"Accept": IMAGE_ACCEPT, "Accept-Encoding": "identity"},
        )
        try:
            if resp.status_code >= 400:
                result["probe_error"] = f"HTTP {resp.status_code}"
                return result
            head = next(resp.iter_content(_SNIFF_BYTES), b"")
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            result["served_format"] = (
                _sniff_image_format(head) or _CONTENT_TYPE_FORMATS.get(content_type)
            )
            if result["served_format"] is None:
                result["probe_error"] = (
                    f"not a recognized image (Content-Type: {content_type or 'none'})"
                )
            length = resp.headers.get("Content-Length")
            result["served_bytes"] = int(length) if length and length.isdigit() else None
            vary = resp.headers.get("Vary", "").lower()
            result["negotiated"] = "accept" in [v.strip() for v in vary.split(",")]
        finally:
            resp.close()
    except URLSafetyError as exc:
        result["probe_error"] = f"url_safety: {exc}"
    except requests.exceptions.RequestException as exc:
        result["probe_error"] = f"request failed: {exc}"
    return result


def probe_images(images: list, timeout: int = 15, limit: int = 50) -> list:
    """Add the served-format fields from ``probe_image_format`` to each image entry.

    Probes at most ``limit`` distinct URLs; entries past the limit get
    ``probe_error`` set so the report never guesses their format.

    A lazy-loaded image is probed at its ``resolved_src``, since its ``src``
    is only a placeholder. ``probed_src`` records the URL that was asked for.
    """
    cache: dict = {}
    for image in images:
        src = image.get("resolved_src") or image.get("src", "")
        if src not in cache:
            if len(cache) >= limit:
                cache[src] = {
                    "served_format": None,
                    "served_bytes": None,
                    "negotiated": False,
                    "probe_error": f"skipped: probe limit of {limit} images reached",
                }
            else:
                cache[src] = probe_image_format(src, timeout=timeout)
        image.update(cache[src])
        image["probed_src"] = src
    return images


def _has_rel_token(tag, token: str) -> bool:
    """Case-insensitively check whether a tag's ``rel`` attribute carries ``token``.

    bs4 treats ``rel`` as a multi-valued attribute for ``<a>`` and ``<link>``
    tags, splitting it on whitespace into a list. Both the attribute *name*
    (``REL=``) and the surrounding tag name are lower-cased by the underlying
    HTML parser, but the attribute *value* is preserved verbatim, so
    ``rel="Alternate"`` or ``rel="CANONICAL"`` never matched an exact,
    lower-case comparison such as ``soup.find("link", rel="canonical")``.
    """
    rel = tag.get("rel", [])
    if isinstance(rel, str):
        rel = rel.split()
    return any(isinstance(value, str) and value.lower() == token for value in rel or [])


def _element_text(tag) -> str:
    """Return a tag's visible text with each run of whitespace collapsed to one space.

    ``get_text(strip=True)`` strips every text node before joining them, so the
    spaces next to inline tags are lost (``for <em>every</em> dollar`` becomes
    ``foreverydollar``). Joining the unstripped text and collapsing whitespace
    keeps those spaces and also folds newlines in multi-line headings.

    A ``<br>`` is a line break, so it separates words (``Foo<br>Bar`` reads
    ``Foo Bar``). Other inline tags add nothing: ``Web<span>Obs</span>`` stays
    ``WebObs``. The break is swapped for a space on a copy, so the parsed
    document is left as it was.
    """
    if tag.find("br") is not None:
        tag = copy.copy(tag)
        for br in tag.find_all("br"):
            br.replace_with(" ")
    return " ".join(tag.get_text().split())


def _detect_lazy_method(img) -> str:
    """Return a coarse classification of the image's lazy-loading mechanism.

    Order of detection: native -> perfmatters -> ewww -> js-generic -> none.
    Specific JS lazy-loaders are checked before the generic bucket so reports
    can attribute the optimization to the right plugin (which informs whether
    a site is using a specific WP optimization stack).

    Returns one of: 'native', 'perfmatters', 'ewww', 'js-generic', 'none'.
    """
    if img.get("loading", "").lower() == "lazy":
        return "native"

    class_list = set(img.get("class", []) or [])

    if any(img.get(a) for a in _PERFMATTERS_ATTRS) or class_list & _PERFMATTERS_CLASSES:
        return "perfmatters"

    if any(img.get(a) for a in _EWWW_ATTRS) or class_list & _EWWW_CLASSES:
        return "ewww"

    if any(img.get(a) for a in _GENERIC_LAZY_ATTRS) or class_list & _GENERIC_LAZY_CLASSES:
        return "js-generic"

    return "none"


def _attr_text(tag, name: str) -> str:
    """Return an attribute as one string, whatever shape the parser gave it."""
    value = tag.get(name)
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value)
    return str(value)


def _parse_srcset(value: str) -> list:
    """Split a ``srcset`` value into ``(url, descriptor)`` pairs.

    The URL is read up to the next whitespace before any comma is looked at,
    so the commas inside a ``data:`` URL are not taken for separators. A URL
    that ends in a comma has no descriptor; otherwise the descriptor runs to
    the next comma.
    """
    pairs = []
    remaining = value[:_MAX_SRCSET_CHARS]
    while len(pairs) < _MAX_SRCSET_CANDIDATES * 5:
        remaining = remaining.lstrip(" ,\t\r\n\f")
        if not remaining:
            break
        pieces = remaining.split(None, 1)
        token = pieces[0]
        rest = pieces[1] if len(pieces) > 1 else ""
        if token.endswith(","):
            pairs.append((token.rstrip(","), ""))
            remaining = rest
        else:
            descriptor, _, remaining = rest.partition(",")
            pairs.append((token, descriptor.strip()))
    return pairs


def _resolve_candidate_url(base_url: Optional[str], value: str) -> Optional[str]:
    """Resolve one candidate image URL, or return None when it is not usable.

    Unusable means empty, over-long, malformed (such as ``http://[bad/a.jpg``)
    or not a web URL (``data:``, ``blob:``, ``javascript:``). A bad candidate
    is skipped and never aborts the parse. Without a base URL a relative value
    stays relative, the same way ``src`` does.
    """
    value = value.strip()
    if not value or len(value) > _MAX_URL_CHARS:
        return None
    try:
        full = urljoin(base_url, value) if base_url else value
        scheme = urlparse(full).scheme.lower()
    except ValueError:
        return None
    return full if scheme in ("http", "https", "") else None


def _image_sources(img, base_url: Optional[str], src: str) -> tuple:
    """Return ``(resolved_src, srcset_candidates)`` for one image.

    ``srcset_candidates`` lists the usable entries of the first of
    ``data-srcset`` (and its plugin variants) or ``srcset`` that has any.

    ``resolved_src`` is the real image URL when ``src`` is not it:

    1. A lazy source attribute wins over ``src``. Loaders that keep a 1x1 gif
       or a blurred preview in ``src`` are covered without guessing from the
       file name.
    2. Otherwise the last candidate of a lazy ``data-srcset``.
    3. Otherwise, when ``src`` is empty or a ``data:`` / ``blob:`` placeholder,
       the last ``srcset`` candidate.

    It is None when nothing was found or the result is ``src`` itself.
    """
    candidates: list = []
    from_lazy_srcset = False
    for attr in (*_LAZY_SRCSET_ATTRS, "srcset"):
        for url, descriptor in _parse_srcset(_attr_text(img, attr)):
            full = _resolve_candidate_url(base_url, url)
            if full and len(candidates) < _MAX_SRCSET_CANDIDATES:
                candidates.append(
                    {"url": full, "descriptor": descriptor[:_MAX_DESCRIPTOR_CHARS]}
                )
        if candidates:
            from_lazy_srcset = attr != "srcset"
            break

    raw_src = _attr_text(img, "src").strip().lower()
    src_is_placeholder = not raw_src or raw_src.startswith(_PLACEHOLDER_SCHEMES)

    resolved = None
    for attr in _LAZY_SRC_ATTRS:
        resolved = _resolve_candidate_url(base_url, _attr_text(img, attr))
        if resolved:
            break
    if not resolved and candidates and (from_lazy_srcset or src_is_placeholder):
        resolved = candidates[-1]["url"]
    if resolved == src:
        resolved = None
    return resolved, candidates


def _is_decorative_image(img) -> bool:
    """True when the image has no alt text and is marked as decoration.

    The mark is ``aria-hidden="true"`` or ``role="presentation"`` /
    ``role="none"`` on the image or on any ancestor. Such an image is skipped
    by assistive technology, so a missing alt on it is not a finding.
    """
    if _attr_text(img, "alt").strip():
        return False
    node = img
    while node is not None and getattr(node, "attrs", None) is not None:
        if _attr_text(node, "aria-hidden").strip().lower() == "true":
            return True
        if {"presentation", "none"} & set(_attr_text(node, "role").lower().split()):
            return True
        node = node.parent
    return False


def _site_host(netloc: str) -> str:
    """Return a netloc lower-cased and without one leading ``www.``.

    ``example.com`` and ``WWW.Example.com`` are the same site. Any other
    subdomain (``blog.example.com``) is a different host and stays external.
    """
    host = netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _is_json_ld(script) -> bool:
    """True for ``type="application/ld+json"`` in any letter case.

    Surrounding whitespace and parameters are allowed, as in
    ``application/ld+json; charset=utf-8``.
    """
    return _attr_text(script, "type").split(";")[0].strip().lower() == "application/ld+json"


def _hidden_source(tag, controlled_ids: set) -> Optional[str]:
    """Say why ``tag`` hides its text from the reader, or return None.

    Returns one of ``_HIDDEN_SOURCES``, or ``"collapsed"`` for a hidden
    element that is a legitimately collapsed panel: its class names it as FAQ,
    accordion or tab panel content, its role is ``region`` or ``tabpanel``, or
    a disclosure control points at it with ``aria-controls``.
    """
    if tag.name in ("template", "noscript"):
        return tag.name

    source = None
    if tag.has_attr("hidden"):
        source = "hidden_attr"
    elif _attr_text(tag, "aria-hidden").strip().lower() == "true":
        source = "aria_hidden"
    else:
        style = "".join(_attr_text(tag, "style").lower().split())
        if "display:none" in style or "visibility:hidden" in style:
            source = "inline_style"

    classes = _attr_text(tag, "class").lower()
    if source:
        if (
            any(token in classes for token in _COLLAPSED_CLASS_TOKENS)
            or _attr_text(tag, "role").strip().lower() in _COLLAPSED_ROLES
            or _attr_text(tag, "id").strip() in controlled_ids
        ):
            return "collapsed"
        return source
    if _SR_ONLY_CLASSES & set(classes.split()):
        return "sr_only_class"
    return None


def _scan_hidden_text(soup) -> dict:
    """Measure text that is in the HTML but not shown to a reader.

    One pass in document order. Each outermost hidden element is one block, so
    nested hiding is counted once; an HTML comment outside a hidden element is
    a block of its own. Characters are counted after collapsing whitespace.
    The samples are the longest blocks, since a long hidden passage matters
    more than a hidden icon label. Read-only: the document is not changed.

    Inline and attribute-based hiding only. See the module docstring for what
    this cannot see.
    """
    controlled_ids: set = set()
    for control in soup.find_all(attrs={"aria-controls": True}):
        controlled_ids.update(_attr_text(control, "aria-controls").split())
    controlled_ids.discard("")

    blocks: list = []
    collapsed_chars = 0
    # id(tag) -> the hidden block that owns its text, "collapsed", or
    # _IGNORED_TEXT. A tag that is absent is visible. A parent is always
    # visited before its children, so one lookup settles each node.
    state: dict = {}

    for node in soup.descendants:
        owner = state.get(id(node.parent))
        if isinstance(node, Tag):
            if node.name in ("script", "style"):
                state[id(node)] = _IGNORED_TEXT
            elif owner is _IGNORED_TEXT or isinstance(owner, dict):
                state[id(node)] = owner
            else:
                source = _hidden_source(node, controlled_ids)
                if source == "collapsed":
                    state[id(node)] = "collapsed"
                elif source:
                    block = {"source": source, "chars": 0, "text": ""}
                    blocks.append(block)
                    state[id(node)] = block
                elif owner is not None:
                    state[id(node)] = owner
            continue

        if owner is _IGNORED_TEXT:
            continue
        if isinstance(node, Comment):
            if not isinstance(owner, dict):
                owner = {"source": "comment", "chars": 0, "text": ""}
                blocks.append(owner)
        elif isinstance(node, PreformattedString):
            continue  # doctype, declaration, processing instruction, CDATA

        text = " ".join(str(node).split())
        if not text:
            continue
        if isinstance(owner, dict):
            owner["chars"] += len(text)
            if len(owner["text"]) < _HIDDEN_SAMPLE_CHARS:
                owner["text"] = f"{owner['text']} {text}".strip()[:_HIDDEN_SAMPLE_CHARS]
        elif owner == "collapsed":
            collapsed_chars += len(text)

    by_source = dict.fromkeys(_HIDDEN_SOURCES, 0)
    for block in blocks:
        by_source[block["source"]] += block["chars"]
    longest = sorted(
        (block for block in blocks if block["chars"]),
        key=lambda block: block["chars"],
        reverse=True,
    )
    return {
        "chars": sum(by_source.values()),
        "by_source": by_source,
        "collapsed_chars": collapsed_chars,
        "samples": longest[:_MAX_HIDDEN_SAMPLES],
    }


def _inherit_context(node: dict[str, Any], context: Any) -> dict[str, Any]:
    """Return a JSON-LD node that carries the document's ``@context``.

    A ``@graph`` container is not an entity: it declares the document's
    ``@context`` and its entries inherit it. Flattening the container used to
    drop that ``@context``, so every entry came out looking like a block with
    an ``@type`` but no ``@context``, which the seo-schema instructions read as
    broken markup. An entry that declares its own ``@context`` keeps it. The
    input node is never mutated, so the parsed document stays intact.
    """
    if context is None or "@context" in node:
        return node
    return {"@context": context, **node}


def parse_html(html: str, base_url: Optional[str] = None) -> dict:
    """
    Parse HTML and extract SEO-relevant elements.

    Args:
        html: HTML content to parse
        base_url: Base URL for resolving relative links

    Returns:
        Dictionary with extracted SEO data
    """
    soup = BeautifulSoup(html, _HTML_PARSER)
    resource_base_url = base_url
    base = soup.find("base", href=True)
    if base:
        try:
            candidate = urljoin(base_url or "", base["href"])
            # Only a web base is honoured, so file:, mailto:, data: and
            # javascript: never reach the output. An empty scheme is a relative
            # base read without a page URL, and it stays relative.
            if urlparse(candidate).scheme.lower() in {"http", "https", ""}:
                resource_base_url = candidate
        except ValueError:
            pass  # An invalid base falls back to the document URL.

    result = {
        "title": None,
        "meta_description": None,
        "meta_robots": None,
        "canonical": None,
        "h1": [],
        "h2": [],
        "h3": [],
        "heading_outline": [],
        "images": [],
        "links": {
            "internal": [],
            "external": [],
        },
        "schema": [],
        "schema_invalid": {"count": 0, "samples": []},
        "open_graph": {},
        "twitter_card": {},
        "word_count": 0,
        "hreflang": [],
        "hidden_text": {},
    }

    # Title
    title_tag = soup.find("title")
    if title_tag:
        result["title"] = _element_text(title_tag)

    # Meta tags
    for meta in soup.find_all("meta"):
        name = meta.get("name", "").lower()
        property_attr = meta.get("property", "").lower()
        content = meta.get("content", "")

        if name == "description":
            result["meta_description"] = content
        elif name == "robots":
            result["meta_robots"] = content

        # Open Graph
        if property_attr.startswith("og:"):
            result["open_graph"][property_attr] = content

        # Twitter Card
        if name.startswith("twitter:"):
            result["twitter_card"][name] = content

    # Canonical
    canonical = next(
        (link for link in soup.find_all("link") if _has_rel_token(link, "canonical")), None
    )
    if canonical:
        result["canonical"] = canonical.get("href")

    # Hreflang
    for link in soup.find_all("link"):
        if not _has_rel_token(link, "alternate"):
            continue
        hreflang = link.get("hreflang")
        if hreflang:
            result["hreflang"].append({
                "lang": hreflang,
                "href": link.get("href"),
            })

    # Headings
    for tag in ["h1", "h2", "h3"]:
        for heading in soup.find_all(tag):
            text = _element_text(heading)
            if text:
                result[tag].append(text)
                # Flag suspiciously short or purely numeric headings (likely counters/stats)
                stripped = text.strip()
                is_suspicious = (
                    len(stripped) <= 3
                    or stripped.replace(",", "").replace(".", "").replace("+", "").replace("-", "").replace("%", "").replace(" ", "").isdigit()
                )
                if is_suspicious:
                    key = f"{tag}_suspicious"
                    if key not in result:
                        result[key] = []
                    result[key].append(text)

    # Heading outline: every level in document order, so a skipped level
    # (an h4 straight after an h2) can be seen. Same text rule as above.
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if len(result["heading_outline"]) >= _MAX_OUTLINE_HEADINGS:
            break
        text = _element_text(heading)
        if text:
            result["heading_outline"].append(
                {"level": int(heading.name[1]), "text": text[:_MAX_HEADING_CHARS]}
            )

    # Images
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if resource_base_url and src:
            try:
                src = urljoin(resource_base_url, src)
            except ValueError:
                # Such as http://[bad/a.jpg. Keep the raw value so the image
                # is still counted, and carry on with the rest of the page.
                result.setdefault("malformed_urls", []).append({"tag": "img", "value": src})

        resolved_src, srcset_candidates = _image_sources(img, resource_base_url, src)

        result["images"].append({
            "src": src,
            "alt": img.get("alt"),
            "width": img.get("width"),
            "height": img.get("height"),
            "loading": img.get("loading"),
            "lazy_method": _detect_lazy_method(img),
            "resolved_src": resolved_src,
            "srcset_candidates": srcset_candidates,
            "decorative": _is_decorative_image(img),
        })

    # Links
    if base_url:
        base_domain = _site_host(urlparse(base_url).netloc)
        # A fragment-only href resolves against the document base URL (HTML
        # spec), so it stays on this page only while the base is this page.
        # With <base> pointing elsewhere, #frag is a link to that other URL.
        base_is_page = urldefrag(resource_base_url)[0] == urldefrag(base_url)[0]

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not href or href.startswith("javascript:"):
                continue
            if href.startswith("#") and base_is_page:
                continue

            try:
                full_url = urljoin(resource_base_url, href)
                parsed = urlparse(full_url)
            except ValueError:
                # Such as http://[bad/x. Record it and carry on.
                result.setdefault("malformed_urls", []).append({"tag": "a", "value": href})
                continue

            link_data = {
                "href": full_url,
                "text": _element_text(a)[:100],
                "rel": a.get("rel", []),
            }

            if _site_host(parsed.netloc) == base_domain:
                result["links"]["internal"].append(link_data)
            else:
                result["links"]["external"].append(link_data)

    # Schema (JSON-LD)
    for script in soup.find_all("script"):
        if not _is_json_ld(script):
            continue
        too_deep = False
        try:
            # A linear scan of the text, with no recursion, before anything
            # is built from it.
            too_deep = json_depth_exceeds(script.string or "", _MAX_JSON_LD_DEPTH)
            if too_deep:
                raise ValueError("JSON-LD nested too deep")
            schema_data = json.loads(script.string)
            # Flatten @graph containers so each @type is a separate entry.
            # The container is not an entity, so it carries no @type of its
            # own, but its @context is inherited by the entries it holds.
            if isinstance(schema_data, dict) and "@graph" in schema_data:
                inherited_context = schema_data.get("@context")
                graph = schema_data["@graph"]
                if isinstance(graph, dict):
                    graph = [graph]
                elif not isinstance(graph, list):
                    raise ValueError("@graph must be an object or list")
                for item in graph:
                    if isinstance(item, dict):
                        result["schema"].append(_inherit_context(item, inherited_context))
            elif isinstance(schema_data, list):
                for item in schema_data:
                    if isinstance(item, dict):
                        result["schema"].append(item)
            else:
                result["schema"].append(schema_data)
        except (ValueError, TypeError, RecursionError) as exc:
            # Not valid JSON, empty, nested too deep, or a @graph that cannot
            # be walked. Count the block and keep a short sample instead of
            # dropping it without a trace. RecursionError is the backstop for
            # the depth scan above.
            invalid = result["schema_invalid"]
            invalid["count"] += 1
            if too_deep or isinstance(exc, RecursionError):
                reason = f"nested deeper than {_MAX_JSON_LD_DEPTH} levels"
                invalid.setdefault("too_deep", {"count": 0, "reason": reason})["count"] += 1
            if len(invalid["samples"]) < _MAX_INVALID_SCHEMA_SAMPLES:
                raw = str(script.string or "")[: _INVALID_SCHEMA_SAMPLE_CHARS * 5]
                invalid["samples"].append(" ".join(raw.split())[:_INVALID_SCHEMA_SAMPLE_CHARS])

    # Hidden text. Measured before the word count below removes elements, and
    # read-only, so the word count is unchanged.
    result["hidden_text"] = _scan_hidden_text(soup)

    # Word count (visible text only)
    for element in soup(["script", "style", "nav", "footer", "header"]):
        element.decompose()

    text = soup.get_text(separator=" ", strip=True)
    words = re.findall(r"\b\w+\b", text)
    result["word_count"] = len(words)

    return result


def main():
    parser = argparse.ArgumentParser(description="Parse HTML for SEO analysis")
    parser.add_argument("file", nargs="?", help="HTML file to parse")
    parser.add_argument("--url", "-u", help="Base URL for resolving links")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--probe-images",
        action="store_true",
        help="Fetch each image as a browser would and record the format actually served",
    )

    args = parser.parse_args()

    if args.file:
        real_path = os.path.realpath(args.file)
        if not os.path.isfile(real_path):
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(real_path, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        html = sys.stdin.read()
        if not html and args.url:
            resp = safe_requests_get(args.url, timeout=30, allow_redirects=True)
            html = decode_response_text(resp)
            args.url = resp.url

    result = parse_html(html, args.url)
    if args.probe_images:
        probe_images(result["images"])

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Title: {result['title']}")
        print(f"Meta Description: {result['meta_description']}")
        print(f"Canonical: {result['canonical']}")
        print(f"H1 Tags: {len(result['h1'])}")
        print(f"H2 Tags: {len(result['h2'])}")
        print(f"Images: {len(result['images'])}")
        print(f"Internal Links: {len(result['links']['internal'])}")
        print(f"External Links: {len(result['links']['external'])}")
        print(f"Schema Blocks: {len(result['schema'])}")
        print(f"Word Count: {result['word_count']}")


if __name__ == "__main__":
    main()
