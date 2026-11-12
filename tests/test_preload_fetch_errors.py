"""Failed fetches are not successful low-content preload audits."""
import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import preload_check  # noqa: E402


@pytest.mark.parametrize("status", [404, 429, 503])
def test_http_failure_has_json_error_without_a_score(monkeypatch, capsys, status):
    response = requests.Response()
    response.status_code = status
    response.url = "https://example.com/"
    response._content = b"<html><body>Service unavailable</body></html>"
    monkeypatch.setattr(preload_check, "safe_requests_get", lambda *a, **k: response)
    monkeypatch.setattr(sys, "argv", ["preload_check.py", response.url, "--json"])

    assert preload_check.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert str(status) in result["error"]
    assert "score" not in result


@pytest.mark.parametrize("error", [requests.Timeout("timed out"),
                                  requests.ConnectionError("connection failed")])
def test_network_errors_stay_machine_readable(monkeypatch, capsys, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(preload_check, "safe_requests_get", fail)
    monkeypatch.setattr(sys, "argv", ["preload_check.py", "https://example.com/", "--json"])
    assert preload_check.main() == 1
    assert str(error) in json.loads(capsys.readouterr().out)["error"]


def test_refused_url_retains_exit_two_and_json(monkeypatch, capsys):
    def refuse(*args, **kwargs):
        raise preload_check.URLSafetyError("refused")

    monkeypatch.setattr(preload_check, "safe_requests_get", refuse)
    monkeypatch.setattr(sys, "argv", ["preload_check.py", "http://127.0.0.1/", "--json"])
    assert preload_check.main() == 2
    assert "refused" in json.loads(capsys.readouterr().out)["error"]
