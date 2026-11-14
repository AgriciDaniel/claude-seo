"""Schema.org type IRIs are valid JSON-LD @type values."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from schema_ecommerce_validate import validate  # noqa: E402


@pytest.mark.parametrize("namespace", ["http://schema.org/", "https://schema.org/"])
@pytest.mark.parametrize("as_list", [False, True])
def test_expanded_product_and_offer_types(namespace, as_list):
    def kind(name):
        value = namespace + name
        return ["https://example.com/Custom", value] if as_list else value

    product = {"@type": kind("Product"), "name": "Test product", "image": "image.jpg",
               "offers": {"@type": kind("Offer"), "price": 12, "priceCurrency": "USD"}}
    result = validate(product)
    assert not any(f["rule"] in {"missing-product", "merchant-listing-offer-type"}
                   for f in result["findings"])


def test_expanded_types_keep_special_type_checks():
    product = {"@type": "https://schema.org/Product", "name": "Test", "image": "image.jpg",
               "offers": {"@type": "https://schema.org/AggregateOffer"},
               "subjectOf": {"@type": "https://schema.org/ClaimReview"}}
    rules = {f["rule"] for f in validate(product)["findings"]}
    assert "merchant-listing-offer-type" in rules
    assert "deprecated-type" in rules


@pytest.mark.parametrize("kind", ["https://example.com/Product", "https://schema.org/Product/Other",
                                 "https://schema.org/http://schema.org/Product"])
def test_other_namespaces_and_paths_are_not_schema_product(kind):
    assert "missing-product" in {f["rule"] for f in validate({"@type": kind})["findings"]}
