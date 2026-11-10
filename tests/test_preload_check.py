"""
Tests for scripts/preload_check.py — the Speculation Rules / preload auditor.

Regression coverage for non-object speculationrules bodies: ``json.loads``
accepts a bare array, string, or ``null`` (all valid JSON), so the
``JSONDecodeError`` guard does not catch them. Before the fix,
``_extract_speculation_actions`` then called ``.get()`` on a non-dict and
raised ``AttributeError``, which propagated through ``analyse`` and crashed
the whole audit on an otherwise-fetchable page.
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import preload_check  # noqa: E402


def test_non_object_speculationrules_body_yields_no_actions() -> None:
    # Valid JSON that is not an object: array, null, string, number.
    for body in ('[{"source": "list", "urls": ["/next"]}]', "null", '"x"', "123"):
        assert preload_check._extract_speculation_actions(body) == [], body


def test_object_speculationrules_body_still_extracts_actions() -> None:
    body = '{"prefetch": [{"source": "list", "urls": ["/a"]}]}'
    assert preload_check._extract_speculation_actions(body) == ["prefetch"]


def test_analyse_does_not_crash_on_array_speculationrules_block() -> None:
    html = (
        '<html><head><script type="speculationrules">'
        '[{"source": "list", "urls": ["/next"]}]'
        "</script></head><body></body></html>"
    )
    # Must not raise; the block contributes no actions.
    result = preload_check.analyse(html)
    assert result["speculation_rules"]["actions"] == []
