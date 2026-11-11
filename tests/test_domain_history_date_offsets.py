"""WHOIS date offsets must not silently remove domain-age information."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import domain_history  # noqa: E402


@pytest.mark.parametrize(("value", "expected"), [
    ("2020-06-01T12:30:00+00:00", "2020-06-01"),
    ("2020-06-01T12:30:00.123456-05:00", "2020-06-01"),
    ("2020-01-01T00:30:00+02:00", "2019-12-31"),
    ("2020-01-01T23:30:00-02:00", "2020-01-02"),
    ("2020-06-01T12:30:00Z", "2020-06-01"),
    ("01-Jun-2020", "2020-06-01"),
    ("01.06.2020", "2020-06-01"),
    ("not a date", None),
])
def test_offset_and_legacy_dates(value, expected):
    assert domain_history._parse_date(value) == expected


def test_lookup_keeps_age_and_lifecycle_dates_from_offset_whois(monkeypatch):
    monkeypatch.setattr(domain_history, "_shell_whois", lambda _: """
Creation Date: 2000-01-01T12:00:00+00:00
Updated Date: 2025-01-01T12:00:00+00:00
Registry Expiry Date: 2030-01-01T12:00:00+00:00
""")
    result = domain_history.lookup("example.com")
    assert result["created"] == "2000-01-01"
    assert result["updated"] == "2025-01-01"
    assert result["expires"] == "2030-01-01"
    assert result["years_registered"] is not None
