#!/usr/bin/env python3
"""Post-edit schema validation hook for Claude Code.

Validates JSON-LD schema after file edits. Returns exit code 2 to block
if critical validation errors found.

Hook configuration in ~/.claude/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "node",
            "args": [
              "${CLAUDE_PLUGIN_ROOT}/hooks/run-python-hook.js",
              "${CLAUDE_PLUGIN_ROOT}/hooks/validate-schema.py",
              "${tool_input.file_path}"
            ]
          }
        ]
      }
    ]
  }
}

Note: matcher filters by tool name only (Edit, Write). The script itself
checks if the file contains schema markup before validating.
"""

import json
import os
import re
import sys
from typing import Any, List

BRACKET_PLACEHOLDERS = (
    "[Business Name]",
    "[City]",
    "[State]",
    "[Phone]",
    "[Address]",
    "[Your",
    "[INSERT",
    "[URL]",
    "[Email]",
)
BARE_PLACEHOLDER_RE = re.compile(r"\bREPLACE(?:_[A-Z]+)*\b")


def _configure_utf8() -> None:
    """Keep hook diagnostics printable on legacy Windows console encodings."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def validate_jsonld(content: str) -> List[str]:
    """Validate JSON-LD blocks in HTML content."""
    errors = []
    pattern = r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>'
    blocks = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)

    if not blocks:
        return []  # No schema found; not an error

    for i, block in enumerate(blocks, 1):
        block = block.strip()
        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            errors.append(f"Block {i}: Invalid JSON; {e}")
            continue

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    errors.extend(_validate_schema_object(item, i))
                else:
                    errors.append(f"Block {i}: JSON-LD list members must be objects")
        elif isinstance(data, dict):
            errors.extend(_validate_schema_object(data, i))
        else:
            errors.append(f"Block {i}: JSON-LD root must be an object or list")

    return errors


def _validate_schema_object(
    obj: dict[str, Any], block_num: int, *, inherited_context: bool = False
) -> List[str]:
    """Validate one schema node, including members of a top-level ``@graph``."""
    errors = []
    prefix = f"Block {block_num}"

    # Check @context
    if "@context" not in obj and not inherited_context:
        errors.append(f"{prefix}: Missing @context")
    elif "@context" in obj and obj["@context"] not in (
        "https://schema.org",
        "http://schema.org",
    ):
        errors.append(f"{prefix}: @context should be 'https://schema.org'")

    graph = obj.get("@graph")
    has_graph = isinstance(graph, list)

    # A graph container does not need its own @type. Its object members do.
    if "@type" not in obj and not has_graph:
        errors.append(f"{prefix}: Missing @type")

    # Check for placeholder text
    placeholder_scope = {key: value for key, value in obj.items() if key != "@graph"}
    text = json.dumps(placeholder_scope, ensure_ascii=False)
    for p in BRACKET_PLACEHOLDERS:
        if p.lower() in text.lower():
            errors.append(f"{prefix}: Contains placeholder text: {p}")
    for placeholder in BARE_PLACEHOLDER_RE.findall(text):
        errors.append(f"{prefix}: Contains placeholder text: {placeholder}")

    # Check for deprecated types
    schema_type = obj.get("@type", "")
    deprecated = {
        "HowTo": "deprecated September 2023",
        "SpecialAnnouncement": "deprecated July 31, 2025",
        "CourseInfo": "retired June 2025",
        "EstimatedSalary": "retired June 2025",
        "LearningVideo": "retired June 2025",
        "ClaimReview": "retired June 2025; fact-check rich results discontinued",
        "VehicleListing": "retired June 2025; vehicle listing structured data discontinued",
    }
    if schema_type in deprecated:
        errors.append(f"{prefix}: @type '{schema_type}' is {deprecated[schema_type]}")

    # Check for restricted types used incorrectly.
    # FAQPage is intentionally NOT flagged: Google retired FAQ rich results for
    # all sites (May 7, 2026), but FAQPage remains a valid Schema.org type.
    # This project makes no claim of a confirmed AI or ranking benefit.
    restricted: dict = {}
    if schema_type in restricted:
        errors.append(f"{prefix}: @type '{schema_type}' is {restricted[schema_type]}; verify site qualifies")

    if "@graph" in obj:
        if not isinstance(graph, list):
            errors.append(f"{prefix}: @graph must be a list")
        else:
            context_is_inherited = inherited_context or "@context" in obj
            for index, item in enumerate(graph, 1):
                if not isinstance(item, dict):
                    errors.append(
                        f"{prefix}: @graph member {index} must be an object"
                    )
                    continue
                errors.extend(
                    _validate_schema_object(
                        item,
                        block_num,
                        inherited_context=context_is_inherited,
                    )
                )

    return errors


def _resolve_filepath():
    """File path from argv (exec-form template) or the stdin hook-event JSON.

    Claude Code's documented hook contract delivers the event as JSON on stdin;
    the argv template is kept for harnesses that substitute it. Whichever yields
    an existing file wins.
    """
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        return sys.argv[1]
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw.strip():
                event = json.loads(raw)
                fp = (event.get("tool_input") or {}).get("file_path")
                if fp and os.path.isfile(fp):
                    return fp
    except (OSError, ValueError):
        pass
    return None


def main():
    _configure_utf8()
    filepath = _resolve_filepath()
    if not filepath:
        sys.exit(0)

    # Only validate HTML-like files
    valid_extensions = (".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".php", ".ejs")
    if not filepath.lower().endswith(valid_extensions):
        sys.exit(0)

    # File-size guard: skip files >10MB to bound memory + hook latency.
    # Real source files almost never exceed this; bigger inputs are typically
    # generated, minified bundles or accidental binary writes.
    MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MiB
    try:
        if os.path.getsize(filepath) > MAX_FILE_BYTES:
            sys.exit(0)
    except OSError:
        sys.exit(0)

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except (OSError, IOError):
        sys.exit(0)

    errors = validate_jsonld(content)

    if not errors:
        sys.exit(0)

    # Categorize errors
    critical_keywords = ["placeholder", "deprecated", "retired"]
    critical = [e for e in errors if any(kw in e.lower() for kw in critical_keywords)]
    warnings = [e for e in errors if e not in critical]

    if warnings:
        print("⚠️  Schema validation warnings:")
        for w in warnings:
            print(f"  - {w}")

    if critical:
        print("🛑 Schema validation ERRORS (blocking):")
        for e in critical:
            print(f"  - {e}")
        sys.exit(2)  # Block the edit

    sys.exit(1)  # Warnings only; proceed


if __name__ == "__main__":
    main()
