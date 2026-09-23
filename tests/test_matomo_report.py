"""Tests for the Matomo extension (scripts/matomo_auth.py, scripts/matomo_report.py).

Covers:
- Envelope shape (status / data / error / metadata)
- Auth probe (HTTP error classes mapped to friendly error messages)
- Token never appears in output / URL parameters
- URL shape check (allows self-hosted, rejects malformed)
- SSRF: every request goes through url_safety's pinned helpers; a private
  instance needs CLAUDE_SEO_LOCAL_TARGETS; redirects off the instance refused
- Env-var and config-file credential loading (env wins over file when both set)
- Credential storage: 0600, atomic, argv-based, never in ~/.claude/settings.json
- Args / CLI error paths surface a structured error envelope
- Token redaction of incoming Matomo ``result=error`` messages
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import matomo_auth  # noqa: E402
import matomo_report  # noqa: E402
import url_safety  # noqa: E402

SECRET_TOKEN = "abcdef0123456789abcdef0123456789"
PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def _isolated_credentials(monkeypatch, tmp_path):
    """Isolate tests from both env vars and any real config file.

    A developer machine may have ~/.config/claude-seo/matomo.json with
    live credentials; without config isolation, CLI tests would pick it
    up and make real network calls. CONFIG_PATH points at a missing
    tmp file by default; tests that need a config file monkeypatch it
    themselves (later setattr wins over this fixture).
    """
    for k in ("MATOMO_URL", "MATOMO_API_TOKEN", "MATOMO_TOKEN",
              "MATOMO_SITE_ID", "MATOMO_IDSITE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(
        matomo_auth, "CONFIG_PATH", str(tmp_path / "missing-matomo.json")
    )


def _mock_response(status_code: int, body, headers=None) -> Mock:
    resp = Mock(status_code=status_code, text=json.dumps(body))
    resp.json.return_value = body
    resp.headers = headers or {}
    return resp


@contextlib.contextmanager
def _patch_session(response=None, side_effect=None):
    """Stub the DNS-pinned session so transport tests stay offline.

    Patches ``matomo_auth.safe_requests_session``, the single seam every
    Matomo request passes through. The SSRF behaviour of that seam is covered
    separately by the tests that let the real ``url_safety`` run.
    """
    session = Mock()
    if side_effect is not None:
        session.post.side_effect = side_effect
    else:
        session.post.return_value = response

    @contextlib.contextmanager
    def fake_session(url):
        fake_session.url = url
        yield session

    with patch.object(matomo_auth, "safe_requests_session", fake_session):
        yield session, fake_session


@contextlib.contextmanager
def _real_guard(monkeypatch, resolved_ip=PUBLIC_IP, response=None):
    """Let ``url_safety`` run for real, with DNS and the socket write stubbed.

    ``requests.Session.post`` is patched at the class level so the pinned
    session is genuinely constructed and ``validate_url_strict`` genuinely
    decides, but nothing leaves the machine.
    """
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(var, raising=False)

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
                 (resolved_ip, port or 80))]

    monkeypatch.setattr(url_safety.socket, "getaddrinfo", fake_getaddrinfo)
    post = Mock(return_value=response if response is not None
                else _mock_response(200, {"value": "5.13.0"}))

    def _unguarded(*args, **kwargs):
        raise AssertionError(
            "a Matomo request bypassed url_safety: module-level requests.post "
            "was called instead of the pinned session"
        )

    with patch.object(matomo_report.requests.Session, "post", post), \
            patch.object(matomo_report.requests, "post", _unguarded), \
            patch.object(matomo_auth.requests, "post", _unguarded):
        yield post


def _ok_envelope(data=None, method=None):
    return {
        "status": "success",
        "data": data if data is not None else {},
        "error": None,
        "metadata": {"source": "matomo_report",
                     "timestamp": matomo_report.datetime.now(
                         matomo_report.timezone.utc
                     ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     **({"method": method} if method else {})},
    }


def test_envelope_shape_and_metadata_source():
    """Every result envelope is {status, data, error, metadata:{source, ...}}."""
    env = matomo_report._envelope("success", {"x": 1}, None, method="API.getX")
    assert env["status"] == "success"
    assert env["data"] == {"x": 1}
    assert env["error"] is None
    assert env["metadata"]["source"] == "matomo_report"
    assert env["metadata"]["method"] == "API.getX"
    assert "timestamp" in env["metadata"]


def test_url_shape_check_allows_self_hosted_https():
    assert matomo_auth._normalize_instance_url("https://analytics.example.com") \
        == "https://analytics.example.com"
    assert matomo_auth._normalize_instance_url("http://localhost:8080/") \
        == "http://localhost:8080"
    assert matomo_auth._normalize_instance_url("https://10.0.0.5/matomo/") \
        == "https://10.0.0.5/matomo"


def test_url_shape_check_rejects_malformed():
    assert matomo_auth._normalize_instance_url("") is None
    assert matomo_auth._normalize_instance_url("not-a-url") is None
    assert matomo_auth._normalize_instance_url("ftp://example.com") is None
    # Userinfo in URL would leak credentials if accidentally configured.
    assert matomo_auth._normalize_instance_url(
        "https://user:pass@example.com") is None


def test_load_config_falls_back_to_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MATOMO_URL", "https://env.example.com")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)
    monkeypatch.setenv("MATOMO_SITE_ID", "7")
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(tmp_path / "missing.json"))
    cfg = matomo_auth.load_config()
    assert cfg["matomo_url"] == "https://env.example.com"
    assert cfg["matomo_token"] == SECRET_TOKEN
    assert cfg["matomo_site_id"] == "7"


def test_load_config_falls_back_to_file(monkeypatch, tmp_path):
    config_file = tmp_path / "matomo.json"
    config_file.write_text(json.dumps({
        "matomo_url": "https://file.example.com",
        "matomo_token": "file_token_" + "a" * 22,
        "matomo_site_id": "3",
    }))
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(config_file))
    for k in ("MATOMO_URL", "MATOMO_API_TOKEN", "MATOMO_SITE_ID"):
        monkeypatch.delenv(k, raising=False)
    cfg = matomo_auth.load_config()
    assert cfg["matomo_url"] == "https://file.example.com"
    assert cfg["matomo_token"].startswith("file_token_")
    assert cfg["matomo_site_id"] == "3"


def test_check_credentials_unavailable_when_no_url(monkeypatch, tmp_path):
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(tmp_path / "missing.json"))
    status = matomo_auth.check_credentials()
    assert status["available"] is False
    assert "URL" in status["error"] or "url" in status["error"].lower()


def test_check_credentials_unavailable_when_no_token(monkeypatch, tmp_path):
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("MATOMO_URL", "https://analytics.example.com")
    status = matomo_auth.check_credentials()
    assert status["available"] is False
    assert "token_auth" in status["error"] or "token" in status["error"].lower()


def test_check_credentials_probes_version(monkeypatch, tmp_path):
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("MATOMO_URL", "https://analytics.example.com")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)
    monkeypatch.setenv("MATOMO_SITE_ID", "1")

    resp = _mock_response(200, "5.1.2")
    with _patch_session(resp) as (post_session, _):
        status = matomo_auth.check_credentials()

    assert status["available"] is True
    assert status["instance"] == "https://analytics.example.com"
    assert status["site_id"] == "1"
    assert status["verified"] is True
    assert status["version"] == "5.1.2"
    # Token must be in POST body, never in URL.
    call = post_session.post.call_args
    assert call.kwargs["data"]["token_auth"] == SECRET_TOKEN
    assert "token_auth" not in call.kwargs.get("params", {})


def test_check_credentials_handles_matomo5_version_object(monkeypatch, tmp_path):
    """Matomo 5+ returns API.getMatomoVersion as {"value": "5.13.0"}."""
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("MATOMO_URL", "https://analytics.example.com")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)

    resp = _mock_response(200, {"value": "5.13.0"})
    with _patch_session(resp):
        status = matomo_auth.check_credentials()
    assert status["available"] is True
    assert status["version"] == "5.13.0"


def test_check_credentials_surfaces_auth_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("MATOMO_URL", "https://analytics.example.com")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)
    resp = _mock_response(401, {"result": "error", "message": "no access"})
    with _patch_session(resp):
        status = matomo_auth.check_credentials()
    assert status["available"] is False
    assert "authentication" in status["error"].lower() or "auth" in status["error"].lower()
    # Token must not appear in the error message.
    assert SECRET_TOKEN not in status["error"]


def test_check_credentials_surfaces_connection_error(monkeypatch, tmp_path):
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("MATOMO_URL", "https://analytics.example.com")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)
    with _patch_session(side_effect=matomo_auth.requests.exceptions.ConnectionError(
        "refused"
    )):
        status = matomo_auth.check_credentials()
    assert status["available"] is False
    assert "connection" in status["error"].lower()


def test_token_redaction_strips_query_params():
    """Incoming Matomo error messages with token_auth=... get redacted."""
    raw = "API error: token_auth=" + SECRET_TOKEN + "&other=value"
    redacted = matomo_report._redact(raw)
    assert SECRET_TOKEN not in redacted
    assert "<redacted>" in redacted
    assert "other=value" in redacted


def test_request_maps_matomo_result_error_to_envelope():
    resp = _mock_response(200, {"result": "error",
                                "message": "No data available"})
    with _patch_session(resp):
        env = matomo_report._request("https://m.test", "tok", {"method": "X"})
    assert env["status"] == "error"
    assert "No data available" in env["error"]
    assert env["metadata"]["method"] == "X"


def test_request_redacts_token_in_matomo_error():
    leaked = "Bad token_auth=" + SECRET_TOKEN + " for site"
    resp = _mock_response(200, {"result": "error", "message": leaked})
    with _patch_session(resp):
        env = matomo_report._request("https://m.test", "tok", {"method": "X"})
    assert SECRET_TOKEN not in (env.get("error") or "")


def test_request_maps_401_to_friendly_error():
    resp = _mock_response(401, {})
    with _patch_session(resp):
        env = matomo_report._request("https://m.test", "tok", {"method": "X"})
    assert env["status"] == "error"
    assert "authentication" in env["error"].lower() or "token" in env["error"].lower()


def test_request_maps_timeout_to_friendly_error():
    with _patch_session(side_effect=matomo_report.requests.exceptions.Timeout(
        "read timeout"
    )):
        env = matomo_report._request("https://m.test", "tok", {"method": "X"})
    assert env["status"] == "error"
    assert "timed out" in env["error"].lower() or "timeout" in env["error"].lower()


def test_request_does_not_echo_token_in_call_args():
    resp = _mock_response(200, "5.1.2")
    with _patch_session(resp) as (session, _):
        matomo_report._request("https://m.test", SECRET_TOKEN, {"method": "X"})
    call = session.post.call_args
    assert call.kwargs["data"]["token_auth"] == SECRET_TOKEN
    # No query params; token is POST body only.
    assert "params" not in call.kwargs or not call.kwargs["params"]
    # And never in the URL either.
    assert SECRET_TOKEN not in call.args[0]


def test_cli_errors_when_url_missing(monkeypatch):
    """`--check` with no configured URL returns a friendly error envelope."""
    for k in ("MATOMO_URL", "MATOMO_API_TOKEN", "MATOMO_SITE_ID",
              "MATOMO_TOKEN", "MATOMO_IDSITE"):
        monkeypatch.delenv(k, raising=False)
    with _patch_session(_mock_response(200, {"value": "5.13.0"})) as (post_session, _):
        env = matomo_auth.check_credentials()
    assert env["available"] is False
    assert "url" in env["error"].lower()
    post_session.post.assert_not_called()


def test_organic_report_builds_daily_and_pages(monkeypatch):
    """organic_traffic_report rolls daily VisitsSummary into totals + pages.

    Uses the real Matomo 5 shapes: date-keyed object for the daily summary,
    JSON array with entry_* fields for entry pages (no precomputed rate).
    """
    daily = {
        "2026-01-01": {"nb_visits": 100, "nb_uniq_visitors": 80,
                       "nb_actions": 150, "nb_pageviews": 200,
                       "bounce_count": 30, "sum_visit_length": 6000},
        "2026-01-02": {"nb_visits": 50, "nb_uniq_visitors": 40,
                       "nb_actions": 80, "nb_pageviews": 100,
                       "bounce_count": 10, "sum_visit_length": 3000},
    }
    pages = [
        {"label": "en", "nb_visits": 146, "nb_hits": 181,
         "entry_nb_visits": 111, "entry_nb_actions": 583,
         "entry_bounce_count": 23},
        {"label": "blog", "nb_visits": 90, "nb_hits": 120,
         "entry_nb_visits": 60, "entry_nb_actions": 240,
         "entry_bounce_count": 6},
    ]
    responses = [
        _mock_response(200, daily),
        _mock_response(200, pages),
    ]
    with _patch_session(side_effect=responses):
        env = matomo_report.organic_traffic_report("1", "https://m.test",
                                                    SECRET_TOKEN, days=2)
    assert env["status"] == "success"
    data = env["data"]
    assert data["site_id"] == "1"
    assert data["totals"]["visits"] == 150
    assert data["totals"]["unique_visitors"] == 120
    assert len(data["daily_data"]) == 2
    assert data["daily_data"][0]["bounce_rate"] == 30.0
    assert len(data["top_pages"]) == 2
    top = data["top_pages"][0]
    assert top["url"] == "en"
    assert top["visits"] == 146
    assert top["actions"] == 583
    assert top["hits"] == 181
    # 23 bounces / 111 entry visits
    assert top["bounce_rate"] == 20.7
    assert top["bounce_rate"] == round(23 / 111 * 100, 1)


def test_device_breakdown_handles_matomo5_array(monkeypatch):
    """DevicesDetection.getType returns a JSON array with bounce_count."""
    raw = [
        {"label": "Desktop", "nb_visits": 672, "nb_actions": 6222,
         "bounce_count": 250, "sum_daily_nb_uniq_visitors": 549},
        {"label": "Smartphone", "nb_visits": 214, "nb_actions": 680,
         "bounce_count": 81, "sum_daily_nb_uniq_visitors": 190},
        {"label": "Tablet", "nb_visits": 20, "nb_actions": 60,
         "bounce_count": 3, "sum_daily_nb_uniq_visitors": 18},
    ]
    with _patch_session(_mock_response(200, raw)):
        env = matomo_report.device_breakdown("1", "https://m.test",
                                             SECRET_TOKEN, days=7)
    assert env["status"] == "success"
    devices = env["data"]["devices"]
    assert [d["device_type"] for d in devices] == ["Desktop", "Smartphone", "Tablet"]
    assert devices[0]["unique_visitors"] == 549
    # 250 / 672 = 37.2%
    assert devices[0]["bounce_rate"] == round(250 / 672 * 100, 1)


def test_country_breakdown_handles_matomo5_array(monkeypatch):
    """UserCountry.getCountry returns an array with a ``code`` field and
    localized labels; country_code comes from ``code``, not the array index."""
    raw = [
        {"label": "Deutschland", "code": "de", "nb_visits": 434,
         "sum_daily_nb_uniq_visitors": 374},
        {"label": "Vereinigte Staaten", "code": "us", "nb_visits": 79,
         "sum_daily_nb_uniq_visitors": 70},
    ]
    with _patch_session(_mock_response(200, raw)):
        env = matomo_report.country_breakdown("1", "https://m.test",
                                              SECRET_TOKEN, days=7, limit=5)
    assert env["status"] == "success"
    countries = env["data"]["countries"]
    assert [c["country_code"] for c in countries] == ["de", "us"]
    assert countries[0]["country"] == "Deutschland"
    assert countries[0]["unique_visitors"] == 374


def test_referrers_report_uses_matomo5_method_and_shapes(monkeypatch):
    """Referrers.getReferrerType (singular) is the real method name; rows
    arrive as an array with localized labels and machine-readable segment."""
    types = [
        {"label": "Direkte Zugriffe", "nb_visits": 535, "nb_actions": 3991,
         "bounce_count": 280, "sum_daily_nb_uniq_visitors": 426,
         "segment": "referrerType==direct", "referrer_type": "1"},
        {"label": "Suchmaschinen", "nb_visits": 314, "nb_actions": 2443,
         "bounce_count": 51, "sum_daily_nb_uniq_visitors": 290,
         "segment": "referrerType==search", "referrer_type": "2"},
    ]
    engines = [
        {"label": "Google", "nb_visits": 142},
        {"label": "Bing", "nb_visits": 95},
    ]
    with _patch_session(side_effect=[_mock_response(200, types),
                                     _mock_response(200, engines)]) as (post_session, _):
        env = matomo_report.referrers_report("1", "https://m.test",
                                             SECRET_TOKEN, days=7)
    assert env["status"] == "success"
    # Correct Matomo 4/5 method name (getReferrersType does not exist).
    first_method = post_session.post.call_args_list[0].kwargs["data"]["method"]
    assert first_method == "Referrers.getReferrerType"
    channels = env["data"]["channels"]
    assert [c["channel_code"] for c in channels] == ["direct", "search"]
    assert channels[0]["channel"] == "Direkte Zugriffe"
    assert channels[0]["unique_visitors"] == 426
    engines_out = env["data"]["search_engines"]
    assert [e["search_engine"] for e in engines_out] == ["Google", "Bing"]


def test_keywords_report_flags_anonymized_share(monkeypatch):
    """Anonymized keywords collapse into one "(not provided)" row.

    Real Matomo 5 shape: JSON array; the localized label
    ("Suchbegriff nicht definiert") and the locale-independent segment
    (``referrerKeyword==``) both mark anonymized rows.
    """
    raw = [
        {"label": "Suchbegriff nicht definiert", "nb_visits": 80,
         "segment": "referrerType==search;referrerKeyword=="},
        {"label": "(no keyword)", "nb_visits": 5,
         "segment": "referrerType==search;referrerKeyword=="},
        {"label": "kw1", "nb_visits": 10,
         "segment": "referrerType==search;referrerKeyword==kw1"},
        {"label": "kw2", "nb_visits": 5,
         "segment": "referrerType==search;referrerKeyword==kw2"},
    ]
    with _patch_session(_mock_response(200, raw)):
        env = matomo_report.keywords_report("1", "https://m.test",
                                            SECRET_TOKEN, days=7, limit=10)
    assert env["status"] == "success"
    data = env["data"]
    assert data["anonymized_share_pct"] == 85.0
    assert "anonymization" in data["note"].lower()
    anonymized = [k for k in data["keywords"] if k["keyword"] == "(not provided)"]
    assert len(anonymized) == 1
    assert anonymized[0]["visits"] == 85
    # Real keywords keep their own rows, sorted by visits.
    real = [k for k in data["keywords"] if k["keyword"] != "(not provided)"]
    assert [(k["keyword"], k["visits"]) for k in real] == [("kw1", 10), ("kw2", 5)]


def test_keywords_report_english_anonymized_label(monkeypatch):
    """English instances label the row "Keyword not defined"."""
    raw = [
        {"label": "Keyword not defined", "nb_visits": 70,
         "segment": "referrerType==search;referrerKeyword=="},
        {"label": "best seo tool", "nb_visits": 30,
         "segment": "referrerType==search;referrerKeyword==best%20seo%20tool"},
    ]
    with _patch_session(_mock_response(200, raw)):
        env = matomo_report.keywords_report("1", "https://m.test",
                                            SECRET_TOKEN, days=7, limit=10)
    data = env["data"]
    assert data["anonymized_share_pct"] == 70.0


def test_device_breakdown_supports_legacy_dict_shape(monkeypatch):
    """Dict-keyed responses (older Matomo / single-row objects) still parse."""
    raw = {
        "desktop": {"label": "Desktop", "nb_visits": 100,
                    "nb_uniq_visitors": 80, "bounce_rate": 0.4},
    }
    with _patch_session(_mock_response(200, raw)):
        env = matomo_report.device_breakdown("1", "https://m.test",
                                             SECRET_TOKEN, days=7)
    assert env["status"] == "success"
    assert env["data"]["devices"][0]["device_type"] == "Desktop"


def test_main_returns_nonzero_on_envelope_error(monkeypatch, capsys):
    """Missing creds -> error envelope -> exit 1."""
    for k in ("MATOMO_URL", "MATOMO_API_TOKEN", "MATOMO_SITE_ID",
              "MATOMO_TOKEN", "MATOMO_IDSITE"):
        monkeypatch.delenv(k, raising=False)
    with patch("sys.argv", ["matomo_report.py", "organic", "--json"]):
        rc = matomo_report.main()
    assert rc == 1
    captured = capsys.readouterr()
    assert "MATOMO_URL" in captured.err or "MATOMO_API_TOKEN" in captured.err


def test_main_json_emits_envelope(monkeypatch):
    monkeypatch.setenv("MATOMO_URL", "https://m.test")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)
    monkeypatch.setenv("MATOMO_SITE_ID", "1")
    with _patch_session(_mock_response(200, "5.1.2")), patch("sys.argv",
             ["matomo_report.py", "check", "--json"]):
        rc = matomo_report.main()
    assert rc == 0


def test_check_command_honors_site_id_override(monkeypatch, tmp_path):
    """`check --site-id N` must surface N even when config has no default."""
    config_file = tmp_path / "matomo.json"
    config_file.write_text(json.dumps({
        "matomo_url": "https://m.test",
        "matomo_token": SECRET_TOKEN,
    }))
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(config_file))
    resp = _mock_response(200, {"value": "5.13.0"})
    with _patch_session(resp):
        env = matomo_report.check_command(site_id_override="5")
    assert env["status"] == "success"
    assert env["data"]["site_id"] == "5"


def test_main_missing_site_id_exits_one(monkeypatch, capsys):
    monkeypatch.setenv("MATOMO_URL", "https://m.test")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)
    monkeypatch.delenv("MATOMO_SITE_ID", raising=False)
    with patch("sys.argv", ["matomo_report.py", "organic", "--json"]):
        rc = matomo_report.main()
    assert rc == 1
    captured = capsys.readouterr()
    assert "--site-id" in captured.err or "MATOMO_SITE_ID" in captured.err


# --------------------------------------------------------------------------
# SSRF: every request to the Matomo instance goes through url_safety.
# These let the real guard run; only DNS and the socket write are stubbed.
# --------------------------------------------------------------------------


def test_public_instance_goes_through_the_pinned_helpers(monkeypatch):
    """A public MATOMO_URL is validated, pinned, and reached."""
    with _real_guard(monkeypatch) as post:
        env = matomo_report._request("https://analytics.example.com",
                                     SECRET_TOKEN, {"method": "API.getX"})
    assert env["status"] == "success"
    assert env["data"] == {"value": "5.13.0"}
    # Went out through the pinned session, not a bare requests.post.
    assert post.call_count == 1
    assert post.call_args.args[0] == "https://analytics.example.com/index.php"
    assert post.call_args.kwargs["allow_redirects"] is False


def test_private_instance_is_refused_without_the_allowlist(monkeypatch):
    """A self-hosted instance on a private address fails closed by default."""
    monkeypatch.delenv(matomo_auth.LOCAL_TARGETS_ENV, raising=False)
    with _real_guard(monkeypatch, resolved_ip="10.0.0.5") as post:
        env = matomo_report._request("http://10.0.0.5:8080", SECRET_TOKEN,
                                     {"method": "API.getX"})
    assert env["status"] == "error"
    assert post.call_count == 0
    assert matomo_auth.LOCAL_TARGETS_ENV in env["error"]
    assert "10.0.0.5:8080" in env["error"]
    assert SECRET_TOKEN not in env["error"]


def test_private_instance_is_accepted_with_the_allowlist(monkeypatch):
    """CLAUDE_SEO_LOCAL_TARGETS is the supported route to a private instance."""
    monkeypatch.setenv(matomo_auth.LOCAL_TARGETS_ENV, "10.0.0.5:8080")
    with _real_guard(monkeypatch, resolved_ip="10.0.0.5") as post:
        env = matomo_report._request("http://10.0.0.5:8080", SECRET_TOKEN,
                                     {"method": "API.getX"})
    assert env["status"] == "success"
    assert post.call_count == 1
    assert post.call_args.args[0] == "http://10.0.0.5:8080/index.php"


def test_allowlist_entry_does_not_open_a_different_private_host(monkeypatch):
    """The allowlist matches exactly; a neighbour on the same subnet stays closed."""
    monkeypatch.setenv(matomo_auth.LOCAL_TARGETS_ENV, "10.0.0.5:8080")
    with _real_guard(monkeypatch, resolved_ip="10.0.0.6") as post:
        env = matomo_report._request("http://10.0.0.6:8080", SECRET_TOKEN,
                                     {"method": "API.getX"})
    assert env["status"] == "error"
    assert post.call_count == 0


def test_redirect_off_the_instance_is_refused(monkeypatch):
    """A 30x to another host is refused, not followed: the pin does not cover it."""
    redirect = _mock_response(
        302, {}, headers={"Location": "https://attacker.example.com/index.php"}
    )
    with _real_guard(monkeypatch, response=redirect) as post:
        env = matomo_report._request("https://analytics.example.com",
                                     SECRET_TOKEN, {"method": "API.getX"})
    assert env["status"] == "error"
    assert "attacker.example.com" in env["error"]
    assert "redirect" in env["error"].lower()
    assert post.call_args.kwargs["allow_redirects"] is False
    assert SECRET_TOKEN not in env["error"]


def test_auth_probe_also_goes_through_the_guard(monkeypatch, tmp_path):
    """matomo_auth --check uses the same pinned path, not a bare requests.post."""
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("MATOMO_URL", "http://10.0.0.5:8080")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)
    monkeypatch.delenv(matomo_auth.LOCAL_TARGETS_ENV, raising=False)
    with _real_guard(monkeypatch, resolved_ip="10.0.0.5") as post:
        status = matomo_auth.check_credentials()
    assert status["available"] is False
    assert post.call_count == 0
    assert matomo_auth.LOCAL_TARGETS_ENV in status["error"]
    assert SECRET_TOKEN not in status["error"]


def test_token_never_reaches_an_error_string_or_stderr(monkeypatch, capsys):
    """The token stays out of every error path, envelope, and stream.

    Three shapes at once: a Matomo error payload that echoes the token back,
    a transport exception whose message carries it, and the CLI's own stderr.
    """
    leaked = f"Invalid token_auth={SECRET_TOKEN}&idSite=1"
    resp = _mock_response(200, {"result": "error", "message": leaked})
    with _patch_session(resp):
        env = matomo_report._request("https://m.test", SECRET_TOKEN,
                                     {"method": "API.getX"})
    assert SECRET_TOKEN not in json.dumps(env)
    assert "<redacted>" in env["error"]

    boom = matomo_report.requests.exceptions.ConnectionError(
        f"failed to POST token_auth={SECRET_TOKEN}"
    )
    with _patch_session(side_effect=boom):
        env = matomo_report._request("https://m.test", SECRET_TOKEN,
                                     {"method": "API.getX"})
    assert SECRET_TOKEN not in json.dumps(env)

    assert matomo_auth.redact(leaked) == "Invalid token_auth=<redacted>&idSite=1"

    monkeypatch.setenv("MATOMO_URL", "http://10.0.0.5:8080")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)
    monkeypatch.setenv("MATOMO_SITE_ID", "1")
    monkeypatch.delenv(matomo_auth.LOCAL_TARGETS_ENV, raising=False)
    with _real_guard(monkeypatch, resolved_ip="10.0.0.5"), patch(
        "sys.argv", ["matomo_report.py", "organic"]
    ):
        rc = matomo_report.main()
    assert rc == 1
    captured = capsys.readouterr()
    assert SECRET_TOKEN not in captured.out
    assert SECRET_TOKEN not in captured.err
    assert matomo_auth.LOCAL_TARGETS_ENV in captured.err


def test_resolves_to_private_address_drives_the_installer_hint(monkeypatch):
    """The installers use this to decide whether to print the allowlist hint."""
    def fake_getaddrinfo(host, port, *args, **kwargs):
        ip = "10.1.2.3" if host == "matomo.internal" else PUBLIC_IP
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
                 (ip, port or 80))]

    monkeypatch.setattr(matomo_auth.socket, "getaddrinfo", fake_getaddrinfo)
    assert matomo_auth.resolves_to_private_address("http://matomo.internal:8080")
    assert not matomo_auth.resolves_to_private_address("https://analytics.example.com")
    # IP literals need no DNS at all.
    assert matomo_auth.resolves_to_private_address("http://127.0.0.1:8080")
    assert not matomo_auth.resolves_to_private_address("https://93.184.216.34")
    # A malformed URL is not a private address.
    assert not matomo_auth.resolves_to_private_address("not-a-url")


# --------------------------------------------------------------------------
# Credential storage: ~/.config/claude-seo/matomo.json, 0600, atomic.
# --------------------------------------------------------------------------

INSTALL_SH = ROOT / "extensions" / "matomo" / "install.sh"
INSTALL_PS1 = ROOT / "extensions" / "matomo" / "install.ps1"
UNINSTALL_SH = ROOT / "extensions" / "matomo" / "uninstall.sh"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="asserts 0o600 mode bits, which Windows does not represent",
)
def test_save_config_writes_0600(monkeypatch, tmp_path):
    target = tmp_path / "nested" / "matomo.json"
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(target))
    matomo_auth.save_config({
        "matomo_url": "https://analytics.example.com",
        "matomo_token": SECRET_TOKEN,
        "matomo_site_id": "1",
    })
    assert target.stat().st_mode & 0o777 == 0o600
    assert json.loads(target.read_text()) == {
        "matomo_url": "https://analytics.example.com",
        "matomo_token": SECRET_TOKEN,
        "matomo_site_id": "1",
    }


def test_save_config_drops_empty_and_unknown_keys(monkeypatch, tmp_path):
    """A blank optional field must not shadow the env fallback later."""
    target = tmp_path / "matomo.json"
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(target))
    matomo_auth.save_config({
        "matomo_url": "https://analytics.example.com",
        "matomo_token": SECRET_TOKEN,
        "matomo_site_id": "",
        "something_else": "dropped",
    })
    stored = json.loads(target.read_text())
    assert "matomo_site_id" not in stored
    assert "something_else" not in stored

    monkeypatch.setenv("MATOMO_SITE_ID", "9")
    assert matomo_auth.load_config()["matomo_site_id"] == "9"


def test_save_config_is_atomic_and_leaves_no_temp_file(monkeypatch, tmp_path):
    """A failed write leaves the previous credentials intact, not truncated."""
    target = tmp_path / "matomo.json"
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(target))
    matomo_auth.save_config({"matomo_url": "https://old.example.com",
                             "matomo_token": "old-token"})
    before = target.read_text()

    def boom(src, dst):
        raise OSError("simulated crash during rename")

    monkeypatch.setattr(matomo_auth.os, "replace", boom)
    with pytest.raises(OSError):
        matomo_auth.save_config({"matomo_url": "https://new.example.com",
                                 "matomo_token": SECRET_TOKEN})

    assert target.read_text() == before
    assert SECRET_TOKEN not in target.read_text()
    assert sorted(f.name for f in tmp_path.iterdir()) == ["matomo.json"]


def test_env_still_overrides_the_config_file(monkeypatch, tmp_path):
    """The env fallback is kept: it is the right answer on a shared machine."""
    target = tmp_path / "matomo.json"
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(target))
    matomo_auth.save_config({"matomo_url": "https://file.example.com",
                             "matomo_token": "file-token"})
    cfg = matomo_auth.load_config()
    assert cfg["matomo_url"] == "https://file.example.com"

    # Nothing in the file: env supplies the rest.
    monkeypatch.setenv("MATOMO_SITE_ID", "42")
    assert matomo_auth.load_config()["matomo_site_id"] == "42"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="asserts 0o600 mode bits, which Windows does not represent",
)
def test_load_config_tightens_a_world_readable_file(monkeypatch, tmp_path):
    """A file left 0644 by an older installer is remediated before it is read."""
    target = tmp_path / "matomo.json"
    target.write_text(json.dumps({"matomo_url": "https://m.test",
                                  "matomo_token": SECRET_TOKEN}))
    target.chmod(0o644)
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(target))
    cfg = matomo_auth.load_config()
    assert cfg["matomo_token"] == SECRET_TOKEN
    assert target.stat().st_mode & 0o777 == 0o600


def test_installers_do_not_put_the_token_in_settings_json():
    """The token belongs in ~/.config/claude-seo/matomo.json, not settings.json.

    settings.json is a general-purpose config file that tooling reads, prints,
    and syncs. The PR's installers wrote MATOMO_API_TOKEN into its env block.
    """
    forbidden = (
        'SETTINGS_JSON=',        # the shell variable the old installer used
        '$SettingsJson',         # its PowerShell counterpart
        'setdefault("env"',      # the env-block write itself
        "setdefault('env'",
        'env["MATOMO',
        "env['MATOMO",
    )
    for path in (INSTALL_SH, INSTALL_PS1):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, (
                f"{path.name} still writes credentials into settings.json ({needle})"
            )
        assert "save_config" in text, f"{path.name} must use matomo_auth.save_config"
        assert ".config/claude-seo" in text or "CONFIG_PATH" in text, (
            f"{path.name} must name the credential file it writes"
        )


def test_installers_pass_credentials_through_env_not_source_or_argv():
    """No credential is interpolated into Python source (issue #189) or put on
    the command line, where other local users can read it through ps."""
    sh = INSTALL_SH.read_text(encoding="utf-8")
    assert "<<'PY'" in sh, "install.sh must use a quoted heredoc"
    assert "sys.argv" in sh
    assert ("'" * 3 + "${") not in sh

    ps1 = INSTALL_PS1.read_text(encoding="utf-8")
    # PowerShell here-strings: @" ... "@ interpolates, so the credential must
    # arrive in the environment, never inside the here-string or on argv.
    assert "sys.argv" in ps1
    assert "$TokenPlain" not in ps1.split('@"')[1].split('"@')[0]
    assert "$env:CLAUDE_SEO_SECRET = $TokenPlain" in ps1
    assert "python - $MatomoAuth $MatomoUrl $SiteId" in ps1
    assert 'CLAUDE_SEO_SECRET="${MATOMO_TOKEN}" python3 -' in sh


def test_uninstall_removes_the_config_and_the_legacy_env_entry():
    text = UNINSTALL_SH.read_text(encoding="utf-8")
    assert ".config/claude-seo/matomo.json" in text
    assert "MATOMO_API_TOKEN" in text, "must still clear the pre-v2.4.0 env entry"
    assert "os.replace" in text, "the settings.json rewrite must stay atomic"


def test_installers_warn_about_a_private_instance_address():
    for path in (INSTALL_SH, INSTALL_PS1):
        text = path.read_text(encoding="utf-8")
        assert "--local-target-hint" in text, (
            f"{path.name} must print the CLAUDE_SEO_LOCAL_TARGETS hint"
        )


_HEREDOC_RE = re.compile(r"<<'PY'\n(.*?)\nPY\n", re.DOTALL)


def _installer_writer() -> str:
    """The credential-writing Python the shell installer feeds to python3."""
    match = _HEREDOC_RE.search(INSTALL_SH.read_text(encoding="utf-8"))
    assert match, "install.sh has no quoted <<'PY' heredoc"
    return match.group(1)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="asserts 0o600 mode bits, which Windows does not represent",
)
def test_installer_writer_is_inert_against_an_injection_shaped_token(tmp_path):
    """A token full of shell and Python metacharacters is data, not code."""
    home = tmp_path / "home"
    home.mkdir()
    nasty = "tok" + "'" * 3 + '"$(touch ' + str(tmp_path / "pwned") + ")"
    proc = subprocess.run(
        [sys.executable, "-c", _installer_writer(),
         str(ROOT / "scripts" / "matomo_auth.py"),
         "https://analytics.example.com", "3"],
        capture_output=True, text=True,
        env={**os.environ, "HOME": str(home), "CLAUDE_SEO_SECRET": nasty},
    )
    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / "pwned").exists(), "installer executed the token"

    written = home / ".config" / "claude-seo" / "matomo.json"
    assert written.stat().st_mode & 0o777 == 0o600
    assert json.loads(written.read_text())["matomo_token"] == nasty


def test_installer_writer_survives_a_dropped_optional_argument(tmp_path):
    """PowerShell 5.1 drops an empty native argument; the site ID is optional."""
    home = tmp_path / "home"
    home.mkdir()
    proc = subprocess.run(
        [sys.executable, "-c", _installer_writer(),
         str(ROOT / "scripts" / "matomo_auth.py"),
         "https://analytics.example.com"],   # no site-ID argument
        capture_output=True, text=True,
        env={**os.environ, "HOME": str(home), "CLAUDE_SEO_SECRET": SECRET_TOKEN},
    )
    assert proc.returncode == 0, proc.stderr
    stored = json.loads((home / ".config" / "claude-seo" / "matomo.json").read_text())
    assert stored["matomo_token"] == SECRET_TOKEN
    assert "matomo_site_id" not in stored
