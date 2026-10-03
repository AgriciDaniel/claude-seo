"""claude-seo can use the person's own gcloud sign-in for Google APIs.

A service account (GOOGLE_APPLICATION_CREDENTIALS) may lack access to a
property the person owns; their `gcloud auth application-default login`
account does have it. These tests never touch the network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_auth  # noqa: E402


def _adc(tmp_path: Path, kind: str = "authorized_user") -> Path:
    data = {"type": kind, "client_id": "id", "client_secret": "s", "refresh_token": "r", "account": "person@example.com"}
    (tmp_path / "application_default_credentials.json").write_text(json.dumps(data))
    return tmp_path


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(google_auth, "CONFIG_PATH", str(tmp_path / "google-api.json"))
    monkeypatch.setattr(google_auth, "TOKEN_PATH", str(tmp_path / "oauth-token.json"))
    for name in ("GOOGLE_APPLICATION_CREDENTIALS", "CLAUDE_SEO_GOOGLE_AUTH", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    gcloud = tmp_path / "gcloud"
    gcloud.mkdir()
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(gcloud))
    return gcloud


def test_gcloud_user_sign_in_is_found(isolated):
    _adc(isolated)
    assert google_auth._load_gcloud_adc()["account"] == "person@example.com"


def test_a_service_account_in_the_gcloud_file_is_not_the_person(isolated):
    _adc(isolated, kind="service_account")
    assert google_auth._load_gcloud_adc() is None


def test_gcloud_is_the_fallback_when_nothing_else_is_configured(isolated):
    _adc(isolated)
    creds = google_auth.get_oauth_credentials(["https://www.googleapis.com/auth/webmasters.readonly"])
    assert creds is not None and creds.refresh_token == "r"
    check = google_auth.check_credentials("gsc")
    assert check["available"] and check["method"] == "gcloud_adc" and check["account"] == "person@example.com"


def test_explicit_choice_beats_a_configured_service_account(isolated, monkeypatch, tmp_path):
    _adc(isolated)
    sa = tmp_path / "sa.json"
    sa.write_text(json.dumps({"type": "service_account", "client_email": "bot@x.iam.gserviceaccount.com", "private_key": "k"}))
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(sa))
    assert google_auth.check_credentials("gsc")["method"] == "service_account"
    monkeypatch.setenv("CLAUDE_SEO_GOOGLE_AUTH", "adc")
    assert google_auth.check_credentials("gsc")["method"] == "gcloud_adc"
    creds = google_auth.get_oauth_credentials(["https://www.googleapis.com/auth/webmasters.readonly"])
    assert creds is not None and getattr(creds, "refresh_token", None) == "r"


def test_no_sign_in_anywhere_still_explains_the_options(isolated):
    check = google_auth.check_credentials("gsc")
    assert not check["available"] and "service account" in check["error"]
