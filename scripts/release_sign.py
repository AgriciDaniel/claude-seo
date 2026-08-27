#!/usr/bin/env python3
"""
Generate a SHA-256 manifest of every git-tracked file in the repository.

The manifest is published alongside each release tag (attached to the
GitHub release artifacts) so users — and the install scripts — can
verify the contents of a checkout against the maintainer's signed
record.

Usage
=====

Generate a manifest for the current working tree::

    python scripts/release_sign.py > release-manifest.json

Compare two manifests to find drift between releases::

    python scripts/release_sign.py --compare old.json new.json

Threat model
============
This manifest defends against tag rewrites and partial supply-chain
tampering where an attacker can modify some repository files but not
the published manifest. It does NOT defend against a fully compromised
release (manifest + files both replaced by an attacker who controls
the GitHub repo). For that level of trust the maintainer signs the
manifest with a GPG key whose fingerprint is published out of band
(SECURITY.md, the maintainer's site, etc.).

Output schema
=============
::

    {
      "version": "v2.0.0",                      # plugin.json version
      "tag":     "v2.0.0",                      # git tag or "(uncommitted)"
      "commit":  "abc123…",                     # git HEAD
      "generated_at": "2026-05-17T14:32:00Z",
      "files": {
        "scripts/url_safety.py": "<sha256 hex>",
        …
      },
      "tree_sha256": "<sha256 hex of the sorted manifest itself>"
    }

The ``tree_sha256`` field lets a single hash be quoted in a release
note or signed with GPG without needing to attach the whole JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    """Run ``git`` from the repo root and return stripped stdout."""
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def _git_or_none(*args: str) -> str | None:
    try:
        return _git(*args)
    except subprocess.CalledProcessError:
        return None


def _tracked_files() -> list[str]:
    """Return every file tracked by git (sorted, repo-relative)."""
    out = _git("ls-files")
    return sorted(line for line in out.splitlines() if line)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_plugin_version() -> str:
    manifest = REPO_ROOT / ".claude-plugin" / "plugin.json"
    try:
        with manifest.open() as fh:
            return json.load(fh).get("version", "unknown")
    except (OSError, json.JSONDecodeError):
        return "unknown"


def build_manifest(files: Iterable[str] | None = None) -> dict:
    """Build the SHA-256 manifest for the current working tree."""
    if files is None:
        files = _tracked_files()

    hashes: dict[str, str] = {}
    for rel in files:
        abs_path = REPO_ROOT / rel
        if not abs_path.is_file():
            # Submodule entries and broken symlinks fall through git
            # ls-files; skip them but record the absence.
            continue
        hashes[rel] = _sha256(abs_path)

    # Compute a hash-of-hashes so a single value identifies the whole
    # manifest. Deterministic ordering: sorted file paths, one
    # ``<sha>  <path>\n`` line each (matching sha256sum's wire format).
    tree_input = "".join(f"{sha}  {path}\n" for path, sha in sorted(hashes.items()))
    tree_sha = hashlib.sha256(tree_input.encode("utf-8")).hexdigest()

    return {
        "version": _read_plugin_version(),
        "tag": _git_or_none("describe", "--tags", "--exact-match") or "(uncommitted)",
        "commit": _git_or_none("rev-parse", "HEAD") or "(uncommitted)",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": hashes,
        "tree_sha256": tree_sha,
    }


def compare(old: dict, new: dict) -> dict:
    """Diff two manifests; return added / removed / changed files."""
    old_files = old.get("files", {})
    new_files = new.get("files", {})
    return {
        "added": sorted(set(new_files) - set(old_files)),
        "removed": sorted(set(old_files) - set(new_files)),
        "changed": sorted(
            p for p in set(new_files) & set(old_files) if old_files[p] != new_files[p]
        ),
        "tree_sha256_old": old.get("tree_sha256"),
        "tree_sha256_new": new.get("tree_sha256"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or compare claude-seo release SHA-256 manifests."
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("OLD", "NEW"),
        help="Diff two manifests instead of generating a new one.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation (default 2).",
    )
    args = parser.parse_args()

    if args.compare:
        with open(args.compare[0]) as fh:
            old = json.load(fh)
        with open(args.compare[1]) as fh:
            new = json.load(fh)
        json.dump(compare(old, new), sys.stdout, indent=args.indent)
        sys.stdout.write("\n")
        return 0

    manifest = build_manifest()
    json.dump(manifest, sys.stdout, indent=args.indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
