"""Supported Course nodes must not trigger a retired-feature failure."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import schema_ecommerce_validate as validator  # noqa: E402


def product():
    return {
        "@type": "Product", "name": "Statistics workbook",
        "image": "https://example.com/workbook.png",
        "offers": {"@type": "Offer", "price": "15", "priceCurrency": "USD"},
    }


def payload(course):
    return {"@context": "https://schema.org", "@graph": [product(), course]}


@pytest.mark.parametrize("kind", [
    "Course", ["LearningResource", "Course"],
    "https://schema.org/Course", "http://schema.org/Course",
])
def test_course_nodes_are_not_deprecated(kind):
    result = validator.validate(payload({
        "@type": kind, "name": "Introductory statistics",
        "description": "Learn descriptive statistics.",
    }))
    assert result["ok"]
    assert not any(f["rule"] == "deprecated-type" for f in result["findings"])


def test_course_list_nodes_do_not_fail_a_product_graph():
    course_list = {
        "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": number, "item": {
                "@type": "Course", "name": f"Statistics module {number}",
                "description": "A guided statistics curriculum.",
                "url": f"https://example.com/courses/{number}",
            }}
            for number in range(1, 4)
        ],
    }
    result = validator.validate(payload(course_list))
    assert result["ok"]
    assert result["summary"]["critical"] == 0


def test_course_type_does_not_change_successful_cli_exit_status():
    result = subprocess.run(
        [sys.executable, validator.__file__, "--json"],
        input=json.dumps(payload({"@type": "Course", "name": "Statistics"})),
        capture_output=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["ok"]


def test_known_retired_type_remains_a_critical_finding():
    result = validator.validate(payload({"@type": "ClaimReview"}))
    assert not result["ok"]
    assert result["summary"]["critical"] == 1


def test_course_only_input_still_requires_a_product():
    result = validator.validate({"@type": "Course", "name": "Statistics"})
    assert not result["ok"]
    assert any(f["rule"] == "missing-product" for f in result["findings"])
