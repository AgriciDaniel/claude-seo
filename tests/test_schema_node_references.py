"""Local JSON-LD node references should validate like their inline values."""

import copy
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import schema_ecommerce_validate as schema  # noqa: E402


def product(offer):
    return {"@type": "Product", "name": "Example", "image": "https://example.com/p.png",
            "description": "Example product", "offers": offer}


def offer(node_id="#offer"):
    return {"@id": node_id, "@type": "Offer", "price": "12.00",
            "priceCurrency": "USD", "availability": "https://schema.org/InStock"}


@pytest.mark.parametrize("node_id", ["#offer", "https://example.com/product#offer", "_:offer"])
@pytest.mark.parametrize("as_list", [False, True])
def test_offer_reference_matches_inline_validation(node_id, as_list):
    definition = offer(node_id)
    ref = {"@id": node_id}
    payload = {"@context": "https://schema.org", "@graph": [
        product([ref] if as_list else ref), definition,
    ]}
    original = copy.deepcopy(payload)
    expected = schema.validate(product([definition] if as_list else definition))
    assert expected["ok"] is True
    assert schema.validate(payload) == expected
    assert payload == original


def test_policies_shipping_and_loyalty_specs_resolve_without_false_warnings():
    policy = {"@id": "#returns", "@type": "MerchantReturnPolicy",
              "applicableCountry": "US", "returnPolicyCategory": "MerchantReturnFiniteReturnWindow"}
    shipping = {"@id": "#shipping", "@type": "OfferShippingDetails",
                "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "US"},
                "deliveryTime": {"@type": "ShippingDeliveryTime"}}
    price = {"@id": "#member-price", "@type": "UnitPriceSpecification",
             "validForMemberTier": {"@id": "#tier"}}
    inline = offer() | {"hasMerchantReturnPolicy": [policy], "shippingDetails": [shipping],
                        "priceSpecification": [price]}
    linked = offer() | {"hasMerchantReturnPolicy": [{"@id": "#returns"}],
                        "shippingDetails": [{"@id": "#shipping"}],
                        "priceSpecification": [{"@id": "#member-price"}]}
    payload = {"@context": "https://schema.org", "@graph": [
        product({"@id": "#offer"}), linked, policy, shipping, price,
    ]}
    expected = schema.validate(product(inline))
    assert expected["summary"]["medium"] == 0
    assert schema.validate(payload) == expected


def test_shared_definition_does_not_create_extra_product_findings():
    definition = offer()
    payload = [product({"@id": "#offer"}), product({"@id": "#offer"}), definition]
    assert schema.validate(payload) == schema.validate([product(definition), product(definition)])


@pytest.mark.parametrize("definition", [None, {"@id": "#other", "@type": "Offer"}])
def test_unresolved_reference_still_fails(definition):
    payload = [product({"@id": "https://remote.example/offer"})]
    if definition:
        payload.append(definition)
    assert schema.validate(payload)["ok"] is False


def test_conflicting_definitions_do_not_arbitrarily_pass():
    payload = [product({"@id": "#offer"}), offer(), offer() | {"@type": "AggregateOffer"}]
    assert schema.validate(payload)["ok"] is False


def test_identical_repeated_definitions_are_unambiguous():
    payload = [product({"@id": "#offer"}), offer(), offer()]
    assert schema.validate(payload) == schema.validate(product(offer()))


def test_context_definition_is_not_an_offer_node():
    payload = product({"@id": "#offer"}) | {"@context": {"fake": offer()}}
    assert schema.validate(payload)["ok"] is False


def test_relative_ids_under_different_bases_are_not_conflated():
    p = product({"@id": "#offer"}) | {"@context": {"@base": "https://other.example/"}}
    payload = {"@context": {"@base": "https://example.com/"}, "@graph": [p, offer()]}
    assert schema.validate(payload)["ok"] is False


def test_absolute_ids_are_independent_of_base_contexts():
    node_id = "https://example.com/#offer"
    p = product({"@id": node_id}) | {"@context": {"@base": "https://other.example/"}}
    assert schema.validate([p, offer(node_id)]) == schema.validate(product(offer(node_id)))


def test_compact_iri_prefixes_from_different_contexts_are_not_conflated():
    definition = offer("offer:item") | {"@context": {"offer": "https://inside.example/"}}
    payload = {"@context": {"@vocab": "https://schema.org/", "offer": "https://outside.example/"},
               "@graph": [product({"@id": "offer:item"}), definition]}
    assert schema.validate(payload)["ok"] is False


@pytest.mark.parametrize("product_in_named_graph", [False, True])
def test_references_cannot_borrow_properties_from_another_graph(product_in_named_graph):
    p = product({"@id": "#offer"})
    inner, outer = (p, offer()) if product_in_named_graph else (offer(), p)
    payload = [outer, {"@id": "#named", "@graph": [inner]}]
    assert schema.validate(payload)["ok"] is False


def test_same_identifier_resolves_independently_in_named_graphs():
    payload = [
        {"@id": "#one", "@graph": [product({"@id": "#offer"}), offer()]},
        {"@id": "#two", "@graph": [product({"@id": "#offer"}),
                                     offer() | {"@type": "AggregateOffer"}]},
    ]
    expected = schema.validate([product(offer()), product(offer() | {"@type": "AggregateOffer"})])
    assert schema.validate(payload) == expected


def test_cyclic_reference_does_not_expand_recursively():
    definition = offer() | {"hasMerchantReturnPolicy": {"@id": "#offer"}}
    result = schema.validate([product({"@id": "#offer"}), definition])
    rules = {finding["rule"] for finding in result["findings"]}
    assert result["ok"] is True
    assert "return-policy-applicableCountry" in rules
    assert "return-policy-returnPolicyCategory" in rules


def test_cli_accepts_a_locally_linked_offer(monkeypatch, capsys):
    payload = {"@context": "https://schema.org", "@graph": [
        product({"@id": "#offer"}), offer(),
    ]}
    monkeypatch.setattr(sys, "argv", ["schema_ecommerce_validate.py", "--json"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert schema.main() == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
