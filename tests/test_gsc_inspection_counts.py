"""Inspection totals describe attempted URLs, not blank or truncated entries."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("googleapiclient")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gsc_inspect  # noqa: E402


@pytest.fixture
def inspected(monkeypatch):
    urls = []

    def inspect(url, *args):
        urls.append(url)
        return {"url": url, "verdict": "PASS", "error": None}

    monkeypatch.setattr(gsc_inspect, "inspect_url", inspect)
    monkeypatch.setattr(gsc_inspect.time, "sleep", lambda _: None)
    return urls


def test_blank_urls_do_not_inflate_inspection_total(inspected):
    result = gsc_inspect.batch_inspect(["", " https://example.com/a ", "  ", "https://example.com/b"],
                                       "sc-domain:example.com", delay=0)
    assert result["total"] == len(result["results"]) == 2
    assert result["requested_total"] == 2
    assert inspected == ["https://example.com/a", "https://example.com/b"]


def test_quota_limit_applies_to_nonempty_urls_and_reports_actual_total(inspected, monkeypatch):
    monkeypatch.setattr(gsc_inspect, "DAILY_LIMIT", 2)
    result = gsc_inspect.batch_inspect(["", "https://example.com/a", " ",
                                       "https://example.com/b", "https://example.com/c"],
                                      "sc-domain:example.com", delay=0)
    assert result["total"] == len(result["results"]) == 2
    assert result["requested_total"] == 3
    assert result["summary"]["pass"] == 2
    assert "Batch size (3)" in result["error"]
    assert inspected == ["https://example.com/a", "https://example.com/b"]


def test_empty_batch_has_no_attempts(inspected):
    result = gsc_inspect.batch_inspect(["", " "], "sc-domain:example.com", delay=0)
    assert result["total"] == 0
    assert result["requested_total"] == 0
    assert inspected == []
