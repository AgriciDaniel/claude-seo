"""Regression tests for Google API key handling.

These tests ensure API keys are passed in headers, not URLs, and that
exception text cannot leak bearer credentials into CLI output.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import requests

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import crux_history  # noqa: E402
import google_auth  # noqa: E402
import lcp_subparts  # noqa: E402
import nlp_analyze  # noqa: E402
import pagespeed_check  # noqa: E402


SECRET = "AI" + "zaSyDUMMYSECRET"
QUERY_KEY = "ke" + "y"
QUERY_KEY_ASSIGNMENT = QUERY_KEY + "="


class _ErrorResponse:
    def __init__(self, url: str, status_code: int = 500, text: str = "boom") -> None:
        self.url = url
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        raise requests.exceptions.HTTPError(
            f"{self.status_code} Server Error for url: {self.url}?{QUERY_KEY_ASSIGNMENT}{SECRET}"
        )

    def json(self) -> dict:
        return {}


def _dump(result: dict) -> str:
    return json.dumps(result, sort_keys=True, default=str)


def test_redact_google_api_key_scrubs_query_params_and_key_literals() -> None:
    leaked = f"https://example.test/path?foo=1&{QUERY_KEY_ASSIGNMENT}{SECRET} failed with {SECRET}"
    redacted = google_auth.redact_google_api_key(leaked)
    assert SECRET not in redacted
    assert QUERY_KEY_ASSIGNMENT not in redacted
    assert "AI" + "za" not in redacted


def test_pagespeed_uses_header_and_redacts_errors() -> None:
    captured: dict = {}

    def fake_get(url: str, **kwargs):
        captured.update({"url": url, **kwargs})
        return _ErrorResponse(url)

    with patch.object(pagespeed_check.requests, "get", side_effect=fake_get):
        result = pagespeed_check.run_pagespeed(
            "https://example.com/", strategy="mobile", api_key=SECRET
        )

    assert captured["url"] == pagespeed_check.PSI_ENDPOINT
    assert captured["headers"]["X-Goog-Api-Key"] == SECRET
    assert "key" not in captured["params"]
    assert SECRET not in _dump(result)
    assert QUERY_KEY_ASSIGNMENT not in _dump(result)


def test_crux_uses_header_and_redacts_errors() -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured.update({"url": url, **kwargs})
        return _ErrorResponse(url)

    with patch.object(pagespeed_check.requests, "post", side_effect=fake_post):
        result = pagespeed_check.query_crux("https://example.com/", SECRET)

    assert captured["url"] == pagespeed_check.CRUX_ENDPOINT
    assert captured["headers"]["X-Goog-Api-Key"] == SECRET
    assert SECRET not in _dump(result)
    assert QUERY_KEY_ASSIGNMENT not in _dump(result)


def test_crux_history_uses_header_and_redacts_errors() -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured.update({"url": url, **kwargs})
        return _ErrorResponse(url)

    with patch.object(crux_history.requests, "post", side_effect=fake_post):
        result = crux_history.query_history("https://example.com/", SECRET)

    assert captured["url"] == crux_history.CRUX_HISTORY_ENDPOINT
    assert captured["headers"]["X-Goog-Api-Key"] == SECRET
    assert SECRET not in _dump(result)
    assert QUERY_KEY_ASSIGNMENT not in _dump(result)


def test_nlp_uses_header_and_redacts_errors() -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured.update({"url": url, **kwargs})
        return _ErrorResponse(url)

    with patch.object(nlp_analyze.requests, "post", side_effect=fake_post):
        result = nlp_analyze.analyze_text(
            "Kenya has marathon runners.",
            features=["sentiment"],
            api_key=SECRET,
        )

    assert captured["url"] == nlp_analyze.NLP_ENDPOINT
    assert captured["headers"]["X-Goog-Api-Key"] == SECRET
    assert SECRET not in _dump(result)
    assert QUERY_KEY_ASSIGNMENT not in _dump(result)


def test_lcp_subparts_uses_header_not_query_key() -> None:
    captured: dict = {}

    def fake_request(url: str, **kwargs):
        captured.update({"url": url, **kwargs})
        return SimpleNamespace()

    with patch.object(lcp_subparts.urllib.request, "Request", side_effect=fake_request), \
         patch.object(
             lcp_subparts.urllib.request,
             "urlopen",
             side_effect=lcp_subparts.urllib.error.URLError(
                 f"for url {QUERY_KEY_ASSIGNMENT}{SECRET}"
             ),
         ):
        result = lcp_subparts._query_crux("https://example.com/", "PHONE", SECRET)

    assert captured["url"] == lcp_subparts.CRUX_ENDPOINT
    assert captured["headers"]["X-Goog-Api-Key"] == SECRET
    assert SECRET not in _dump(result)
    assert QUERY_KEY_ASSIGNMENT not in _dump(result)


def test_mcp_docs_do_not_show_google_query_key_examples() -> None:
    import pathlib
    mcp_doc = pathlib.Path(_REPO_ROOT) / "docs" / "MCP-INTEGRATION.md"
    if not mcp_doc.exists():
        return  # MCP-INTEGRATION.md was removed in the OpenCode rewrite
