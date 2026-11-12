#!/usr/bin/env python3
"""Discover sitemaps through robots.txt and common locations safely.

Every network request uses the repository's DNS-pinned URL safety layer. The
helper accepts cross-host Sitemap directives because the sitemap protocol
allows them, but validates each target independently before connecting.
A gzip sitemap (.xml.gz, detected by its magic bytes) is inflated under the
50 MiB uncompressed cap and classified by its content; its entry carries
"gzip": true.

Usage:
    sitemap_discovery.py <url> --json
    sitemap_discovery.py <url> --expand --json
    sitemap_discovery.py <url> --expand --max-children 200 --sample 5 --json

--expand also reads every sitemap that was found: it follows a sitemap index
one level down to its child sitemaps and adds an "expanded" object with
per-file statistics (URL count, lastmod quality, off-host entries, protocol
limit findings) and totals across files. Every URL is counted; only a bounded
sample is printed.

Sitemap file URLs are printed without their query string ("query_redacted").
"sample_urls" are page URLs meant to be requested, so they keep their query;
a page URL with a credential-like parameter (token, session, signature) is
never sampled, and is counted and shown with the value replaced in
"redacted_url_count" and "redacted_url_examples" instead.

Duplicates are counted per entry, after normalisation. In one file, the first
entry for a URL that an earlier file already listed is one cross-file
duplicate ("duplicates_across_files"); every further entry for a URL the same
file already listed is one within-file duplicate ("duplicate_count",
"duplicates_within_files"). Each entry is counted once, so for the page
sitemaps: URLs = unique + within-file + cross-file duplicates + invalid locs.

A malformed URL in robots.txt or in a sitemap is recorded and skipped.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import sys
import zlib
from collections import Counter
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urljoin, urlparse, urlunparse

import requests
from lxml import etree

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from url_safety import URLSafetyError, read_bounded, safe_requests_session, validate_url  # noqa: E402

COMMON_PATHS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
)
MAX_DECLARED = 16
MAX_ROBOTS_BYTES = 1024 * 1024
MAX_SITEMAP_BYTES = 50 * 1024 * 1024
MAX_SITEMAP_URLS = 50000
# Protocol limit: a <loc> value must be shorter than 2,048 characters.
MAX_LOC_CHARS = 2048
DEFAULT_MAX_CHILDREN = 50
DEFAULT_SAMPLE = 20
MAX_EXAMPLES = 5
# Distinct URLs remembered for duplicate detection (about 100 bytes each).
MAX_TRACKED_URLS = 2_000_000
USER_AGENT = "ClaudeSEO/2.2 SitemapDiscovery"
_SITEMAP_LINE = re.compile(r"^\s*sitemap\s*:\s*(\S+)\s*$", re.IGNORECASE)
_TOO_LARGE = "Sitemap exceeds the 50 MiB uncompressed protocol limit"
_GZIP_MAGIC = b"\x1f\x8b"
_INFLATE_CHUNK = 1024 * 1024
_TRACKING_KEYS = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid", "_ga", "ref"})
# W3C Datetime: YYYY, YYYY-MM, YYYY-MM-DD, or a date with a time and a zone.
_W3C_DATETIME = re.compile(
    r"(\d{4})(?:-(\d{2})(?:-(\d{2})"
    r"(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d{1,9})?)?(Z|[+-]\d{2}:\d{2}))?)?)?",
    re.ASCII,
)
# Query parameters whose value is a credential, not part of the page address.
_SECRET_PARAM = re.compile(
    r"token|secret|passw|signature|credential|session|sessid|api[-_]?key|access[-_]?key"
    r"|^(?:key|sig|auth|pwd|sid|jwt)$"
)
_MALFORMED = "Malformed sitemap URL"
# Element that holds one entry, per sitemap kind.
_ENTRY_TAG = {"urlset": "url", "sitemapindex": "sitemap", "rss": "item", "feed": "entry"}


def _display_url(url: str) -> tuple[str, bool]:
    """Return a safe-to-display URL with userinfo, query, and fragment removed.

    Never raises: text that does not parse as a URL is cut the same way by hand.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        text = re.split(r"[?#]", url, maxsplit=1)[0]
        return re.sub(r"(?<=//)[^/]*@", "", text), True
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


def _bounded_fetch(url: str, max_bytes: int) -> dict:
    """Fetch at most max_bytes after decompression without exposing response text."""
    result = {
        "status_code": None,
        "content": b"",
        "content_type": "",
        "final_url": url,
        "too_large": False,
        "error": None,
    }
    try:
        with safe_requests_session(url) as session:
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
            result["content"], result["too_large"] = read_bounded(response, max_bytes)
            response.close()
    except URLSafetyError:
        result["error"] = "URL safety validation failed"
    except requests.exceptions.Timeout:
        result["error"] = "Request timed out"
    except requests.exceptions.RequestException:
        result["error"] = "Request failed"
    except ValueError:
        # Text that is not a URL at all, such as an unclosed IPv6 bracket.
        result["error"] = _MALFORMED
    return result


def _robots_sitemaps(content: bytes) -> list[str]:
    """Return Sitemap URLs declared in a robots.txt body.

    Google's robots.txt syntax is ``field:value`` with an optional ``#``
    comment through the end of the line. The comment is not part of the URL.
    A leading UTF-8 BOM is an encoding signature, not part of the first field.
    """
    text = content.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    found = []
    for line in text.splitlines():
        line = line.split("#", 1)[0]
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


def _classify(content: bytes, content_type: str, url: str) -> tuple[str | None, str | None, object, list[str] | None]:
    """Classify a sitemap body. Returns (kind, error, XML root, text lines).

    The root is set for an accepted XML sitemap and the lines for a text
    sitemap, including one refused for passing the 50,000 URL limit, so
    --expand can count entries without parsing the body a second time.
    """
    if not content.strip():
        return None, "empty response", None, None
    if b"<!DOCTYPE" in content.upper():
        return None, "DOCTYPE is not allowed in sitemap XML", None, None

    stripped = content.removeprefix(b"\xef\xbb\xbf").lstrip()
    if stripped.startswith(b"<"):
        try:
            parser = etree.XMLParser(
                resolve_entities=False,
                no_network=True,
                load_dtd=False,
                recover=False,
                huge_tree=False,
            )
            root = etree.fromstring(content, parser=parser, base_url=url)
        except (etree.XMLSyntaxError, ValueError):
            return None, "invalid XML", None, None
        local = etree.QName(root).localname.lower()
        if local in {"urlset", "sitemapindex"}:
            return local, None, root, None
        if local in {"rss", "feed"}:
            return local, None, root, None
        return None, "unsupported XML root", None, None

    if "text/plain" in content_type.lower() or _url_path(url).lower().endswith(".txt"):
        # Decode the BOM-free bytes: a leading UTF-8 BOM is an encoding
        # signature, not part of the first URL.
        lines = [line.strip() for line in stripped.decode("utf-8", errors="replace").splitlines() if line.strip()]
        if len(lines) > MAX_SITEMAP_URLS:
            return None, "text sitemap exceeds the 50,000 URL protocol limit", None, lines
        # Entries are reported only as a sitemap classification, not fetched.
        # Avoid up to 50,000 DNS lookups here; connection-time validation still
        # applies to every sitemap candidate that discovery fetches.
        if lines and all(_valid_sitemap_url_syntax(line) for line in lines):
            return "text", None, None, lines
        return None, "invalid text sitemap", None, None
    return None, "response is not a supported sitemap format", None, None


def _sitemap_kind(content: bytes, content_type: str, url: str) -> tuple[str | None, str | None]:
    kind, error, _root, _lines = _classify(content, content_type, url)
    return kind, error


def _gunzip_bounded(raw: bytes, max_bytes: int) -> tuple[bytes, bool]:
    """Inflate gzip data in chunks, stopping once the output passes max_bytes.

    Returns (data, too_large). The output is never held past max_bytes plus
    one chunk, so a gzip bomb cannot exhaust memory. Raises ValueError when
    the data is not a complete gzip stream.
    """
    chunks = []
    total = 0
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            while True:
                chunk = stream.read(_INFLATE_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    return b"", True
                chunks.append(chunk)
    except (OSError, EOFError, zlib.error) as exc:
        raise ValueError("invalid gzip data") from exc
    return b"".join(chunks), False


def _read_body(fetched: dict) -> dict:
    """Classify a fetched body. A gzip file is inflated first, under the size cap."""
    body = {
        "kind": None,
        "error": None,
        "root": None,
        "lines": None,
        "gzip": False,
        "decompressed_bytes": None,
        "too_large": False,
    }
    content = fetched["content"]
    url = fetched["final_url"]
    if content[:2] == _GZIP_MAGIC:
        body["gzip"] = True
        try:
            content, body["too_large"] = _gunzip_bounded(content, MAX_SITEMAP_BYTES)
        except ValueError:
            body["error"] = "invalid gzip data"
            return body
        if body["too_large"]:
            body["error"] = _TOO_LARGE
            return body
        body["decompressed_bytes"] = len(content)
        try:
            parsed = urlparse(url)
            if parsed.path.lower().endswith(".gz"):
                # sitemap.txt.gz is a text sitemap: classify it by the inner name.
                url = urlunparse(parsed._replace(path=parsed.path[:-3]))
        except ValueError:
            pass
    body["kind"], body["error"], body["root"], body["lines"] = _classify(content, fetched["content_type"], url)
    return body


def _fetch_sitemap(url: str) -> tuple[dict, dict | None, str | None]:
    """Fetch one sitemap candidate through the bounded, validated fetch.

    Returns (fetched, body, error). The body is None when nothing usable came
    back: a refused or failed request, an oversized body, or a non-2xx status.
    """
    fetched = _bounded_fetch(url, MAX_SITEMAP_BYTES)
    if fetched["error"]:
        return fetched, None, fetched["error"]
    if fetched["too_large"]:
        return fetched, None, _TOO_LARGE
    status = fetched["status_code"]
    if status is None or not 200 <= status < 300:
        return fetched, None, f"HTTP {status}" if status is not None else "No response"
    body = _read_body(fetched)
    return fetched, body, body["error"]


def _parses(url: str) -> bool:
    try:
        urlparse(url)
    except ValueError:
        return False
    return True


def _url_path(url: str) -> str:
    try:
        return urlparse(url).path
    except ValueError:
        return ""


def _host(url: str) -> str:
    """Lower-case host of a URL; empty when the text does not parse."""
    try:
        return (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _sample_url(loc: str) -> tuple[str, bool]:
    """Return a valid page URL as printed, and whether a value was replaced.

    A sample is there to be requested, so the query is kept. The fragment is
    dropped (it is never sent). The value of a credential-like parameter is
    replaced, which makes that URL useless for a status check.
    """
    if "?" not in loc:
        return loc.split("#", 1)[0], False
    parsed = urlparse(loc)
    pairs = []
    replaced = False
    for pair in parsed.query.split("&"):
        key, equals, _value = pair.partition("=")
        if equals and _SECRET_PARAM.search(unquote(key).lower()):
            pair = f"{key}=REDACTED"
            replaced = True
        pairs.append(pair)
    if not replaced:
        return loc.split("#", 1)[0], False
    netloc = parsed.netloc.rpartition("@")[2]
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, "&".join(pairs), "")), True


def _local(element) -> str:
    """Lower-case tag name without its namespace; empty for comments and PIs."""
    tag = element.tag
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def _xml_entries(kind: str, root) -> Iterator[tuple[str | None, str | None]]:
    """Yield (loc, lastmod) for each entry of a parsed sitemap, index, or feed."""
    feed = kind in {"rss", "feed"}
    for node in root.iter() if feed else root:
        if _local(node) != _ENTRY_TAG[kind]:
            continue
        loc = lastmod = None
        for child in node:
            tag = _local(child)
            text = (child.text or "").strip()
            if kind == "feed":
                if tag == "link" and loc is None and child.get("rel", "alternate") == "alternate":
                    loc = (child.get("href") or "").strip()
                    if loc:
                        try:
                            loc = urljoin(child.base or "", loc)
                        except ValueError:
                            # Leave malformed links for the URL-quality report.
                            pass
                elif tag == "updated" and lastmod is None:
                    lastmod = text
            elif kind == "rss":
                if tag == "link" and loc is None:
                    loc = text
            elif tag == "loc" and loc is None:
                loc = text
            elif tag == "lastmod" and lastmod is None:
                lastmod = text
        yield loc or None, lastmod or None


def _parse_w3c_datetime(value: str) -> datetime | None:
    """Return a comparable UTC time for a W3C Datetime value, or None."""
    match = _W3C_DATETIME.fullmatch(value)
    if not match:
        return None
    year, month, day, hour, minute, second, zone = match.groups()
    try:
        moment = datetime(
            int(year), int(month or 1), int(day or 1),
            int(hour or 0), int(minute or 0), int(second or 0),
            tzinfo=timezone.utc,
        )
        if zone and zone != "Z":
            hours, minutes = int(zone[1:3]), int(zone[4:6])
            if hours > 23 or minutes > 59:
                return None
            offset = timedelta(hours=hours, minutes=minutes)
            moment = moment - offset if zone[0] == "+" else moment + offset
    except (ValueError, OverflowError):
        return None
    return moment


def _normalize_url(url: str) -> str | None:
    """Normalise a URL for duplicate detection only; never fetch or print it.

    Lower-cases scheme and host, drops a default port, the fragment, and
    tracking parameters, and collapses repeated slashes. The trailing slash is
    kept: /about and /about/ are different addresses.
    """
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.lower().rstrip(".")
    if ":" in host:
        host = f"[{host}]"
    netloc = f"{host}:{port}" if port and port != (443 if scheme == "https" else 80) else host
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    kept = []
    for pair in parsed.query.split("&"):
        key = unquote(pair.split("=", 1)[0]).lower()
        if pair and not key.startswith("utm_") and key not in _TRACKING_KEYS:
            kept.append(pair)
    return urlunparse((scheme, netloc, path, parsed.params, "&".join(kept), ""))


class _Expansion:
    """Per-file statistics and cross-file totals for --expand.

    Duplicates are counted per entry on the normalised URL. In one file, the
    first entry for a URL that an earlier file listed is a cross-file
    duplicate; any further entry for a URL that file already listed is a
    within-file duplicate. No entry is counted both ways.
    """

    def __init__(self, sample_size: int) -> None:
        self.sample_size = sample_size
        self.files: list[dict] = []
        # Fetched and final URL of every sitemap request so far, with its kind.
        self.kinds: dict[str, str | None] = {}
        # Final URLs of the valid files already reported.
        self.analysed: set[str] = set()
        # Top-level indexes waiting for their children: (report, final URL, child URLs).
        self.pending: list[tuple[dict, str, list[str]]] = []
        # Digest of a normalised URL -> number of the last file that listed it.
        self.seen: dict[bytes, int] = {}
        self.tracking_complete = True
        self.unique = 0

    def add_top_level(self, candidate: str, entry: dict, fetched: dict, body: dict | None) -> None:
        """Record a candidate from robots.txt or a common path."""
        final_url = fetched["final_url"]
        self.kinds[candidate] = entry["kind"]
        if entry["valid"] and final_url in self.analysed:
            return
        self.kinds[final_url] = entry["kind"]
        report, children = self._report(entry, fetched, body)
        if entry["valid"]:
            self.analysed.add(final_url)
            if entry["kind"] == "sitemapindex":
                self.pending.append((report, final_url, children))
        if entry["valid"] or report["findings"]:
            self.files.append(report)

    def follow_children(self, max_children: int, warnings: list[str]) -> dict:
        """Fetch the child sitemaps of every top-level index, one level deep.

        Child URLs come from fetched content, so each one takes the same
        validated fetch path as any other candidate. A child that is itself an
        index is reported, never followed.
        """
        listed = fetched_count = skipped = 0
        scheduled: set[str] = set()
        for parent, parent_url, children in self.pending:
            for loc in children:
                if loc in self.kinds:
                    if self.kinds[loc] == "sitemapindex":
                        self._nested(parent, _display_url(loc)[0], warnings)
                    continue
                if loc in scheduled:
                    continue
                scheduled.add(loc)
                listed += 1
                if fetched_count >= max_children:
                    skipped += 1
                    continue
                fetched_count += 1
                fetched, body, error = _fetch_sitemap(loc)
                kind = body["kind"] if body else None
                final_url = fetched["final_url"]
                self.kinds[loc] = kind
                if kind is not None and final_url in self.analysed:
                    # Redirects to a file that is already reported: count it once.
                    if self.kinds.get(final_url) == "sitemapindex":
                        self._nested(parent, _display_url(final_url)[0], warnings)
                    continue
                self.kinds[final_url] = kind
                display, redacted = _display_url(final_url if kind is not None else loc)
                entry = {
                    "url": display,
                    "query_redacted": redacted or _display_url(loc)[1],
                    "source": "sitemapindex",
                    "parent": parent["url"],
                    "status_code": fetched["status_code"],
                    "kind": kind,
                    "valid": kind is not None,
                    "error": error,
                }
                if _host(loc) != _host(parent_url):
                    entry["cross_host"] = True
                report, _grandchildren = self._report(entry, fetched, body)
                if kind is not None:
                    self.analysed.add(final_url)
                self.files.append(report)
                if kind == "sitemapindex":
                    self._nested(parent, display, warnings)
        if skipped:
            warnings.append(
                f"Child sitemap limit reached ({max_children}); {skipped} child sitemaps were not fetched"
            )
        return {"limit": max_children, "listed": listed, "fetched": fetched_count, "skipped": skipped}

    def totals(self, warnings: list[str]) -> dict:
        valid = [item for item in self.files if item["valid"]]
        totals = {
            "sitemap_files": len(valid),
            "total_urls": sum(item["url_count"] for item in valid),
            "unique_urls": self.unique,
            "duplicates_within_files": sum(
                item["duplicate_count"] or 0 for item in valid if item["kind"] != "sitemapindex"
            ),
            "duplicates_across_files": sum(item["_cross_file_duplicates"] for item in valid),
            "invalid_locs": sum(item["invalid_loc_count"] for item in valid),
        }
        if not self.tracking_complete:
            totals["unique_urls"] = None
            totals["duplicates_within_files"] = None
            totals["duplicates_across_files"] = None
            warnings.append(
                f"More than {MAX_TRACKED_URLS} distinct URLs; unique and duplicate totals are not reported"
            )
        for item in self.files:
            item.pop("_cross_file_duplicates", None)
        return totals

    @staticmethod
    def _nested(parent: dict, display: str, warnings: list[str]) -> None:
        if "nested_sitemap_index" not in parent["findings"]:
            parent["findings"].append("nested_sitemap_index")
        warnings.append(f"Nested sitemap index was not followed: {display} (listed in {parent['url']})")

    def _report(self, entry: dict, fetched: dict, body: dict | None) -> tuple[dict, list[str]]:
        """Build the report for one file. Returns it with the child URLs of an index."""
        report = dict(entry)
        report.update({
            "gzip": bool(body and body["gzip"]),
            "bytes": None if fetched["too_large"] else len(fetched["content"]),
            "decompressed_bytes": body["decompressed_bytes"] if body else None,
            "url_count": None,
            "child_count": None,
            "invalid_loc_count": None,
            "duplicate_count": None,
            "lastmod_count": None,
            "lastmod_invalid_count": None,
            "lastmod_oldest": None,
            "lastmod_newest": None,
            "lastmod_most_common": None,
            "lastmod_identical_share": None,
            "cross_host_url_count": None,
            "cross_host_url_examples": [],
            "redacted_url_count": None,
            "redacted_url_examples": [],
            "findings": [],
            "sample_urls": [],
            "_cross_file_duplicates": 0,
        })
        if fetched["too_large"] or (body and body["too_large"]):
            report["findings"].append("over_50mib_uncompressed")
        if body is None:
            return report, []
        if body["kind"] is None:
            if body["lines"] is not None:
                # A text sitemap refused for its size: the count is still known.
                report["url_count"] = len(body["lines"])
                report["findings"].append("over_50000_urls")
            return report, []
        if body["root"] is not None:
            entries: Iterable[tuple[str | None, str | None]] = _xml_entries(body["kind"], body["root"])
        else:
            entries = ((line, None) for line in body["lines"])
        return report, self._summarise(report, body["kind"], entries, fetched["final_url"])

    def _summarise(self, report: dict, kind: str, entries: Iterable, final_url: str) -> list[str]:
        """Count every entry of one file into its report. Returns an index's child URLs."""
        index = kind == "sitemapindex"
        file_number = len(self.files)
        host = _host(final_url)
        count = invalid = with_lastmod = bad_lastmod = cross_host = repeats = cross_file = secret = 0
        oldest: tuple[datetime, str] | None = None
        newest: tuple[datetime, str] | None = None
        lastmods: Counter[str] = Counter()
        examples: list[str] = report["cross_host_url_examples"]
        secret_examples: list[str] = report["redacted_url_examples"]
        sampled: set[str] = set()
        children: list[str] = []
        child_set: set[str] = set()
        for loc, lastmod in entries:
            count += 1
            if lastmod:
                with_lastmod += 1
                moment = _parse_w3c_datetime(lastmod)
                if moment is None:
                    bad_lastmod += 1
                else:
                    lastmods[lastmod] += 1
                    if oldest is None or moment < oldest[0]:
                        oldest = (moment, lastmod)
                    if newest is None or moment > newest[0]:
                        newest = (moment, lastmod)
            if not loc or len(loc) >= MAX_LOC_CHARS or not _valid_sitemap_url_syntax(loc):
                invalid += 1
                continue
            if _host(loc) != host:
                cross_host += 1
                shown = _display_url(loc)[0]
                if len(examples) < MAX_EXAMPLES and shown not in examples:
                    examples.append(shown)
            if index:
                if loc in child_set:
                    repeats += 1
                else:
                    child_set.add(loc)
                    children.append(loc)
                continue
            shown, replaced = _sample_url(loc)
            if replaced:
                secret += 1
                if len(secret_examples) < MAX_EXAMPLES and shown not in secret_examples:
                    secret_examples.append(shown)
            elif len(sampled) < self.sample_size and shown not in sampled:
                sampled.add(shown)
                report["sample_urls"].append(shown)
            seen_in = self._track(loc, file_number)
            if seen_in == "same_file":
                repeats += 1
            elif seen_in == "earlier_file":
                cross_file += 1

        report.update({
            "url_count": 0 if index else count,
            "child_count": count if index else 0,
            "invalid_loc_count": invalid,
            "duplicate_count": repeats if index or self.tracking_complete else None,
            "lastmod_count": with_lastmod,
            "lastmod_invalid_count": bad_lastmod,
            "lastmod_oldest": oldest[1] if oldest else None,
            "lastmod_newest": newest[1] if newest else None,
            "cross_host_url_count": cross_host,
            "redacted_url_count": secret,
            "_cross_file_duplicates": cross_file,
        })
        if lastmods:
            value, uses = lastmods.most_common(1)[0]
            report["lastmod_most_common"] = value
            report["lastmod_identical_share"] = round(uses / with_lastmod, 4)
        if count > MAX_SITEMAP_URLS:
            report["findings"].append("over_50000_sitemaps" if index else "over_50000_urls")
        return children

    def _track(self, loc: str, file_number: int) -> str | None:
        """Remember one entry and say where its URL was listed before.

        Returns "new", "same_file" (this file already listed it: a within-file
        duplicate), "earlier_file" (first entry in this file for a URL that an
        earlier file listed: a cross-file duplicate), or None when the URL
        cannot be tracked. The table then points at this file, so a second
        entry here is a within-file duplicate, not another cross-file one.
        """
        key = _normalize_url(loc)
        if key is None:
            return None
        digest = hashlib.blake2b(key.encode("utf-8", "replace"), digest_size=8).digest()
        last_file = self.seen.get(digest)
        if last_file is None:
            if len(self.seen) < MAX_TRACKED_URLS:
                self.seen[digest] = file_number
                self.unique += 1
                return "new"
            self.tracking_complete = False
            return None
        if last_file == file_number:
            return "same_file"
        self.seen[digest] = file_number
        return "earlier_file"


def discover_sitemaps(
    target_url: str,
    expand: bool = False,
    max_children: int = DEFAULT_MAX_CHILDREN,
    sample_size: int = DEFAULT_SAMPLE,
) -> dict:
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
    robots = _bounded_fetch(robots_url, MAX_ROBOTS_BYTES)
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

    expansion = _Expansion(sample_size) if expand else None
    target_host = urlparse(origin).hostname
    # Several paths can redirect to one sitemap (/sitemap.xml to
    # /sitemap_index.xml): list each file once, by its final URL.
    listed = set()
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
        if not _parses(candidate):
            # robots.txt is page-controlled text: record the line, fetch nothing.
            entry["error"] = _MALFORMED
            result["checked"].append(entry)
            continue
        if urlparse(candidate).hostname != target_host and candidate in declared_raw:
            entry["cross_host"] = True

        fetched, body, entry["error"] = _fetch_sitemap(candidate)
        entry["status_code"] = fetched["status_code"]
        if body is not None:
            if body["gzip"]:
                entry["gzip"] = True
            entry["kind"] = body["kind"]
            entry["valid"] = body["kind"] is not None
            if entry["valid"]:
                final_display, final_redacted = _display_url(fetched["final_url"])
                entry["url"] = final_display
                entry["query_redacted"] = query_redacted or final_redacted
                if fetched["final_url"] not in listed:
                    listed.add(fetched["final_url"])
                    result["found"].append(dict(entry))
        result["checked"].append(entry)
        if expansion is not None:
            expansion.add_top_level(candidate, entry, fetched, body)

    if expansion is not None:
        # Release the last parsed tree before the child sitemaps are read.
        fetched = body = None
        children = expansion.follow_children(max_children, result["warnings"])
        result["expanded"] = {
            "files": expansion.files,
            "totals": expansion.totals(result["warnings"]),
            "children": children,
            "truncated": children["skipped"] > 0,
            "sample_size": sample_size,
        }
    return result


def _bounded_int(low: int, high: int):
    def parse(value: str) -> int:
        number = int(value)
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f"must be between {low} and {high}")
        return number
    return parse


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover sitemaps safely")
    parser.add_argument("url", help="Public site URL")
    parser.add_argument("--json", action="store_true", help="Output structured JSON")
    parser.add_argument(
        "--expand",
        action="store_true",
        help="Read each sitemap found, follow a sitemap index to its children, and report per-file statistics",
    )
    parser.add_argument(
        "--max-children",
        type=_bounded_int(0, MAX_SITEMAP_URLS),
        default=DEFAULT_MAX_CHILDREN,
        metavar="N",
        help=f"With --expand: most child sitemaps to fetch across all indexes (default {DEFAULT_MAX_CHILDREN})",
    )
    parser.add_argument(
        "--sample",
        type=_bounded_int(0, 1000),
        default=DEFAULT_SAMPLE,
        metavar="N",
        help=f"With --expand: URLs kept per file in sample_urls; all are counted (default {DEFAULT_SAMPLE})",
    )
    args = parser.parse_args()
    result = discover_sitemaps(args.url, expand=args.expand, max_children=args.max_children, sample_size=args.sample)
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["error"]:
        print(f"Error: {result['error']}", file=sys.stderr)
    elif args.expand and result["expanded"]["files"]:
        for item in result["expanded"]["files"]:
            if not item["valid"]:
                detail = item["error"]
            elif item["kind"] == "sitemapindex":
                detail = f"{item['child_count']} child sitemaps"
            else:
                detail = f"{item['url_count']} URLs"
            flags = f" [{', '.join(item['findings'])}]" if item["findings"] else ""
            print(f"{item['url']} ({item['kind'] or 'invalid'}, {detail}){flags}")
        totals = result["expanded"]["totals"]
        print(f"Total: {totals['total_urls']} URLs in {totals['sitemap_files']} files, {totals['unique_urls']} unique")
        for warning in result["warnings"]:
            print(f"Warning: {warning}", file=sys.stderr)
    elif result["found"]:
        for item in result["found"]:
            print(f"{item['url']} ({item['kind']})")
    else:
        print("No valid sitemap found")
    return 1 if result["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
