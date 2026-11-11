"""Semicolon path parameters identify different pages, not tracking data."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from drift_baseline import normalize_url, url_hash  # noqa: E402


@pytest.mark.parametrize("url", [
    "https://example.com/page;lang=en", "https://example.com/page;v=2?sort=asc",
    "https://example.com/page;lang=en;theme=dark",
])
def test_final_segment_parameters_survive_normalization(url):
    assert normalize_url(url) == url


def test_different_parameterized_pages_do_not_share_a_baseline_key():
    urls = ["https://example.com/page", "https://example.com/page;lang=en", "https://example.com/page;lang=fr"]
    assert len({url_hash(url) for url in urls}) == len(urls)


def test_tracking_parameters_are_still_removed():
    assert normalize_url("https://example.com/page;lang=en?utm_source=test") == "https://example.com/page;lang=en"
