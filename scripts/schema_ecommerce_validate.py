#!/usr/bin/env python3
"""
Product schema validator focused on Google merchant-listing fields.

The 2025 Google Search docs for Product structured data list four
property groups that strongly influence merchant listing diagnostics:

  - ``name`` + ``image`` + ``offers``   (confirmed merchant listing minimum)
  - ``offers.@type`` must be ``Offer``  (not ``AggregateOffer``)
  - ``description``                     (recommended Product field)
  - ``hasMerchantReturnPolicy``         (recommended or conditional)
  - ``shippingDetails``                 (recommended or conditional)
  - ``MemberProgram``                    (loyalty pricing visibility)
  - ``energyEfficiencyClass``            (REQUIRED in the EU for in-scope
                                          categories under EPREL)
  - ``ProductGroup`` for size/colour variants

The Rich Results Test catches structural errors. This validator catches
the *policy* errors — fields that parse fine but disqualify the product
from a rich feature. It also flags the deprecated v1.x types
(Vehicle Listing, Claim Review, Estimated Salary, Learning Video,
Course Info, Special Announcement).

Usage::

    cat product.json | python scripts/schema_ecommerce_validate.py
    python scripts/schema_ecommerce_validate.py product.json --eu
    python scripts/schema_ecommerce_validate.py product.json --json

Exit code 0 on PASS, 1 on at least one Critical or High finding.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# Types Google retired June 2025 (announced via developers.google.com/search/blog
# /2025/06/simplifying-search-results). Generating any of these in 2026 is a
# Critical finding because the rich result no longer renders.
_DEPRECATED_TYPES: dict[str, str] = {
    "Vehicle": "Vehicle Listing rich result retired June 2025.",
    "VehicleListing": "Vehicle Listing rich result retired June 2025.",
    "ClaimReview": "Claim Review rich result retired June 2025.",
    "EstimatedSalary": "Estimated Salary rich result retired June 2025.",
    "LearningVideo": "Learning Video rich result retired June 2025.",
    "Course": (
        "The Course rich result is still live but the Course Info carousel "
        "variant was retired June 2025. Verify which use-case applies."
    ),
    "SpecialAnnouncement": (
        "Special Announcement rich result deprecated July 2025."
    ),
}


_REQUIRED_PRODUCT_FIELDS = ("name", "image", "offers")
_RECOMMENDED_PRODUCT_FIELDS = ("description",)
_RECOMMENDED_OFFER_FIELDS = ("price", "priceCurrency", "availability")
_REQUIRED_RETURN_POLICY_FIELDS = (
    "applicableCountry",
    "returnPolicyCategory",
)
_REQUIRED_SHIPPING_FIELDS = (
    "shippingDestination",
    "deliveryTime",
)


def _iter_typed(payload, target_type: str):
    """Yield every dict in ``payload`` whose @type matches ``target_type``."""
    if isinstance(payload, dict):
        kind = payload.get("@type")
        if isinstance(kind, str) and kind == target_type:
            yield payload
        elif isinstance(kind, list) and target_type in kind:
            yield payload
        for v in payload.values():
            yield from _iter_typed(v, target_type)
    elif isinstance(payload, list):
        for v in payload:
            yield from _iter_typed(v, target_type)


def _all_types(payload) -> list[str]:
    types: list[str] = []
    if isinstance(payload, dict):
        kind = payload.get("@type")
        if isinstance(kind, str):
            types.append(kind)
        elif isinstance(kind, list):
            types.extend(t for t in kind if isinstance(t, str))
        for v in payload.values():
            types.extend(_all_types(v))
    elif isinstance(payload, list):
        for v in payload:
            types.extend(_all_types(v))
    return types


def _has_type(payload: dict, target_type: str) -> bool:
    kind = payload.get("@type")
    if isinstance(kind, str):
        return kind == target_type
    if isinstance(kind, list):
        return target_type in kind
    return False


def validate(payload: dict | list, *, require_eu_energy: bool = False) -> dict:
    findings: list[dict] = []

    # 1. Deprecated rich-result type generation.
    for kind in _all_types(payload):
        if kind in _DEPRECATED_TYPES:
            findings.append({
                "severity": "Critical",
                "rule": "deprecated-type",
                "message": f"@type={kind!r}: {_DEPRECATED_TYPES[kind]}",
            })

    products = list(_iter_typed(payload, "Product"))
    if not products:
        findings.append({
            "severity": "High",
            "rule": "missing-product",
            "message": "No @type=\"Product\" block found in the JSON-LD.",
        })

    for prod in products:
        # 2. Required base Product fields.
        for field in _REQUIRED_PRODUCT_FIELDS:
            if field not in prod or prod[field] in (None, "", []):
                findings.append({
                    "severity": "High",
                    "rule": f"missing-product-{field}",
                    "message": f"Product is missing required {field!r}.",
                })

        for field in _RECOMMENDED_PRODUCT_FIELDS:
            if field not in prod or prod[field] in (None, "", []):
                findings.append({
                    "severity": "Medium",
                    "rule": f"recommended-product-{field}",
                    "message": f"Product is missing recommended {field!r}.",
                })

        # 3. Offers must use @type Offer. Price, currency, and availability
        # are recommended diagnostics, not merchant-listing failure gates.
        offers = prod.get("offers", [])
        if isinstance(offers, dict):
            offers_list = [offers]
        elif isinstance(offers, list):
            offers_list = offers
        else:
            offers_list = []

        for offer in offers_list:
            if not isinstance(offer, dict):
                continue
            if _has_type(offer, "AggregateOffer"):
                findings.append({
                    "severity": "High",
                    "rule": "merchant-listing-offer-type",
                    "message": "Merchant listings require offers.@type='Offer', "
                               "not 'AggregateOffer'.",
                })
            elif not _has_type(offer, "Offer"):
                findings.append({
                    "severity": "High",
                    "rule": "merchant-listing-offer-type",
                    "message": "Merchant listings require offers.@type='Offer'.",
                })
            for field in _RECOMMENDED_OFFER_FIELDS:
                if field not in offer or offer[field] in (None, "", []):
                    findings.append({
                        "severity": "Medium",
                        "rule": f"recommended-offer-{field}",
                        "message": f"Offer is missing recommended {field!r}.",
                    })

        # 4. hasMerchantReturnPolicy (recommended or conditional).
        return_policy = prod.get("hasMerchantReturnPolicy") or (
            offers_list[0].get("hasMerchantReturnPolicy") if offers_list else None
        )
        if not return_policy:
            findings.append({
                "severity": "Medium",
                "rule": "missing-return-policy",
                "message": "Product (or its Offer) is missing "
                           "hasMerchantReturnPolicy.",
            })
        elif isinstance(return_policy, dict):
            for field in _REQUIRED_RETURN_POLICY_FIELDS:
                if field not in return_policy:
                    findings.append({
                        "severity": "Medium",
                        "rule": f"return-policy-{field}",
                        "message": f"MerchantReturnPolicy is missing {field!r}.",
                    })

        # 5. shippingDetails (recommended or conditional).
        shipping = prod.get("shippingDetails") or (
            offers_list[0].get("shippingDetails") if offers_list else None
        )
        if not shipping:
            findings.append({
                "severity": "Medium",
                "rule": "missing-shipping-details",
                "message": "Product (or its Offer) is missing "
                           "shippingDetails.",
            })
        elif isinstance(shipping, dict):
            for field in _REQUIRED_SHIPPING_FIELDS:
                if field not in shipping:
                    findings.append({
                        "severity": "Medium",
                        "rule": f"shipping-{field}",
                        "message": f"OfferShippingDetails is missing {field!r}.",
                    })

        # 6. Loyalty / MemberProgram visibility (Medium).
        if not prod.get("hasMemberProgram") and not any(
            o.get("priceSpecification", {}).get("@type") == "UnitPriceSpecification"
            and o.get("priceSpecification", {}).get("validForMemberTier")
            for o in offers_list if isinstance(o, dict)
        ):
            findings.append({
                "severity": "Medium",
                "rule": "missing-member-program",
                "message": "No MemberProgram or loyalty-tier pricing declared. "
                           "Add hasMemberProgram for visibility of loyalty "
                           "pricing in Google Shopping.",
            })

        # 7. EU energy label (only fires if --eu flag is set).
        if require_eu_energy and "energyEfficiencyClass" not in prod:
            findings.append({
                "severity": "High",
                "rule": "missing-eu-energy-class",
                "message": "EU mode: in-scope products require "
                           "energyEfficiencyClass per EPREL regulation.",
            })

    # 8. ProductGroup variant guidance — emit as Info if a Product is found
    # without any variant declaration.
    has_product_group = bool(list(_iter_typed(payload, "ProductGroup")))
    if products and not has_product_group:
        findings.append({
            "severity": "Info",
            "rule": "no-product-group",
            "message": "Consider ProductGroup if the product has size/colour "
                       "variants — Google increasingly enforces this for "
                       "apparel.",
        })

    severities = [f["severity"] for f in findings]
    return {
        "ok": all(s not in ("Critical", "High") for s in severities),
        "findings": findings,
        "summary": {
            "critical": severities.count("Critical"),
            "high":     severities.count("High"),
            "medium":   severities.count("Medium"),
            "info":     severities.count("Info"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Product JSON-LD against Google merchant rules."
    )
    parser.add_argument("source", nargs="?", default="-",
                        help="JSON-LD file path or '-' for stdin (default '-').")
    parser.add_argument("--eu", action="store_true",
                        help="Require energyEfficiencyClass (EPREL scope).")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    raw = sys.stdin.read() if args.source == "-" \
        else Path(args.source).read_text(encoding="utf-8")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON ({exc})", file=sys.stderr)
        return 2

    result = validate(payload, require_eu_energy=args.eu)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        status = "PASS" if result["ok"] else "FAIL"
        s = result["summary"]
        print(f"Status: {status}  ({s['critical']} critical, {s['high']} high, "
              f"{s['medium']} medium, {s['info']} info)")
        for f in result["findings"]:
            print(f"  [{f['severity']:<8}] {f['rule']}: {f['message']}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
