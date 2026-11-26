"""The opt-in energy check accepts Google-supported Product markup.

Reference: https://developers.google.com/search/docs/appearance/structured-data/
merchant-listing#certification
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import schema_ecommerce_validate as validator  # noqa: E402


def product(**properties):
    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Dimmable LED",
        "image": "https://example.com/led.jpg",
        "offers": {"@type": "Offer", "price": 2.30, "priceCurrency": "EUR"},
        **properties,
    }


def certification(**properties):
    return {
        "@type": "Certification",
        "name": "EPREL",
        "issuedBy": {"@type": "Organization", "name": "European_Commission"},
        "certificationIdentification": "123456",
        **properties,
    }


def energy_findings(payload, *, enabled=True):
    return [
        item for item in validator.validate(payload, require_eu_energy=enabled)["findings"]
        if item["rule"] == "missing-eu-energy-class"
    ]


@pytest.mark.parametrize("issuer", ["European_Commission", "EC"])
def test_eprel_certificate_with_either_supported_issuer(issuer):
    data = product(hasCertification=certification(
        issuedBy={"@type": "Organization", "name": issuer},
    ))
    assert energy_findings(data) == []
    assert validator.validate(data, require_eu_energy=True)["ok"] is True


def test_repeated_certifications_can_include_unrelated_certificates():
    data = product(hasCertification=[
        certification(name="Vehicle_CO2_Class", issuedBy={"name": "BMWK"}),
        certification(),
    ])
    assert energy_findings(data) == []


def test_expanded_and_multi_typed_certificates():
    certificate = certification()
    certificate["@type"] = ["CreativeWork", "https://schema.org/Certification"]
    certificate["issuedBy"]["@type"] = "http://schema.org/Organization"
    assert energy_findings(product(hasCertification=certificate)) == []


def test_local_certificate_and_issuer_references():
    certificate = certification(**{"@id": "#energy"})
    issuer = {"@id": "#issuer", **certificate["issuedBy"]}
    certificate["issuedBy"] = {"@id": "#issuer"}
    payload = {"@context": "https://schema.org", "@graph": [
        product(hasCertification={"@id": "#energy"}), certificate, issuer,
    ]}
    original = copy.deepcopy(payload)
    assert energy_findings(payload) == []
    assert payload == original


@pytest.mark.parametrize("change", [
    {"@type": "CreativeWork"},
    {"@type": "https://example.com/Certification"},
    {"name": "Vehicle_CO2_Class"},
    {"name": ["EPREL"]},
    {"issuedBy": {"@type": "Organization", "name": "ADEME"}},
    {"issuedBy": {"@type": "Organization", "name": ["EC"]}},
    {"issuedBy": "European_Commission"},
    {"issuedBy": None},
    {"certificationIdentification": ""},
    {"certificationIdentification": "  "},
    {"certificationIdentification": None},
    {"certificationIdentification": True},
    {"certificationIdentification": {"value": "123456"}},
    {"certificationIdentification": None, "certificationRating": {
        "@type": "Rating", "ratingValue": "A", "bestRating": "A", "worstRating": "G",
    }},
])
def test_incomplete_or_unrelated_certification_does_not_satisfy_eu_check(change):
    assert energy_findings(product(hasCertification=certification(**change)))


@pytest.mark.parametrize("category", ["A", "A1Plus", "A2Plus", "A3Plus", "B", "C", "D", "E", "F", "G"])
def test_legacy_energy_consumption_markup_is_still_supported(category):
    details = {
        "@type": "EnergyConsumptionDetails",
        "hasEnergyEfficiencyCategory": f"https://schema.org/EUEnergyEfficiencyCategory{category}",
        "energyEfficiencyScaleMin": "https://schema.org/EUEnergyEfficiencyCategoryG",
        "energyEfficiencyScaleMax": "https://schema.org/EUEnergyEfficiencyCategoryA3Plus",
    }
    assert energy_findings(product(hasEnergyConsumptionDetails=details)) == []


def test_legacy_reference_with_explicit_enumeration_id():
    details = {
        "@id": "#energy",
        "@type": "http://schema.org/EnergyConsumptionDetails",
        "hasEnergyEfficiencyCategory": {"@id": "http://schema.org/EUEnergyEfficiencyCategoryC"},
    }
    payload = [product(hasEnergyConsumptionDetails=[{"@id": "#energy"}]), details]
    assert energy_findings(payload) == []


@pytest.mark.parametrize("category", [
    None, "", "A", "https://schema.org/EUEnergyEfficiencyCategoryH",
    "https://schema.org/EnergyStarCertified", "https://example.com/EUEnergyEfficiencyCategoryA",
    {"name": "EUEnergyEfficiencyCategoryA"},
])
def test_invalid_or_non_eu_legacy_categories_are_not_energy_labels(category):
    details = {"@type": "EnergyConsumptionDetails", "hasEnergyEfficiencyCategory": category}
    assert energy_findings(product(hasEnergyConsumptionDetails=details))


@pytest.mark.parametrize("value", ["A", None, "", [], False])
def test_nonstandard_energy_efficiency_class_no_longer_bypasses_check(value):
    assert energy_findings(product(energyEfficiencyClass=value))


@pytest.mark.parametrize("property_name", ["hasCertification", "hasEnergyConsumptionDetails"])
@pytest.mark.parametrize("value", [None, {}, "A", [None, "A", {}, {"@id": "#missing"}]])
def test_unusable_energy_objects_are_reported(property_name, value):
    assert energy_findings(product(**{property_name: value}))


def test_each_product_needs_its_own_energy_markup():
    payload = [product(hasCertification=certification()), product(name="Unlabelled lamp")]
    assert len(energy_findings(payload)) == 1


def test_energy_check_remains_opt_in():
    assert energy_findings(product(), enabled=False) == []


@pytest.mark.parametrize("energy_properties,expected_exit", [
    ({"hasCertification": certification()}, 0),
    ({"energyEfficiencyClass": "A"}, 1),
])
def test_cli_reports_supported_energy_markup(energy_properties, expected_exit):
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS / "schema_ecommerce_validate.py"), "--eu", "--json"],
        input=json.dumps(product(**energy_properties)), text=True, capture_output=True,
        check=False,
    )
    result = json.loads(completed.stdout)
    assert completed.returncode == expected_exit, completed.stderr
    assert result["ok"] is (expected_exit == 0)
