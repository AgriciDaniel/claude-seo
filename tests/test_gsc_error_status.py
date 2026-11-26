"""HTTP error classifications must not depend on numbers in URLs or messages."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("googleapiclient")
import gsc_inspect  # noqa: E402
import gsc_query  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402
from httplib2 import Response  # noqa: E402


def _http_error(status, *, uri="https://www.googleapis.com/query", message="API request failed"):
    return HttpError(
        Response({"status": str(status)}),
        json.dumps({"error": {"code": status, "message": message}}).encode(),
        uri=uri,
    )


def _run(monkeypatch, kind, error):
    service = Mock()
    if kind == "query":
        service.searchanalytics.return_value.query.return_value.execute.side_effect = error
        monkeypatch.setattr(gsc_query, "_build_gsc_service", lambda: service)
        return gsc_query.query_search_analytics("sc-domain:example403.com")
    service.urlInspection.return_value.index.return_value.inspect.return_value.execute.side_effect = error
    monkeypatch.setattr(gsc_inspect, "_build_inspection_service", lambda: service)
    monkeypatch.setattr(gsc_inspect, "validate_url", lambda url: True)
    return gsc_inspect.inspect_url("https://example403.com/page", "sc-domain:example403.com")


@pytest.mark.parametrize("kind,status,uri,expected", [
    ("query", 404, "https://www.googleapis.com/sites/example403.com", "Property"),
    ("query", 429, "https://www.googleapis.com/sites/example403.com", "GSC API error:"),
    ("query", 500, "https://www.googleapis.com/sites/example404.com", "GSC API error:"),
    ("inspection", 429, "https://www.googleapis.com/inspect?site=example403.com", "Rate limit exceeded."),
    ("inspection", 400, "https://www.googleapis.com/inspect?site=example429.com", "Invalid request."),
    ("inspection", 500, "https://www.googleapis.com/inspect?site=example403.com", "URL Inspection API error:"),
])
def test_response_status_wins_over_numbers_in_the_request_uri(
    monkeypatch, kind, status, uri, expected,
):
    result = _run(monkeypatch, kind, _http_error(status, uri=uri))
    assert result["error"].startswith(expected)
    assert "Permission denied" not in result["error"]


@pytest.mark.parametrize("kind", ["query", "inspection"])
def test_numbers_in_the_api_message_are_not_status_codes(monkeypatch, kind):
    error = _http_error(500, message="The backend for property 403429404 is temporarily unavailable")
    result = _run(monkeypatch, kind, error)
    assert "API error:" in result["error"]
    assert "temporarily unavailable" in result["error"]
    assert "Permission denied" not in result["error"]


@pytest.mark.parametrize("kind", ["query", "inspection"])
def test_non_http_errors_keep_the_original_diagnostic(monkeypatch, kind):
    result = _run(monkeypatch, kind, TimeoutError("Connection to example403.com timed out"))
    assert "API error: Connection to example403.com timed out" in result["error"]
    assert "Permission denied" not in result["error"]


@pytest.mark.parametrize("kind,status,expected", [
    ("query", 403, "Permission denied for property"),
    ("query", 404, "Property"),
    ("inspection", 403, "Permission denied."),
    ("inspection", 429, "Rate limit exceeded."),
    ("inspection", 400, "Invalid request."),
])
def test_known_response_status_messages_are_preserved(monkeypatch, kind, status, expected):
    result = _run(monkeypatch, kind, _http_error(status))
    assert result["error"].startswith(expected)


@pytest.mark.parametrize("kind", ["query", "inspection"])
def test_other_http_statuses_keep_the_api_error(monkeypatch, kind):
    result = _run(monkeypatch, kind, _http_error(503, message="Service unavailable"))
    assert "API error:" in result["error"]
    assert "Service unavailable" in result["error"]
