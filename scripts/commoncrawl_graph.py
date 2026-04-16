#!/usr/bin/env python3
"""
Common Crawl Web Graph parser for Claude SEO.

Downloads and parses Common Crawl's domain-level web graph to extract
backlink metrics: in-degree, out-degree, PageRank, harmonic centrality,
and top referring domains. No API key needed (public data).

Data source: s3://commoncrawl/projects/hyperlinkgraph/
Releases: Quarterly (cc-main-YYYY-WW)

Usage:
    python commoncrawl_graph.py example.com --json
    python commoncrawl_graph.py example.com --update --json
    python commoncrawl_graph.py --info --json
    python commoncrawl_graph.py example.com --top-referrers 20 --json
"""

import argparse
import csv
import gzip
import io
import json
import os
import sys
import time
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
try:
    from backlinks_auth import get_cache_dir, load_config
    from google_auth import validate_url
except ImportError:
    print("Error: backlinks_auth.py and google_auth.py required in scripts/", file=sys.stderr)
    sys.exit(1)

# Common Crawl web graph base URL (HTTP access to S3 bucket)
CC_GRAPH_BASE = "https://data.commoncrawl.org/projects/hyperlinkgraph"

# Known recent releases (newest first).
# Update periodically: check https://commoncrawl.github.io/cc-webgraph-statistics/
# Naming convention: cc-main-YYYY-mon-mon-mon (quarterly, lowercase month abbreviations)
KNOWN_RELEASES = [
    "cc-main-2026-jan-feb-mar",
    "cc-main-2025-oct-nov-dec",
    "cc-main-2025-jul-aug-sep",
    "cc-main-2025-apr-may-jun",
    "cc-main-2025-jan-feb-mar",
    "cc-main-2024-oct-nov-dec",
]

# Graph file types — filenames include the release name as prefix
# e.g., domain/cc-main-2026-jan-feb-mar-domain-vertices.txt.gz
VERTICES_SUFFIX = "-domain-vertices.txt.gz"
EDGES_SUFFIX = "-domain-edges.txt.gz"
RANKINGS_SUFFIX = "-domain-ranks.txt.gz"


def _graph_file_url(release: str, suffix: str) -> str:
    """Build the full URL for a CC web graph file."""
    return f"{CC_GRAPH_BASE}/{release}/domain/{release}{suffix}"


def _safe_float(s: str) -> Optional[float]:
    """Safely parse a float from a string, returning None on failure."""
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _get_latest_release() -> Optional[str]:
    """
    Discover the latest available CC web graph release.

    Tries known releases in order, returns the first one that exists.

    Returns:
        Release name (e.g., 'cc-main-2026-jan-feb-mar') or None.
    """
    for release in KNOWN_RELEASES:
        url = _graph_file_url(release, VERTICES_SUFFIX)
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                return release
        except requests.exceptions.RequestException:
            continue
    return None


def _get_cache_path(domain: str, release: str, data_type: str) -> str:
    """Get the cache file path for a domain's data."""
    cache_dir = get_cache_dir()
    safe_domain = domain.replace("/", "_").replace(":", "_")
    return os.path.join(cache_dir, f"{safe_domain}-{release}-{data_type}.json")


def _is_cached(domain: str, release: str) -> Optional[dict]:
    """Check if domain data is cached for a given release."""
    cache_path = _get_cache_path(domain, release, "combined")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)
            # Check cache age (90 days max)
            cached_time = cached.get("metadata", {}).get("cached_at", 0)
            if time.time() - cached_time < 90 * 86400:
                return cached
        except (json.JSONDecodeError, IOError):
            pass
    return None


def _save_cache(domain: str, release: str, data: dict) -> None:
    """Save domain data to cache."""
    cache_path = _get_cache_path(domain, release, "combined")
    data.setdefault("metadata", {})["cached_at"] = time.time()
    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)


def _stream_gz_lines(url: str, timeout: int = 120):
    """
    Stream and decompress a gzipped text file line by line.

    Downloads the file in chunks and decompresses on the fly to avoid
    loading multi-GiB files into memory.

    Yields:
        Decoded text lines.
    """
    resp = requests.get(url, stream=True, timeout=timeout)
    resp.raise_for_status()

    decompressor = gzip.GzipFile(fileobj=io.BytesIO(resp.content))
    for line in io.TextIOWrapper(decompressor, encoding="utf-8"):
        yield line.rstrip("\n")


def _stream_gz_chunked(url: str, target_domain: str, timeout: int = 120,
                        max_lines: int = 0) -> list:
    """
    Stream a gzipped file and filter for lines matching the target domain.

    Uses incremental zlib decompression to process large gzipped files
    without loading everything into memory. Stops early when enough matches
    are found.

    Args:
        url: URL of the gzipped file.
        target_domain: Domain to filter for (may be reversed, e.g., com.google).
        timeout: Request timeout in seconds.
        max_lines: Maximum matching lines to return (0 = unlimited).

    Returns:
        List of matching lines (tab-separated field lists).
    """
    import zlib

    matches = []
    max_compressed_bytes = 500 * 1024 * 1024  # 500 MiB safety cap
    total_downloaded = 0

    try:
        resp = requests.get(url, stream=True, timeout=timeout)
        resp.raise_for_status()

        # Incremental gzip decompression (wbits=16+MAX for gzip format)
        decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)
        leftover = ""

        for chunk in resp.iter_content(chunk_size=256 * 1024):  # 256 KiB chunks
            total_downloaded += len(chunk)
            if total_downloaded > max_compressed_bytes:
                break

            try:
                text = decompressor.decompress(chunk).decode("utf-8", errors="replace")
            except zlib.error:
                break

            text = leftover + text
            lines = text.split("\n")
            leftover = lines[-1]  # Incomplete last line carries over

            for line in lines[:-1]:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                fields = line.split("\t")
                for field in fields:
                    if field == target_domain or field.endswith(f".{target_domain}"):
                        matches.append(fields)
                        break
                if max_lines and len(matches) >= max_lines:
                    resp.close()
                    return matches

    except requests.exceptions.Timeout:
        pass  # Return whatever we found so far
    except MemoryError:
        pass

    return matches


def get_domain_metrics(domain: str, release: Optional[str] = None,
                       force_update: bool = False, timeout: int = 120,
                       top_referrers: int = 20) -> dict:
    """
    Get domain-level backlink metrics from Common Crawl web graph.

    Args:
        domain: Target domain (e.g., 'example.com').
        release: CC release name. Auto-detects latest if None.
        force_update: Force re-download, bypassing cache.
        timeout: Download timeout in seconds.
        top_referrers: Number of top referring domains to return.

    Returns:
        Standard response dict with domain metrics.
    """
    # Clean domain
    domain = domain.lower().strip()
    if domain.startswith("http"):
        if not validate_url(domain):
            return {
                "status": "error",
                "data": None,
                "error": f"Invalid or blocked URL: {domain}",
                "metadata": {"source": "commoncrawl"},
            }
        from urllib.parse import urlparse
        domain = urlparse(domain).netloc
    domain = domain.replace("www.", "")

    # Find release
    if not release:
        release = _get_latest_release()
        if not release:
            return {
                "status": "error",
                "data": None,
                "error": "Could not find any Common Crawl web graph release. Check connectivity.",
                "metadata": {"source": "commoncrawl"},
            }

    # Check cache
    if not force_update:
        cached = _is_cached(domain, release)
        if cached:
            cached["metadata"]["from_cache"] = True
            return cached

    # Fetch rankings file (has PageRank + harmonic centrality + reversed domain names)
    # Format: harmonicc_pos \t harmonicc_val \t pr_pos \t pr_val \t host_rev \t n_hosts
    # Domains are reversed: com.google = google.com
    rankings_url = _graph_file_url(release, RANKINGS_SUFFIX)
    rankings_data = {}

    # Reverse domain for matching: google.com -> com.google
    reversed_domain = ".".join(reversed(domain.split(".")))

    try:
        ranking_matches = _stream_gz_chunked(rankings_url, reversed_domain,
                                              timeout=timeout, max_lines=5)
        for fields in ranking_matches:
            if len(fields) >= 6:
                # fields[4] is the reversed hostname (e.g., com.google)
                if fields[4] == reversed_domain:
                    rankings_data = {
                        "harmonic_centrality_rank": int(fields[0]) if fields[0].isdigit() else None,
                        "harmonic_centrality": _safe_float(fields[1]),
                        "pagerank_rank": int(fields[2]) if fields[2].isdigit() else None,
                        "pagerank": _safe_float(fields[3]),
                        "n_hosts": int(fields[5]) if fields[5].isdigit() else None,
                    }
                    break
    except Exception as e:
        rankings_data = {"error": str(e)}

    # Note: The edges file uses numeric vertex IDs (not domain names), so we cannot
    # directly look up referring domains without building a full vertex-ID mapping table.
    referring_domains = []

    # If not found in rankings, check vertices file to confirm domain was crawled at all
    in_rankings = bool(rankings_data.get("pagerank"))
    in_crawl = in_rankings  # If in rankings, definitely in crawl

    if not in_rankings:
        vertices_url = _graph_file_url(release, VERTICES_SUFFIX)
        try:
            vertex_matches = _stream_gz_chunked(vertices_url, reversed_domain,
                                                 timeout=min(timeout, 60), max_lines=1)
            in_crawl = len(vertex_matches) > 0
        except Exception:
            pass  # Vertices file may be very large; timeout is acceptable

    # Build appropriate note based on what we found
    if in_rankings:
        note = "Domain-level metrics from CC web graph. Quarterly updates."
    elif in_crawl:
        note = "Domain found in CC crawl but below ranking threshold (too small/new for PageRank rankings)."
    else:
        note = "Domain not found in Common Crawl data. It may be too new, too small, or not yet crawled."

    result = {
        "status": "success",
        "data": {
            "domain": domain,
            "in_crawl": in_crawl,
            "in_rankings": in_rankings,
            "pagerank": rankings_data.get("pagerank"),
            "pagerank_rank": rankings_data.get("pagerank_rank"),
            "harmonic_centrality": rankings_data.get("harmonic_centrality"),
            "harmonic_centrality_rank": rankings_data.get("harmonic_centrality_rank"),
            "n_hosts": rankings_data.get("n_hosts"),
            "top_referring_domains": referring_domains,
            "referring_domains_sample": len(referring_domains),
            "note": note,
        },
        "error": None,
        "metadata": {
            "source": "commoncrawl",
            "release": release,
            "from_cache": False,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }

    # Cache the result
    _save_cache(domain, release, result)

    return result


def get_graph_info() -> dict:
    """
    Get information about available CC web graph releases and cache status.

    Returns:
        Standard response dict with release info.
    """
    latest = _get_latest_release()
    cache_dir = get_cache_dir()
    cached_files = []
    if os.path.exists(cache_dir):
        cached_files = [f for f in os.listdir(cache_dir) if f.endswith(".json")]

    return {
        "status": "success",
        "data": {
            "latest_release": latest,
            "known_releases": KNOWN_RELEASES,
            "cache_dir": cache_dir,
            "cached_files": len(cached_files),
            "cached_domains": [f.split("-cc-main")[0] for f in cached_files],
        },
        "error": None,
        "metadata": {
            "source": "commoncrawl",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Common Crawl Web Graph parser for Claude SEO"
    )
    parser.add_argument(
        "domain",
        nargs="?",
        default=None,
        help="Target domain to look up (e.g., example.com)",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show available releases and cache status",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Force re-download, bypassing cache",
    )
    parser.add_argument(
        "--release",
        default=None,
        help="Specific CC release to query (e.g., cc-main-2025-18)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Download timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--top-referrers",
        type=int,
        default=20,
        help="Number of top referring domains to return (default: 20)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    if args.info:
        result = get_graph_info()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            data = result["data"]
            print(f"Common Crawl Web Graph Info")
            print(f"  Latest release: {data.get('latest_release', 'unknown')}")
            print(f"  Known releases: {', '.join(data.get('known_releases', []))}")
            print(f"  Cache dir:      {data.get('cache_dir', 'N/A')}")
            print(f"  Cached domains: {data.get('cached_files', 0)}")
        return

    if not args.domain:
        print("Error: domain argument required (or use --info)", file=sys.stderr)
        sys.exit(1)

    result = get_domain_metrics(
        domain=args.domain,
        release=args.release,
        force_update=args.update,
        timeout=args.timeout,
        top_referrers=args.top_referrers,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["status"] == "success" and result["data"]:
            data = result["data"]
            cached = result.get("metadata", {}).get("from_cache", False)
            release = result.get("metadata", {}).get("release", "unknown")
            print(f"Common Crawl Domain Metrics: {data.get('domain', args.domain)}")
            print(f"  Release:                   {release} {'(cached)' if cached else ''}")
            print(f"  PageRank:                  {data.get('pagerank', 'N/A')} (rank #{data.get('pagerank_rank', 'N/A')})")
            print(f"  Harmonic Centrality:       {data.get('harmonic_centrality', 'N/A')} (rank #{data.get('harmonic_centrality_rank', 'N/A')})")
            print(f"  Number of hosts:           {data.get('n_hosts', 'N/A')}")
            referrers = data.get("top_referring_domains", [])
            if referrers:
                print(f"  Top referring domains ({len(referrers)}):")
                for d in referrers[:10]:
                    print(f"    {d}")
            else:
                print("  No referring domains found in sample.")
        elif result.get("error"):
            print(f"Error: {result['error']}", file=sys.stderr)


if __name__ == "__main__":
    main()
