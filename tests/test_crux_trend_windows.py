"""Missing weeks must not silently move the comparison windows into the past."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import crux_history  # noqa: E402


@pytest.mark.parametrize("values", [
    [100] * 4 + [50] * 4 + [None] * 4,
    [None] * 4 + [100] * 4 + [50] * 4,
    [100] * 4 + [75] * 4 + [50, 50, None, 50],
])
def test_missing_endpoint_periods_are_insufficient_data(values):
    metrics = {"largest_contentful_paint": {"p75_values": values, "unit": "ms"}}
    trend = crux_history.detect_trends(metrics)["largest_contentful_paint"]
    assert trend["direction"] == "insufficient_data"


def test_missing_middle_periods_do_not_change_complete_endpoint_windows():
    metrics = {"largest_contentful_paint": {
        "p75_values": [100] * 4 + [None] * 4 + [50] * 4, "unit": "ms",
    }}
    trend = crux_history.detect_trends(metrics)["largest_contentful_paint"]
    assert trend["direction"] == "improving"
    assert trend["earliest_avg"] == 100
    assert trend["latest_avg"] == 50
