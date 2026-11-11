"""Merchant API structured price/rating objects retain numeric product data."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dataforseo_normalize import normalize_merchant  # noqa: E402


def test_structured_price_currency_and_rating_votes():
    item = {"title": "Example", "price": {"current": 108.25, "regular": 125, "currency": "EUR"},
            "rating": {"value": "4.36", "votes_count": 24805}}
    result = normalize_merchant([item])[0]
    assert result["price"] == 108.25
    assert result["currency"] == "EUR"
    assert result["rating"] == 4.4
    assert result["reviews_count"] == 24805


def test_zero_values_and_explicit_legacy_fields_take_precedence():
    item = {"price": {"current": 0, "currency": "EUR"}, "currency": "GBP",
            "rating": {"value": 0, "rating_value": 5, "votes_count": 10}, "reviews_count": 0}
    result = normalize_merchant([item])[0]
    assert result["price"] == 0
    assert result["currency"] == "GBP"
    assert result["rating"] == 0
    assert result["reviews_count"] == 0


@pytest.mark.parametrize(("price", "expected"), [(12.5, 12.5), ("$1,299.50", 1299.5),
                                                 ({"current": None, "regular": 20}, None)])
def test_scalar_prices_and_unavailable_current_price(price, expected):
    assert normalize_merchant([{"price": price}])[0]["price"] == expected
