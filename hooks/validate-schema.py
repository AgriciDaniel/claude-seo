#!/usr/bin/env python3
"""Post-edit schema validation hook for Claude Code.

Validates JSON-LD schema after file edits. The file is already written when
a PostToolUse hook runs, so nothing here can undo the edit; the hook makes
sure Claude reads what is wrong:

- critical errors (placeholders, deprecated or retired types): exit 2, with
  the errors on stderr, which Claude Code feeds back to Claude;
- warnings only: exit 0, with the warnings as hookSpecificOutput
  additionalContext JSON on stdout, which Claude reads without an error
  notice (exit 1 would show them to the user only).

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

# Match every <script ...>...</script> pair, then filter on the type attribute.
# The previous pattern required ``type`` to be the first and only attribute, so
# blocks carrying a CSP ``nonce``, an ``id`` or ``data-*`` attributes, or an
# unquoted type value were skipped without validation.
#
# The attribute group is a small tokenizer, not a plain ``[^>]*``: it consumes a
# double-quoted value, a single-quoted value, or a run of characters that is
# neither a quote nor ``>``. A ``[^>]*`` scan ends the tag at the first ``>`` it
# sees, quoted or not, so an attribute value containing ``>`` (``data-cond="a>b"``,
# a templated nonce) truncated the tag early and fed the remainder of the
# attributes plus the real body to the JSON parser as garbage. Treating a quoted
# span as atomic keeps an embedded ``>`` from ending the tag prematurely.
# The fallback class excludes both quote characters: if it matched an
# apostrophe, the alternation would be ambiguous and a tag with many
# apostrophes and no closing tag would backtrack exponentially, hanging the
# blocking hook.
_ATTRS_RE = r'(?:"[^"]*"|\'[^\']*\'|[^"\'>])*'
SCRIPT_TAG_RE = re.compile(
    r"<script\b(" + _ATTRS_RE + r")>(.*?)</script\s*>", re.DOTALL | re.IGNORECASE
)
LD_JSON_TYPE_RE = re.compile(
    r"""(?:^|\s)type\s*=\s*"""
    r"""(?:"application/ld\+json"|'application/ld\+json'|application/ld\+json(?=\s|$))""",
    re.IGNORECASE,
)

# Server- or client-side template expressions that render JSON-LD at runtime.
# The hook runs on .jsx/.tsx/.vue/.svelte/.php/.ejs sources, where the script
# body is frequently an expression rather than literal JSON. Those blocks cannot
# be validated statically and must not be reported as invalid JSON.
SERVER_TEMPLATE_RE = re.compile(
    r"""^(?:
        <\?(?:php\b|=)            # <?php ... ?> / <?= ... ?>
      | <%                        # EJS / ERB
    )""",
    re.VERBOSE,
)
COMPONENT_EXPRESSION_RE = re.compile(
    r"""^(?:
        \{\{                      # Vue / Handlebars / Twig
      | \{@html\b                 # Svelte
      | \$\{                      # JS template literal
      | \{\s*[A-Za-z_$][\w$.]*    # JSX expression: {schema} / {JSON.stringify(...)}
    )""",
    re.VERBOSE,
)
COMPONENT_EXTENSIONS = (".jsx", ".tsx", ".vue", ".svelte")

SCHEMA_ORG_CONTEXTS = frozenset(
    {"https://schema.org", "http://schema.org", "https://schema.org/", "http://schema.org/"}
)


def _configure_utf8() -> None:
    """Keep hook diagnostics printable on legacy Windows console encodings."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def _extract_ld_json_blocks(content: str) -> List[str]:
    """Return the bodies of every ``<script type="application/ld+json">`` block.

    Attribute order, extra attributes (``nonce``, ``id``, ``data-*``), tag case
    and unquoted type values are all accepted; only the type value is decisive.
    """
    blocks = []
    for attributes, body in SCRIPT_TAG_RE.findall(content):
        if LD_JSON_TYPE_RE.search(attributes):
            blocks.append(body)
    return blocks


def _is_template_expression(block: str, filepath: str = "") -> bool:
    """True when the script body is rendered at runtime rather than literal JSON.

    Server-side markers (PHP, EJS) are never valid JSON and are skipped for
    every file type. Component expressions (JSX, Vue, Svelte, template
    literals) are only skipped in component sources, so a malformed object
    literal in a plain ``.html`` file is still reported.
    """
    if SERVER_TEMPLATE_RE.match(block):
        return True
    if filepath.lower().endswith(COMPONENT_EXTENSIONS):
        return bool(COMPONENT_EXPRESSION_RE.match(block))
    return False


def _is_schema_org_context(value: Any) -> bool:
    """Accept the schema.org context in its string, list and object forms."""
    if isinstance(value, str):
        return value in SCHEMA_ORG_CONTEXTS
    if isinstance(value, list):
        return any(_is_schema_org_context(item) for item in value)
    if isinstance(value, dict):
        return _is_schema_org_context(value.get("@vocab"))
    return False


def validate_jsonld(content: str, filepath: str = "") -> List[str]:
    """Validate JSON-LD blocks in HTML content."""
    errors = []
    blocks = _extract_ld_json_blocks(content)

    if not blocks:
        return []  # No schema found; not an error

    for i, block in enumerate(blocks, 1):
        block = block.strip()
        if _is_template_expression(block, filepath):
            continue  # Rendered at runtime; nothing to validate statically
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
    elif "@context" in obj and not _is_schema_org_context(obj["@context"]):
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

    errors = validate_jsonld(content, filepath)

    if not errors:
        sys.exit(0)

    # Categorize errors
    critical_keywords = ["placeholder", "deprecated", "retired"]
    critical = [e for e in errors if any(kw in e.lower() for kw in critical_keywords)]
    warnings = [e for e in errors if e not in critical]

    if critical:
        # Exit 2: Claude Code feeds stderr back to Claude (stdout is ignored).
        print("🛑 Schema validation ERRORS (flagged for Claude, fix before shipping):", file=sys.stderr)
        for e in critical:
            print(f"  - {e}", file=sys.stderr)
        if warnings:
            print("⚠️  Also warnings:", file=sys.stderr)
            for w in warnings:
                print(f"  - {w}", file=sys.stderr)
        sys.exit(2)

    # Warnings only: exit 0 with JSON, so Claude reads them as context.
    context = "Schema validation warnings for " + filepath + ":\n" + "\n".join(f"- {w}" for w in warnings)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}))
    sys.exit(0)


if __name__ == "__main__":
    main()
