"""youtube_search never prints the API key (GHSA-xgff-93hv-6369).

google-api-python-client sends the key as a ``key=`` query parameter and its
errors can quote the request URL. Every path that turns an exception into
stdout, stderr or JSON text must redact it first.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("googleapiclient")
import youtube_search  # noqa: E402

SECRET = "AI" + "zaSyDUMMYYOUTUBESECRET"
ODD_SECRET = "not-a-standard-looking-key-0123456789"
QUERY_KEY_ASSIGNMENT = "ke" + "y="


def _leaky_error(key: str, status: int = 500) -> Exception:
    return RuntimeError(
        f"<HttpError {status} when requesting "
        f"https://youtube.googleapis.com/youtube/v3/search?part=snippet&q=x&"
        f"{QUERY_KEY_ASSIGNMENT}{key}&alt=json returned \"backend error ({key})\">"
    )


class _FailingService:
    """Every request raises an error that quotes the request URL."""

    def __init__(self, key: str, status: int = 500) -> None:
        self._key = key
        self._status = status

    def __getattr__(self, _name):
        return lambda *args, **kwargs: self

    def execute(self):
        raise _leaky_error(self._key, self._status)


def _use_failing_service(monkeypatch, status: int = 500) -> None:
    monkeypatch.setattr(
        youtube_search, "build",
        lambda *args, developerKey=None, **kwargs: _FailingService(developerKey, status),
    )


CALLS = [
    lambda key: youtube_search.search_videos("seo", api_key=key),
    lambda key: youtube_search.get_video_details("dQw4w9WgXcQ", api_key=key),
    lambda key: youtube_search.get_channel_info("UC123", api_key=key),
]


@pytest.mark.parametrize("call", CALLS)
@pytest.mark.parametrize("key", [SECRET, ODD_SECRET])
def test_api_errors_do_not_carry_the_key(monkeypatch, call, key) -> None:
    _use_failing_service(monkeypatch)
    result = call(key)
    dumped = json.dumps(result, default=str)
    assert result["error"]
    assert key not in dumped
    assert QUERY_KEY_ASSIGNMENT not in dumped
    # The rest of the message is kept, so the error stays useful.
    assert "backend error" in dumped


def test_configured_key_is_redacted_too(monkeypatch) -> None:
    # No api_key argument: the key comes from the config or environment.
    monkeypatch.setattr(youtube_search, "get_api_key", lambda: ODD_SECRET)
    _use_failing_service(monkeypatch)
    result = youtube_search.get_channel_info("UC123")
    assert result["error"] and ODD_SECRET not in json.dumps(result)


def test_403_and_429_keep_their_fixed_messages(monkeypatch) -> None:
    _use_failing_service(monkeypatch, status=403)
    assert "access denied" in youtube_search.search_videos("seo", api_key=SECRET)["error"]
    _use_failing_service(monkeypatch, status=429)
    assert "quota exceeded" in youtube_search.search_videos("seo", api_key=SECRET)["error"]


@pytest.mark.parametrize("key", [SECRET, ODD_SECRET])
def test_build_failure_does_not_print_the_key(monkeypatch, capsys, key) -> None:
    def build(*args, developerKey=None, **kwargs):
        raise _leaky_error(developerKey)

    monkeypatch.setattr(youtube_search, "build", build)
    result = youtube_search.search_videos("seo", api_key=key)
    captured = capsys.readouterr()
    assert result["error"]
    assert "Error building YouTube service" in captured.err
    for text in (captured.out, captured.err, json.dumps(result)):
        assert key not in text
        assert QUERY_KEY_ASSIGNMENT not in text


@pytest.mark.parametrize("json_flag", [[], ["--json"]])
def test_cli_output_does_not_carry_the_key(monkeypatch, capsys, json_flag) -> None:
    _use_failing_service(monkeypatch)
    monkeypatch.setattr(
        sys, "argv", ["youtube_search.py", "video", "dQw4w9WgXcQ", "--api-key", SECRET, *json_flag]
    )
    if json_flag:
        youtube_search.main()
    else:
        with pytest.raises(SystemExit):
            youtube_search.main()
    captured = capsys.readouterr()
    assert "YouTube API error" in captured.err
    for text in (captured.out, captured.err):
        assert SECRET not in text
        assert QUERY_KEY_ASSIGNMENT not in text
