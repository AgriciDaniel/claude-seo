"""The Google sign-in asks for the least it needs (GHSA-xhpf-w7hf-f6ph).

The default --auth is read-only. The Indexing API scope is granted only with
--auth --indexing, the unused Search Console write scope is gone, a token
saved by an earlier version keeps working, and indexing_notify.py names the
command to run when the saved sign-in lacks the Indexing scope instead of
passing on a raw 403. Nothing here touches Google.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_auth  # noqa: E402

READ_GSC = "https://www.googleapis.com/auth/webmasters.readonly"
WRITE_GSC = "https://www.googleapis.com/auth/webmasters"
READ_GA4 = "https://www.googleapis.com/auth/analytics.readonly"
INDEXING = "https://www.googleapis.com/auth/indexing"
OPT_IN = "--auth --indexing"


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(google_auth, "CONFIG_PATH", str(tmp_path / "google-api.json"))
    monkeypatch.setattr(google_auth, "TOKEN_PATH", str(tmp_path / "oauth-token.json"))
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path / "no-gcloud"))
    for name in ("CLAUDE_SEO_GOOGLE_AUTH", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def _save_token(tmp_path, scope) -> None:
    token = {
        "access_token": "at",
        "refresh_token": "rt",
        "expires_at": time.time() + 3600,
        "client_id": "client-id.apps.googleusercontent.com",
    }
    if scope is not None:
        token["scope"] = scope
    (tmp_path / "oauth-token.json").write_text(json.dumps(token))


def test_default_scopes_are_read_only() -> None:
    assert set(google_auth.OAUTH_SCOPES.split()) == {READ_GSC, READ_GA4}
    assert set(google_auth.oauth_scopes().split()) == {READ_GSC, READ_GA4}


def test_opt_in_adds_only_the_indexing_scope() -> None:
    assert set(google_auth.oauth_scopes(include_indexing=True).split()) == {
        READ_GSC, READ_GA4, INDEXING,
    }


def test_search_console_write_scope_is_not_defined() -> None:
    assert "gsc_write" not in google_auth.SCOPES
    assert WRITE_GSC not in google_auth.SCOPES.values()
    assert WRITE_GSC not in google_auth.oauth_scopes(include_indexing=True).split()


def test_cli_passes_the_opt_in_to_the_flow(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        google_auth, "run_oauth_flow",
        lambda creds, include_indexing=False: calls.append((creds, include_indexing)),
    )
    monkeypatch.setattr(sys, "argv", ["google_auth.py", "--auth", "--creds", "c.json"])
    google_auth.main()
    monkeypatch.setattr(sys, "argv", ["google_auth.py", "--auth", "--indexing", "--creds", "c.json"])
    google_auth.main()
    assert calls == [("c.json", False), ("c.json", True)]


def test_indexing_flag_without_auth_is_an_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["google_auth.py", "--indexing"])
    with pytest.raises(SystemExit) as exc:
        google_auth.main()
    assert exc.value.code == 1
    assert "--auth" in capsys.readouterr().err


def test_token_from_an_earlier_version_keeps_working(isolated) -> None:
    pytest.importorskip("google.oauth2.credentials")
    _save_token(isolated, f"{INDEXING} {WRITE_GSC} {READ_GA4}")
    creds = google_auth.get_oauth_credentials([READ_GSC])
    assert creds is not None and creds.token == "at"
    assert google_auth.check_credentials("gsc")["available"] is True
    # It was granted the Indexing scope, so that keeps working too.
    assert google_auth.indexing_scope_error() is None
    assert google_auth.check_credentials("indexing")["available"] is True
    assert "Indexing API" in google_auth.detect_tier()["capabilities"]


def test_token_without_recorded_scopes_is_not_refused(isolated) -> None:
    _save_token(isolated, None)
    assert google_auth.indexing_scope_error() is None
    assert google_auth.check_credentials("indexing")["available"] is True


def test_read_only_token_is_reported_with_the_command(isolated) -> None:
    _save_token(isolated, f"{READ_GSC} {READ_GA4}")
    message = google_auth.indexing_scope_error()
    assert message and OPT_IN in message and INDEXING in message
    assert google_auth.check_credentials("gsc")["available"] is True
    indexing = google_auth.check_credentials("indexing")
    assert indexing["available"] is False
    assert OPT_IN in indexing["error"]
    assert "Indexing API" not in google_auth.detect_tier()["capabilities"]


def test_readonly_scope_does_not_count_as_a_prefix_match(isolated) -> None:
    # "webmasters" must not be read out of "webmasters.readonly".
    assert google_auth._token_has_scope({"scope": READ_GSC}, WRITE_GSC) is False
    assert google_auth._token_has_scope({"scope": [READ_GSC, INDEXING]}, INDEXING) is True


class TestIndexingNotify:
    @pytest.fixture
    def notify(self, isolated, monkeypatch):
        pytest.importorskip("googleapiclient")
        import indexing_notify

        monkeypatch.setattr(indexing_notify, "validate_url", lambda url: True)
        monkeypatch.setattr(indexing_notify.time, "sleep", lambda *_: None)
        return indexing_notify

    def test_read_only_sign_in_gets_a_clear_message_and_no_api_call(
        self, notify, isolated, monkeypatch
    ) -> None:
        _save_token(isolated, f"{READ_GSC} {READ_GA4}")
        monkeypatch.setattr(
            notify, "_build_indexing_service",
            lambda: pytest.fail("the API must not be called without the scope"),
        )
        result = notify.notify_url("https://example.com/jobs/1")
        assert result["error_code"] == "missing_indexing_scope"
        assert OPT_IN in result["error"]
        assert "403" not in result["error"]
        status = notify.get_notification_metadata("https://example.com/jobs/1")
        assert status["error_code"] == "missing_indexing_scope"
        assert OPT_IN in status["error"]

    def test_batch_stops_at_the_first_missing_scope_error(self, notify, isolated) -> None:
        _save_token(isolated, f"{READ_GSC} {READ_GA4}")
        result = notify.batch_notify(["https://example.com/1", "https://example.com/2"], delay=0)
        assert len(result["results"]) == 1
        assert OPT_IN in result["error"]

    def test_scope_403_from_google_is_translated(self, notify, isolated, monkeypatch) -> None:
        # No recorded scopes, so the request is made and Google answers 403.
        _save_token(isolated, None)

        class _Service:
            def urlNotifications(self):
                return self

            def publish(self, body):
                return self

            def execute(self):
                raise RuntimeError(
                    '<HttpError 403 "Request had insufficient authentication scopes." '
                    "Details: ACCESS_TOKEN_SCOPE_INSUFFICIENT>"
                )

        monkeypatch.setattr(notify, "_build_indexing_service", lambda: _Service())
        result = notify.notify_url("https://example.com/jobs/1")
        assert result["error_code"] == "missing_indexing_scope"
        assert OPT_IN in result["error"]

    def test_owner_403_keeps_its_own_message(self, notify, isolated, monkeypatch) -> None:
        _save_token(isolated, f"{READ_GSC} {INDEXING}")

        class _Service:
            def urlNotifications(self):
                return self

            def publish(self, body):
                return self

            def execute(self):
                raise RuntimeError('<HttpError 403 "Permission denied. Failed to verify the URL ownership.">')

        monkeypatch.setattr(notify, "_build_indexing_service", lambda: _Service())
        result = notify.notify_url("https://example.com/jobs/1")
        assert "error_code" not in result
        assert "Owner" in result["error"]


def test_docs_list_the_scopes_the_code_requests() -> None:
    doc = (
        Path(__file__).resolve().parents[1]
        / "skills" / "seo-google" / "references" / "auth-setup.md"
    ).read_text(encoding="utf-8")
    for scope in google_auth.oauth_scopes(include_indexing=True).split():
        assert f"`{scope}`" in doc
    assert f"| `{WRITE_GSC}` |" not in doc
    assert OPT_IN in doc
