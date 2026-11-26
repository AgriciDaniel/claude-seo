"""Quick-win selection must consider all returned Search Analytics rows."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("googleapiclient")
import gsc_query  # noqa: E402


def _row(query, impressions, position=6):
    return {"keys": [query], "clicks": 10, "impressions": impressions,
            "ctr": 10 / impressions, "position": position}


def _service(monkeypatch, rows):
    service = Mock()
    calls = []

    def query(*, siteUrl, body):
        calls.append(dict(body))
        assert siteUrl == "sc-domain:example.com"
        if body["dimensions"] == []:
            response = {"rows": [{"clicks": 500, "impressions": 10000,
                                   "ctr": 0.05, "position": 3}]}
        else:
            start = body["startRow"]
            response = {"rows": rows[start:start + body["rowLimit"]]}
        return Mock(execute=Mock(return_value=response))

    service.searchanalytics.return_value.query.side_effect = query
    monkeypatch.setattr(gsc_query, "_build_gsc_service", lambda: service)
    return calls


def _run(monkeypatch, rows, *, row_limit=None, dimensions=None):
    calls = _service(monkeypatch, rows)
    result = gsc_query.query_search_analytics(
        "sc-domain:example.com", start_date="2026-11-01", end_date="2026-11-10",
        dimensions=["query"] if dimensions is None else dimensions,
        row_limit=row_limit or len(rows),
    )
    assert result["error"] is None
    return result, calls


def test_eligible_query_after_200_higher_impression_rows_is_retained(monkeypatch):
    rows = [_row(f"already-first-{i}", 1000 + i, position=1) for i in range(200)]
    rows.append(_row("useful-query", 500, position=6.25))

    result, _ = _run(monkeypatch, rows)

    assert [row["keys"] for row in result["quick_wins"]] == [["useful-query"]]
    assert result["quick_wins"][0]["position"] == 6.2
    assert result["quick_wins"][0]["ctr"] == 2.0
    assert result["quick_wins"][0]["impressions"] == 500
    assert result["quick_wins"][0]["clicks"] == 10
    assert result["row_count"] == 201
    assert result["totals"] == {"clicks": 500, "impressions": 10000,
                                "ctr": 5.0, "position": 3}
    assert result["totals_complete"] is True


def test_top_20_eligible_queries_are_ranked_across_the_whole_result(monkeypatch):
    rows = [_row(f"far-away-{i}", 2000 + i, position=20) for i in range(195)]
    rows += [_row(f"opportunity-{i}", 100 + i) for i in range(30)]

    result, _ = _run(monkeypatch, rows)

    assert [row["keys"][0] for row in result["quick_wins"]] == [
        f"opportunity-{i}" for i in range(29, 9, -1)
    ]
    assert len(result["rows"]) == len(rows)


def test_quick_wins_include_rows_from_later_api_pages(monkeypatch):
    rows = [_row(f"already-first-{i}", 1000, position=1) for i in range(25000)]
    rows.append(_row("second-page-opportunity", 500))

    result, calls = _run(monkeypatch, rows)

    assert [row["keys"] for row in result["quick_wins"]] == [["second-page-opportunity"]]
    assert [call["startRow"] for call in calls if call["dimensions"]] == [0, 25000]


def test_position_and_impression_thresholds_are_unchanged(monkeypatch):
    rows = [_row("too-high", 500, 3.99), _row("too-low", 500, 10.01),
            _row("too-few-impressions", 50, 6), _row("position-four", 100, 4),
            _row("position-ten", 51, 10)]

    result, _ = _run(monkeypatch, rows)

    assert [row["keys"][0] for row in result["quick_wins"]] == [
        "position-four", "position-ten",
    ]


def test_equal_impressions_keep_returned_row_order(monkeypatch):
    rows = [_row("first", 500), _row("second", 500)]
    result, _ = _run(monkeypatch, rows)
    assert [row["keys"][0] for row in result["quick_wins"]] == ["first", "second"]


def test_explicit_row_limit_still_limits_quick_win_candidates(monkeypatch):
    rows = [_row("already-first", 1000, 1), _row("not-returned", 500)]
    result, calls = _run(monkeypatch, rows, row_limit=1)
    assert result["quick_wins"] == []
    assert result["row_count"] == 1
    assert calls[0]["rowLimit"] == 1


def test_non_query_dimensions_do_not_generate_quick_wins(monkeypatch):
    result, _ = _run(monkeypatch, [_row("US", 500)], dimensions=["country"])
    assert result["quick_wins"] == []


@pytest.mark.parametrize("as_json", [False, True])
def test_cli_includes_opportunities_outside_the_old_cutoff(monkeypatch, capsys, as_json):
    rows = [_row(f"already-first-{i}", 1000, 1) for i in range(200)]
    rows.append(_row("useful-query", 500))
    _service(monkeypatch, rows)
    argv = ["gsc_query.py", "--property", "sc-domain:example.com", "--dimensions", "query"]
    if as_json:
        argv.append("--json")
    monkeypatch.setattr(sys, "argv", argv)

    gsc_query.main()

    output = capsys.readouterr().out
    if as_json:
        assert [row["keys"] for row in json.loads(output)["quick_wins"]] == [["useful-query"]]
    else:
        assert "Quick Wins (1 found):" in output
        assert "useful-query" in output
