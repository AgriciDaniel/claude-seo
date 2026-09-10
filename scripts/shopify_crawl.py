#!/usr/bin/env python3
"""
Sitemap-driven Shopify storefront crawler with Crawler Access signatures.

Shopify publishes a complete nested sitemap for every storefront, so the URL
set comes from sitemap.xml instead of link following and no page cap is
needed. When `.shopify-env` (see shopify_env.py) holds a Crawler Access
signature for the target host, its three headers are attached to every
request and the storefront lifts its rate limit. The signature is sent to
that one origin only.

Every request goes through url_safety: the root is validated with
validate_url_strict, DNS is pinned for the crawl, only URLs on the root's
scheme and host are fetched, response bodies are read up to a byte limit,
and redirects are recorded but never followed. The sitemap walk is bounded
in depth, sitemap count and URL count.

Outputs in --out:
    pages.jsonl   one record per URL (machine input; never hand this to a model)
    summary.json  aggregate counts, issue tallies, latency percentiles
    sample.json   a stratified sample of pages per template type

Usage:
    python shopify_crawl.py https://shop.example --out ./crawl
    python shopify_crawl.py https://shop.example --max-pages 2000 --concurrency 4
    python shopify_crawl.py https://shop.example --resume --json

Exit codes: 0 ok, 1 nothing crawled, 5 rate limited on a signed request.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import os
import random
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from html import unescape
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

try:
    import requests
    from lxml import etree
except ImportError:
    print("Error: requests and lxml required. Install with: pip install requests lxml", file=sys.stderr)
    sys.exit(1)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
import shopify_env  # noqa: E402
from url_safety import URLSafetyError, safe_requests_session, validate_url_strict  # noqa: E402

USER_AGENT = "ClaudeSEO-ShopifyCrawler (+https://github.com/AgriciDaniel/claude-seo)"
BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8,*;q=0.5",
    "Accept-Encoding": "gzip, deflate",
}
RATE_LIMIT_STATUSES = (429, 430, 503)

# Bounds on what one crawl will read. Shopify's own sitemap index nests two
# levels deep; the depth cap leaves room for a store that puts a proxy in
# front of it without letting a hostile chain run forever.
MAX_SITEMAP_DEPTH = 5
MAX_SITEMAPS = 500
MAX_DISCOVERED_URLS = 250_000
MAX_ROBOTS_BYTES = 1024 * 1024
MAX_SITEMAP_BYTES = 50 * 1024 * 1024
MAX_PAGE_BYTES = 10 * 1024 * 1024

# Shopify storefront URL shapes, in match order. Everything else is "page".
TEMPLATE_PATTERNS = [
    ("product", re.compile(r"/products/")),
    ("collection", re.compile(r"/collections/[^/?]+/?$")),
    ("collection_filtered", re.compile(r"/collections/.+\?")),
    ("blog_article", re.compile(r"/blogs/[^/]+/[^/]+")),
    ("blog_index", re.compile(r"/blogs/[^/]+/?$")),
    ("policy", re.compile(r"/policies/")),
    ("account", re.compile(r"/account")),
    ("home", re.compile(r"^https?://[^/]+/?$")),
]

BUILTIN_DEFAULTS = {
    "max_pages": 0,
    "timeout": 30,
    "sample_per_template": 6,
    "include": None,
    "exclude": None,
    "save_html": False,
    "ignore_robots": False,
}


class RateLimitGovernor:
    """Grow the per-request delay when the storefront pushes back and shrink
    it again after successes. Concurrency stays fixed for the run."""

    def __init__(self, delay: float):
        self.lock = threading.Lock()
        self.base_delay = delay
        self.delay = delay
        self.hits = 0

    def penalize(self) -> float:
        with self.lock:
            self.hits += 1
            self.delay = min(self.delay * 2 if self.delay else 1.0, 30.0)
            return self.delay * (1 + random.random())

    def reward(self) -> None:
        with self.lock:
            if self.delay > self.base_delay:
                self.delay = max(self.base_delay, self.delay / 1.5)

    def wait(self) -> None:
        if self.delay:
            time.sleep(self.delay)


class Origin:
    """The one scheme and host this crawl talks to."""

    def __init__(self, scheme: str, authority: str):
        self.scheme = scheme
        self.authority = authority.lower()
        self.root = f"{scheme}://{self.authority}"

    def owns(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme == self.scheme and parsed.netloc.lower() == self.authority


def classify(url: str) -> str:
    for name, pattern in TEMPLATE_PATTERNS:
        if pattern.search(url):
            return name
    return "page"


def headers_for(url: str, origin: Origin, sig_headers: dict | None) -> dict:
    """Base headers, plus the signature only for the origin it was issued for.

    Scheme is part of the check: an http:// entry for an https:// store would
    otherwise carry the signature in cleartext."""
    headers = dict(BASE_HEADERS)
    if sig_headers and origin.owns(url):
        headers.update(sig_headers)
    return headers


def read_bounded(response, max_bytes: int) -> tuple[bytes, bool]:
    """Read a streamed response up to max_bytes after decompression.

    Returns (content, too_large). Mirrors sitemap_discovery._bounded_fetch so
    a multi-megabyte body never lands in memory in full, times the crawl's
    concurrency."""
    chunks: list[bytes] = []
    size = 0
    too_large = False
    try:
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            size += len(chunk)
            if size > max_bytes:
                too_large = True
                break
            chunks.append(chunk)
    finally:
        response.close()
    return b"".join(chunks), too_large


def decode_body(content: bytes, response) -> str:
    encoding = response.encoding or "utf-8"
    try:
        return content.decode(encoding, errors="replace")
    except LookupError:
        return content.decode("utf-8", errors="replace")


def sitemap_locs(content: bytes) -> tuple[str, list[str]]:
    """Return (kind, locs) for a sitemap document; kind is 'sitemapindex' or 'urlset'.

    Only <loc> directly under <url> or <sitemap> counts. Shopify product
    sitemaps also carry <image:loc>; those are assets, not pages.
    """
    if b"<!DOCTYPE" in content[:512].upper():
        raise ValueError("DOCTYPE is not allowed in sitemap XML")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False,
                             recover=False, huge_tree=False)
    tree = etree.fromstring(content, parser=parser)
    kind = etree.QName(tree).localname.lower()
    locs = []
    for entry in tree:
        if not isinstance(entry.tag, str) or etree.QName(entry).localname not in ("url", "sitemap"):
            continue
        for child in entry:
            if isinstance(child.tag, str) and etree.QName(child).localname == "loc" and child.text:
                locs.append(child.text.strip())
                break
    return kind, locs


def fetch_sitemap_urls(session, origin: Origin, governor: RateLimitGovernor,
                       sig_headers: dict | None = None, target: int = 0,
                       robots_text: str | None = None, log=print) -> tuple[list[str], dict]:
    """Walk sitemap.xml and sitemap indexes recursively, same origin only.

    `target` > 0 stops the walk once that many URLs are collected so a capped
    crawl does not open every child sitemap of a large store. Independently
    of `target`, the walk stops at MAX_SITEMAP_DEPTH, MAX_SITEMAPS and
    MAX_DISCOVERED_URLS. Returns (urls, stats).
    """
    seen_maps: set[str] = set()
    queue: list[tuple[str, int]] = []
    urls: list[str] = []
    stats = {"sitemaps_fetched": 0, "skipped_foreign": 0, "discovery_capped": None}

    if robots_text:
        queue += [(loc, 1) for loc in re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots_text)]
    queue.append((f"{origin.root}/sitemap.xml", 1))

    while queue:
        if target and len(urls) >= target:
            log(f"  stopping sitemap walk at {len(urls)} URLs ({len(queue)} sitemaps not opened)")
            break
        if stats["sitemaps_fetched"] >= MAX_SITEMAPS:
            stats["discovery_capped"] = f"more than {MAX_SITEMAPS} sitemaps"
            break
        if len(urls) >= MAX_DISCOVERED_URLS:
            stats["discovery_capped"] = f"more than {MAX_DISCOVERED_URLS} URLs"
            break
        current, depth = queue.pop(0)
        if current in seen_maps:
            continue
        if not origin.owns(current):
            stats["skipped_foreign"] += 1
            continue
        if depth > MAX_SITEMAP_DEPTH:
            stats["discovery_capped"] = f"sitemap index nested deeper than {MAX_SITEMAP_DEPTH}"
            break
        seen_maps.add(current)
        try:
            response = session.get(current, timeout=30, allow_redirects=False, stream=True,
                                   headers=headers_for(current, origin, sig_headers))
        except requests.RequestException as exc:
            log(f"  sitemap failed {current}: {exc}")
            continue
        stats["sitemaps_fetched"] += 1
        if response.status_code in RATE_LIMIT_STATUSES:
            response.close()
            queue.append((current, depth))
            seen_maps.discard(current)
            time.sleep(governor.penalize())
            continue
        if response.status_code != 200:
            response.close()
            continue
        content, too_large = read_bounded(response, MAX_SITEMAP_BYTES)
        if too_large:
            log(f"  sitemap skipped, larger than {MAX_SITEMAP_BYTES} bytes: {current}")
            continue
        if not content.strip():
            continue
        try:
            kind, locs = sitemap_locs(content)
        except (etree.XMLSyntaxError, ValueError):
            continue
        if kind == "sitemapindex":
            queue += [(loc, depth + 1) for loc in locs]
        else:
            for loc in locs:
                if origin.owns(loc):
                    urls.append(loc)
                else:
                    stats["skipped_foreign"] += 1
        log(f"  {current}: {len(locs)} entries ({kind})")

    if stats["skipped_foreign"]:
        log(f"  skipped {stats['skipped_foreign']} sitemap entries outside {origin.root}")
    if stats["discovery_capped"]:
        log(f"  discovery stopped: {stats['discovery_capped']}")
    return list(dict.fromkeys(urls)), stats


TAG_RE = re.compile(r"<(script|style|noscript|template)[^>]*>.*?</\1>", re.S | re.I)
STRIP_RE = re.compile(r"<[^>]+>")


def analyze_html(html: str) -> dict:
    """Regex-level extraction, dependency-free. Aggregate signals only; the
    per-page subagents still do real DOM analysis on the sample."""
    def collapse(value: str) -> str:
        return re.sub(r"\s+", " ", unescape(value)).strip()

    def first(pattern: str):
        found = re.search(pattern, html, re.I | re.S)
        return collapse(found.group(1)) if found else None

    title = first(r"<title[^>]*>(.*?)</title>")
    description = first(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']')
    if not description:
        description = first(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']')
    canonical = first(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']')
    robots_meta = first(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'](.*?)["\']')

    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    hreflang = re.findall(r'<link[^>]+rel=["\']alternate["\'][^>]+hreflang=["\']([^"\']+)', html, re.I)

    schema_types: list[str] = []
    for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                            html, re.I | re.S):
        schema_types += re.findall(r'"@type"\s*:\s*"([^"]+)"', block)

    # Count images on the rendered page only; themes keep <img> inside script
    # templates and <noscript> fallbacks too.
    visible = TAG_RE.sub(" ", html)
    images = re.findall(r"<img\b[^>]*>", visible, re.I)
    without_alt = [img for img in images if not re.search(r"\balt\s*=", img, re.I)]
    words = len(STRIP_RE.sub(" ", visible).split())

    return {
        "title": title,
        "title_length": len(title) if title else 0,
        "meta_description": description,
        "meta_description_length": len(description) if description else 0,
        "canonical": canonical,
        "robots_meta": robots_meta,
        "h1_count": len(h1s),
        "h1_first": collapse(STRIP_RE.sub("", h1s[0]))[:200] if h1s else None,
        "hreflang": sorted(set(hreflang)),
        "schema_types": sorted(set(schema_types)),
        "image_count": len(images),
        "images_without_alt": len(without_alt),
        "word_count": words,
    }


def crawl_one(session_for: Callable[[], requests.Session], url: str, origin: Origin,
              sig_headers: dict | None, governor: RateLimitGovernor, timeout: int,
              save_html_dir: Path | None) -> dict:
    session = session_for()
    headers = headers_for(url, origin, sig_headers)
    record: dict = {"url": url, "template": classify(url), "signed": bool(sig_headers)}
    for attempt in range(4):
        governor.wait()
        started = time.time()
        try:
            response = session.get(url, headers=headers, timeout=timeout,
                                   allow_redirects=False, stream=True)
        except requests.RequestException as exc:
            record["error"] = str(exc)
            time.sleep(1 + attempt)
            continue

        record["status"] = response.status_code
        record["elapsed_ms"] = int((time.time() - started) * 1000)
        if 300 <= response.status_code < 400:
            record["redirect_to"] = response.headers.get("Location")

        if response.status_code in RATE_LIMIT_STATUSES:
            response.close()
            record["rate_limited"] = True
            time.sleep(governor.penalize())
            continue

        governor.reward()
        record.pop("error", None)
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        record["content_type"] = content_type
        record["html"] = response.status_code == 200 and "html" in content_type
        if record["html"]:
            content, too_large = read_bounded(response, MAX_PAGE_BYTES)
            if too_large:
                record["html"] = False
                record["too_large"] = True
                return record
            text = decode_body(content, response)
            record.update(analyze_html(text))
            if save_html_dir:
                name = re.sub(r"[^A-Za-z0-9]+", "_", urlparse(url).path)[:120] or "index"
                (save_html_dir / f"{name}.html").write_text(text, encoding="utf-8")
        else:
            response.close()
        return record

    record["failed"] = True
    return record


def summarize(records: list[dict]) -> dict:
    by_template = Counter(r["template"] for r in records)
    statuses = Counter(r.get("status") for r in records)
    ok = [r for r in records if r.get("status") == 200]
    # Sitemaps list agents.md, feeds and other non-HTML resources too; issue
    # counts only make sense for HTML documents.
    html_pages = [r for r in ok if r.get("html")]
    titles = Counter(r.get("title") for r in html_pages if r.get("title"))

    def count(predicate) -> int:
        return sum(1 for r in html_pages if predicate(r))

    schema_coverage: dict[str, int] = defaultdict(int)
    for record in html_pages:
        for schema_type in record.get("schema_types", []):
            schema_coverage[schema_type] += 1

    latencies = sorted(r["elapsed_ms"] for r in ok if r.get("elapsed_ms"))
    return {
        "pages_crawled": len(records),
        "pages_ok": len(ok),
        "html_documents": len(html_pages),
        "non_html_resources": len(ok) - len(html_pages),
        "redirects": sum(1 for r in records if r.get("redirect_to")),
        "too_large": sum(1 for r in records if r.get("too_large")),
        "content_types": {str(k): v for k, v in Counter(r.get("content_type") for r in ok).most_common()},
        "status_distribution": {str(k): v for k, v in statuses.most_common()},
        "template_distribution": dict(by_template.most_common()),
        "rate_limited_requests": sum(1 for r in records if r.get("rate_limited")),
        "issues": {
            "missing_title": count(lambda r: not r.get("title")),
            "title_over_60": count(lambda r: r.get("title_length", 0) > 60),
            "missing_meta_description": count(lambda r: not r.get("meta_description")),
            "meta_description_out_of_range": count(
                lambda r: r.get("meta_description")
                and not 150 <= r.get("meta_description_length", 0) <= 160),
            "duplicate_titles": sum(c for c in titles.values() if c > 1),
            "missing_canonical": count(lambda r: not r.get("canonical")),
            "noindex": count(lambda r: "noindex" in (r.get("robots_meta") or "")),
            "h1_missing": count(lambda r: r.get("h1_count") == 0),
            "h1_multiple": count(lambda r: r.get("h1_count", 0) > 1),
            "thin_content_under_250_words": count(lambda r: r.get("word_count", 0) < 250),
            "images_without_alt": sum(r.get("images_without_alt", 0) for r in html_pages),
        },
        "schema_coverage": dict(sorted(schema_coverage.items(), key=lambda kv: -kv[1])),
        "latency_ms": {
            "p50": latencies[len(latencies) // 2] if latencies else None,
            "p95": latencies[int(len(latencies) * 0.95)] if latencies else None,
        },
        "duplicate_title_examples": [t for t, c in titles.most_common(10) if c > 1],
    }


def stratified_sample(records: list[dict], per_template: int) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        buckets[record["template"]].append(record)
    sample: list[dict] = []
    for items in buckets.values():
        ok = [r for r in items if r.get("html")] or items
        step = max(1, len(ok) // per_template)
        sample += ok[::step][:per_template]
    return sample


def resolve_settings(args: argparse.Namespace, env: dict, entry: dict | None, signed: bool) -> None:
    """CLI flag beats the domain block, which beats the global keys, which beat
    the built-in defaults. Unset attributes on `args` are filled in place."""
    builtin = dict(BUILTIN_DEFAULTS)
    builtin["concurrency"] = 6 if signed else 2
    builtin["delay"] = 0.2 if signed else 1.0
    layers = [builtin, env.get("crawl", {}), (entry or {}).get("crawl", {})]
    for field, fallback in builtin.items():
        if getattr(args, field, None) is None:
            value = fallback
            for layer in layers:
                if layer.get(field) is not None:
                    value = layer[field]
            setattr(args, field, value)


class ThreadSessions:
    """One requests.Session per worker thread. Sessions are not documented as
    thread-safe; DNS pinning is process-wide, so every session stays pinned."""

    def __init__(self):
        self._local = threading.local()
        self._all: list[requests.Session] = []
        self._lock = threading.Lock()

    def get(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update(BASE_HEADERS)
            self._local.session = session
            with self._lock:
                self._all.append(session)
        return session

    def close(self) -> None:
        with self._lock:
            for session in self._all:
                session.close()
            self._all.clear()


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sitemap-driven Shopify storefront crawler")
    parser.add_argument("url", help="storefront root, e.g. https://shop.example")
    parser.add_argument("--out", default="./crawl", help="output directory")
    # Defaults stay None so .shopify-env can fill them; the command line still wins.
    parser.add_argument("--max-pages", type=int, help="0 = no cap (default)")
    parser.add_argument("--concurrency", type=int, help="default 6 signed, 2 unsigned")
    parser.add_argument("--delay", type=float, help="base delay per request; grows on 429")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--sample-per-template", type=int)
    parser.add_argument("--include", help="regex; crawl only matching URLs")
    parser.add_argument("--exclude", help="regex; skip matching URLs")
    parser.add_argument("--save-html", action="store_true", default=None)
    parser.add_argument("--resume", action="store_true", help="skip URLs already in pages.jsonl")
    parser.add_argument("--ignore-robots", action="store_true", default=None)
    parser.add_argument("--no-signature", action="store_true",
                        help="crawl unsigned even when a signature exists")
    parser.add_argument("--json", action="store_true", help="print the full summary as JSON")
    args = parser.parse_args(argv)

    raw = args.url if "://" in args.url else f"https://{args.url}"
    try:
        norm_url, _ = validate_url_strict(raw)
    except URLSafetyError as exc:
        _log(f"Error: {exc}")
        return 1
    parsed = urlparse(norm_url)
    origin = Origin(parsed.scheme, parsed.netloc)
    authority = origin.authority

    env = shopify_env.load()
    if env["path"]:
        _log(f"Using crawl settings from {env['path']}")
        warning = shopify_env.gitignore_warning(env["path"])
        if warning:
            _log(warning)
        for problem in env["problems"]:
            _log(f"  {problem}")

    entry = env["authorities"].get(authority)
    sig_headers = None
    if args.no_signature:
        entry = None
    elif entry and shopify_env.days_left(entry.get("expires")) > 0:
        sig_headers = shopify_env.signature_headers(entry)
        _log(f"Crawler Access signature active for {authority} "
             f"({shopify_env.days_left(entry['expires']):.0f} days left)")
    elif entry:
        _log(f"WARNING: signature for {authority} is expired; crawling unsigned at normal rate limits.")
    else:
        _log(f"No signature for {authority}; crawling unsigned.")

    resolve_settings(args, env, entry, bool(sig_headers))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_file = out_dir / "pages.jsonl"
    html_dir = None
    if args.save_html:
        html_dir = out_dir / "html"
        html_dir.mkdir(exist_ok=True)

    governor = RateLimitGovernor(args.delay)
    sessions = ThreadSessions()
    with safe_requests_session(origin.root) as session:
        session.headers.update(BASE_HEADERS)

        robots_text = None
        try:
            robots_url = f"{origin.root}/robots.txt"
            robots_response = session.get(robots_url, timeout=15, allow_redirects=False, stream=True,
                                          headers=headers_for(robots_url, origin, sig_headers))
            if robots_response.status_code == 200:
                content, too_large = read_bounded(robots_response, MAX_ROBOTS_BYTES)
                if not too_large:
                    robots_text = content.decode("utf-8", errors="replace")
            else:
                robots_response.close()
        except requests.RequestException:
            pass

        _log(f"Discovering URLs from sitemaps of {origin.root} ...")
        urls, discovery = fetch_sitemap_urls(session, origin, governor, sig_headers=sig_headers,
                                             target=args.max_pages, robots_text=robots_text, log=_log)
        if not urls:
            _log("Error: no sitemap URLs found. Shopify storefronts always expose /sitemap.xml; "
                 "check the host, or whether the store is password-protected.")
            return 1

        if args.include:
            pattern = re.compile(args.include)
            urls = [u for u in urls if pattern.search(u)]
        if args.exclude:
            pattern = re.compile(args.exclude)
            urls = [u for u in urls if not pattern.search(u)]

        if not args.ignore_robots and robots_text:
            robots = RobotFileParser()
            robots.parse(robots_text.splitlines())
            urls = [u for u in urls if robots.can_fetch(USER_AGENT, u)]

        done: set[str] = set()
        if args.resume and pages_file.exists():
            for line in pages_file.read_text(encoding="utf-8").splitlines():
                try:
                    done.add(json.loads(line)["url"])
                except (json.JSONDecodeError, KeyError):
                    continue
            urls = [u for u in urls if u not in done]
            _log(f"Resuming: {len(done)} already crawled, {len(urls)} left")

        discovered = len(urls) + len(done)
        if args.max_pages and len(urls) > args.max_pages:
            _log(f"Capping at --max-pages {args.max_pages} of {len(urls)} discovered URLs; "
                 f"report this truncation in the audit.")
            urls = urls[:args.max_pages]

        _log(f"Crawling {len(urls)} URLs, concurrency {args.concurrency}, delay {args.delay}s"
             + ("" if args.max_pages else " (no page cap)"))
        progress_every = max(25, min(500, len(urls) // 50 or 25))
        started_at = time.time()
        records: list[dict] = []
        write_lock = threading.Lock()
        mode = "a" if (args.resume and pages_file.exists()) else "w"

        try:
            with pages_file.open(mode, encoding="utf-8") as sink:
                with futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                    pending = {pool.submit(crawl_one, sessions.get, url, origin, sig_headers,
                                           governor, args.timeout, html_dir): url for url in urls}
                    for index, future in enumerate(futures.as_completed(pending), 1):
                        record = future.result()
                        with write_lock:
                            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
                            sink.flush()
                        records.append(record)
                        if index % progress_every == 0 or index == len(urls):
                            elapsed = time.time() - started_at
                            eta = elapsed / (index / len(urls)) - elapsed
                            _log(f"  {index}/{len(urls)} ({index / len(urls):.0%}) ETA {eta / 60:.0f} min, "
                                 f"delay {governor.delay:.2f}s, {governor.hits} rate-limit hits")
        finally:
            sessions.close()

    if args.resume and done:
        for line in pages_file.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("url") in done:
                records.append(record)

    summary = summarize(records)
    summary["authority"] = authority
    summary["signed"] = bool(sig_headers)
    summary["urls_discovered"] = discovered
    summary["discovery_capped"] = discovery["discovery_capped"]
    summary["truncated"] = bool(discovery["discovery_capped"]) or (
        bool(args.max_pages) and discovered > summary["pages_crawled"])
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "sample.json").write_text(
        json.dumps(stratified_sample(records, args.sample_per_template), indent=2, ensure_ascii=False),
        encoding="utf-8")

    _log(f"Done. {summary['pages_crawled']} pages -> {out_dir}")
    print(json.dumps(summary if args.json else summary["issues"], indent=2, ensure_ascii=False))

    if governor.hits and sig_headers:
        _log("WARNING: rate limited despite a signature. Shopify treats that as an invalid "
             "signature; check its expiry and that the host matches the one it was issued for.")
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
