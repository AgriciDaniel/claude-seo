"""A publish receipt must describe the requested notification type."""

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import indexing_notify  # noqa: E402

URL = "https://example.com/jobs/123"
UPDATED = "2026-11-01T12:00:00Z"
REMOVED = "2026-11-15T12:00:00Z"


@pytest.fixture
def publish(monkeypatch):
    service = Mock()
    call = service.urlNotifications.return_value.publish
    call.return_value.execute.return_value = {
        "urlNotificationMetadata": {
            "latestUpdate": {"type": "URL_UPDATED", "notifyTime": UPDATED},
            "latestRemove": {"type": "URL_DELETED", "notifyTime": REMOVED},
        },
    }
    monkeypatch.setattr(indexing_notify, "_build_indexing_service", lambda: service)
    monkeypatch.setattr(indexing_notify, "indexing_scope_error", lambda: None)
    monkeypatch.setattr(indexing_notify, "validate_url", lambda _: True)
    monkeypatch.setattr(indexing_notify.time, "sleep", lambda _: None)
    return call


@pytest.mark.parametrize("action,expected", [
    ("URL_UPDATED", UPDATED), ("URL_DELETED", REMOVED),
])
def test_publish_selects_the_requested_notification(publish, action, expected):
    result = indexing_notify.notify_url(URL, action)
    assert result["error"] is None
    assert result["notify_time"] == expected
    publish.assert_called_once_with(body={"url": URL, "type": action})


@pytest.mark.parametrize("action,other", [
    ("URL_UPDATED", "latestRemove"), ("URL_DELETED", "latestUpdate"),
])
def test_missing_receipt_does_not_reuse_the_other_action(publish, action, other):
    publish.return_value.execute.return_value = {
        "urlNotificationMetadata": {other: {"notifyTime": UPDATED}},
    }
    result = indexing_notify.notify_url(URL, action)
    assert result["notify_time"] is None
    assert result["error"] is None


def test_empty_metadata_keeps_unknown_receipt_time(publish):
    publish.return_value.execute.return_value = {"urlNotificationMetadata": {}}
    result = indexing_notify.notify_url(URL, "URL_DELETED")
    assert result["notify_time"] is None
    assert result["error"] is None


def test_batch_deletions_keep_their_removal_receipts(publish):
    result = indexing_notify.batch_notify([URL, URL + "4"], "URL_DELETED", delay=0)
    assert result["summary"] == {"success": 2, "error": 0}
    assert [row["notify_time"] for row in result["results"]] == [REMOVED, REMOVED]
    assert all(call.kwargs["body"]["type"] == "URL_DELETED" for call in publish.call_args_list)


@pytest.mark.parametrize("as_json", [False, True])
def test_delete_cli_reports_the_removal_time(publish, monkeypatch, capsys, as_json):
    argv = ["indexing_notify.py", URL, "--action", "URL_DELETED"]
    if as_json:
        argv.append("--json")
    monkeypatch.setattr(sys, "argv", argv)
    indexing_notify.main()
    output = capsys.readouterr().out
    if as_json:
        assert json.loads(output)["notify_time"] == REMOVED
    else:
        assert f"(URL_DELETED) at {REMOVED}" in output
    assert UPDATED not in output
