"""Policy regression for the JSON-LD validation hook.

FAQPage must NOT block because it remains a valid Schema.org type, even though
Google retired its rich results in May 2026 and no AI or ranking benefit is
confirmed. Genuinely deprecated types must still block the edit (exit 2).
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
    html = tmp_path / "page.html"
    html.write_text(
        '<html><head><script type="application/ld+json">\n'
        f'{{"@context":"https://schema.org","@type":"{schema_type}"{extra}}}\n'
        "</script></head></html>",
        encoding="utf-8",
    )
    return subprocess.run([sys.executable, str(HOOK), str(html)]).returncode


def _run_payload(tmp_path: Path, payload: object, **kwargs: object) -> subprocess.CompletedProcess:
    html = tmp_path / "payload.html"
    html.write_text(
        '<html><head><script type="application/ld+json">'
        + json.dumps(payload, ensure_ascii=False)
        + "</script></head></html>",
        encoding="utf-8",
    )
    return subprocess.run([sys.executable, str(HOOK), str(html)], **kwargs)


def test_faqpage_not_blocked(tmp_path):
    assert _run(tmp_path, "FAQPage") == 0


def test_deprecated_type_still_blocks(tmp_path):
    assert _run(tmp_path, "ClaimReview") == 2


def test_valid_top_level_graph_does_not_require_container_type(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "name": "Example"},
            {"@type": "WebSite", "name": "Example"},
        ],
    }
    assert _run_payload(tmp_path, payload).returncode == 0


def test_graph_members_inherit_context_but_still_require_type(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": [{"name": "Missing type"}],
    }
    result = _run_payload(tmp_path, payload, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Missing @type" in result.stdout
    assert "Missing @context" not in result.stdout


def test_deprecated_graph_member_still_blocks(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": [{"@type": "ClaimReview", "name": "Old markup"}],
    }
    assert _run_payload(tmp_path, payload).returncode == 2


def test_non_object_graph_members_are_reported_without_crashing(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": ["not-a-node", 42],
    }
    result = _run_payload(tmp_path, payload, capture_output=True, text=True)
    assert result.returncode == 1
    assert "@graph member 1 must be an object" in result.stdout
    assert "@graph member 2 must be an object" in result.stdout


def test_graph_must_be_a_list(tmp_path: Path) -> None:
    payload = {
        "@context": "https://schema.org",
        "@graph": {"@type": "Organization"},
    }
    result = _run_payload(tmp_path, payload, capture_output=True, text=True)
    assert result.returncode == 1
    assert "@graph must be a list" in result.stdout


def test_replace_placeholder_matches_tokens_not_normal_words(tmp_path: Path) -> None:
    safe = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Replacement coils",
        "description": "Replace the filter yearly",
    }
    assert _run_payload(tmp_path, safe).returncode == 0

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
