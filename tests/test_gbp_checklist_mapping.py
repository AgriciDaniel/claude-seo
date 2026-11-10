"""Verified status comes from DataForSEO is_claimed, not a guess (#334).

The 50-point checklist stays as it is. Only the data mapping changes:
https://docs.dataforseo.com/v3/business_data/google/my_business_info/live/
describes is_claimed as whether the owner verified the listing on Google Maps.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / "skills" / "seo" / "references" / "maps-gbp-checklist.md"


def test_verified_status_uses_is_claimed_and_keeps_the_point_scale() -> None:
    text = CHECKLIST.read_text(encoding="utf-8")
    folded = " ".join(text.split())
    assert "is_claimed" in text
    assert "Not directly exposed" not in text
    assert "infer from profile completeness" not in folded
    assert "Maps SERP presence" not in folded
    assert "| 8 | **Verified status** | 2 |" in text
    assert "(score / 50) * 100" in text
    assert "Unknown (manual check required)" in text
