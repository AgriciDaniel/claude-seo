#!/usr/bin/env python3
"""Resolve a user URL against Creaitor list_domains output, fail closed."""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


def normalize(value: str, *, require_absolute: bool) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("URL/domain must be a non-empty string")
    raw = value.strip()
    if any(ord(char) < 32 for char in raw):
        raise ValueError("control characters are not allowed")
    if require_absolute and "://" not in raw:
        raise ValueError("target must be an absolute http(s) URL")
    parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
    if unquote(parsed.netloc) != parsed.netloc:
        raise ValueError("encoded authorities are not allowed")
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("only http and https URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL userinfo is not allowed")
    try:
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("malformed URL authority") from exc
    if not host:
        raise ValueError("URL host is required")
    try:
        ipaddress.ip_address(host.rstrip("."))
    except ValueError:
        pass
    else:
        raise ValueError("IP-literal domains are not allowed")
    default_port = 80 if parsed.scheme.lower() == "http" else 443
    if port is not None and port != default_port:
        raise ValueError("non-default ports are not allowed")
    try:
        ascii_host = host.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("invalid IDNA hostname") from exc
    if ascii_host.startswith("www."):
        ascii_host = ascii_host[4:]
    if not ascii_host or "." not in ascii_host:
        raise ValueError("hostname must be a qualified domain name")
    return ascii_host


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True)
    args = parser.parse_args()
    try:
        request = json.loads(Path(args.input_file).read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise ValueError("input file must contain a JSON object")
        raw_url = request.get("url")
        payload = request.get("domains")
        if not isinstance(raw_url, str):
            raise ValueError("input.url must be a string")
        target = normalize(raw_url, require_absolute=True)
        if not isinstance(payload, list):
            raise ValueError("input.domains must contain the list returned by list_domains")
        matches = []
        rejected = []
        for item in payload:
            if not isinstance(item, dict) or "id" not in item or "domain" not in item:
                rejected.append("malformed domain record")
                continue
            try:
                candidate = normalize(item["domain"], require_absolute=False)
            except ValueError as exc:
                rejected.append(f"{item.get('domain')!r}: {exc}")
                continue
            if candidate == target:
                matches.append({"id": item["id"], "domain": item["domain"]})
        print(json.dumps({
            "input_url": raw_url,
            "normalized_host": target,
            "matches": matches,
            "domain_id": matches[0]["id"] if len(matches) == 1 else None,
            "returned_domain_count": len(payload),
            "may_be_truncated": len(payload) >= 25,
            "rejected_records": rejected,
        }, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
