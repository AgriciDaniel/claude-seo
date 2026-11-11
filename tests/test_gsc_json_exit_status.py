"""JSON output must retain failure status for shell and agent callers."""
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("googleapiclient")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gsc_inspect  # noqa: E402
import gsc_query  # noqa: E402


def run(module, argv, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [module.__name__ + ".py", *argv, "--json"])
    try:
        module.main()
    except SystemExit as exc:
        code = exc.code
    else:
        code = 0
    return code, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(("command", "function"), [
    ("query", "query_search_analytics"), ("sitemaps", "list_sitemaps"), ("sites", "list_sites"),
])
def test_query_command_errors_exit_one_with_json(command, function, monkeypatch, capsys):
    payload = {"error": "API quota exceeded"}
    monkeypatch.setattr(gsc_query, function, lambda *a, **kw: payload)
    code, result = run(gsc_query, [command, "--property", "sc-domain:example.com"], monkeypatch, capsys)
    assert code == 1
    assert result == payload


def test_inspection_api_error_exits_one_with_json(monkeypatch, capsys):
    payload = {"url": "https://example.com/", "error": "Permission denied", "verdict": None}
    monkeypatch.setattr(gsc_inspect, "inspect_url", lambda *a, **kw: payload)
    code, result = run(gsc_inspect, [payload["url"], "--site-url", "sc-domain:example.com"], monkeypatch, capsys)
    assert code == 1
    assert result == payload


def test_batch_partial_api_failure_exits_one(monkeypatch, capsys, tmp_path):
    urls = tmp_path / "urls.txt"
    urls.write_text("https://example.com/\n", encoding="utf-8")
    payload = {"error": None, "total": 2, "summary": {"pass": 1, "error": 1}, "results": []}
    monkeypatch.setattr(gsc_inspect, "batch_inspect", lambda *a, **kw: payload)
    code, result = run(gsc_inspect, ["--batch", str(urls), "--site-url", "sc-domain:example.com"],
                       monkeypatch, capsys)
    assert code == 1
    assert result == payload


def test_nonindexed_verdict_is_a_successful_inspection(monkeypatch, capsys):
    payload = {"url": "https://example.com/", "error": None, "verdict": "FAIL"}
    monkeypatch.setattr(gsc_inspect, "inspect_url", lambda *a, **kw: payload)
    assert run(gsc_inspect, [payload["url"], "--site-url", "sc-domain:example.com"], monkeypatch, capsys)[0] == 0
