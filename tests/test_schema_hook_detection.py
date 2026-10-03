"""Block detection regressions for the JSON-LD validation hook.

Two failure classes are covered:

1. False negatives. The hook must find every ``application/ld+json`` block,
   whatever the attribute order, the presence of a CSP ``nonce`` or ``id``,
   the quoting of the type value or the case of the tag. A missed block means
   a placeholder or a retired type reaches production unnoticed.
2. False positives. Component and server templates render JSON-LD at runtime.
   Their script bodies are expressions, not JSON, and must not be reported as
   invalid on every edit. A malformed literal in plain HTML is still reported.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "validate-schema.py"

RETIRED = '{"@context":"https://schema.org","@type":"ClaimReview"}'
PLACEHOLDER = '{"@context":"https://schema.org","@type":"LocalBusiness","name":"[Business Name]"}'
VALID = '{"@context":"https://schema.org","@type":"Organization","name":"Example"}'


def _run(tmp_path: Path, filename: str, head: str) -> subprocess.CompletedProcess:
    target = tmp_path / filename
    target.write_text(f"<html><head>{head}</head><body></body></html>", encoding="utf-8")
    # The hook prints emoji markers as UTF-8; decode explicitly, because on
    # Windows text=True uses cp1252 and a decode error inside the pipe reader
    # thread leaves stderr as None.
    return subprocess.run(
        [sys.executable, str(HOOK), str(target)],
        capture_output=True, encoding="utf-8", errors="replace",
    )


def _warnings(result: subprocess.CompletedProcess) -> str:
    """The warnings a warnings-only run hands Claude: exit 0, JSON additionalContext on stdout."""
    if result.returncode != 0 or not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


def _clean(result: subprocess.CompletedProcess) -> bool:
    """Nothing to report: exit 0 and nothing on either stream."""
    return result.returncode == 0 and result.stdout == "" and result.stderr == ""


# --- false negatives -------------------------------------------------------


def test_block_with_csp_nonce_is_validated(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        "page.html",
        f'<script type="application/ld+json" nonce="r4nd0m">{PLACEHOLDER}</script>',
    )
    assert result.returncode == 2
    assert "[Business Name]" in result.stderr


def test_attribute_before_type_is_validated(tmp_path: Path) -> None:
    result = _run(
        tmp_path, "page.html", f'<script id="schema" type="application/ld+json">{RETIRED}</script>'
    )
    assert result.returncode == 2
    assert "ClaimReview" in result.stderr


def test_unquoted_type_value_is_validated(tmp_path: Path) -> None:
    result = _run(tmp_path, "page.html", f"<script type=application/ld+json>{RETIRED}</script>")
    assert result.returncode == 2


def test_uppercase_tag_and_attribute_are_validated(tmp_path: Path) -> None:
    result = _run(tmp_path, "page.html", f'<SCRIPT TYPE="application/ld+json">{RETIRED}</SCRIPT>')
    assert result.returncode == 2


def test_other_script_types_are_ignored(tmp_path: Path) -> None:
    head = f'<script type="module">{RETIRED}</script><script type="text/javascript">var x = {RETIRED};</script>'
    assert _clean(_run(tmp_path, "page.html", head))


def test_valid_block_with_extra_attributes_passes(tmp_path: Path) -> None:
    head = f'<script data-testid="ld" type="application/ld+json" nonce="abc">{VALID}</script>'
    assert _clean(_run(tmp_path, "page.html", head))


# --- false positives on templates -------------------------------------------


def test_jsx_expression_body_is_not_reported(tmp_path: Path) -> None:
    head = '<script type="application/ld+json">{JSON.stringify(schema)}</script>'
    result = _run(tmp_path, "page.tsx", head)
    assert _clean(result)


def test_jsx_identifier_body_is_not_reported(tmp_path: Path) -> None:
    result = _run(tmp_path, "Page.jsx", '<script type="application/ld+json">{jsonLd}</script>')
    assert _clean(result)


def test_vue_mustache_body_is_not_reported(tmp_path: Path) -> None:
    result = _run(tmp_path, "Page.vue", '<script type="application/ld+json">{{ jsonLd }}</script>')
    assert _clean(result)


def test_svelte_html_body_is_not_reported(tmp_path: Path) -> None:
    head = '<script type="application/ld+json">{@html JSON.stringify(schema)}</script>'
    assert _clean(_run(tmp_path, "Page.svelte", head))


def test_php_echo_body_is_not_reported(tmp_path: Path) -> None:
    head = '<script type="application/ld+json"><?php echo json_encode($schema); ?></script>'
    assert _clean(_run(tmp_path, "page.php", head))


def test_ejs_body_is_not_reported(tmp_path: Path) -> None:
    head = '<script type="application/ld+json"><%- JSON.stringify(schema) %></script>'
    assert _clean(_run(tmp_path, "page.ejs", head))


def test_literal_json_in_component_file_is_still_validated(tmp_path: Path) -> None:
    result = _run(tmp_path, "Page.tsx", f'<script type="application/ld+json">{RETIRED}</script>')
    assert result.returncode == 2


def test_malformed_object_literal_in_html_is_still_reported(tmp_path: Path) -> None:
    result = _run(
        tmp_path, "page.html", '<script type="application/ld+json">{name: "unquoted"}</script>'
    )
    assert "Invalid JSON" in _warnings(result)


# --- @context forms ---------------------------------------------------------


def test_context_with_trailing_slash_is_accepted(tmp_path: Path) -> None:
    head = '<script type="application/ld+json">{"@context":"https://schema.org/","@type":"Organization","name":"X"}</script>'
    result = _run(tmp_path, "page.html", head)
    assert _clean(result)


def test_context_object_with_schema_vocab_is_accepted(tmp_path: Path) -> None:
    head = (
        '<script type="application/ld+json">'
        '{"@context":{"@vocab":"https://schema.org/"},"@type":"Organization","name":"X"}'
        "</script>"
    )
    assert _clean(_run(tmp_path, "page.html", head))


def test_context_list_containing_schema_org_is_accepted(tmp_path: Path) -> None:
    head = (
        '<script type="application/ld+json">'
        '{"@context":["https://schema.org",{"ex":"https://example.com/ns#"}],"@type":"Organization","name":"X"}'
        "</script>"
    )
    assert _clean(_run(tmp_path, "page.html", head))


def test_foreign_context_is_still_reported(tmp_path: Path) -> None:
    head = '<script type="application/ld+json">{"@context":"https://example.com/ns","@type":"Organization"}</script>'
    result = _run(tmp_path, "page.html", head)
    assert "@context should be" in _warnings(result)


# --- tokenizer regressions (a quoted attribute value may contain ">") ------


def test_two_plain_ldjson_blocks_are_both_detected(tmp_path: Path) -> None:
    head = (
        f'<script type="application/ld+json">{VALID}</script>'
        f'<script type="application/ld+json">{RETIRED}</script>'
    )
    result = _run(tmp_path, "page.html", head)
    assert result.returncode == 2
    assert "Block 2" in result.stderr
    assert "ClaimReview" in result.stderr


def test_block_with_nonce_and_id_is_validated(tmp_path: Path) -> None:
    head = f'<script id="ld-schema" type="application/ld+json" nonce="r4nd0m">{RETIRED}</script>'
    result = _run(tmp_path, "page.html", head)
    assert result.returncode == 2
    assert "ClaimReview" in result.stderr


def test_attribute_value_containing_angle_bracket_is_detected(tmp_path: Path) -> None:
    """A ``[^>]*`` attribute scan ends the tag at the embedded ">", truncating
    the real JSON-LD body. At the pre-tokenizer PR head this exited 1 (Invalid
    JSON) instead of recognizing and validating the block.
    """
    head = f'<script type="application/ld+json" data-cond="a>b">{VALID}</script>'
    result = _run(tmp_path, "page.html", head)
    assert _clean(result)


def test_jsx_json_stringify_inside_ldjson_script_is_not_flagged(tmp_path: Path) -> None:
    head = '<script type="application/ld+json">{JSON.stringify(schema)}</script>'
    result = _run(tmp_path, "page.jsx", head)
    assert _clean(result)


def test_renal_replacement_therapy_string_is_not_flagged(tmp_path: Path) -> None:
    head = (
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"MedicalTherapy",'
        '"name":"Renal replacement therapy"}'
        "</script>"
    )
    result = _run(tmp_path, "page.html", head)
    assert _clean(result)


def test_top_level_graph_is_detected(tmp_path: Path) -> None:
    head = (
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@graph":['
        '{"@type":"Organization","name":"X"},'
        f"{RETIRED}"
        "]}"
        "</script>"
    )
    result = _run(tmp_path, "page.html", head)
    assert result.returncode == 2
    assert "ClaimReview" in result.stderr


def test_blocking_message_goes_to_stderr_not_stdout(tmp_path: Path) -> None:
    # Claude Code feeds a PostToolUse hook's stderr back to Claude on exit 2 and
    # ignores its stdout, so a blocking reason printed to stdout never arrives.
    result = _run(
        tmp_path,
        "page.html",
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"LocalBusiness","name":"[Business Name]"}'
        "</script>",
    )
    assert result.returncode == 2
    assert "[Business Name]" in result.stderr
    assert result.stdout == ""
