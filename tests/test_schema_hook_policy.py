"""Policy regression for the JSON-LD validation hook.

FAQPage must NOT block because it remains a valid Schema.org type, even though
Google retired its rich results in May 2026 and no AI or ranking benefit is
confirmed. Genuinely deprecated types must still block the edit (exit 2).
"""

from __future__ import annotations

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


def test_faqpage_not_blocked(tmp_path):
    assert _run(tmp_path, "FAQPage") == 0


def test_deprecated_type_still_blocks(tmp_path):
    assert _run(tmp_path, "ClaimReview") == 2


def test_replacement_text_is_not_treated_as_placeholder(tmp_path):
    assert _run(tmp_path, "Product", ',"description":"Replacement coils"') == 0


def test_standalone_replace_still_blocks(tmp_path):
    assert _run(tmp_path, "Product", ',"description":"REPLACE"') == 2


def test_replace_verb_is_not_treated_as_placeholder(tmp_path):
    assert _run(tmp_path, "Product", ',"description":"Replace the cartridge every 6 months"') == 0


def test_underscore_replace_placeholder_still_blocks(tmp_path):
    assert _run(tmp_path, "Product", ',"description":"REPLACE_WITH_URL"') == 2
