"""Policy regression for the JSON-LD validation hook.

FAQPage must NOT block because it remains a valid Schema.org type, even though
Google retired its rich results in May 2026 and no AI or ranking benefit is
confirmed. Genuinely deprecated types must still block the edit (exit 2).

A node may also declare several types ("@type": ["LocalBusiness",
"FinancialService"]). Every type is checked on its own, and a node that lists
one retired type among several still blocks.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "validate-schema.py"


def _run(tmp_path: Path, schema_type: str, extra: str = "") -> int:
    """2 for critical errors, 1 when warnings were handed to Claude, 0 when clean."""
    html = tmp_path / "page.html"
    html.write_text(
        '<html><head><script type="application/ld+json">\n'
        f'{{"@context":"https://schema.org","@type":"{schema_type}"{extra}}}\n'
        "</script></head></html>",
        encoding="utf-8",
    )
    result = subprocess.run([sys.executable, str(HOOK), str(html)], capture_output=True, encoding="utf-8")
    return 1 if result.returncode == 0 and result.stdout.strip() else result.returncode


def _run_payload(tmp_path: Path, payload: object, **kwargs: object) -> subprocess.CompletedProcess:
    html = tmp_path / "payload.html"
    html.write_text(
        '<html><head><script type="application/ld+json">'
        + json.dumps(payload, ensure_ascii=False)
        + "</script></head></html>",
        encoding="utf-8",
    )
    return subprocess.run([sys.executable, str(HOOK), str(html)], **kwargs)


def _warnings(result: subprocess.CompletedProcess) -> str:
    """The warnings a warnings-only run hands Claude: exit 0, JSON additionalContext on stdout."""
    if result.returncode != 0 or not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


def _clean(result: subprocess.CompletedProcess) -> bool:
    """Nothing to report: exit 0 and nothing on either stream."""
    return result.returncode == 0 and result.stdout == "" and result.stderr == ""


def test_faqpage_not_blocked(tmp_path):
    assert _run(tmp_path, "FAQPage") == 0


def test_deprecated_type_still_blocks(tmp_path):
    assert _run(tmp_path, "ClaimReview") == 2


def test_multiple_types_are_validated_like_a_single_type(tmp_path: Path) -> None:
    # A list-valued @type used to crash the hook with
    # "TypeError: cannot use 'list' as a dict key", which lost every finding
    # for the file. The node has to validate like a single-typed one.
    payload = {
        "@context": "https://schema.org",
        "@type": ["LocalBusiness", "FinancialService"],
        "name": "Example Advisory",
    }
    assert _clean(_run_payload(tmp_path, payload, capture_output=True, encoding="utf-8"))


def test_deprecated_type_inside_a_type_list_still_blocks(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@type": ["HowTo", "Article"],
    }
    result = _run_payload(tmp_path, payload, capture_output=True, encoding="utf-8")
    assert result.returncode == 2
    assert "Block 1: @type 'HowTo' is deprecated September 2023" in result.stderr


def test_non_string_type_entries_do_not_crash(tmp_path: Path) -> None:
    # A @type that is not a string cannot name a type; it must be ignored
    # instead of crashing the membership check the way a list did.
    payload = {
        "@context": "https://schema.org",
        "@type": [{"name": "Organization"}, 42, None],
    }
    assert _clean(_run_payload(tmp_path, payload, capture_output=True, encoding="utf-8"))


def test_valid_top_level_graph_does_not_require_container_type(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "name": "Example"},
            {"@type": "WebSite", "name": "Example"},
        ],
    }
    assert _clean(_run_payload(tmp_path, payload, capture_output=True, encoding="utf-8"))


def test_graph_members_inherit_context_but_still_require_type(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": [{"name": "Missing type"}],
    }
    # The hook forces UTF-8 on its own stdout (_configure_utf8); decode with the
    # same codec, not the locale default, which is cp1252 on Windows and cannot
    # represent the emoji markers.
    result = _run_payload(tmp_path, payload, capture_output=True, encoding="utf-8")
    assert "Missing @type" in _warnings(result)
    assert "Missing @context" not in _warnings(result)


def test_deprecated_graph_member_still_blocks(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": [{"@type": "ClaimReview", "name": "Old markup"}],
    }
    assert _run_payload(tmp_path, payload).returncode == 2


def test_deprecated_type_inside_a_graph_member_type_list_blocks(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": [{"@type": ["LocalBusiness", "ClaimReview"], "name": "Old markup"}],
    }
    result = _run_payload(tmp_path, payload, capture_output=True, encoding="utf-8")
    assert result.returncode == 2
    assert "ClaimReview" in result.stderr


def test_non_object_graph_members_are_reported_without_crashing(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": ["not-a-node", 42],
    }
    result = _run_payload(tmp_path, payload, capture_output=True, encoding="utf-8")
    assert "@graph member 1 must be an object" in _warnings(result)
    assert "@graph member 2 must be an object" in _warnings(result)


def test_graph_must_be_a_list(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": {"@type": "Organization"},
    }
    result = _run_payload(tmp_path, payload, capture_output=True, encoding="utf-8")
    assert "@graph must be a list" in _warnings(result)


def test_replace_placeholder_matches_tokens_not_normal_words(tmp_path: Path) -> None:
    safe = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Replacement coils",
        "description": "Replace the filter yearly",
    }
    assert _clean(_run_payload(tmp_path, safe, capture_output=True, encoding="utf-8"))

    for value in ("REPLACE", "REPLACE_TITLE"):
        blocked = {**safe, "name": value}
        assert _run_payload(tmp_path, blocked).returncode == 2


def test_hook_diagnostics_do_not_crash_under_cp1252(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@type": "ClaimReview",
        "name": "Crème brûlée",
    }
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    result = _run_payload(tmp_path, payload, env=env, capture_output=True)
    assert result.returncode == 2
    assert b"UnicodeEncodeError" not in result.stderr
