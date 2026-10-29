"""Regression coverage for CrUX trends whose initial CLS average is zero."""

import json
import os
import sys
from unittest.mock import patch

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

pytest.importorskip("requests")
import crux_history  # noqa: E402


def _cls(values):
    return {"cumulative_layout_shift": {"p75_values": values, "label": "CLS", "unit": ""}}


@pytest.mark.parametrize(
    ("values", "direction", "change_pct"),
    [
        ([0] * 4 + [0.2] * 4, "degrading", None),
        ([0] * 8, "stable", 0),
        ([0.2] * 4 + [0] * 4, "improving", -100),
        ([0.1] * 4 + [0.2] * 4, "degrading", 100),
    ],
)
def test_cls_zero_baseline_and_nonzero_controls(values, direction, change_pct):
    trend = crux_history.detect_trends(_cls(values))["cumulative_layout_shift"]
    assert trend["direction"] == direction
    assert trend["change_pct"] == change_pct
    assert trend["earliest_avg"] == values[0]
    assert trend["latest_avg"] == values[-1]
    assert trend["data_points"] == 8
    json.dumps(trend, allow_nan=False)


@pytest.mark.parametrize("json_output", [False, True])
def test_cli_reports_a_zero_baseline_without_a_misleading_percentage(capsys, json_output):
    result = {
        "target": "https://example.com",
        "form_factor": "ALL",
        "trends": crux_history.detect_trends(_cls([0] * 4 + [0.2] * 4)),
    }
    argv = ["crux_history.py", "https://example.com", "--api-key", "DUMMY"]
    if json_output:
        argv.append("--json")
    with patch.object(sys, "argv", argv), patch.object(crux_history, "query_history", return_value=result):
        crux_history.main()
    output = capsys.readouterr().out
    if json_output:
        trend = json.loads(output)["trends"]["cumulative_layout_shift"]
        assert trend["direction"] == "degrading"
        assert trend["change_pct"] is None
    else:
        assert "CLS: DEGRADING" in output
        assert "zero baseline" in output
        assert "+0.0%" not in output
