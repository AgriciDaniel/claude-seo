#!/usr/bin/env python3
"""Discover sitemaps through robots.txt and common locations safely.

Every network request uses the repository's DNS-pinned URL safety layer. The
helper accepts cross-host Sitemap directives because the sitemap protocol
allows them, but validates each target independently before connecting.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.parse import urlparse, urlunparse

import requests
from lxml import etree

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from url_safety import URLSafetyError, safe_requests_session, validate_url  # noqa: E402

COMMON_PATHS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
)
MAX_DECLARED = 16
MAX_ROBOTS_BYTES = 1024 * 1024
MAX_SITEMAP_BYTES = 50 * 1024 * 1024
USER_AGENT = "ClaudeSEO/2.2 SitemapDiscovery"
_SITEMAP_LINE = re.compile(r"^\s*sitemap\s*:\s*(\S+)\s*$", re.IGNORECASE)


def _display_url(url: str) -> tuple[str, bool]:
    """Return a safe-to-display URL with userinfo, query, and fragment removed."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
        redacted = True
    else:
        redacted = False
    if port:
        host = f"{host}:{port}"
    clean = urlunparse((parsed.scheme, host, parsed.path or "/", "", "", ""))
    redacted = redacted or bool(parsed.username or parsed.password or parsed.query or parsed.fragment)
    return clean, redacted


def _origin(url: str) -> str:
    if "://" not in url:
        url = f"https://{url}"
    if not validate_url(url):
        raise ValueError("Target must be a public HTTP or HTTPS URL")
    parsed = urlparse(url)
    netloc = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Target URL contains an invalid port") from exc
    if port:
        netloc = f"{netloc}:{port}"
    return urlunparse((parsed.scheme, netloc, "", "", "", ""))


def _bounded_fetch(
    url: str, max_bytes: int, *, allow_local_target: bool = False
) -> dict:
    """Fetch at most max_bytes after decompression without exposing response text.

    Only the operator-derived origin paths may opt into local-target access.
    URLs discovered in robots.txt remain untrusted and use the default False.
    """
    result = {
        "status_code": None,
        "content": b"",
        "content_type": "",
        "final_url": url,
        "too_large": False,
        "error": None,
    }
    try:
        with safe_requests_session(
            url, allow_local_target=allow_local_target
        ) as session:
            response = session.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml,text/plain,*/*"},
                timeout=30,
                allow_redirects=True,
                stream=True,
            )
            result["status_code"] = response.status_code
            result["content_type"] = response.headers.get("Content-Type", "")
            result["final_url"] = response.url
            chunks = []
            size = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                size += len(chunk)
                if size > max_bytes:
                    result["too_large"] = True
                    break
                chunks.append(chunk)
            result["content"] = b"".join(chunks)
            response.close()
    except URLSafetyError:
        result["error"] = "URL safety validation failed"
    except requests.exceptions.Timeout:
        result["error"] = "Request timed out"
    except requests.exceptions.RequestException:
        result["error"] = "Request failed"
    return result


def _robots_sitemaps(content: bytes) -> list[str]:
    text = content.decode("utf-8", errors="replace")
    found = []
    for line in text.splitlines():
        match = _SITEMAP_LINE.match(line)
        if match and match.group(1) not in found:
            found.append(match.group(1))
    return found


def _valid_sitemap_url_syntax(value: str) -> bool:
    """Check a text-sitemap entry without resolving or connecting to its host."""
    if not value or any(char.isspace() for char in value) or "\\" in value:
        return False
    try:
        parsed = urlparse(value)
        _ = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.lower() in {"http", "https"}
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
    )


def _sitemap_kind(content: bytes, content_type: str, url: str) -> tuple[str | None, str | None]:
    if not content.strip():
        return None, "empty response"
    if b"<!DOCTYPE" in content.upper():
        return None, "DOCTYPE is not allowed in sitemap XML"

    stripped = content.lstrip()
    if stripped.startswith(b"<"):
        try:
            parser = etree.XMLParser(
                resolve_entities=False,
                no_network=True,
                load_dtd=False,
                recover=False,
                huge_tree=False,
            )
            root = etree.fromstring(content, parser=parser)
        except (etree.XMLSyntaxError, ValueError):
            return None, "invalid XML"
        local = etree.QName(root).localname.lower()
        if local in {"urlset", "sitemapindex"}:
            return local, None
        if local in {"rss", "feed"}:
            return local, None
        return None, "unsupported XML root"

    if "text/plain" in content_type.lower() or urlparse(url).path.lower().endswith(".txt"):
        lines = [line.strip() for line in content.decode("utf-8", errors="replace").splitlines() if line.strip()]
        if len(lines) > 50000:
            return None, "text sitemap exceeds the 50,000 URL protocol limit"
        # Entries are reported only as a sitemap classification, not fetched.
        # Avoid up to 50,000 DNS lookups here; connection-time validation still
        # applies to every sitemap candidate that discovery fetches.
        if lines and all(_valid_sitemap_url_syntax(line) for line in lines):
            return "text", None
        return None, "invalid text sitemap"
    return None, "response is not a supported sitemap format"


def discover_sitemaps(target_url: str) -> dict:
    result = {
        "target": None,
        "robots_url": None,
        "declared": [],
        "found": [],
        "checked": [],
        "warnings": [],
        "error": None,
    }
    try:
        origin = _origin(target_url)
    except ValueError as exc:
        result["error"] = str(exc)
        return result

    result["target"] = origin
    robots_url = f"{origin}/robots.txt"
    result["robots_url"] = robots_url
    robots = _bounded_fetch(
        robots_url, MAX_ROBOTS_BYTES, allow_local_target=True
    )
    declared_raw = []
    if robots["error"]:
        result["warnings"].append("robots.txt could not be fetched safely")
    elif robots["too_large"]:
        result["warnings"].append("robots.txt exceeded the 1 MiB discovery limit")
    elif robots["status_code"] == 200:
        declared_raw = _robots_sitemaps(robots["content"])
    elif robots["status_code"] is not None:
        result["warnings"].append(f"robots.txt returned HTTP {robots['status_code']}")

    if len(declared_raw) > MAX_DECLARED:
        result["warnings"].append(
            f"robots.txt declared more than {MAX_DECLARED} sitemaps; extra entries were not fetched"
        )
        declared_raw = declared_raw[:MAX_DECLARED]

    for item in declared_raw:
        display, redacted = _display_url(item)
        result["declared"].append({"url": display, "query_redacted": redacted})

    candidates = list(declared_raw)
    candidates.extend(f"{origin}{path}" for path in COMMON_PATHS)
    deduped = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)

    target_host = urlparse(origin).hostname
    for candidate in deduped:
        display, query_redacted = _display_url(candidate)
        entry = {
            "url": display,
            "query_redacted": query_redacted,
            "source": "robots.txt" if candidate in declared_raw else "common_path",
            "status_code": None,
            "kind": None,
            "valid": False,
            "error": None,
        }
        if urlparse(candidate).hostname != target_host and candidate in declared_raw:
            entry["cross_host"] = True

        fetched = _bounded_fetch(
            candidate,
            MAX_SITEMAP_BYTES,
            allow_local_target=candidate not in declared_raw,
        )
        entry["status_code"] = fetched["status_code"]
        if fetched["error"]:
            entry["error"] = fetched["error"]
        elif fetched["too_large"]:
            entry["error"] = "Sitemap exceeds the 50 MiB uncompressed protocol limit"
        elif fetched["status_code"] is None or not 200 <= fetched["status_code"] < 300:
            entry["error"] = f"HTTP {fetched['status_code']}" if fetched["status_code"] is not None else "No response"
        else:
            kind, error = _sitemap_kind(
                fetched["content"], fetched["content_type"], fetched["final_url"]
            )
            entry["kind"] = kind
            entry["error"] = error
            entry["valid"] = kind is not None
            if entry["valid"]:
                final_display, final_redacted = _display_url(fetched["final_url"])
                entry["url"] = final_display
                entry["query_redacted"] = query_redacted or final_redacted
                result["found"].append(dict(entry))
        result["checked"].append(entry)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover sitemaps safely")
    parser.add_argument("url", help="Public site URL")
    parser.add_argument("--json", action="store_true", help="Output structured JSON")
    args = parser.parse_args()
    result = discover_sitemaps(args.url)
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["error"]:
        print(f"Error: {result['error']}", file=sys.stderr)
    elif result["found"]:
        for item in result["found"]:
            print(f"{item['url']} ({item['kind']})")
    else:
        print("No valid sitemap found")
    return 1 if result["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
