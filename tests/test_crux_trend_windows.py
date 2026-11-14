"""Missing weeks must not silently move the comparison windows into the past.

Rule: leading weeks without data are trimmed, the latest window is the last
four calendar weeks, the earliest window is the first four calendar weeks after
the trim, each window needs three values, and the windows must not overlap.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import crux_history  # noqa: E402


def _trend(values):
    metrics = {"largest_contentful_paint": {"p75_values": values, "unit": "ms"}}
    return crux_history.detect_trends(metrics)["largest_contentful_paint"]


@pytest.mark.parametrize("values", [
    # Trailing gap of two or more weeks: the latest window is too thin.
    [100] * 4 + [50] * 4 + [None] * 4,
    [100] * 4 + [75] * 4 + [50, 50, None, None],
    [100] * 4 + [75] * 4 + [None, 50, None, 50],
    # Two weeks missing inside the earliest window.
    [100, None, None, 100] + [75] * 4 + [50] * 4,
    # Leading gap trimmed, then two more weeks missing in the earliest window.
    [None] * 3 + [100, None, None, 100] + [50] * 5,
    # Fewer than eight calendar weeks once the leading gap is trimmed.
    [None] * 5 + [100] * 4 + [50] * 3,
    [100] * 4 + [50] * 3,
    [None] * 12,
    [],
])
def test_thin_or_overlapping_windows_are_insufficient_data(values):
    trend = _trend(values)
    assert trend["direction"] == "insufficient_data"
    assert set(trend) == {"direction", "label"}


def test_missing_middle_periods_do_not_change_complete_endpoint_windows():
    trend = _trend([100] * 4 + [None] * 4 + [50] * 4)
    assert trend["direction"] == "improving"
    assert trend["earliest_avg"] == 100
    assert trend["latest_avg"] == 50


def test_leading_gap_is_trimmed_and_still_gives_a_trend():
    # Lower LCP is better, so 100 ms falling to 50 ms is improving.
    trend = _trend([None] * 4 + [100] * 4 + [50] * 4)
    assert trend["direction"] == "improving"
    assert trend["change_pct"] == -50
    assert trend["earliest_avg"] == 100
    assert trend["latest_avg"] == 50
    assert trend["data_points"] == 8


def test_leading_gap_then_rising_values_is_degrading():
    trend = _trend([None] * 10 + [50] * 4 + [60] * 7 + [100] * 4)
    assert trend["direction"] == "degrading"
    assert trend["earliest_avg"] == 50
    assert trend["latest_avg"] == 100


@pytest.mark.parametrize(("values", "earliest", "latest"), [
    ([100] * 4 + [75] * 4 + [50, 50, None, 50], 100, 50),
    ([100] * 4 + [75] * 4 + [50, 50, 50, None], 100, 50),
    ([100, None, 100, 100] + [75] * 4 + [50] * 4, 100, 50),
    # The average uses only the values present in the window.
    ([90, None, 120, 90] + [75] * 4 + [40, 60, None, 50], 100, 50),
])
def test_one_missing_week_inside_a_window_still_gives_a_trend(values, earliest, latest):
    trend = _trend(values)
    assert trend["direction"] == "improving"
    assert trend["earliest_avg"] == earliest
    assert trend["latest_avg"] == latest
    assert trend["change_pct"] == -50


def test_trailing_gap_never_relabels_older_weeks_as_latest():
    # The four weeks of 50 are not the latest calendar weeks.
    assert _trend([100] * 4 + [50] * 4 + [None, None])["direction"] == "insufficient_data"


def test_exactly_eight_weeks_after_the_trim_do_not_overlap():
    trend = _trend([None, None] + [100] * 4 + [100] * 4)
    assert trend["direction"] == "stable"
    assert trend["change_pct"] == 0


def test_output_keys_are_unchanged():
    assert set(_trend([100] * 8)) == {
        "direction", "change_pct", "earliest_avg", "latest_avg", "label", "data_points",
    }
