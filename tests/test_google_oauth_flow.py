"""The Google sign-in flow (--auth / --exchange) is bound to the run that started it.

state rejects forged or stray redirects, PKCE (S256) binds the code to this
machine, and both token calls carry a timeout. These tests run a real local
redirect server on a free port and never touch Google.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_auth  # noqa: E402

CLIENT = {
    "client_id": "client-id.apps.googleusercontent.com",
    "client_secret": "client-secret",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(google_auth, "CONFIG_PATH", str(tmp_path / "google-api.json"))
    monkeypatch.setattr(google_auth, "TOKEN_PATH", str(tmp_path / "oauth-token.json"))
    monkeypatch.setattr(google_auth, "OAUTH_REDIRECT_URI", f"http://localhost:{_free_port()}")
    creds = tmp_path / "client_secret.json"
    creds.write_text(json.dumps({"installed": CLIENT}))
    return creds


class _TokenResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


def _fake_urlopen(calls: list):
    def urlopen(req, timeout=None):
        calls.append({"url": req.full_url, "data": urllib.parse.parse_qs(req.data.decode()), "timeout": timeout})
        return _TokenResponse({"access_token": "at", "refresh_token": "rt", "expires_in": 3600})
    return urlopen


def _get(url: str, timeout: float = 5) -> int:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def _run_flow_with_browser(isolated, monkeypatch, browser):
    """Run run_oauth_flow with ``browser(auth_url)`` standing in for the person."""
    exchanged = {}
    monkeypatch.setattr(
        google_auth, "_exchange_code",
        lambda client, code, creds_path=None, code_verifier=None: exchanged.update(
            code=code, code_verifier=code_verifier
        ),
    )
    opened = {}

    def open_browser(url):
        opened["url"] = url
        opened["thread"] = threading.Thread(target=browser, args=(url,), daemon=True)
        opened["thread"].start()
        return True

    monkeypatch.setattr("webbrowser.open", open_browser)
    try:
        google_auth.run_oauth_flow(str(isolated))
    finally:
        # The flow returns once the server has answered; let the "browser"
        # finish reading that answer before the test inspects it.
        if "thread" in opened:
            opened["thread"].join(timeout=30)
    return opened["url"], exchanged


def _redirect(url_params: dict) -> str:
    return f"{google_auth.OAUTH_REDIRECT_URI}/?{urllib.parse.urlencode(url_params)}"


def test_auth_url_carries_state_and_s256_challenge(isolated, monkeypatch):
    def browser(url):
        state = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["state"][0]
        _get(_redirect({"state": state, "code": "the-code"}))

    url, exchanged = _run_flow_with_browser(isolated, monkeypatch, browser)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["client_id"] == [CLIENT["client_id"]]
    assert q["redirect_uri"] == [google_auth.OAUTH_REDIRECT_URI]
    assert q["code_challenge_method"] == ["S256"]
    assert len(q["state"][0]) >= 32
    verifier = exchanged["code_verifier"]
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert q["code_challenge"] == [expected]
    assert 43 <= len(verifier) <= 128
    assert exchanged["code"] == "the-code"


def test_stray_and_forged_requests_do_not_end_the_wait(isolated, monkeypatch):
    statuses = []

    def browser(url):
        state = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["state"][0]
        statuses.append(_get(f"{google_auth.OAUTH_REDIRECT_URI}/favicon.ico"))
        statuses.append(_get(_redirect({"state": "forged", "code": "attacker-code"})))
        statuses.append(_get(_redirect({"code": "no-state-code"})))
        statuses.append(_get(_redirect({"state": state, "code": "real-code"})))

    _url, exchanged = _run_flow_with_browser(isolated, monkeypatch, browser)
    assert statuses == [400, 400, 400, 200]
    assert exchanged["code"] == "real-code"


def test_a_silent_connection_does_not_block_the_real_redirect(isolated, monkeypatch):
    monkeypatch.setattr(google_auth, "OAUTH_WAIT_SECONDS", 30)
    monkeypatch.setattr(google_auth, "OAUTH_REQUEST_TIMEOUT", 1)
    port = urllib.parse.urlparse(google_auth.OAUTH_REDIRECT_URI).port
    idle = []

    def browser(url):
        state = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["state"][0]
        idle.append(socket.create_connection(("localhost", port)))  # connects, sends nothing
        # The server drops the idle connection after OAUTH_REQUEST_TIMEOUT.
        _get(_redirect({"state": state, "code": "real-code"}), timeout=20)

    started = time.monotonic()
    _url, exchanged = _run_flow_with_browser(isolated, monkeypatch, browser)
    for sock in idle:
        sock.close()
    assert exchanged["code"] == "real-code"
    assert time.monotonic() - started < 15


def test_google_error_with_our_state_stops_and_clears_the_pending_flow(isolated, monkeypatch, capsys):
    def browser(url):
        state = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["state"][0]
        _get(_redirect({"state": state, "error": "access_denied"}))

    with pytest.raises(SystemExit):
        _run_flow_with_browser(isolated, monkeypatch, browser)
    assert "access_denied" in capsys.readouterr().err
    assert google_auth._load_pending_flow() is None


def test_timeout_keeps_the_pending_flow_for_manual_exchange(isolated, monkeypatch):
    monkeypatch.setattr(google_auth, "OAUTH_WAIT_SECONDS", 1)
    with pytest.raises(SystemExit):
        _run_flow_with_browser(isolated, monkeypatch, lambda url: None)
    pending = google_auth._load_pending_flow()
    assert pending and pending["code_verifier"] and pending["state"]
    path = google_auth._pending_flow_path()
    if os.name == "posix":
        assert os.stat(path).st_mode & 0o777 == 0o600


def test_manual_exchange_checks_state_of_a_pasted_url(isolated):
    google_auth._save_pending_flow("good-state", "v" * 64)
    code, verifier, error = google_auth._manual_exchange_inputs(_redirect({"state": "good-state", "code": "c1"}))
    assert (code, verifier, error) == ("c1", "v" * 64, None)
    code, verifier, error = google_auth._manual_exchange_inputs(_redirect({"state": "other", "code": "c2"}))
    assert code is None and "pending sign-in" in error
    code, verifier, error = google_auth._manual_exchange_inputs("bare-code")
    assert (code, verifier, error) == ("bare-code", "v" * 64, None)


def test_expired_pending_flow_is_refused(isolated, monkeypatch):
    google_auth._save_pending_flow("s", "v" * 64)
    real_time = time.time
    monkeypatch.setattr(google_auth.time, "time", lambda: real_time() + google_auth.OAUTH_PENDING_MAX_AGE + 5)
    assert google_auth._load_pending_flow() is None
    assert not os.path.exists(google_auth._pending_flow_path())


def test_exchange_sends_verifier_with_timeout_and_clears_pending(isolated, monkeypatch):
    google_auth._save_pending_flow("s", "v" * 64)
    calls: list = []
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(calls))
    google_auth._exchange_code(CLIENT, "the-code", None, "v" * 64)
    assert calls[0]["data"]["code_verifier"] == ["v" * 64]
    assert calls[0]["timeout"] == 30
    assert google_auth._load_pending_flow() is None
    token = json.loads(Path(google_auth.TOKEN_PATH).read_text())
    assert "client_secret" not in token and token["access_token"] == "at"


def test_refresh_passes_a_timeout(isolated, monkeypatch):
    calls: list = []
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(calls))
    refreshed = google_auth._refresh_oauth_token(CLIENT, {"refresh_token": "rt"})
    assert refreshed and refreshed["access_token"] == "at"
    assert calls[0]["timeout"] == 30
