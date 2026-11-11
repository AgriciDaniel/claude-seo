"""Preserve the Merchant API's documented product_availability values."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dataforseo_normalize import normalize_merchant  # noqa: E402


@pytest.mark.parametrize(("raw", "expected"), [
    ("in_stock", "in_stock"),
    ("limited_stock", "limited_stock"),
    ("out_of_stock", "out_of_stock"),
    ("backordered", "backordered"),
    ("pre_order_available", "preorder"),
    ("on_display_to_order", "on_display_to_order"),
])
def test_native_merchant_stock_values(raw, expected):
    item = {"title": "Example product", "product_availability": raw}
    assert normalize_merchant([item])[0]["availability"] == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("In stock", "in_stock"),
    ("Out of stock", "out_of_stock"),
    ("Not in stock", "out_of_stock"),
    ("Pre-order", "preorder"),
    (None, "unknown"),
])
def test_legacy_availability_values(raw, expected):
    assert normalize_merchant([{"availability": raw}])[0]["availability"] == expected


def test_explicit_legacy_value_is_preserved_when_both_fields_exist():
    item = {"availability": "out_of_stock", "product_availability": "in_stock"}
    assert normalize_merchant([item])[0]["availability"] == "out_of_stock"
