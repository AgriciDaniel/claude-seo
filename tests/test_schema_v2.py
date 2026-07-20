"""
Tests for the v2 Checkpoint 4 schema scripts:
    scripts/schema_generate.py
    scripts/schema_ecommerce_validate.py

The deprecated-types reference file (skills/seo-schema/references/
deprecated-types-2024-2026.md) is documentation only and is exercised
indirectly: any retired type generated through schema_generate.py is
caught by the ecommerce validator's deprecated-type rule.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import schema_generate  # noqa: E402
import schema_ecommerce_validate as ev  # noqa: E402


# ---------------------------------------------------------------------------
# schema_generate
# ---------------------------------------------------------------------------


def test_reservation_default_is_food_establishment() -> None:
    r = schema_generate.reservation("Marea", "2026-06-04T19:30:00Z", party_size=4)
    assert r["@type"] == "FoodEstablishmentReservation"
    assert r["@context"] == "https://schema.org"
    assert r["provider"]["name"] == "Marea"
    assert r["partySize"] == 4
    assert r["reservationFor"]["@type"] == "FoodEstablishment"


def test_reservation_kind_override() -> None:
    r = schema_generate.reservation(
        "Hilton NYC", "2026-08-12T15:00:00Z",
        kind="LodgingReservation",
    )
    assert r["@type"] == "LodgingReservation"
    assert r["reservationFor"]["@type"] == "Place"


def test_reservation_includes_under_name_when_customer_provided() -> None:
    r = schema_generate.reservation(
        "Marea", "2026-06-04T19:30:00Z",
        customer_name="Daniel A", customer_email="da@example.com",
    )
    assert r["underName"]["@type"] == "Person"
    assert r["underName"]["name"] == "Daniel A"
    assert r["underName"]["email"] == "da@example.com"


def test_order_action_includes_required_target() -> None:
    r = schema_generate.order_action("Acme Pizza",
                                     order_url="https://acme.example/order")
    assert r["@type"] == "OrderAction"
    assert r["target"]["@type"] == "EntryPoint"
    assert r["target"]["urlTemplate"] == "https://acme.example/order"
    assert "DesktopWebPlatform" in r["target"]["actionPlatform"][0]


def test_discussion_includes_interaction_statistic_when_likes_set() -> None:
    r = schema_generate.discussion(
        "How do you score INP correctly?",
        "Sara Park",
        url="https://forum.example.com/t/123",
        date_published="2026-05-12T14:00:00Z",
        interaction_count={"LikeAction": 47},
    )
    assert r["@type"] == "DiscussionForumPosting"
    stats = r["interactionStatistic"]
    assert stats[0]["userInteractionCount"] == 47
    assert "LikeAction" in stats[0]["interactionType"]


def test_profile_includes_same_as_and_knows_about() -> None:
    r = schema_generate.profile(
        "Daniel Agrici",
        url="https://agricidaniel.com/about",
        same_as=["https://github.com/AgriciDaniel", "https://orcid.org/0000-0000-0000-0000"],
        knows_about=["SEO", "Schema markup", "Core Web Vitals"],
    )
    assert r["@type"] == "ProfilePage"
    person = r["mainEntity"]
    assert person["sameAs"][0].startswith("https://github.com/")
    assert "SEO" in person["knowsAbout"]


def test_strip_nones_removes_optional_missing_fields() -> None:
    r = schema_generate.profile(
        "X", url="https://x.example/",
        same_as=None, knows_about=None,
    )
    cleaned = schema_generate._strip_nones(r)
    assert "sameAs" not in cleaned["mainEntity"]
    assert "knowsAbout" not in cleaned["mainEntity"]


def test_strip_nones_recurses_into_lists() -> None:
    payload = {"a": [{"b": None, "c": 1}, {"b": 2}]}
    cleaned = schema_generate._strip_nones(payload)
    assert cleaned == {"a": [{"c": 1}, {"b": 2}]}


# ---------------------------------------------------------------------------
# schema_ecommerce_validate
# ---------------------------------------------------------------------------


def _minimal_product() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Example",
        "image": "https://example.com/i.jpg",
        "description": "An example product.",
        "offers": [{
            "@type": "Offer",
            "price": 99.99,
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
        }],
    }


def test_validate_warns_for_missing_return_policy_and_shipping() -> None:
    result = ev.validate(_minimal_product())
    severities = {f["rule"]: f["severity"] for f in result["findings"]}
    assert severities["missing-return-policy"] == "Medium"
    assert severities["missing-shipping-details"] == "Medium"
    assert result["ok"] is True


def test_validate_passes_when_return_policy_and_shipping_present() -> None:
    product = _minimal_product()
    product["offers"][0]["hasMerchantReturnPolicy"] = {
        "@type": "MerchantReturnPolicy",
        "applicableCountry": "US",
        "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
        "merchantReturnDays": 30,
    }
    product["offers"][0]["shippingDetails"] = {
        "@type": "OfferShippingDetails",
        "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "US"},
        "deliveryTime": {"@type": "ShippingDeliveryTime"},
    }
    product["hasMemberProgram"] = {"@type": "MemberProgram", "name": "Acme Rewards"}
    result = ev.validate(product)
    high = [f for f in result["findings"] if f["severity"] == "High"]
    assert high == []
    assert result["ok"] is True


def test_validate_flags_deprecated_types() -> None:
    payload = {
        "@context": "https://schema.org",
        "@type": "ClaimReview",
        "claimReviewed": "x",
    }
    result = ev.validate(payload)
    rules = [f["rule"] for f in result["findings"]]
    assert "deprecated-type" in rules


def test_validate_eu_mode_requires_energy_class() -> None:
    product = _minimal_product()
    product["offers"][0]["hasMerchantReturnPolicy"] = {"@type": "MerchantReturnPolicy"}
    product["offers"][0]["shippingDetails"] = {"@type": "OfferShippingDetails"}

    result = ev.validate(product, require_eu_energy=True)
    rules = [f["rule"] for f in result["findings"]]
    assert "missing-eu-energy-class" in rules

    product["energyEfficiencyClass"] = "A"
    result = ev.validate(product, require_eu_energy=True)
    rules = [f["rule"] for f in result["findings"]]
    assert "missing-eu-energy-class" not in rules


def test_validate_emits_info_when_no_product_group() -> None:
    result = ev.validate(_minimal_product())
    info = [f for f in result["findings"] if f["severity"] == "Info"]
    assert any("ProductGroup" in f["message"] for f in info)


def test_validate_finds_offers_when_offers_is_single_dict() -> None:
    product = _minimal_product()
    product["offers"] = product["offers"][0]  # single dict, not list
    result = ev.validate(product)
    # Should still find the inner offer for return-policy / shipping checks.
    rules = [f["rule"] for f in result["findings"]]
    assert "missing-product-offers" not in rules


def test_validate_no_product_block_at_all_fails_loudly() -> None:
    result = ev.validate({"@type": "Article", "headline": "x"})
    rules = [f["rule"] for f in result["findings"]]
    assert "missing-product" in rules


def test_validate_summary_counts_severities() -> None:
    result = ev.validate(_minimal_product())
    s = result["summary"]
    assert s["medium"] >= 2  # missing return policy + shipping
    assert s["high"] == 0
    assert s["critical"] >= 0
    assert sum(s.values()) == len(result["findings"])


# ---------------------------------------------------------------------------
# deprecated-types reference file
# ---------------------------------------------------------------------------


def test_deprecated_types_reference_exists_and_lists_retired_kinds() -> None:
    from pathlib import Path

    ref = (
        Path(__file__).resolve().parents[1]
        / "skills" / "seo-schema" / "references"
        / "deprecated-types-2024-2026.md"
    )
    assert ref.is_file(), f"reference file missing: {ref}"
    text = ref.read_text(encoding="utf-8")
    for retired in (
        "Vehicle Listing",
        "Claim Review",
        "Estimated Salary",
        "Learning Video",
        "Course Info",
        "Special Announcement",
        "HowTo",
        "FAQ",
    ):
        assert retired in text, f"reference must mention {retired!r}"
    # Primary source must be linked.
    assert "developers.google.com/search/blog/2025/06/simplifying-search-results" in text


def test_faq_rich_results_retirement_documented() -> None:
    """FAQ rich results were fully retired on 2026-05-07 (supersedes the older
    Aug 2023 gov/health restriction). The canonical schema references must reflect
    the retirement and point users to QAPage for genuine Q&A — while keeping
    FAQPage as an AI/entity signal (not a Critical removal)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    deprecated = (
        root / "skills" / "seo-schema" / "references"
        / "deprecated-types-2024-2026.md"
    ).read_text(encoding="utf-8")
    schema_types = (
        root / "skills" / "seo" / "references" / "schema-types.md"
    ).read_text(encoding="utf-8")

    # Retirement date documented in both canonical references.
    assert "May 7, 2026" in deprecated, "deprecated-types must date the FAQ retirement"
    assert "May 7, 2026" in schema_types, "schema-types must date the FAQ retirement"
    # QAPage offered as the replacement for genuine Q&A.
    assert "QAPage" in deprecated and "QAPage" in schema_types
    # Google's faqpage doc cited as primary source.
    assert "structured-data/faqpage" in deprecated
