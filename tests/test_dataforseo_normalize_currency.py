"""
Tests for scripts/dataforseo_normalize.py: _normalize_currency symbol mapping.

_normalize_currency documents itself as "Normalize currency to ISO 4217 code"
and comments "Handle common symbols". It mapped the dollar sign "$" -> "USD",
but the other symbol_map entries were ISO codes mapping to themselves
("EUR" -> "EUR"), which are no-ops already covered by the fallback. The common
currency symbols the comment promises to handle -- "EUR" sign, "GBP" sign,
"JPY/CNY" sign -- fell through to the `text[:3] if len >= 3 else "USD"` branch.
Because each is a single character, len < 3, so they silently became "USD":
a Euro- or Pound-priced product was reported in US dollars.
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import dataforseo_normalize  # noqa: E402


def test_dollar_symbol_maps_to_usd():
    # Baseline behaviour that already worked, kept as a guard.
    assert dataforseo_normalize._normalize_currency("$") == "USD"


def test_euro_symbol_maps_to_eur():
    assert dataforseo_normalize._normalize_currency("€") == "EUR"


def test_pound_symbol_maps_to_gbp():
    assert dataforseo_normalize._normalize_currency("£") == "GBP"


def test_iso_codes_pass_through_unchanged():
    assert dataforseo_normalize._normalize_currency("EUR") == "EUR"
    assert dataforseo_normalize._normalize_currency("gbp") == "GBP"
    assert dataforseo_normalize._normalize_currency("usd") == "USD"


def test_empty_defaults_to_usd():
    assert dataforseo_normalize._normalize_currency("") == "USD"
    assert dataforseo_normalize._normalize_currency(None) == "USD"
