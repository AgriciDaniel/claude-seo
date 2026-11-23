#!/usr/bin/env python3
"""Find exact and near-duplicate images on one page.

Exact duplicates are the same bytes at more than one URL (SHA-256).
Near duplicates are different bytes whose difference hash is within
``NEAR_DISTANCE``. Flat images (solid colors, spacers) are not compared
that way, because a difference hash cannot tell two flat colors apart.
Decorative images, tracking pixels, and files that are not images are
left out.

This does not search Google's image index. That needs an external API
the maintainer parked with the DataForSEO v3 work. The check here is the
page's own images.

Usage:
    python image_duplicates.py --url https://example.com --json
    python image_duplicates.py --images images.json --json

``--images`` is a JSON list, or an object with an ``images`` list, in the
shape ``parse_html.py`` writes (``resolved_src``, ``src``, ``decorative``,
``width``, ``height``).

Every image fetch goes through ``url_safety.safe_requests_get``. A body
over 8 MiB is not hashed. A partial body is never treated as the file.

Exit codes:
    0  the check ran, including when nothing was duplicated
    1  a page or the images file could not be read
    2  bad arguments or invalid JSON
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

MAX_IMAGE_BYTES = 8 * 1024 * 1024
DEFAULT_LIMIT = 50
MIN_CONTENT_BYTES = 64
TINY_DIMENSION = 2
NEAR_DISTANCE = 6
_DHASH_WIDTH = 9
_DHASH_HEIGHT = 8
_FLAT_VARIANCE = 4.0


def _dimension(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip().rstrip("px")
        if text.isdigit():
            return int(text)
    return None


def image_url(image: dict) -> str:
    for key in ("resolved_src", "src"):
        value = image.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def skip_reason(image: dict) -> str | None:
    """Why this tag is not a content image, or None when it should be fetched."""
    if image.get("decorative") is True:
        return "decorative"
    width = _dimension(image.get("width"))
    height = _dimension(image.get("height"))
    if (
        width is not None
        and height is not None
        and width <= TINY_DIMENSION
        and height <= TINY_DIMENSION
    ):
        return "tracking pixel"
    url = image_url(image)
    if not url:
        return "no url"
    if url.lower().startswith("data:"):
        return "data url"
    try:
        scheme = urlparse(url).scheme.lower()
    except ValueError:
        return "malformed url"
    if scheme not in ("http", "https"):
        return "not an http(s) url"
    return None


def collect_candidates(images: list, limit: int) -> tuple[list[dict], list[dict]]:
    """Unique content URLs, in order, plus everything that was left out."""
    if not isinstance(images, list):
        raise ValueError("images must be a list")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    skipped: list[dict] = []
    chosen: list[dict] = []
    seen: dict[str, dict] = {}
    for image in images:
        if not isinstance(image, dict):
            skipped.append({"url": "", "reason": "not an image object"})
            continue
        url = image_url(image)
        reason = skip_reason(image)
        if reason:
            skipped.append({"url": url, "reason": reason})
            continue
        if url in seen:
            seen[url]["references"] += 1
            continue
        if len(chosen) >= limit:
            skipped.append({"url": url, "reason": f"limit of {limit} images"})
            continue
        item = {"url": url, "references": 1}
        seen[url] = item
        chosen.append(item)
    return chosen, skipped


def _sniff(body: bytes) -> str | None:
    from parse_html import _sniff_image_format

    return _sniff_image_format(body)


def _perceptual(body: bytes) -> dict:
    """64-bit difference hash, or a reason it could not be computed."""
    try:
        from PIL import Image
    except ImportError:
        return {"hash": None, "flat": None, "reason": "pillow is not installed"}
    try:
        with Image.open(io.BytesIO(body)) as img:
            gray = img.convert("L").resize(
                (_DHASH_WIDTH, _DHASH_HEIGHT),
                Image.Resampling.LANCZOS,
            )
            pixels = list(gray.getdata())
    except Exception:
        return {"hash": None, "flat": None, "reason": "image could not be decoded"}
    if len(pixels) != _DHASH_WIDTH * _DHASH_HEIGHT:
        return {"hash": None, "flat": None, "reason": "image could not be decoded"}
    mean = sum(pixels) / len(pixels)
    variance = sum((pixel - mean) ** 2 for pixel in pixels) / len(pixels)
    bits = 0
    for y in range(_DHASH_HEIGHT):
        row = y * _DHASH_WIDTH
        for x in range(_DHASH_WIDTH - 1):
            bits = (bits << 1) | (1 if pixels[row + x] > pixels[row + x + 1] else 0)
    return {"hash": bits, "flat": variance < _FLAT_VARIANCE, "reason": None}


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def describe_body(body: bytes) -> dict:
    """Classify one downloaded body. Does not fetch."""
    if not body:
        return {"error": "empty body"}
    if len(body) < MIN_CONTENT_BYTES:
        return {"skipped": "smaller than a content image"}
    kind = _sniff(body)
    if kind is None:
        return {"error": "not a recognized image"}
    perceptual = _perceptual(body)
    described = {
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "format": kind,
        "dhash": None if perceptual["hash"] is None else f"{perceptual['hash']:016x}",
        "flat": perceptual["flat"],
    }
    if perceptual["reason"]:
        described["dhash_reason"] = perceptual["reason"]
    return described


def fetch_image(url: str, timeout: int = 15) -> dict:
    """Download one image through the SSRF-safe client. Never returns a partial body."""
    import requests
    from parse_html import IMAGE_ACCEPT
    from url_safety import URLSafetyError, read_bounded, safe_requests_get

    try:
        response = safe_requests_get(
            url,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
            headers={"Accept": IMAGE_ACCEPT, "Accept-Encoding": "identity"},
        )
    except URLSafetyError as exc:
        return {"error": f"url_safety: {exc}"}
    except requests.exceptions.RequestException as exc:
        return {"error": f"request failed: {exc}"}
    try:
        if response.status_code >= 400:
            return {"error": f"HTTP {response.status_code}"}
        length = response.headers.get("Content-Length")
        if length and length.isdigit() and int(length) > MAX_IMAGE_BYTES:
            return {"error": f"larger than {MAX_IMAGE_BYTES} bytes"}
        body, too_large = read_bounded(response, MAX_IMAGE_BYTES)
        if too_large:
            return {"error": f"larger than {MAX_IMAGE_BYTES} bytes"}
    finally:
        response.close()
    return {"body": body}


def _union_find(size: int) -> tuple[list[int], object, object]:
    parent = list(range(size))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        parent[find(left)] = find(right)

    return parent, find, union


def report(fetched: list[dict], skipped: list[dict] | None = None) -> dict:
    """Build the duplicate report from already-downloaded results.

    Each fetched item is ``{"url", "references", "body" | "error"}``.
    """
    skipped = list(skipped or [])
    failed: list[dict] = []
    measured: list[dict] = []
    for item in fetched:
        url = item.get("url", "")
        if item.get("error"):
            failed.append({"url": url, "error": item["error"]})
            continue
        described = describe_body(item.get("body") or b"")
        if described.get("skipped"):
            skipped.append({"url": url, "reason": described["skipped"]})
            continue
        if described.get("error"):
            failed.append({"url": url, "error": described["error"]})
            continue
        measured.append({
            "url": url,
            "references": item.get("references", 1),
            **described,
        })

    by_hash: dict[str, list[dict]] = defaultdict(list)
    for item in measured:
        by_hash[item["sha256"]].append(item)
    exact = []
    for digest, group in by_hash.items():
        if len(group) < 2:
            continue
        exact.append({
            "sha256": digest,
            "bytes": group[0]["bytes"],
            "format": group[0]["format"],
            "urls": [item["url"] for item in group],
        })
    exact.sort(key=lambda group: (-len(group["urls"]), group["sha256"]))

    representatives = [
        group[0]
        for group in by_hash.values()
        if group[0].get("dhash") and not group[0].get("flat")
    ]
    _parent, find, union = _union_find(len(representatives))
    distances: dict[tuple[int, int], int] = {}
    for left in range(len(representatives)):
        for right in range(left + 1, len(representatives)):
            distance = hamming(
                int(representatives[left]["dhash"], 16),
                int(representatives[right]["dhash"], 16),
            )
            if distance <= NEAR_DISTANCE:
                union(left, right)
                distances[(left, right)] = distance
    clusters: dict[int, list[int]] = defaultdict(list)
    for index in range(len(representatives)):
        clusters[find(index)].append(index)
    near = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        member_ids = set(members)
        urls: list[str] = []
        for index in members:
            digest = representatives[index]["sha256"]
            urls.extend(item["url"] for item in by_hash[digest])
        pair_distances = [
            distance
            for (left, right), distance in distances.items()
            if left in member_ids and right in member_ids
        ]
        near.append({
            "distance": min(pair_distances) if pair_distances else 0,
            "urls": urls,
        })
    near.sort(key=lambda group: (group["distance"], group["urls"]))

    pillow_missing = any(
        item.get("dhash_reason") == "pillow is not installed" for item in measured
    )
    if pillow_missing:
        near_status = "not_checked"
        near_reason = "Pillow is not installed, so only exact duplicates were compared."
    else:
        near_status = "checked"
        near_reason = None

    exact_count = sum(len(group["urls"]) for group in exact)
    if exact or near:
        presentation = (
            f"{len(exact)} exact duplicate group(s) ({exact_count} URLs) and "
            f"{len(near)} near-duplicate group(s). "
            "Exact means the same bytes. Near means a difference hash within "
            f"{NEAR_DISTANCE}; review those, do not call them identical."
        )
    elif not measured and failed:
        presentation = "No image body could be checked. See failed."
    else:
        presentation = "No exact or near-duplicate content images."
    if near_reason:
        presentation += " " + near_reason

    result = {
        "status": "ok",
        "checked": len(measured),
        "skipped": skipped,
        "failed": failed,
        "exact_duplicates": exact,
        "near_duplicates": near,
        "near_distance": NEAR_DISTANCE,
        "near_status": near_status,
        "indexed_image_search": "not performed",
        "presentation": presentation,
    }
    if near_reason:
        result["near_reason"] = near_reason
    return result


def load_images_document(path: Path) -> list:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise OSError(f"could not read {path}: {exc.strerror or exc}") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    if isinstance(document, list):
        return document
    if isinstance(document, dict) and isinstance(document.get("images"), list):
        return document["images"]
    raise ValueError("images JSON must be a list or an object with an images list")


def images_from_url(url: str, timeout: int) -> list:
    from fetch_page import fetch_page
    from parse_html import parse_html

    page = fetch_page(url, timeout=timeout)
    if page.get("error"):
        raise OSError(str(page["error"]))
    html = page.get("content") or ""
    final_url = page.get("url") or url
    return parse_html(html, base_url=final_url).get("images") or []


def _emit(payload: dict) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find exact and near-duplicate images.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="Page whose images are checked")
    source.add_argument("--images", help="JSON file of image records")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Accepted for compatibility. Output is always JSON.",
    )
    args = parser.parse_args(argv)
    if args.limit < 1 or args.timeout < 1:
        _emit({"status": "error", "error": "limit and timeout must be at least 1"})
        return 2

    try:
        if args.url:
            images = images_from_url(args.url, args.timeout)
        else:
            images = load_images_document(Path(args.images))
        chosen, skipped = collect_candidates(images, args.limit)
    except ValueError as exc:
        _emit({"status": "error", "error": str(exc)})
        return 2
    except OSError as exc:
        _emit({"status": "error", "error": str(exc)})
        return 1

    fetched = []
    for item in chosen:
        downloaded = fetch_image(item["url"], timeout=args.timeout)
        fetched.append({**item, **downloaded})
    _emit(report(fetched, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
