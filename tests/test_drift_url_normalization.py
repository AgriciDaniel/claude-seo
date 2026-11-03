"""URL identity must remain valid when drift targets use IPv6 literals."""

import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from drift_baseline import normalize_url, url_hash  # noqa: E402


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("HTTPS://[2001:DB8::1]:443/page/", "https://[2001:db8::1]/page"),
        ("http://[2001:db8::1]:8080/", "http://[2001:db8::1]:8080/"),
        ("http://[2001:db8::1]:80/", "http://[2001:db8::1]/"),
    ],
)
def test_normalization_keeps_ipv6_authority_parseable(url, expected):
    normalized = normalize_url(url)
    assert normalized == expected
    assert urlparse(normalized).hostname == "2001:db8::1"
    assert normalize_url(normalized) == normalized


def test_ipv6_default_port_and_tracking_parameters_share_a_baseline():
    assert url_hash("https://[2001:db8::1]:443/page/?utm_source=test") == url_hash(
        "https://[2001:db8::1]/page"
    )


def test_ipv6_custom_ports_keep_distinct_baselines():
    assert url_hash("https://[2001:db8::1]:8443/") != url_hash("https://[2001:db8::1]/")
