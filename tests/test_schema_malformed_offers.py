"""A non-object offers value must not pass merchant-listing validation."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from schema_ecommerce_validate import validate  # noqa: E402


@pytest.mark.parametrize("offers", ["https://example.com/offer", 12, 0, True, False])
def test_scalar_offers_fail_validation(offers):
    result = validate({"@type": "Product", "name": "Book", "image": "book.jpg", "offers": offers})
    assert result["ok"] is False
    assert any(f["rule"] == "malformed-offer" and f["severity"] == "High"
               for f in result["findings"])


@pytest.mark.parametrize("offers", [{"@type": "Offer"}, [{"@type": "Offer"}]])
def test_offer_object_and_list_remain_supported(offers):
    result = validate({"@type": "Product", "name": "Book", "image": "book.jpg", "offers": offers})
    assert result["ok"] is True
