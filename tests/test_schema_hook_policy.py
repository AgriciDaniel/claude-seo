"""Policy regression for the JSON-LD validation hook.

FAQPage must NOT block because it remains a valid Schema.org type, even though
Google retired its rich results in May 2026 and no AI or ranking benefit is
confirmed. Genuinely deprecated types must still block the edit (exit 2).
"""

from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "validate-schema.py"
VALIDATE_JSONLD = runpy.run_path(str(HOOK))["validate_jsonld"]


def _html(schema: str) -> str:
    return f'<script type="application/ld+json">{schema}</script>'


def _run(tmp_path: Path, schema_type: str, extra: str = "") -> int:
    html = tmp_path / "page.html"
    html.write_text(
        '<html><head><script type="application/ld+json">\n'
        f'{{"@context":"https://schema.org","@type":"{schema_type}"{extra}}}\n'
        "</script></head></html>",
        encoding="utf-8",
    )
    return subprocess.run([sys.executable, str(HOOK), str(html)]).returncode


def test_faqpage_not_blocked(tmp_path):
    assert _run(tmp_path, "FAQPage") == 0


def test_deprecated_type_still_blocks(tmp_path):
    assert _run(tmp_path, "ClaimReview") == 2


def test_graph_container_and_members_are_validated_in_context():
    assert VALIDATE_JSONLD(
        _html(
            '{"@context":"https://schema.org","@graph":['
            '{"@type":"MedicalBusiness","name":"Clinic"},'
            '{"@type":"Physician","name":"Doctor"}'
            "]}"
        )
    ) == []


def test_graph_members_are_checked():
    assert VALIDATE_JSONLD(
        _html('{"@context":"https://schema.org","@graph":[{"@type":"ClaimReview"}]}')
    ) == [
        "Block 1: @type 'ClaimReview' is retired June 2025; fact-check rich results discontinued"
    ]


def test_non_graph_context_validation_is_preserved():
    assert VALIDATE_JSONLD(_html('{"@type":"Organization"}')) == [
        "Block 1: Missing @context"
    ]
    assert VALIDATE_JSONLD(
        _html('{"@context":"https://example.com","@type":"Organization"}')
    ) == ["Block 1: @context should be 'https://schema.org'"]
    assert VALIDATE_JSONLD(
        _html('{"@context":"https://schema.org","@type":"Organization"}')
    ) == []
