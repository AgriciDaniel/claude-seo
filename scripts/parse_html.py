#!/usr/bin/env python3
"""
Parse HTML and extract SEO-relevant elements.

Usage:
    python parse_html.py page.html
    python parse_html.py --url https://example.com
"""

import argparse
import json
import os
import re
import sys
from typing import Optional
from urllib.parse import urljoin, urlparse

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
        result["title"] = title_tag.get_text(strip=True)

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
    canonical = soup.find("link", rel="canonical")
    if canonical:
        result["canonical"] = canonical.get("href")

    # Hreflang
    for link in soup.find_all("link", rel="alternate"):
        hreflang = link.get("hreflang")
        if hreflang:
            result["hreflang"].append({
                "lang": hreflang,
                "href": link.get("href"),
            })

    # Headings
    for tag in ["h1", "h2", "h3"]:
        for heading in soup.find_all(tag):
            text = heading.get_text(strip=True)
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
        if base_url and src:
            src = urljoin(base_url, src)

        result["images"].append({
            "src": src,
            "alt": img.get("alt"),
            "width": img.get("width"),
            "height": img.get("height"),
            "loading": img.get("loading"),
        })

    # Links
    if base_url:
        base_domain = urlparse(base_url).netloc

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)

            link_data = {
                "href": full_url,
                "text": a.get_text(strip=True)[:100],
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
            # Flatten @graph containers so each @type is a separate entry
            if isinstance(schema_data, dict) and "@graph" in schema_data:
                for item in schema_data["@graph"]:
                    if isinstance(item, dict):
                        result["schema"].append(item)
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

    result = parse_html(html, args.url)

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
