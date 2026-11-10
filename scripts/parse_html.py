#!/usr/bin/env python3
"""
Parse HTML and extract SEO-relevant elements.

Usage:
    python parse_html.py page.html
    python parse_html.py --url https://example.com
    python parse_html.py --url https://example.com --probe-images --json
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
    from bs4 import BeautifulSoup
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
from url_safety import URLSafetyError, decode_response_text, safe_requests_get  # noqa: E402, I001

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
    """
    cache: dict = {}
    for image in images:
        src = image.get("src", "")
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
        "images": [],
        "links": {
            "internal": [],
            "external": [],
        },
        "schema": [],
        "open_graph": {},
        "twitter_card": {},
        "word_count": 0,
        "hreflang": [],
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

        result["images"].append({
            "src": src,
            "alt": img.get("alt"),
            "width": img.get("width"),
            "height": img.get("height"),
            "loading": img.get("loading"),
            "lazy_method": _detect_lazy_method(img),
        })

    # Links
    if base_url:
        base_domain = urlparse(base_url).netloc
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

            if parsed.netloc == base_domain:
                result["links"]["internal"].append(link_data)
            else:
                result["links"]["external"].append(link_data)

    # Schema (JSON-LD)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            schema_data = json.loads(script.string)
            # Flatten @graph containers so each @type is a separate entry.
            # The container is not an entity, so it carries no @type of its
            # own, but its @context is inherited by the entries it holds.
            if isinstance(schema_data, dict) and "@graph" in schema_data:
                inherited_context = schema_data.get("@context")
                for item in schema_data["@graph"]:
                    if isinstance(item, dict):
                        result["schema"].append(_inherit_context(item, inherited_context))
            elif isinstance(schema_data, list):
                for item in schema_data:
                    if isinstance(item, dict):
                        result["schema"].append(item)
            else:
                result["schema"].append(schema_data)
        except (json.JSONDecodeError, TypeError):
            pass

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
