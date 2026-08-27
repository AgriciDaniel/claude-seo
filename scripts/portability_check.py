#!/usr/bin/env python3
"""
Cross-platform portability lint for SKILL.md files.

claude-seo skills run under Claude Code, but also Cursor / Cursor Cloud
Agents / Google Antigravity / Gemini CLI / OpenAI Codex CLI / Cline /
Aider. Most harnesses share a minimum frontmatter contract:

  - ``name``        (string, kebab-case, < 64 chars)
  - ``description`` (string, < 1024 chars, ends with a period or noun phrase)

Claude-Code-specific fields are tolerated by other harnesses (they are
ignored, not rejected):

  - ``model``        (e.g. sonnet, haiku, opus)
  - ``maxTurns``     (int)
  - ``tools``        (comma-separated list with optional inline comments)
  - ``compatibility`` (free text, e.g. "Requires the @ahrefs/mcp MCP server")
  - ``metadata``     (a dict; metadata.version is read by the consistency tests)

The check walks every ``SKILL.md`` under ``skills/`` and ``extensions/``
and reports portability findings. Severity:

  - ``error``: a harness will outright reject the file (missing required
              field, malformed YAML, name not kebab-case).
  - ``warning``: the file works but loses information in a non-Claude
              harness (e.g. tools list with inline comments may be
              parsed differently).
  - ``info``: noteworthy but harmless (e.g. very long description).

Exit code 0 if no errors; 1 otherwise. Warnings + info do not fail the
build but are surfaced in the report.

Usage::

    python scripts/portability_check.py
    python scripts/portability_check.py --json
    python scripts/portability_check.py --strict   # warnings also fail
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _find_skill_files() -> list[Path]:
    """Every SKILL.md under skills/ and extensions/."""
    paths: list[Path] = []
    for root in ("skills", "extensions"):
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        paths.extend(base.rglob("SKILL.md"))
    return sorted(paths)


def _parse_frontmatter(text: str) -> dict[str, str] | None:
    """Light YAML-ish parser. Doesn't require PyYAML — we accept the
    documented subset (scalar string values, no nested mappings except
    for the metadata: block which we treat as opaque)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None

    body = m.group(1)
    fields: dict[str, str] = {}
    in_metadata = False
    metadata_buf: list[str] = []
    for line in body.splitlines():
        if not line.strip():
            continue
        if line.startswith(" ") or line.startswith("\t"):
            if in_metadata:
                metadata_buf.append(line)
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "metadata":
            in_metadata = True
            metadata_buf = []
            fields["metadata"] = ""  # placeholder; we fill below
        else:
            in_metadata = False
            fields[key] = value.strip("'\"")

    if metadata_buf:
        fields["metadata"] = "\n".join(metadata_buf).strip()

    return fields


def check_one(path: Path) -> list[dict]:
    findings: list[dict] = []
    try:
        relpath = str(path.relative_to(REPO_ROOT))
    except ValueError:
        # Path is outside the repo (e.g. unit tests use tmp_path).
        relpath = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append({
            "severity": "error", "path": relpath,
            "rule": "io-error", "message": f"cannot read: {exc}",
        })
        return findings

    frontmatter = _parse_frontmatter(text)
    if frontmatter is None:
        findings.append({
            "severity": "error", "path": relpath,
            "rule": "no-frontmatter",
            "message": "SKILL.md must open with a YAML --- block",
        })
        return findings

    name = frontmatter.get("name", "").strip()
    if not name:
        findings.append({
            "severity": "error", "path": relpath,
            "rule": "missing-name",
            "message": "frontmatter must declare a 'name'",
        })
    elif not _NAME_RE.match(name):
        findings.append({
            "severity": "error", "path": relpath,
            "rule": "name-not-kebab-case",
            "message": f"name {name!r} must be kebab-case "
                       "(lowercase, hyphens, no leading/trailing dash)",
        })

    description = frontmatter.get("description", "").strip()
    if not description:
        findings.append({
            "severity": "error", "path": relpath,
            "rule": "missing-description",
            "message": "frontmatter must declare a 'description'",
        })
    elif len(description) > 1024:
        findings.append({
            "severity": "warning", "path": relpath,
            "rule": "long-description",
            "message": f"description is {len(description)} chars "
                       "(Codex truncates above 1024; Cursor truncates "
                       "above 2048)",
        })

    # tools is optional. If present, Cline and Codex parse the list more
    # strictly than Claude Code — warn if there are inline comments
    # (e.g., "Read, Bash # for analyse").
    tools = frontmatter.get("tools", "")
    if tools and "#" in tools:
        findings.append({
            "severity": "warning", "path": relpath,
            "rule": "tools-has-inline-comment",
            "message": "Cline + Codex may include the comment in the "
                       "tool name. Move comments below the frontmatter.",
        })

    # metadata.version is referenced by the consistency tests but is
    # purely informational for non-Claude harnesses.
    if frontmatter.get("metadata", ""):
        if 'version' not in frontmatter["metadata"]:
            findings.append({
                "severity": "info", "path": relpath,
                "rule": "metadata-without-version",
                "message": "metadata block present but no version field; "
                           "claude-seo's manifest test expects "
                           "metadata.version on every skill",
            })

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cross-platform portability lint for claude-seo SKILL.md files."
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors (exit 1).")
    args = parser.parse_args()

    paths = _find_skill_files()
    all_findings: list[dict] = []
    for path in paths:
        all_findings.extend(check_one(path))

    error_count = sum(1 for f in all_findings if f["severity"] == "error")
    warning_count = sum(1 for f in all_findings if f["severity"] == "warning")
    info_count = sum(1 for f in all_findings if f["severity"] == "info")

    if args.json:
        json.dump({
            "skills_checked": len(paths),
            "errors": error_count,
            "warnings": warning_count,
            "info": info_count,
            "findings": all_findings,
        }, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Portability lint: {len(paths)} SKILL.md files checked")
        print(f"  errors:   {error_count}")
        print(f"  warnings: {warning_count}")
        print(f"  info:     {info_count}")
        for f in all_findings:
            print(f"  [{f['severity']:<8}] {f['path']} :: {f['rule']}")
            print(f"           {f['message']}")

    fail = error_count > 0 or (args.strict and warning_count > 0)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
