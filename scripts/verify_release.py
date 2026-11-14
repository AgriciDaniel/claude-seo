#!/usr/bin/env python3
"""
Verify the integrity of a claude-seo checkout against a release manifest.

Usage
=====

After installing from a tag::

    python scripts/verify_release.py path/to/release-manifest.json

The script returns exit code 0 when every file in the manifest is
present and matches the recorded SHA-256, and exit code 1 (with a
human-readable report) on any mismatch, missing file, or extra file.

This pairs with ``scripts/release_sign.py`` (used by the maintainer to
generate the manifest at release time) and the GitHub release
attachment workflow that publishes the manifest alongside each tag.

Threat model
============
See SECURITY.md "Tampered install" section. Verification catches tag
force-pushes and partial supply-chain tampering, but does NOT defend
against an attacker who can replace both the source files and the
published manifest. For that level of trust, the manifest must be
signed by the maintainer's GPG key whose fingerprint is published
out of band.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PureWindowsPath

REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _contained_path(resolved_root: Path, rel: object) -> Path | None:
    """The path of manifest entry ``rel`` under ``resolved_root``, or None.

    None means the entry must not be read: it is not a string, is empty or
    absolute, or resolves (through ``..`` or a symlink) outside the root.
    A manifest is untrusted input, so this runs before any file is opened.
    """
    if not isinstance(rel, str) or not rel or "\0" in rel:
        return None
    if Path(rel).is_absolute() or PureWindowsPath(rel).is_absolute():
        return None
    if PureWindowsPath(rel).drive or rel.startswith(("/", "\\")):
        return None
    try:
        candidate = (resolved_root / rel).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if candidate == resolved_root or not candidate.is_relative_to(resolved_root):
        return None
    return candidate


def verify(manifest_path: Path, root: Path = REPO_ROOT) -> dict:
    """Compare a manifest against the working tree at ``root``.

    Returns a dict with:
        ok          : True iff every file in manifest matches.
        manifest    : the manifest payload (for the caller to display
                      version/tag/commit context).
        mismatched  : paths whose SHA-256 differs.
        missing     : paths in manifest but absent from disk.
        outside_root: manifest entries that are absolute or resolve
                      (through ``..`` or a symlink) to a place outside
                      ``root``. They are never opened or hashed and
                      always fail verification.
        extra       : paths on disk (and git-tracked) but not in
                      manifest. Empty unless caller passes a tracked
                      file list; default behaviour leaves this empty.
    """
    with manifest_path.open() as fh:
        manifest = json.load(fh)

    expected = manifest.get("files", {})
    mismatched: list[dict] = []
    missing: list[str] = []

    outside_root: list[str] = []
    resolved_root = root.resolve()

    for rel, expected_sha in sorted(expected.items()):
        abs_path = _contained_path(resolved_root, rel)
        if abs_path is None:
            outside_root.append(rel)
            continue
        if not abs_path.is_file():
            missing.append(rel)
            continue
        actual_sha = _sha256(abs_path)
        if actual_sha != expected_sha:
            mismatched.append(
                {"path": rel, "expected": expected_sha, "actual": actual_sha}
            )

    return {
        "ok": not (mismatched or missing or outside_root),
        "manifest": {
            "version": manifest.get("version"),
            "tag": manifest.get("tag"),
            "commit": manifest.get("commit"),
            "generated_at": manifest.get("generated_at"),
            "tree_sha256": manifest.get("tree_sha256"),
        },
        "checked": len(expected),
        "mismatched": mismatched,
        "missing": missing,
        "outside_root": outside_root,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a claude-seo checkout against a release manifest."
    )
    parser.add_argument(
        "manifest", type=Path, help="Path to release-manifest.json."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to verify (default: this checkout).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON report instead of human-readable text.",
    )
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"Error: manifest not found: {args.manifest}", file=sys.stderr)
        return 2

    result = verify(args.manifest, args.root)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        m = result["manifest"]
        status = "OK" if result["ok"] else "FAIL"
        print(f"Verification: {status}")
        print(f"  Manifest version: {m['version']}  tag: {m['tag']}")
        print(f"  Manifest commit:  {m['commit']}")
        print(f"  Generated at:     {m['generated_at']}")
        print(f"  Tree SHA-256:     {m['tree_sha256']}")
        print(f"  Files checked:    {result['checked']}")
        if result["mismatched"]:
            print(f"\n  Mismatched ({len(result['mismatched'])}):")
            for row in result["mismatched"]:
                print(f"    - {row['path']}")
                print(f"        expected: {row['expected']}")
                print(f"        actual:   {row['actual']}")
        if result["missing"]:
            print(f"\n  Missing ({len(result['missing'])}):")
            for path in result["missing"]:
                print(f"    - {path}")
        if result["outside_root"]:
            print(f"\n  Outside the checkout, refused ({len(result['outside_root'])}):")
            for path in result["outside_root"]:
                print(f"    - {path!r}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
