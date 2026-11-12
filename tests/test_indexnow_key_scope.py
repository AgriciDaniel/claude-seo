"""Do not send URLs outside the ownership scope of the IndexNow key file."""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import indexnow_submit  # noqa: E402


@pytest.mark.parametrize("url", [
    "https://example.com/help/page", "https://example.com/catalogue/page",
    "https://shop.example.com/catalog/page", "https://example.com/catalog/../help/page",
    "https://example.com/catalog/%2e%2e/help/page",
])
def test_out_of_scope_urls_are_rejected_before_submission(monkeypatch, url):
    sent = []
    class Response:
        status_code = 200
        text = ""

    def post(*args, **kwargs):
        sent.append(kwargs)
        return Response()

    monkeypatch.setattr(indexnow_submit, "validate_url_strict", lambda u: (u, "1.1.1.1"))
    monkeypatch.setattr(requests, "post", post)
    result = indexnow_submit.submit("example.com", "a" * 32,
                                   "https://example.com/catalog/key.txt", [url])
    assert not sent
    assert result["ok"] is False
    assert result["submitted"] == 0


@pytest.mark.parametrize("key_location", [
    "https://example.com/key.txt", "https://example.com/catalog/key.txt",
])
def test_in_scope_urls_still_submit(monkeypatch, key_location):
    class Response:
        status_code = 200
        text = ""

    monkeypatch.setattr(indexnow_submit, "validate_url_strict", lambda u: (u, "1.1.1.1"))
    monkeypatch.setattr(requests, "post", lambda *a, **k: Response())
    result = indexnow_submit.submit("example.com", "a" * 32, key_location,
                                   ["https://example.com/catalog/page?item=1"])
    assert result["ok"] is True
