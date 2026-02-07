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
            "command": "python3 ~/.claude/skills/seo/hooks/validate-schema.py \"$FILE_PATH\"",
            "exitCodes": { "2": "block" }
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
import re
import sys
import os
from typing import List


def validate_jsonld(content: str) -> List[str]:
    """Validate JSON-LD blocks in HTML content."""
    errors = []
    pattern = r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>'
    blocks = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)

    if not blocks:
        return []  # No schema found — not an error

    for i, block in enumerate(blocks, 1):
        block = block.strip()
        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            errors.append(f"Block {i}: Invalid JSON — {e}")
            continue

        if isinstance(data, list):
            for item in data:
                errors.extend(_validate_schema_object(item, i))
        elif isinstance(data, dict):
            errors.extend(_validate_schema_object(data, i))

    return errors


def _validate_schema_object(obj: dict, block_num: int) -> List[str]:
    """Validate a single schema object."""
    errors = []
    prefix = f"Block {block_num}"

    # Check @context
    if "@context" not in obj:
        errors.append(f"{prefix}: Missing @context")
    elif obj["@context"] not in ("https://schema.org", "http://schema.org"):
        errors.append(f"{prefix}: @context should be 'https://schema.org'")

    # Check @type
    if "@type" not in obj:
        errors.append(f"{prefix}: Missing @type")

    # Check for placeholder text
    placeholders = [
        "[Business Name]",
        "[City]",
        "[State]",
        "[Phone]",
        "[Address]",
        "[Your",
        "[INSERT",
        "REPLACE",
        "[URL]",
        "[Email]",
    ]
    text = json.dumps(obj)
    for p in placeholders:
        if p.lower() in text.lower():
            errors.append(f"{prefix}: Contains placeholder text: {p}")

    # Check for deprecated types
    schema_type = obj.get("@type", "")
    deprecated = {
        "HowTo": "deprecated September 2023",
        "SpecialAnnouncement": "deprecated July 31, 2025",
        "CourseInfo": "retired June 2025",
        "EstimatedSalary": "retired June 2025",
        "LearningVideo": "retired June 2025",
    }
    if schema_type in deprecated:
        errors.append(f"{prefix}: @type '{schema_type}' is {deprecated[schema_type]}")

    # Check for restricted types used incorrectly
    restricted = {"FAQPage": "restricted to government and healthcare sites only (Aug 2023)"}
    if schema_type in restricted:
        errors.append(f"{prefix}: @type '{schema_type}' is {restricted[schema_type]} — verify site qualifies")

    return errors


def main():
    if len(sys.argv) < 2:
        sys.exit(0)

    filepath = sys.argv[1]

    if not os.path.isfile(filepath):
        sys.exit(0)

    # Only validate HTML-like files
    valid_extensions = (".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".php", ".ejs")
    if not filepath.endswith(valid_extensions):
        sys.exit(0)

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
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

    sys.exit(1)  # Warnings only — proceed


if __name__ == "__main__":
    main()
