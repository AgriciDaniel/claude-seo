import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import indexnow_submit  # noqa: E402


@pytest.mark.parametrize(
    ("key", "url", "post_error", "expected"),
    [
        ("short", "https://example.com/a", None, "key must be"),
        ("validkey", "https://other.test/a", None, "don't belong to host"),
        ("validkey", "https://example.com/a", "offline", "HTTP error: offline"),
    ],
)
def test_text_output_reports_submission_errors(monkeypatch, capsys, key, url, post_error, expected):
    monkeypatch.setattr(
        sys, "argv", ["indexnow_submit.py", "--host", "example.com", "--key", key,
                      "--key-location", "https://example.com/key.txt", "--urls", url]
    )
    monkeypatch.setattr(indexnow_submit, "verify_key_published", lambda *_: {"ok": True})
    monkeypatch.setattr(indexnow_submit, "validate_url_strict", lambda _: None)
    with patch.object(requests, "post", side_effect=requests.ConnectionError(post_error)):
        assert indexnow_submit.main() == 1
    output = capsys.readouterr().out
    assert "IndexNow: FAIL" in output
    assert expected in output


def test_json_output_preserves_error_details(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["indexnow_submit.py", "--host", "example.com", "--key", "short",
                      "--key-location", "https://example.com/key.txt", "--urls",
                      "https://example.com/a", "--json"]
    )
    monkeypatch.setattr(indexnow_submit, "verify_key_published", lambda *_: {"ok": True})
    assert indexnow_submit.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert "key must be" in result["error"]


def test_text_output_keeps_endpoint_when_server_responds(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["indexnow_submit.py", "--host", "example.com", "--key", "validkey",
                      "--key-location", "https://example.com/key.txt", "--urls",
                      "https://example.com/a"]
    )
    monkeypatch.setattr(indexnow_submit, "verify_key_published", lambda *_: {"ok": True})
    monkeypatch.setattr(indexnow_submit, "validate_url_strict", lambda _: None)
    with patch.object(requests, "post") as post:
        post.return_value.status_code = 202
        post.return_value.text = ""
        assert indexnow_submit.main() == 0
    output = capsys.readouterr().out
    assert "Submitted: 1 URLs to https://api.indexnow.org/indexnow" in output
