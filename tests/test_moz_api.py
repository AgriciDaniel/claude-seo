"""Moz API authentication and credential-status regressions."""

from __future__ import annotations

import base64
import os
import sys
from unittest.mock import patch

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import backlinks_auth  # noqa: E402
import moz_api  # noqa: E402


class FakeResponse:
    status_code = 200
    text = ""

    def json(self) -> dict:
        return {"results": []}


def test_moz_request_supports_colon_credentials_as_http_basic() -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured.update({"url": url, **kwargs})
        return FakeResponse()

    with patch.object(moz_api, "_rate_limit"), \
         patch.object(moz_api.requests, "post", side_effect=fake_post):
        result = moz_api._moz_request("/v2/url_metrics", {"targets": ["example.com"]}, "access-id:secret")

    expected = base64.b64encode(b"access-id:secret").decode("ascii")
    assert result["status"] == "success"
    assert captured["headers"]["Authorization"] == f"Basic {expected}"
    assert "x-moz-token" not in captured["headers"]


def test_moz_request_accepts_preencoded_basic_credentials() -> None:
    captured: dict = {}
    encoded = base64.b64encode(b"access-id:secret").decode("ascii")

    def fake_post(url: str, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    with patch.object(moz_api, "_rate_limit"), \
         patch.object(moz_api.requests, "post", side_effect=fake_post):
        moz_api._moz_request("/v2/url_metrics", {"targets": ["example.com"]}, encoded)

    assert captured["headers"]["Authorization"] == f"Basic {encoded}"
    assert "x-moz-token" not in captured["headers"]


def test_moz_request_keeps_v2_token_header_for_plain_api_keys() -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    with patch.object(moz_api, "_rate_limit"), \
         patch.object(moz_api.requests, "post", side_effect=fake_post):
        moz_api._moz_request("/v2/url_metrics", {"targets": ["example.com"]}, "mozscape-key")

    assert captured["headers"]["x-moz-token"] == "mozscape-key"
    assert "Authorization" not in captured["headers"]


def test_configured_moz_credentials_are_not_reported_live_verified() -> None:
    with patch.object(backlinks_auth, "load_config", return_value={"moz_api_key": "mozscape-key"}):
        result = backlinks_auth.check_credentials("moz")

    assert result["available"] is True
    assert result["verified"] is False
    assert "not live-verified" in result["note"]
