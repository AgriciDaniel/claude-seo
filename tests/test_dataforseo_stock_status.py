"""Preserve the Merchant API's documented product_availability values."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dataforseo_merchant import _normalize_product  # noqa: E402
from dataforseo_normalize import normalize_merchant  # noqa: E402


@pytest.fixture(params=["normalizer", "merchant_cli"])
def normalize_product(request):
    if request.param == "normalizer":
        return lambda item: normalize_merchant([item])[0]
    return lambda item: _normalize_product(item, "google")


@pytest.mark.parametrize(("raw", "expected"), [
    ("in_stock", "in_stock"),
    ("limited_stock", "limited_stock"),
    ("out_of_stock", "out_of_stock"),
    ("backordered", "backordered"),
    ("pre_order_available", "preorder"),
    ("on_display_to_order", "on_display_to_order"),
])
def test_native_merchant_stock_values(raw, expected, normalize_product):
    item = {"title": "Example product", "product_availability": raw}
    assert normalize_product(item)["availability"] == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("In stock", "in_stock"),
    ("Out of stock", "out_of_stock"),
    ("Not in stock", "out_of_stock"),
    ("Pre-order", "preorder"),
    (None, "unknown"),
])
def test_legacy_availability_values(raw, expected, normalize_product):
    assert normalize_product({"availability": raw})["availability"] == expected


def test_explicit_legacy_value_is_preserved_when_both_fields_exist(normalize_product):
    item = {"availability": "out_of_stock", "product_availability": "in_stock"}
    assert normalize_product(item)["availability"] == "out_of_stock"
