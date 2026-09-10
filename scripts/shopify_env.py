#!/usr/bin/env python3
"""
Read Shopify Crawler Access signatures from a project-local `.shopify-env`.

Shopify merchants mint a crawl credential in their admin under
Online Store > Preferences > Crawler access. The admin prints three HTTP
header values (RFC 9421 message signature, tag "web-bot-auth"). A crawler
that replays them is not rate limited by the storefront. The signature is
bound to one authority (host) and expires after roughly 90 days.

The file lives in the folder an audit runs from, one block per shop. A new
`Domain=` line starts a block; keys before the first `Domain=` are crawl
settings shared by every shop in the file:

    Max-Pages   = 0
    Concurrency = 6

    Domain          = shop.example
    Signature-Input = sig1=("@authority" "signature-agent");keyid="...";tag="web-bot-auth";created=...;expires=...
    Signature       = sig1=:...:
    Signature-Agent = "https://shopify.com"      # optional, this is the default

Lookup order: $SHOPIFY_ENV, then `.shopify-env` in the current directory and
up to five parents. The file holds client credentials; keep it out of git.

Usage:
    python shopify_env.py list [--json]
    python shopify_env.py check <url> [--json]
    python shopify_env.py precheck <url>
    python shopify_env.py headers <url>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ENV_FILENAME = ".shopify-env"
ENV_PATH_VAR = "SHOPIFY_ENV"
DEFAULT_SIGNATURE_AGENT = '"https://shopify.com"'
PARENT_LEVELS = 5
REQUIRED_TAG = "web-bot-auth"
EXPIRY_WARN_DAYS = 14

# Header values are replayed byte-exact; never strip quotes from them.
VERBATIM_KEYS = {"signature-input", "signature", "signature-agent"}


def _flag(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


CRAWL_KEYS = {
    "max-pages": ("max_pages", int),
    "concurrency": ("concurrency", int),
    "delay": ("delay", float),
    "timeout": ("timeout", int),
    "sample-per-template": ("sample_per_template", int),
    "include": ("include", str),
    "exclude": ("exclude", str),
    "save-html": ("save_html", _flag),
    "ignore-robots": ("ignore_robots", _flag),
}


def normalize_key(raw: str) -> str:
    return raw.strip().lower().replace("_", "-")


def normalize_authority(value: str) -> str:
    """Accept a bare host or a full URL and return the lower-cased authority."""
    value = value.strip().strip('"').strip("'")
    if "://" in value:
        return (urlparse(value).netloc or "").lower()
    return value.split("/")[0].lower()


def normalize_signature_agent(value: str) -> str:
    """Shopify expects the value including its quotation marks."""
    value = value.strip()
    if not value:
        return DEFAULT_SIGNATURE_AGENT
    if not value.startswith('"'):
        value = f'"{value.strip(chr(39))}"'
    return value


def parse_signature_input(raw: str) -> dict:
    """Extract label, covered components, keyid, tag, created and expires."""
    meta = {"label": None, "covered": [], "keyid": None, "tag": None,
            "created": None, "expires": None}
    label = re.match(r"\s*([A-Za-z0-9_-]+)\s*=", raw)
    if label:
        meta["label"] = label.group(1)
    covered = re.search(r"=\s*\(([^)]*)\)", raw)
    if covered:
        meta["covered"] = re.findall(r'"([^"]+)"', covered.group(1))
    for key in ("keyid", "tag"):
        found = re.search(rf'{key}="([^"]*)"', raw)
        if found:
            meta[key] = found.group(1)
    for key in ("created", "expires"):
        found = re.search(rf"{key}=(\d+)", raw)
        if found:
            meta[key] = int(found.group(1))
    return meta


def validate_signature_input(meta: dict) -> list[str]:
    problems = []
    if meta["tag"] != REQUIRED_TAG:
        problems.append(f'tag is {meta["tag"]!r}, expected "{REQUIRED_TAG}"')
    if "@authority" not in meta["covered"]:
        problems.append('covered components do not include "@authority"')
    if not meta["keyid"]:
        problems.append("no keyid in Signature-Input")
    if not meta["expires"]:
        problems.append("no expires in Signature-Input")
    return problems


def days_left(expires) -> float:
    if not expires:
        return float("nan")
    return (expires - time.time()) / 86400.0


def find_env_file(start: Path | None = None) -> Path | None:
    explicit = os.environ.get(ENV_PATH_VAR)
    if explicit:
        path = Path(explicit)
        return path if path.is_file() else None
    current = (start or Path.cwd()).resolve()
    for _ in range(PARENT_LEVELS + 1):
        candidate = current / ENV_FILENAME
        if candidate.is_file():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def parse_env_file(path: Path) -> dict:
    result: dict = {"path": str(path), "authorities": {}, "crawl": {}, "problems": []}
    block: dict | None = None

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("[") and line.endswith("]"):
            line = f"Domain={line[1:-1]}"
        if "=" not in line:
            result["problems"].append(f"line {lineno}: no '=' (ignored)")
            continue

        key, _, value = line.partition("=")
        key = normalize_key(key)
        value = value.strip() if key in VERBATIM_KEYS else value.strip().strip('"').strip("'")

        if key == "domain":
            authority = normalize_authority(value)
            if not authority:
                result["problems"].append(f"line {lineno}: empty Domain")
                block = None
                continue
            block = {"authority": authority, "signature_agent": DEFAULT_SIGNATURE_AGENT,
                     "source": f"{path.name}:{lineno}"}
            result["authorities"][authority] = block
            continue

        if key in VERBATIM_KEYS:
            if block is None:
                result["problems"].append(f"line {lineno}: {key} before any Domain= line (ignored)")
                continue
            field = key.replace("-", "_")
            block[field] = normalize_signature_agent(value) if key == "signature-agent" else value
            continue

        if key in CRAWL_KEYS:
            field, caster = CRAWL_KEYS[key]
            try:
                cast = caster(value)
            except (TypeError, ValueError):
                result["problems"].append(f"line {lineno}: {key} is not usable (ignored)")
                continue
            target = block.setdefault("crawl", {}) if block else result["crawl"]
            target[field] = cast
            continue

        result["problems"].append(f"line {lineno}: unknown key {key!r} (ignored)")

    for authority, entry in list(result["authorities"].items()):
        missing = [k for k in ("signature_input", "signature") if not entry.get(k)]
        if missing:
            result["problems"].append(
                f"{authority}: missing {', '.join(m.replace('_', '-') for m in missing)} (domain skipped)")
            result["authorities"].pop(authority)
            continue
        meta = parse_signature_input(entry["signature_input"])
        entry.update({"keyid": meta["keyid"], "created": meta["created"], "expires": meta["expires"]})
        for problem in validate_signature_input(meta):
            result["problems"].append(f"{authority}: {problem}")

    return result


def load(start: Path | None = None) -> dict:
    path = find_env_file(start)
    if not path:
        return {"path": None, "authorities": {}, "crawl": {}, "problems": []}
    return parse_env_file(path)


def lookup(url_or_host: str, start: Path | None = None) -> tuple[str, dict | None, dict]:
    """Return (authority, entry or None, whole env) for one URL or host."""
    authority = normalize_authority(url_or_host)
    env = load(start)
    return authority, env["authorities"].get(authority), env


def signature_headers(entry: dict) -> dict:
    return {
        "Signature-Agent": entry.get("signature_agent", DEFAULT_SIGNATURE_AGENT),
        "Signature-Input": entry["signature_input"],
        "Signature": entry["signature"],
    }


def gitignore_warning(path) -> str:
    """Warn when the env file sits in a git work tree without being ignored."""
    if not path:
        return ""
    path = Path(path)
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(path.parent), capture_output=True, timeout=10)
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", path.name],
            cwd=str(path.parent), capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    if inside.returncode != 0 or b"true" not in inside.stdout or ignored.returncode == 0:
        return ""
    return (f"WARNING: {path.name} holds crawl credentials and is not git-ignored in "
            f"{path.parent}. Add '{ENV_FILENAME}' to .gitignore before committing.")


def precheck(url: str, start: Path | None = None) -> dict:
    """Decide whether an audit of `url` can run the signed, uncapped crawl.

    Never raises: a broken env file must not abort an audit, it just means the
    audit runs the plain link-following crawl.
    """
    result = {"mode": "fallback", "url": url, "authority": None, "reason": None,
              "detail": None, "env_file": None}
    try:
        authority, entry, env = lookup(url, start)
    except Exception as exc:  # noqa: BLE001 - any read problem means fallback
        result["reason"] = "env_unreadable"
        result["detail"] = f"{ENV_FILENAME} could not be read: {exc}"
        return result
    result["authority"] = authority
    result["env_file"] = env["path"]
    if not env["path"]:
        result["reason"] = "no_env_file"
        result["detail"] = f"No {ENV_FILENAME} in the working directory or its parents."
        return result
    if not entry:
        result["reason"] = "no_signature"
        result["detail"] = (f"{env['path']} has no block for {authority}. A signature is bound "
                            f"to one host; if the store serves on the other of apex/www, "
                            f"check that host.")
        return result
    left = days_left(entry.get("expires"))
    if not left == left or left <= 0:  # NaN or expired
        result["reason"] = "signature_expired"
        result["detail"] = (f"The signature for {authority} is expired or has no expiry. Issue "
                            f"a new one in the Shopify admin under Online Store > Preferences "
                            f"> Crawler access.")
        return result
    result["mode"] = "signed"
    result["reason"] = "signature_valid"
    result["days_left"] = round(left)
    result["detail"] = (f"Signature for {authority} is valid for {left:.0f} more days. "
                        f"Crawl the complete sitemap with no page cap.")
    return result


def _describe(authority: str, entry: dict) -> str:
    left = days_left(entry.get("expires"))
    state = "expired" if not left == left or left <= 0 else (
        "expiring" if left < EXPIRY_WARN_DAYS else "ok")
    days = f"{left:6.0f}d" if left == left else "     ?"
    return f"{authority:38s} {state:8s} {days}  {entry.get('source', '')}"


def cmd_list(args) -> int:
    env = load()
    if args.json:
        public = {
            "path": env["path"],
            "crawl": env["crawl"],
            "problems": env["problems"],
            "authorities": {
                a: {"keyid": e.get("keyid"), "expires": e.get("expires"),
                    "days_left": round(days_left(e.get("expires")))
                    if e.get("expires") else None, "crawl": e.get("crawl", {}),
                    "source": e.get("source")}
                for a, e in env["authorities"].items()
            },
        }
        print(json.dumps(public, indent=2))
        return 0 if env["path"] else 3
    if not env["path"]:
        print(f"No {ENV_FILENAME} found in the current directory or its parents.")
        return 3
    print(f"Using {env['path']}")
    warning = gitignore_warning(env["path"])
    if warning:
        print(warning, file=sys.stderr)
    for authority, entry in sorted(env["authorities"].items()):
        print(_describe(authority, entry))
    if env["crawl"]:
        print(f"crawl settings: {json.dumps(env['crawl'])}")
    for problem in env["problems"]:
        print(f"problem: {problem}", file=sys.stderr)
    return 0


def cmd_check(args) -> int:
    authority, entry, env = lookup(args.url)
    if not entry:
        if args.json:
            print(json.dumps({"authority": authority, "signed": False, "env_file": env["path"]}))
        else:
            print(f"No signature for {authority}")
        return 3
    left = days_left(entry.get("expires"))
    valid = left == left and left > 0
    if args.json:
        print(json.dumps({"authority": authority, "signed": valid,
                          "days_left": round(left) if left == left else None,
                          "keyid": entry.get("keyid"), "env_file": env["path"]}))
    elif valid:
        print(f"{authority}: valid, {left:.0f} days left ({entry.get('source')})")
    else:
        print(f"{authority}: expired. Issue a new signature in the Shopify admin "
              f"(Online Store > Preferences > Crawler access).")
    return 0 if valid else 4


def cmd_precheck(args) -> int:
    print(json.dumps(precheck(args.url), indent=2))
    return 0


def cmd_headers(args) -> int:
    """Print the three headers as JSON, or an empty object when none apply."""
    _, entry, _ = lookup(args.url)
    if not entry or not days_left(entry.get("expires")) > 0:
        print("{}")
        return 3
    print(json.dumps(signature_headers(entry)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    lst = sub.add_parser("list", help="list the signatures in the env file with their expiry")
    lst.add_argument("--json", action="store_true")
    lst.set_defaults(func=cmd_list)

    chk = sub.add_parser("check", help="report whether a URL's host has a valid signature")
    chk.add_argument("url")
    chk.add_argument("--json", action="store_true")
    chk.set_defaults(func=cmd_check)

    pre = sub.add_parser("precheck", help="decide signed vs fallback for an audit (always JSON, exit 0)")
    pre.add_argument("url")
    pre.set_defaults(func=cmd_precheck)

    hdr = sub.add_parser("headers", help="print the signature headers for a URL as JSON")
    hdr.add_argument("url")
    hdr.set_defaults(func=cmd_headers)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
