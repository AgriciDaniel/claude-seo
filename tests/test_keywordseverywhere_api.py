"""Keywords Everywhere (Open PageRank) API client regressions.

Covers the fallback backlinks source added for #262 and repaired for #312: a
successful lookup, an authentication error, a rate-limit response, and the
100-domain batch cap. Response shapes follow the current API documentation
(https://openpagerank.keywordseverywhere.com/docs, verified 2026-09-23):
POST /v1/domains/bulk, Bearer auth, ``results[]`` with ``open_page_rank``.
The earlier fixture encoded the removed DomCop-era contract, which kept this
suite green while the live endpoint returned 404.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

pytest.importorskip("requests")
import keywordseverywhere_api  # noqa: E402
from url_safety import URLSafetyError  # noqa: E402

DOCS_SUCCESS_RESPONSE = {
    "as_of": "2026-09-01",
    "count": 1,
    "results": [
        {
            "domain": "example.com",
            "found": True,
            "open_page_rank": 4.68,
            "rank": 51234,
            "referring_domains": 1830,
        }
    ],
    "invalid": [],
}
DOCS_AUTH_ERROR_RESPONSE = {
    "error": {"type": "authentication_error",
              "message": "Missing or invalid Authorization: Bearer <api_key>"},
}
DOCS_RATE_LIMIT_RESPONSE = {
    "error": {"type": "rate_limit_error", "message": "Too many requests"},
}


class FakeResponse:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self) -> dict:
        return self._body


def test_get_rank_posts_the_documented_bulk_request() -> None:
    fake = FakeResponse(200, DOCS_SUCCESS_RESPONSE)
    with patch.object(keywordseverywhere_api, "_post", return_value=fake) as mock_post:
        result = keywordseverywhere_api.get_rank(["example.com"], "opr_live_testkey")

    assert result["status"] == "success" and result["error"] is None
    assert result["data"]["domains"] == [{
        "domain": "example.com",
        "found": True,
        "open_page_rank": 4.68,
        "page_rank_decimal": 4.68,
        "rank": 51234,
        "referring_domains": 1830,
    }]
    assert result["data"]["as_of"] == "2026-09-01"
    args, kwargs = mock_post.call_args
    assert args[0] == "https://openpagerank.keywordseverywhere.com/v1/domains/bulk"
    assert kwargs["headers"]["Authorization"] == "Bearer opr_live_testkey"
    assert kwargs["json"] == {"domains": ["example.com"], "include_history": False}
    assert "params" not in kwargs  # the key never travels in the URL


def test_get_rank_auth_error_maps_to_error_status() -> None:
    fake = FakeResponse(401, DOCS_AUTH_ERROR_RESPONSE)
    with patch.object(keywordseverywhere_api, "_post", return_value=fake):
        result = keywordseverywhere_api.get_rank(["example.com"], "bad-key")

    assert result["status"] == "error"
    assert result["data"] is None
    assert "Invalid Keywords Everywhere API key" in result["error"]


def test_get_rank_rate_limit_maps_to_rate_limited_status() -> None:
    fake = FakeResponse(429, DOCS_RATE_LIMIT_RESPONSE)
    with patch.object(keywordseverywhere_api, "_post", return_value=fake):
        result = keywordseverywhere_api.get_rank(["example.com"], "opr_live_testkey")

    assert result["status"] == "rate_limited"
    assert result["data"] is None
    assert result["metadata"]["rate_limited"] is True


def test_get_rank_html_error_page_is_not_echoed() -> None:
    class HtmlResponse(FakeResponse):
        def json(self):
            raise ValueError("not json")

    fake = HtmlResponse(404, {})
    fake.text = "<html>opr_live_testkey not found</html>"
    with patch.object(keywordseverywhere_api, "_post", return_value=fake):
        result = keywordseverywhere_api.get_rank(["example.com"], "opr_live_testkey")
    assert result["error"] == "HTTP 404: no JSON error body"
    assert "opr_live_testkey" not in result["error"]


def test_get_rank_ssrf_block_surfaces_as_error_not_a_crash() -> None:
    with patch.object(keywordseverywhere_api, "_post", side_effect=URLSafetyError("blocked host")):
        result = keywordseverywhere_api.get_rank(["example.com"], "opr_live_testkey")

    assert result["status"] == "error"
    assert "blocked by SSRF protection" in result["error"]


def test_main_rejects_batches_over_100_domains_without_a_network_call(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    domains = [f"d{i}.example.com" for i in range(101)]
    monkeypatch.setattr(sys, "argv", ["keywordseverywhere_api.py", "rank", *domains, "--json"])
    with patch.object(keywordseverywhere_api, "_post") as mock_get:
        with pytest.raises(SystemExit) as exc_info:
            keywordseverywhere_api.main()

    assert exc_info.value.code == 1
    mock_get.assert_not_called()
    err = capsys.readouterr().err
    assert "101" in err
    assert "max 100" in err


def test_upstream_error_body_never_echoes_the_key(monkeypatch):
    """A 500 whose JSON error repeats the key must not leak it into the result."""
    import keywordseverywhere_api as ke

    class _Resp:
        status_code = 500
        text = ""

        def json(self):
            return {"error": {"type": "api_error",
                              "message": "Bearer opr_live_SECRET123 rejected"}}

    monkeypatch.setattr(ke, "_post", lambda *a, **k: _Resp())
    result = ke.get_rank(["example.com"], api_key="opr_live_SECRET123")
    assert "opr_live_SECRET123" not in str(result)
    assert "<redacted>" in str(result.get("error", ""))


@pytest.mark.parametrize("status,message", [(301, "unexpected redirect"), (200, "was not JSON")])
def test_redirects_and_non_json_bodies_get_a_clear_error(status, message) -> None:
    class Odd(FakeResponse):
        def json(self):
            raise ValueError("Expecting value: line 1 column 1")

    with patch.object(keywordseverywhere_api, "_post", return_value=Odd(status, {})):
        result = keywordseverywhere_api.get_rank(["example.com"], "opr_live_testkey")
    assert result["status"] == "error" and message in result["error"]


def test_post_goes_through_a_pinned_session_without_following_redirects() -> None:
    calls = {}

    class Session:
        def post(self, url, **kwargs):
            calls.update(kwargs, url=url)
            return "resp"

    from contextlib import contextmanager

    @contextmanager
    def fake_session(url):
        calls["pinned"] = url
        yield Session()

    with patch.object(keywordseverywhere_api, "safe_requests_session", fake_session):
        assert keywordseverywhere_api._post(keywordseverywhere_api.KWE_BASE, json={}) == "resp"
    assert calls["pinned"] == keywordseverywhere_api.KWE_BASE
    assert calls["allow_redirects"] is False
