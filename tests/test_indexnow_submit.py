"""IndexNow keyLocation must be the declared host, not a substring of the URL.

`verify_key_published` used `host not in key_location` after a successful
fetch. That accepts https://notexample.com/ when the host is example.com,
and rejects https://example.com/ when the host is written Example.COM.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import indexnow_submit  # noqa: E402

KEY = "a" * 32


class _Response:
    status_code = 200
    text = KEY


def test_lookalike_host_is_rejected_without_fetching(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("fetched a key file on another host")

    monkeypatch.setattr(indexnow_submit, "safe_requests_get", boom)
    result = indexnow_submit.verify_key_published(
        "example.com", KEY, "https://notexample.com/key.txt"
    )
    assert result == {
        "ok": False,
        "error": "keyLocation host does not match declared host",
    }


def test_host_comparison_ignores_case(monkeypatch) -> None:
    monkeypatch.setattr(indexnow_submit, "safe_requests_get", lambda *_a, **_k: _Response())
    result = indexnow_submit.verify_key_published(
        "Example.COM", KEY, "https://example.com/key.txt"
    )
    assert result["ok"] is True
    assert result["status_code"] == 200


def test_www_is_not_the_same_host(monkeypatch) -> None:
    monkeypatch.setattr(indexnow_submit, "safe_requests_get", lambda *_a, **_k: _Response())
    result = indexnow_submit.verify_key_published(
        "example.com", KEY, "https://www.example.com/key.txt"
    )
    assert result["ok"] is False


def test_key_on_a_different_registrable_suffix_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(indexnow_submit, "safe_requests_get", lambda *_a, **_k: _Response())
    result = indexnow_submit.verify_key_published(
        "example.com", KEY, "https://example.com.evil.test/key.txt"
    )
    assert result["ok"] is False
