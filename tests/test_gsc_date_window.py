"""Search Analytics --days counts inclusive dates ending at the data-lag cutoff."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("googleapiclient")
import gsc_query  # noqa: E402


@pytest.fixture
def api(monkeypatch):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 15, 12, 0, tzinfo=tz)

    service = Mock()
    service.searchanalytics.return_value.query.return_value.execute.return_value = {"rows": []}
    monkeypatch.setattr(gsc_query, "datetime", FrozenDateTime)
    monkeypatch.setattr(gsc_query, "_build_gsc_service", lambda: service)
    return service.searchanalytics.return_value.query


def _cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", [
        "gsc_query.py", "--property", "sc-domain:example.com", "--json", *args,
    ])
    gsc_query.main()
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("days,expected_start", [
    (1, "2026-11-12"), (2, "2026-11-11"),
    (28, "2026-10-16"), (90, "2026-08-15"),
])
def test_cli_days_is_an_inclusive_window_before_the_data_lag_cutoff(
    api, monkeypatch, capsys, days, expected_start,
):
    result = _cli(monkeypatch, capsys, "--days", str(days))
    assert result["date_range"] == {"start": expected_start, "end": "2026-11-12"}
    for call in api.call_args_list:
        body = call.kwargs["body"]
        assert body["startDate"] == expected_start
        assert body["endDate"] == "2026-11-12"


def test_programmatic_default_includes_28_complete_dates(api):
    result = gsc_query.query_search_analytics("sc-domain:example.com")
    assert result["date_range"] == {"start": "2026-10-16", "end": "2026-11-12"}


def test_explicit_end_date_anchors_the_cli_window_across_leap_day(api, monkeypatch, capsys):
    result = _cli(monkeypatch, capsys, "--end-date", "2024-03-01", "--days", "3")
    assert result["date_range"] == {"start": "2024-02-28", "end": "2024-03-01"}


def test_programmatic_end_date_anchors_the_default_window(api):
    result = gsc_query.query_search_analytics("sc-domain:example.com", end_date="2024-03-01")
    assert result["date_range"] == {"start": "2024-02-03", "end": "2024-03-01"}


def test_explicit_start_and_end_dates_take_precedence_over_days(api, monkeypatch, capsys):
    result = _cli(monkeypatch, capsys, "--start-date", "2026-09-01",
                  "--end-date", "2026-09-30", "--days", "1")
    assert result["date_range"] == {"start": "2026-09-01", "end": "2026-09-30"}


def test_explicit_start_keeps_default_data_lag_cutoff(api, monkeypatch, capsys):
    result = _cli(monkeypatch, capsys, "--start-date", "2026-09-01")
    assert result["date_range"] == {"start": "2026-09-01", "end": "2026-11-12"}


def test_explicit_programmatic_dates_are_preserved(api):
    result = gsc_query.query_search_analytics(
        "sc-domain:example.com", start_date="2026-09-01", end_date="2026-09-30",
    )
    assert result["date_range"] == {"start": "2026-09-01", "end": "2026-09-30"}


@pytest.mark.parametrize("days", ["0", "-1"])
def test_nonpositive_day_window_is_rejected_before_the_api(api, monkeypatch, capsys, days):
    with pytest.raises(SystemExit) as error:
        _cli(monkeypatch, capsys, "--days", days)
    assert error.value.code == 2
    assert "days must be a positive integer" in capsys.readouterr().err
    api.assert_not_called()


def test_explicit_start_does_not_use_the_day_count(api, monkeypatch, capsys):
    result = _cli(monkeypatch, capsys, "--start-date", "2026-09-01", "--days", "0")
    assert result["date_range"] == {"start": "2026-09-01", "end": "2026-11-12"}


def test_malformed_end_date_is_reported_without_a_traceback(api, monkeypatch, capsys):
    with pytest.raises(SystemExit) as error:
        _cli(monkeypatch, capsys, "--end-date", "not-a-date")
    assert error.value.code == 2
    assert "end_date must use YYYY-MM-DD" in capsys.readouterr().err
    api.assert_not_called()

    result = gsc_query.query_search_analytics("sc-domain:example.com", end_date="not-a-date")
    assert result["error"] == "end_date must use YYYY-MM-DD"
    api.assert_not_called()
