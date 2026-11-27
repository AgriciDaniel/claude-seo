"""claude-seo can use the person's own gcloud sign-in for Google APIs.

A service account (GOOGLE_APPLICATION_CREDENTIALS) may lack access to a
property the person owns; their `gcloud auth application-default login`
account does have it. These tests never touch the network.
"""

from __future__ import annotations

import json
import os
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


def test_cloudsdk_config_expands_a_leading_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("CLOUDSDK_CONFIG", "~/gcloud-xyz")
    expected = os.path.join(str(tmp_path), "gcloud-xyz", "application_default_credentials.json")
    assert os.path.normpath(google_auth._gcloud_adc_path()) == os.path.normpath(expected)


def _config(**fields) -> None:
    Path(google_auth.CONFIG_PATH).write_text(json.dumps({"api_key": "k", **fields}))


GCLOUD_ONLY = ["PageSpeed Insights", "CrUX", "CrUX History", "Search Console", "URL Inspection", "Sitemaps"]


@pytest.mark.parametrize("choice", ["", "adc"])
@pytest.mark.parametrize("property_id", [None, "123456789"])
def test_a_gcloud_sign_in_counts_toward_the_credential_tier(isolated, monkeypatch, choice, property_id):
    # The agent picks its workflow from this tier, so a gcloud-only person
    # rated tier 0 would never get Search Console data. The documented gcloud
    # login grants neither the Analytics nor the Indexing scope, so GA4 and the
    # Indexing API stay out even when a property is set.
    if choice:
        monkeypatch.setenv("CLAUDE_SEO_GOOGLE_AUTH", choice)
    _adc(isolated)
    _config(**({"ga4_property_id": property_id} if property_id else {}))
    tier = google_auth.detect_tier()
    assert tier["tier"] == 1
    assert tier["capabilities"] == GCLOUD_ONLY
    assert "--auth" in tier["missing"]


def test_a_saved_sign_in_used_before_gcloud_keeps_ga4_and_indexing(isolated):
    # gcloud is only the fallback here: the saved OAuth token is what is used.
    _adc(isolated)
    Path(google_auth.TOKEN_PATH).write_text(json.dumps({"access_token": "at", "refresh_token": "rt", "expires_at": 9e9}))
    _config(ga4_property_id="123456789")
    tier = google_auth.detect_tier()
    assert tier["tier"] == 2
    assert tier["capabilities"] == [*GCLOUD_ONLY, "Indexing API", "GA4 Organic Traffic"]


def test_without_a_gcloud_sign_in_an_api_key_stays_tier_0(isolated):
    _config(ga4_property_id="123456789")
    assert google_auth.detect_tier()["tier"] == 0


def test_a_service_account_in_the_gcloud_file_does_not_raise_the_tier(isolated):
    _adc(isolated, kind="service_account")
    _config()
    assert google_auth.detect_tier()["tier"] == 0
