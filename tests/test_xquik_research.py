"""Contract and safety tests for the optional Xquik research adapter."""

from __future__ import annotations

import argparse
import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "extensions" / "xquik" / "scripts" / "xquik_research.py"
SPEC = importlib.util.spec_from_file_location("xquik_research", MODULE_PATH)
assert SPEC and SPEC.loader
xquik = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(xquik)


class FakeResponse:
    def __init__(self, status_code: int, payload, headers=None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None) -> None:
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


def test_search_uses_fixed_endpoint_and_normalizes_evidence() -> None:
    secret = "xq_secret_marker"
    response = FakeResponse(
        200,
        {
            "tweets": [
                {
                    "id": "123",
                    "text": "x" * (xquik.MAX_POST_TEXT + 3),
                    "createdAt": "2026-08-21T10:00:00Z",
                    "likeCount": 8,
                    "replyCount": 2,
                    "retweetCount": 3,
                    "quoteCount": 1,
                    "viewCount": 100,
                    "bookmarkCount": 4,
                    "author": {"username": "example_user", "name": "Example", "verified": True},
                }
            ],
            "has_next_page": True,
            "next_cursor": "opaque",
        },
    )
    session = FakeSession(response=response)

    result = xquik.search_posts(
        session,
        secret,
        query='"product name" problem',
        limit=20,
        query_type="Latest",
        since_time="2026-08-01T00:00:00Z",
        language="en",
    )

    assert session.calls == [
        (
            "https://xquik.com/api/v1/x/tweets/search",
            {
                "params": {
                    "q": '"product name" problem',
                    "limit": 20,
                    "queryType": "Latest",
                    "replies": "exclude",
                    "retweets": "exclude",
                    "sinceTime": "2026-08-01T00:00:00Z",
                    "language": "en",
                },
                "headers": {"Accept": "application/json", "x-api-key": secret},
                "timeout": (5, 30),
                "allow_redirects": False,
            },
        )
    ]
    assert result["total_returned"] == 1
    assert result["results"][0]["text_truncated"] is True
    assert len(result["results"][0]["text"]) == xquik.MAX_POST_TEXT
    assert result["results"][0]["url"] == "https://x.com/example_user/status/123"
    assert result["results"][0]["metrics"] == {
        "likes": 8,
        "replies": 2,
        "reposts": 3,
        "quotes": 1,
        "views": 100,
        "bookmarks": 4,
    }
    assert result["pagination"] == {"has_next_page": True}
    assert secret not in json.dumps(result)


def test_search_preserves_zero_metrics_and_skips_invalid_posts() -> None:
    session = FakeSession(
        response=FakeResponse(
            200,
            {
                "tweets": [
                    {"id": "1", "text": "Useful evidence", "likeCount": 0, "like_count": 9},
                    {"id": "2", "text": ""},
                    "invalid",
                ],
            },
        ),
    )

    result = xquik.search_posts(
        session,
        "placeholder",
        query="  product problem  ",
        limit=20,
        query_type="Latest",
    )

    assert result["query"] == "product problem"
    assert result["total_returned"] == 1
    assert result["results"][0]["metrics"]["likes"] == 0


def test_radar_is_one_bounded_request() -> None:
    session = FakeSession(
        response=FakeResponse(
            200,
            {
                "items": [
                    {
                        "id": "radar_1",
                        "title": "A recurring customer question",
                        "url": "https://example.test/evidence",
                        "source": "reddit",
                        "category": "business",
                        "region": "US",
                        "language": "en",
                        "score": 42.5,
                        "publishedAt": "2026-08-21T09:00:00Z",
                    }
                ],
                "hasMore": False,
            },
        )
    )

    result = xquik.radar_topics(
        session,
        "placeholder",
        source="reddit",
        category="business",
        hours=24,
        limit=10,
        region="US",
    )

    assert session.calls[0][0] == "https://xquik.com/api/v1/radar"
    assert session.calls[0][1]["params"] == {
        "hours": 24,
        "limit": 10,
        "region": "US",
        "source": "reddit",
        "category": "business",
    }
    assert result["total_returned"] == 1
    assert result["results"][0]["source"] == "reddit"
    assert result["results"][0]["score"] == 42.5


def test_radar_skips_empty_items_and_normalizes_region() -> None:
    session = FakeSession(response=FakeResponse(200, {"items": [{}, {"title": "Signal"}]}))

    result = xquik.radar_topics(
        session,
        "placeholder",
        source=None,
        category=None,
        hours=24,
        limit=20,
        region="us",
    )

    assert session.calls[0][1]["params"]["region"] == "US"
    assert result["total_returned"] == 1


def test_normalizers_reject_unsafe_generated_links() -> None:
    tweet = xquik._normalize_tweet(
        {
            "id": "../settings",
            "text": "Evidence",
            "author": {"username": "valid_user"},
        },
    )
    radar = xquik._normalize_radar_item(
        {
            "id": "radar-1",
            "title": "Signal",
            "url": "javascript:alert(1)",
        },
    )

    assert tweet is not None and tweet["url"] is None
    assert radar is not None and radar["url"] is None


@pytest.mark.parametrize(
    ("status", "payload", "expected_code", "expected_message"),
    [
        (401, {"error": "unauthenticated"}, "unauthenticated", "authentication failed"),
        (
            402,
            {"error": {"code": "insufficient_credits"}},
            "insufficient_credits",
            "credits required",
        ),
        (429, {"error": "rate_limit_exceeded"}, "rate_limit_exceeded", "rate limit reached"),
        (502, {"error": "x_api_unavailable"}, "x_api_unavailable", "temporarily unavailable"),
    ],
)
def test_provider_errors_are_bounded(
    status: int,
    payload,
    expected_code: str,
    expected_message: str,
) -> None:
    session = FakeSession(response=FakeResponse(status, payload, {"Retry-After": "60"}))
    with pytest.raises(xquik.ResearchError) as caught:
        xquik._request_json(session, xquik.SEARCH_PATH, {"q": "topic"}, "secret")
    assert caught.value.code == expected_code
    assert expected_message in caught.value.message
    assert caught.value.retry_after == "60"
    assert "secret" not in caught.value.message


def test_network_error_does_not_expose_exception_details() -> None:
    session = FakeSession(
        error=requests.ConnectionError("https://xquik.com/?x-api-key=secret-marker"),
    )
    with pytest.raises(xquik.ResearchError) as caught:
        xquik._request_json(session, xquik.RADAR_PATH, {}, "secret-marker")
    assert caught.value.code == "network_error"
    assert "secret-marker" not in caught.value.message
    assert "x-api-key" not in caught.value.message


def test_redirect_and_non_object_json_fail_closed() -> None:
    redirect = FakeSession(response=FakeResponse(302, {}))
    with pytest.raises(xquik.ResearchError, match="unexpected redirect"):
        xquik._request_json(redirect, xquik.SEARCH_PATH, {}, "key")

    invalid = FakeSession(response=FakeResponse(200, []))
    with pytest.raises(xquik.ResearchError, match="invalid JSON response"):
        xquik._request_json(invalid, xquik.SEARCH_PATH, {}, "key")


def test_api_key_and_cli_values_validate_before_requests() -> None:
    with pytest.raises(xquik.ResearchError, match="API key missing"):
        xquik._api_key({})
    assert xquik._language("es-MX") == "es-MX"
    assert xquik._iso_time("2026-08-01T00:00:00Z") == "2026-08-01T00:00:00Z"
    assert xquik._query("  topic  ") == "topic"
    assert xquik._region("us") == "US"
    with pytest.raises(argparse.ArgumentTypeError, match="language code"):
        xquik._language("english")
    with pytest.raises(argparse.ArgumentTypeError, match="timezone"):
        xquik._iso_time("2026-08-01T00:00:00")
    with pytest.raises(argparse.ArgumentTypeError, match="1 to"):
        xquik._query(" ")
    with pytest.raises(argparse.ArgumentTypeError, match="region code"):
        xquik._region("everywhere")


def test_search_rejects_reversed_time_window_before_request() -> None:
    session = FakeSession(response=FakeResponse(200, {"tweets": []}))

    with pytest.raises(xquik.ResearchError, match="earlier"):
        xquik.search_posts(
            session,
            "placeholder",
            query="topic",
            limit=20,
            query_type="Latest",
            since_time="2026-08-02T00:00:00Z",
            until_time="2026-08-01T00:00:00Z",
        )

    assert session.calls == []


@pytest.mark.parametrize(
    ("kwargs", "expected_code"),
    [
        ({"limit": 101}, "invalid_limit"),
        ({"query_type": "Popular"}, "invalid_query_type"),
        ({"language": "english"}, "invalid_language"),
        ({"since_time": "yesterday"}, "invalid_time"),
    ],
)
def test_search_rejects_invalid_direct_inputs_before_request(kwargs, expected_code: str) -> None:
    session = FakeSession(response=FakeResponse(200, {"tweets": []}))
    arguments = {"query": "topic", "limit": 20, "query_type": "Latest", **kwargs}

    with pytest.raises(xquik.ResearchError) as caught:
        xquik.search_posts(session, "placeholder", **arguments)

    assert caught.value.code == expected_code
    assert session.calls == []


def test_server_results_cannot_exceed_requested_bound() -> None:
    session = FakeSession(
        response=FakeResponse(
            200,
            {"tweets": [{"id": str(index), "text": "Evidence"} for index in range(1, 8)]},
        ),
    )

    result = xquik.search_posts(
        session,
        "placeholder",
        query="topic",
        limit=3,
        query_type="Latest",
    )

    assert result["total_returned"] == 3


def test_invalid_cli_arguments_return_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = xquik.main(["listen", " "])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["status"] == "error"
    assert output["error"]["code"] == "invalid_arguments"
    assert output["metadata"]["command"] is None


def test_main_uses_core_url_safety_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = FakeSession(response=FakeResponse(200, {"tweets": []}))
    origins = []

    @contextmanager
    def safe_session(origin):
        origins.append(origin)
        yield session

    monkeypatch.setenv("X_TWITTER_SCRAPER_API_KEY", "placeholder")
    monkeypatch.setattr(xquik, "safe_requests_session", safe_session)

    exit_code = xquik.main(["listen", "topic"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert origins == ["https://xquik.com"]
    assert output["status"] == "success"


def test_only_read_endpoints_are_supported() -> None:
    session = FakeSession(response=FakeResponse(200, {}))
    with pytest.raises(xquik.ResearchError, match="Unsupported"):
        xquik._request_json(session, "/x/tweets", {}, "key")
    assert session.calls == []
