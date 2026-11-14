#!/usr/bin/env python3
"""
Verify the integrity of a claude-seo checkout against a release manifest.

Usage
=====

On a clean checkout of a release tag::

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
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _checkout_files(root: Path, manifest_path: Path) -> set[str]:
    """List checkout files without following directory symlinks or scanning Git data."""
    root = root.resolve()
    manifest_path = manifest_path.resolve()
    found: set[str] = set()

    def fail_on_walk_error(exc: OSError) -> None:
        raise exc

    for current, dirs, files in os.walk(root, followlinks=False, onerror=fail_on_walk_error):
        current_path = Path(current)
        if current_path == root and ".git" in dirs:
            dirs.remove(".git")
        for name in files:
            if current_path == root and name == ".git":
                continue  # worktree checkouts store .git as a file
            path = current_path / name
            if path != manifest_path:
                found.add(path.relative_to(root).as_posix())
        for name in dirs[:]:
            path = current_path / name
            if path.is_symlink():
                found.add(path.relative_to(root).as_posix())
                dirs.remove(name)
    return found


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(manifest_path: Path, root: Path = REPO_ROOT) -> dict:
    """Compare a manifest against the working tree at ``root``.

    Returns a dict with:
        ok          : True iff every file in manifest matches and no extra
                      checkout files are present.
        manifest    : the manifest payload (for the caller to display
                      version/tag/commit context).
        mismatched  : paths whose SHA-256 differs.
        missing     : paths in manifest but absent from disk.
        extra       : paths on disk but not in the manifest. Git metadata
                      and the manifest file itself are excluded.
    """
    with manifest_path.open() as fh:
        manifest = json.load(fh)

    expected = manifest.get("files", {})
    mismatched: list[dict] = []
    missing: list[str] = []

    for rel, expected_sha in sorted(expected.items()):
        abs_path = root / rel
        if not abs_path.is_file():
            missing.append(rel)
            continue
        actual_sha = _sha256(abs_path)
        if actual_sha != expected_sha:
            mismatched.append(
                {"path": rel, "expected": expected_sha, "actual": actual_sha}
            )

    extra = sorted(_checkout_files(root, manifest_path) - set(expected))

    return {
        "ok": not (mismatched or missing or extra),
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
        "extra": extra,
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
        if result["extra"]:
            print(f"\n  Extra ({len(result['extra'])}):")
            for path in result["extra"]:
                print(f"    - {path}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
