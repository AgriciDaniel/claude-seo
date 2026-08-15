"""Policy regression for the JSON-LD validation hook.

FAQPage must NOT block because it remains a valid Schema.org type, even though
Google retired its rich results in May 2026 and no AI or ranking benefit is
confirmed. Genuinely deprecated types must still block the edit (exit 2).
"""

from __future__ import annotations

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


def test_faqpage_not_blocked(tmp_path):
    assert _run(tmp_path, "FAQPage") == 0


def test_deprecated_type_still_blocks(tmp_path):
    assert _run(tmp_path, "ClaimReview") == 2


def _run_with_encoding(tmp_path: Path, schema_type: str, encoding: str):
    """Run the hook with a console encoding forced via PYTHONIOENCODING."""
    html = tmp_path / "page.html"
    html.write_text(
        '<html><head><script type="application/ld+json">\n'
        f'{{"@context":"https://schema.org","@type":"{schema_type}"}}\n'
        "</script></head></html>",
        encoding="utf-8",
    )
    env = dict(os.environ, PYTHONIOENCODING=encoding)
    return subprocess.run(
        [sys.executable, str(HOOK), str(html)],
        capture_output=True,
        text=True,
        env=env,
    )


def test_blocking_finding_survives_a_cp1252_console(tmp_path):
    """A non-UTF-8 console must not turn a blocking finding into a crash.

    The banners contain non-ASCII markers. Encoding them to cp1252 raised
    UnicodeEncodeError *before* sys.exit(2) ran, so the hook died with exit 1 —
    which the harness reads as "warnings only, proceed". The deprecated type was
    therefore silently non-blocking on Windows, not merely ugly (issue #186).
    """
    result = _run_with_encoding(tmp_path, "ClaimReview", "cp1252")
    assert result.returncode == 2, (
        f"blocking exit code lost on a cp1252 console: {result.stderr}"
    )
    assert "UnicodeEncodeError" not in result.stderr
    assert "ClaimReview" in result.stdout


def test_clean_schema_still_passes_on_a_cp1252_console(tmp_path):
    assert _run_with_encoding(tmp_path, "FAQPage", "cp1252").returncode == 0
