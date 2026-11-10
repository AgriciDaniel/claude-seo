"""DataForSEO Merchant task polling regressions.

A Merchant task_get answers 40601 ("Task Handed") and then 40602 ("Task In
Queue") while the task waits to run, both with ``result: null``. Codes from
https://docs.dataforseo.com/v3/appendix/errors (verified 2026-10-27). The
poller used to keep waiting on 40601 only, so a queued task came back as if it
had finished and ``_extract_items`` crashed iterating ``None``.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

pytest.importorskip("requests")
import dataforseo_merchant  # noqa: E402

ITEM = {"type": "google_shopping_serp", "title": "Standing desk", "price": 249.0}


def _task_get(task_status: int, result: list | None) -> dict:
    return {
        "status_code": 20000,
        "tasks": [{"id": "task-1", "status_code": task_status, "result": result}],
    }


class FakeResponse:
    def __init__(self, body: dict):
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._body


def _poll(bodies: list[dict]) -> tuple[dict, int]:
    responses = iter(FakeResponse(b) for b in bodies)
    with patch.object(dataforseo_merchant.time, "sleep"), patch.object(
        dataforseo_merchant.requests, "get", side_effect=lambda *a, **k: next(responses)
    ) as get:
        data = dataforseo_merchant._poll_results("google_products", "task-1", {})
    return data, get.call_count


def test_keeps_polling_while_task_is_handed_or_queued():
    data, calls = _poll([
        _task_get(40601, None),
        _task_get(40602, None),
        _task_get(20000, [{"items": [ITEM]}]),
    ])
    assert calls == 3
    assert dataforseo_merchant._extract_items(data) == [ITEM]


def test_returns_a_real_task_error_without_waiting():
    body = _task_get(40102, None)
    body["tasks"][0]["status_message"] = "No Search Results."
    data, calls = _poll([body])
    assert calls == 1
    assert data == {
        "error": "task_error",
        "status_code": 40102,
        "message": "No Search Results.",
    }


@pytest.mark.parametrize("command", ["search", "sellers", "compare"])
def test_cli_surfaces_a_terminal_task_error_instead_of_empty_success(
    command, capsys, monkeypatch
):
    """A failed task has ``result: null``; it must not print 0 results as success."""
    monkeypatch.setenv("DATAFORSEO_USERNAME", "user")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "DUMMY")
    failed = _task_get(40501, None)
    failed["tasks"][0]["status_message"] = "Invalid Field."
    posted = {"status_code": 20000, "tasks": [{"id": "task-1"}]}
    argv = ["dataforseo_merchant.py", command, "standing desk"]
    with patch.object(sys, "argv", argv), patch.object(
        dataforseo_merchant.time, "sleep"
    ), patch.object(
        dataforseo_merchant.requests, "post", side_effect=lambda *a, **k: FakeResponse(posted)
    ), patch.object(
        dataforseo_merchant.requests, "get", side_effect=lambda *a, **k: FakeResponse(failed)
    ):
        dataforseo_merchant.main()

    output = json.loads(capsys.readouterr().out)
    if command == "compare":
        assert output["comparison"] == {
            "google": {"error": "Invalid Field."},
            "amazon": {"error": "Invalid Field."},
        }
    else:
        assert output == {
            "error": "task_error",
            "status_code": 40501,
            "message": "Invalid Field.",
        }


def test_extract_items_tolerates_null_result():
    assert dataforseo_merchant._extract_items(_task_get(40102, None)) == []
