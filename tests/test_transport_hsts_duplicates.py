"""An STS field containing repeated directives is not a valid HSTS policy."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from transport_check import analyze_headers  # noqa: E402


@pytest.mark.parametrize("duplicate", [
    "max-age=0", "MAX-AGE=63072000", "includeSubDomains", "PRELOAD",
])
def test_duplicate_directive_prevents_preload_success(duplicate):
    value = "max-age=63072000; includeSubDomains; preload; " + duplicate
    result = analyze_headers({"Strict-Transport-Security": value})["hsts"]
    assert result["max_age"] is None
    assert result["meets_preload_requirements"] is False
    assert any("duplicate" in issue.lower() for issue in result["issues"])
    assert result["preload_gaps"]


def test_separate_header_fields_still_use_the_first_policy():
    result = analyze_headers({"Strict-Transport-Security":
                              "max-age=63072000; includeSubDomains; preload, max-age=0"})["hsts"]
    assert result["max_age"] == 63072000
    assert result["meets_preload_requirements"] is True
