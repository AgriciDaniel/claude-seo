"""Repeated shipping/return policy objects need the same checks as singletons."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from schema_ecommerce_validate import validate  # noqa: E402


@pytest.mark.parametrize(("property_name", "kind", "missing_rule"), [
    ("hasMerchantReturnPolicy", "MerchantReturnPolicy", "return-policy-applicableCountry"),
    ("shippingDetails", "OfferShippingDetails", "shipping-shippingDestination"),
])
@pytest.mark.parametrize("on_offer", [False, True])
def test_each_policy_in_a_list_is_validated(property_name, kind, missing_rule, on_offer):
    product = {"@type": "Product", "name": "Book", "image": "book.jpg", "offers": {"@type": "Offer"}}
    target = product["offers"] if on_offer else product
    target[property_name] = [{"@type": kind}]
    result = validate(product)
    assert any(f["rule"] == missing_rule for f in result["findings"])


def test_complete_policy_lists_do_not_get_missing_field_findings():
    product = {
        "@type": "Product", "name": "Book", "image": "book.jpg", "offers": {"@type": "Offer"},
        "hasMerchantReturnPolicy": [{"applicableCountry": "US", "returnPolicyCategory": "MerchantReturnNotPermitted"}],
        "shippingDetails": [{"shippingDestination": {"addressCountry": "US"}, "deliveryTime": {"@type": "ShippingDeliveryTime"}}],
    }
    result = validate(product)
    assert not any(f["rule"].startswith(("return-policy-", "shipping-")) for f in result["findings"])
