#!/usr/bin/env python3
"""
IndexNow submitter.

POSTs a list of URLs to the IndexNow open API. Amazon, Bing, Naver,
Seznam.cz, Yandex, and Yep consume the same endpoint. Google does not
participate per the IndexNow FAQ, so this is specifically a non-Google
indexing signal.

Setup
=====
1. Generate a 32+ character host key. Any random string works.
2. Place the key in a file named ``<key>.txt`` at the root of your
   site, served at ``https://example.com/<key>.txt`` — the file body
   is the key itself. IndexNow crawls this once to prove host ownership.
3. Pass the key + the key-location URL to this script (or set the
   ``INDEXNOW_KEY`` and ``INDEXNOW_KEY_LOCATION`` env vars).

Usage
=====
::

    python scripts/indexnow_submit.py \\
        --host example.com \\
        --key abcd1234… \\
        --key-location https://example.com/abcd1234.txt \\
        --urls https://example.com/new-post https://example.com/updated-page

    # Or read URLs from a file (one per line):
    python scripts/indexnow_submit.py \\
        --host example.com --key abcd1234… --key-location https://… \\
        --urls-file changed.txt

Spec: https://www.indexnow.org/documentation
FAQ: https://www.indexnow.org/faq
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from url_safety import URLSafetyError, safe_requests_get, validate_url_strict  # noqa: E402

# The umbrella endpoint forwards to every participating engine. Individual
# engine endpoints exist, but api.indexnow.org dispatches automatically.
# One POST covers all six listed IndexNow participants.
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"


def _normalized_host(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"//{value}")
    return (parsed.hostname or value).lower().rstrip(".")


def _belongs_to_host(url: str, host: str) -> bool:
    parsed_host = _normalized_host(url)
    declared_host = _normalized_host(host)
    return parsed_host == declared_host or parsed_host.endswith(f".{declared_host}")


def submit(
    host: str,
    key: str,
    key_location: str,
    urls: Iterable[str],
    *,
    timeout: int = 30,
) -> dict:
    """Submit a batch of URLs to IndexNow. Returns a result dict."""
    import requests

    url_list = list(urls)
    if not url_list:
        return {"ok": False, "error": "empty url list", "submitted": 0}
    if len(url_list) > 10000:
        return {"ok": False, "error": "IndexNow spec caps batch at 10000 URLs", "submitted": 0}
    if len(key) < 8 or len(key) > 128:
        return {"ok": False, "error": "key must be 8-128 chars per IndexNow spec",
                "submitted": 0}

    # Every submitted URL must belong to the declared host. IndexNow rejects
    # cross-host submissions to prevent abuse.
    bad = [u for u in url_list if not _belongs_to_host(u, host)]
    if bad:
        return {
            "ok": False,
            "error": f"{len(bad)} URLs don't belong to host {host!r}",
            "examples": bad[:3],
            "submitted": 0,
        }

    # Validate every submitted URL through url_safety so we don't ship
    # private-IP links to the API by accident.
    for u in url_list:
        try:
            validate_url_strict(u)
        except URLSafetyError as exc:
            return {"ok": False, "error": f"url_safety refused {u!r}: {exc}",
                    "submitted": 0}

    payload = {
        "host": host,
        "key": key,
        "keyLocation": key_location,
        "urlList": url_list,
    }

    try:
        resp = requests.post(
            INDEXNOW_ENDPOINT,
            json=payload,
            timeout=timeout,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
    except requests.exceptions.RequestException as exc:
        return {"ok": False, "error": f"HTTP error: {exc}", "submitted": 0}

    return {
        "ok": resp.status_code in (200, 202),
        "status_code": resp.status_code,
        "submitted": len(url_list),
        "endpoint": INDEXNOW_ENDPOINT,
        "engines": ["Amazon", "Bing", "Naver", "Seznam.cz", "Yandex", "Yep"],
        "response_body_preview": (resp.text or "")[:200],
    }


def verify_key_published(
    host: str, key: str, key_location: str
) -> dict:
    """Fetch the published key file and confirm it matches.

    IndexNow requires the key to be retrievable at the keyLocation URL.
    Missing or wrong content silently rejects every later submission, so
    this pre-flight catches the common ownership-setup mistake.
    """
    try:
        resp = safe_requests_get(key_location, timeout=15)
    except URLSafetyError as exc:
        return {"ok": False, "error": f"url_safety: {exc}"}
    except Exception as exc:  # noqa: BLE001 — surface every transport error verbatim
        return {"ok": False, "error": f"fetch failed: {exc}"}
    if resp.status_code != 200:
        return {"ok": False, "status_code": resp.status_code,
                "error": "keyLocation returned non-200"}
    if resp.text.strip() != key:
        return {
            "ok": False,
            "status_code": 200,
            "error": "keyLocation contents do not match key",
            "expected_length": len(key),
            "actual_length": len(resp.text.strip()),
        }
    if host not in key_location:
        return {"ok": False, "error": "keyLocation host does not match declared host"}
    return {"ok": True, "status_code": 200}


def _load_urls(arg_urls: list[str], urls_file: str | None) -> list[str]:
    items: list[str] = list(arg_urls or [])
    if urls_file:
        for line in Path(urls_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                items.append(line)
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit URLs to IndexNow.")
    parser.add_argument(
        "--host", required=True,
        help="Site host (without scheme), e.g. example.com",
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("INDEXNOW_KEY"),
        help="IndexNow host key (or set INDEXNOW_KEY).",
    )
    parser.add_argument(
        "--key-location",
        default=os.environ.get("INDEXNOW_KEY_LOCATION"),
        help="Public URL that serves the key file "
             "(or set INDEXNOW_KEY_LOCATION).",
    )
    parser.add_argument(
        "--urls", nargs="*", default=[],
        help="URLs to submit (space-separated).",
    )
    parser.add_argument(
        "--urls-file",
        help="File path with one URL per line (lines starting with # ignored).",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Check that the key file is published correctly; do not submit.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.key or not args.key_location:
        print("Error: --key and --key-location required (or set env vars).",
              file=sys.stderr)
        return 2

    if args.verify_only:
        result = verify_key_published(args.host, args.key, args.key_location)
        if args.json:
            json.dump(result, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            status = "OK" if result["ok"] else "FAIL"
            print(f"Key verification: {status}")
            if "error" in result:
                print(f"  {result['error']}")
        return 0 if result["ok"] else 1

    urls = _load_urls(args.urls, args.urls_file)
    if not urls:
        print("Error: pass at least one URL via --urls or --urls-file.",
              file=sys.stderr)
        return 2

    # Pre-flight: verify key publication before sending the batch.
    verify = verify_key_published(args.host, args.key, args.key_location)
    if not verify["ok"]:
        print(f"Pre-flight failed: {verify.get('error', 'unknown')}",
              file=sys.stderr)
        if args.json:
            json.dump({"ok": False, "verify": verify}, sys.stdout, indent=2)
            sys.stdout.write("\n")
        return 1

    result = submit(args.host, args.key, args.key_location, urls)
    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        status = "OK" if result["ok"] else "FAIL"
        print(f"IndexNow: {status} (status={result.get('status_code')})")
        print(f"  Submitted: {result['submitted']} URLs to {result['endpoint']}")
        if result.get("engines"):
            print(f"  Engines:   {', '.join(result['engines'])}")
        if not result["ok"]:
            print(f"  Error: {result.get('error', 'see response_body_preview')}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
