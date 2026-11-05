import sys
from pathlib import Path
from unittest.mock import MagicMock

from googleapiclient.errors import HttpError
from httplib2 import Response

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import indexing_notify  # noqa: E402


def test_batch_stops_after_indexing_api_returns_429(monkeypatch):
    service = MagicMock()
    publish = service.urlNotifications.return_value.publish
    publish.return_value.execute.side_effect = [
        {"urlNotificationMetadata": {"latestUpdate": {"notifyTime": "2026-11-05T00:00:00Z"}}},
        HttpError(Response({"status": "429"}), b'{"error":{"message":"quota exceeded"}}'),
        {"urlNotificationMetadata": {}},
    ]
    monkeypatch.setattr(indexing_notify, "_build_indexing_service", lambda: service)
    monkeypatch.setattr(indexing_notify, "validate_url", lambda _: True)
    monkeypatch.setattr(indexing_notify.time, "sleep", lambda _: None)
    urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]

    result = indexing_notify.batch_notify(urls)

    assert publish.call_count == 2
    assert result["summary"] == {"success": 1, "error": 1}
    assert result["error"] == "Stopped: daily quota exceeded."
    assert len(result["results"]) == 2
    assert result["results"][1]["error_code"] == "quota_exceeded"
    assert "Quota exceeded" in result["results"][1]["error"]


def test_batch_continues_after_non_quota_error(monkeypatch):
    service = MagicMock()
    publish = service.urlNotifications.return_value.publish
    publish.return_value.execute.side_effect = [
        HttpError(Response({"status": "403"}), b'{"error":{"message":"forbidden"}}'),
        {"urlNotificationMetadata": {}},
    ]
    monkeypatch.setattr(indexing_notify, "_build_indexing_service", lambda: service)
    monkeypatch.setattr(indexing_notify, "validate_url", lambda _: True)
    monkeypatch.setattr(indexing_notify.time, "sleep", lambda _: None)

    result = indexing_notify.batch_notify(["https://example.com/1", "https://example.com/2"])

    assert publish.call_count == 2
    assert result["summary"] == {"success": 1, "error": 1}
    assert "error_code" not in result["results"][0]
    assert result["error"] is None
