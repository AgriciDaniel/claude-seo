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
    """organic_traffic_report rolls daily VisitsSummary into totals + pages."""
    daily = {
        "2026-01-01": {"nb_visits": 100, "nb_uniq_visitors": 80,
                       "nb_actions": 150, "nb_pageviews": 200,
                       "bounce_count": 30, "sum_visit_length": 6000},
        "2026-01-02": {"nb_visits": 50, "nb_uniq_visitors": 40,
                       "nb_actions": 80, "nb_pageviews": 100,
                       "bounce_count": 10, "sum_visit_length": 3000},
    }
    pages = [
        {"label": "https://m.test/", "nb_visits": 80, "nb_uniq_visitors": 70,
         "nb_actions": 120, "bounce_rate": 0.3},
        {"label": "https://m.test/blog/x", "nb_visits": 40, "nb_uniq_visitors": 30,
         "nb_actions": 60, "bounce_rate": 0.5},
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
    assert len(data["top_pages"]) == 2
    assert data["top_pages"][0]["url"] == "https://m.test/"


def test_device_breakdown_sorts_by_visits(monkeypatch):
    raw = {
        "desktop": {"label": "Desktop", "nb_visits": 100,
                    "nb_uniq_visitors": 80, "bounce_rate": 0.4},
        "smartphone": {"label": "Smartphone", "nb_visits": 200,
                       "nb_uniq_visitors": 170, "bounce_rate": 0.5},
        "tablet": {"label": "Tablet", "nb_visits": 20,
                   "nb_uniq_visitors": 18, "bounce_rate": 0.3},
    }
    with patch.object(matomo_report.requests, "post",
                      return_value=_mock_response(200, raw)):
        env = matomo_report.device_breakdown("1", "https://m.test",
                                             SECRET_TOKEN, days=7)
    assert env["status"] == "success"
    devices = env["data"]["devices"]
    assert [d["device_type"] for d in devices] == ["Smartphone", "Desktop", "Tablet"]


def test_country_breakdown_caps_limit(monkeypatch):
    raw = {f"C{i}": {"label": f"Country {i}", "nb_visits": 100 - i,
                     "nb_uniq_visitors": 50} for i in range(30)}
    with patch.object(matomo_report.requests, "post",
                      return_value=_mock_response(200, raw)):
        env = matomo_report.country_breakdown("1", "https://m.test",
                                              SECRET_TOKEN, days=7, limit=5)
    assert env["status"] == "success"
    assert len(env["data"]["countries"]) == 5
    assert env["data"]["countries"][0]["country_code"] == "C0"


def test_keywords_report_flags_anonymized_share(monkeypatch):
    raw = {
        "kw1": {"label": "kw1", "nb_visits": 10},
        "kw2": {"label": "kw2", "nb_visits": 5},
        "(not provided)": {"label": "(not provided)", "nb_visits": 80},
        "(no keyword)": {"label": "(no keyword)", "nb_visits": 5},
    }
    with patch.object(matomo_report.requests, "post",
                      return_value=_mock_response(200, raw)):
        env = matomo_report.keywords_report("1", "https://m.test",
                                            SECRET_TOKEN, days=7, limit=10)
    assert env["status"] == "success"
    data = env["data"]
    assert data["anonymized_share_pct"] > 80.0
    assert "anonymization" in data["note"].lower()
    # Anonymized entries collapse to "(not provided)" but their visits are summed.
    anonymized = [k for k in data["keywords"] if k["keyword"] == "(not provided)"]
    assert anonymized and anonymized[0]["visits"] == 85


def test_referrers_report_includes_search_engines(monkeypatch):
    types = {
        "direct": {"label": "Direct Entry", "nb_visits": 30, "nb_uniq_visitors": 25,
                   "nb_actions": 40},
        "search": {"label": "Search Engines", "nb_visits": 70, "nb_uniq_visitors": 60,
                   "nb_actions": 100},
        "social": {"label": "Social Networks", "nb_visits": 20, "nb_uniq_visitors": 18,
                   "nb_actions": 25},
    }
    engines = {
        "Google": {"label": "Google", "nb_visits": 50},
        "Bing": {"label": "Bing", "nb_visits": 20},
    }
    with patch.object(matomo_report.requests, "post",
                      side_effect=[_mock_response(200, types),
                                   _mock_response(200, engines)]):
        env = matomo_report.referrers_report("1", "https://m.test",
                                             SECRET_TOKEN, days=7)
    assert env["status"] == "success"
    channels = env["data"]["channels"]
    assert [c["channel"] for c in channels] == [
        "Search Engines", "Direct Entry", "Social Networks"]
    engines_out = env["data"]["search_engines"]
    assert [e["search_engine"] for e in engines_out] == ["Google", "Bing"]


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


def test_main_missing_site_id_exits_one(monkeypatch, capsys):
    monkeypatch.setenv("MATOMO_URL", "https://m.test")
    monkeypatch.setenv("MATOMO_API_TOKEN", SECRET_TOKEN)
    monkeypatch.delenv("MATOMO_SITE_ID", raising=False)
    with patch("sys.argv", ["matomo_report.py", "organic", "--json"]):
        rc = matomo_report.main()
    assert rc == 1
    captured = capsys.readouterr()
    assert "--site-id" in captured.err or "MATOMO_SITE_ID" in captured.err