"""Tests for the Matomo extension (scripts/matomo_auth.py, scripts/matomo_report.py).

Covers:
- Envelope shape (status / data / error / metadata)
- Auth probe (HTTP error classes mapped to friendly error messages)
- Token never appears in output / URL parameters
- URL sanity check (allows self-hosted, rejects malformed)
- Env-var and config-file credential loading (env wins over file when both set)
- Args / CLI error paths surface a structured error envelope
- Token redaction of incoming Matomo ``result=error`` messages
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import matomo_auth  # noqa: E402
import matomo_report  # noqa: E402


SECRET_TOKEN = "abcdef0123456789abcdef0123456789"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Ensure Matomo env vars do not leak between tests."""
    for k in ("MATOMO_URL", "MATOMO_API_TOKEN", "MATOMO_TOKEN",
              "MATOMO_SITE_ID", "MATOMO_IDSITE"):
        monkeypatch.delenv(k, raising=False)


def _mock_response(status_code: int, body) -> Mock:
    resp = Mock(status_code=status_code, text=json.dumps(body))
    resp.json.return_value = body
    return resp


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


def test_url_sanity_allows_self_hosted_https():
    assert matomo_auth._sanity_check_instance_url("https://analytics.example.com") \
        == "https://analytics.example.com"
    assert matomo_auth._sanity_check_instance_url("http://localhost:8080/") \
        == "http://localhost:8080"
    assert matomo_auth._sanity_check_instance_url("https://10.0.0.5/matomo/") \
        == "https://10.0.0.5/matomo"


def test_url_sanity_rejects_malformed():
    assert matomo_auth._sanity_check_instance_url("") is None
    assert matomo_auth._sanity_check_instance_url("not-a-url") is None
    assert matomo_auth._sanity_check_instance_url("ftp://example.com") is None
    # Userinfo in URL would leak credentials if accidentally configured.
    assert matomo_auth._sanity_check_instance_url(
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
    with patch.object(matomo_auth.requests, "post", return_value=resp) as post:
        status = matomo_auth.check_credentials()

    assert status["available"] is True
    assert status["instance"] == "https://analytics.example.com"
    assert status["site_id"] == "1"
    assert status["verified"] is True
    assert status["version"] == "5.1.2"
    # Token must be in POST body, never in URL.
    call = post.call_args
    assert call.kwargs["data"]["token_auth"] == SECRET_TOKEN
    assert "token_auth" not in call.kwargs.get("params", {})


def test_check_credentials_handles_matomo5_version_object(monkeypatch, tmp_path):
    """Matomo 5+ returns API.getMatomoVersion as {"value": "5.13.0"}."""
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("MATOMO_URL", "https://analytics.example.com")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)

    resp = _mock_response(200, {"value": "5.13.0"})
    with patch.object(matomo_auth.requests, "post", return_value=resp):
        status = matomo_auth.check_credentials()
    assert status["available"] is True
    assert status["version"] == "5.13.0"


def test_check_credentials_surfaces_auth_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("MATOMO_URL", "https://analytics.example.com")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)
    resp = _mock_response(401, {"result": "error", "message": "no access"})
    with patch.object(matomo_auth.requests, "post", return_value=resp):
        status = matomo_auth.check_credentials()
    assert status["available"] is False
    assert "authentication" in status["error"].lower() or "auth" in status["error"].lower()
    # Token must not appear in the error message.
    assert SECRET_TOKEN not in status["error"]


def test_check_credentials_surfaces_connection_error(monkeypatch, tmp_path):
    monkeypatch.setattr(matomo_auth, "CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("MATOMO_URL", "https://analytics.example.com")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)
    with patch.object(
        matomo_auth.requests, "post",
        side_effect=matomo_auth.requests.exceptions.ConnectionError("refused"),
    ):
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
    with patch.object(matomo_report.requests, "post", return_value=resp):
        env = matomo_report._request("https://m.test", "tok", {"method": "X"})
    assert env["status"] == "error"
    assert "No data available" in env["error"]
    assert env["metadata"]["method"] == "X"


def test_request_redacts_token_in_matomo_error():
    leaked = "Bad token_auth=" + SECRET_TOKEN + " for site"
    resp = _mock_response(200, {"result": "error", "message": leaked})
    with patch.object(matomo_report.requests, "post", return_value=resp):
        env = matomo_report._request("https://m.test", "tok", {"method": "X"})
    assert SECRET_TOKEN not in (env.get("error") or "")


def test_request_maps_401_to_friendly_error():
    resp = _mock_response(401, {})
    with patch.object(matomo_report.requests, "post", return_value=resp):
        env = matomo_report._request("https://m.test", "tok", {"method": "X"})
    assert env["status"] == "error"
    assert "authentication" in env["error"].lower() or "token" in env["error"].lower()


def test_request_maps_timeout_to_friendly_error():
    with patch.object(
        matomo_report.requests, "post",
        side_effect=matomo_report.requests.exceptions.Timeout("read timeout"),
    ):
        env = matomo_report._request("https://m.test", "tok", {"method": "X"})
    assert env["status"] == "error"
    assert "timed out" in env["error"].lower() or "timeout" in env["error"].lower()


def test_request_does_not_echo_token_in_call_args():
    resp = _mock_response(200, "5.1.2")
    with patch.object(matomo_report.requests, "post", return_value=resp) as post:
        matomo_report._request("https://m.test", SECRET_TOKEN, {"method": "X"})
    call = post.call_args
    assert call.kwargs["data"]["token_auth"] == SECRET_TOKEN
    # No query params; token is POST body only.
    assert "params" not in call.kwargs or not call.kwargs["params"]


def test_cli_errors_when_url_missing(monkeypatch):
    """`--check` with no configured URL returns a friendly error envelope."""
    for k in ("MATOMO_URL", "MATOMO_API_TOKEN", "MATOMO_SITE_ID",
              "MATOMO_TOKEN", "MATOMO_IDSITE"):
        monkeypatch.delenv(k, raising=False)
    with patch.object(matomo_auth.requests, "post") as post:
        env = matomo_auth.check_credentials()
    assert env["available"] is False
    assert "url" in env["error"].lower()
    post.assert_not_called()


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
    with patch.object(matomo_report.requests, "post",
                      side_effect=responses):
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
    with patch.object(matomo_report.requests, "post",
                      return_value=_mock_response(200, raw)):
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
    with patch.object(matomo_report.requests, "post",
                      return_value=_mock_response(200, raw)):
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
    with patch.object(matomo_report.requests, "post",
                      side_effect=[_mock_response(200, types),
                                   _mock_response(200, engines)]) as post:
        env = matomo_report.referrers_report("1", "https://m.test",
                                             SECRET_TOKEN, days=7)
    assert env["status"] == "success"
    # Correct Matomo 4/5 method name (getReferrersType does not exist).
    first_method = post.call_args_list[0].kwargs["data"]["method"]
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
    with patch.object(matomo_report.requests, "post",
                      return_value=_mock_response(200, raw)):
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
    with patch.object(matomo_report.requests, "post",
                      return_value=_mock_response(200, raw)):
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
    with patch.object(matomo_report.requests, "post",
                      return_value=_mock_response(200, raw)):
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
    with patch.object(
        matomo_auth.requests, "post",
        return_value=_mock_response(200, "5.1.2"),
    ), patch("sys.argv",
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
    with patch.object(matomo_auth.requests, "post", return_value=resp):
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