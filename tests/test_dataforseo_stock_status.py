"""Preserve the Merchant API's documented product_availability values."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dataforseo_merchant import _normalize_product, _normalize_seller  # noqa: E402
from dataforseo_normalize import _normalize_availability, normalize_merchant  # noqa: E402


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


NEGATIVE_LABELS = [
    "Not in stock",
    "not_in_stock",
    "NOT IN STOCK",
    "No longer in stock",
    "Not currently in stock",
    "Out of stock",
    "out-of-stock",
    "Temporarily out of stock",
    "https://schema.org/OutOfStock",
    "Unavailable",
    "Currently unavailable",
    "Not available",
    "Sold out",
]


@pytest.mark.parametrize("raw", NEGATIVE_LABELS)
def test_negative_labels_never_read_as_in_stock(raw, normalize_product):
    assert _normalize_availability(raw) == "out_of_stock"
    assert normalize_product({"availability": raw})["availability"] == "out_of_stock"
    assert normalize_product({"product_availability": raw})["availability"] == "out_of_stock"
    assert _normalize_seller({"product_availability": raw})["availability"] == "out_of_stock"


@pytest.mark.parametrize(("raw", "expected"), [
    ("In Stock", "in_stock"),
    ("Only 3 left in stock", "in_stock"),
    ("https://schema.org/InStock", "in_stock"),
    ("pre_order_available", "preorder"),
    ("Pre order", "preorder"),
    ("Ships in 2 days", "unknown"),
])
def test_positive_and_unrecognised_labels(raw, expected):
    assert _normalize_availability(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("in_stock", "in_stock"),
    ("limited_stock", "limited_stock"),
    ("out_of_stock", "out_of_stock"),
    ("backordered", "backordered"),
    ("pre_order_available", "preorder"),
    ("on_display_to_order", "on_display_to_order"),
])
def test_seller_items_keep_native_product_availability(raw, expected):
    seller = _normalize_seller({"seller_name": "Example shop", "product_availability": raw})
    assert seller["availability"] == expected


def test_seller_availability_fallbacks_match_the_product_normaliser():
    assert _normalize_seller({})["availability"] == "unknown"
    assert _normalize_seller({"availability": "Out of stock"})["availability"] == "out_of_stock"
    both = {"availability": "out_of_stock", "product_availability": "in_stock"}
    assert _normalize_seller(both)["availability"] == "out_of_stock"


def test_seller_normalisation_keeps_its_existing_keys():
    seller = _normalize_seller({
        "seller_name": "Example shop",
        "seller_rating": 4.56,
        "seller_reviews_count": "12",
        "price": "$1,299.50",
        "delivery_info": "Free delivery",
        "url": "https://shop.example/item",
        "product_availability": "in_stock",
    })
    assert seller == {
        "seller_name": "Example shop",
        "seller_rating": 4.6,
        "seller_reviews_count": 12,
        "price": 1299.5,
        "delivery_info": "Free delivery",
        "url": "https://shop.example/item",
        "availability": "in_stock",
    }
