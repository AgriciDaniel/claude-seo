"""
Tests for scripts/indexing_notify.py — the Google Indexing API helper.

Regression coverage for the over-quota warning. batch_notify truncates a
batch larger than the daily quota and sets a warning saying the extra URLs
will be dropped. A second, unconditional ``if len(urls) > 50`` branch then
overwrote that warning (the truncated list is still > 50), so a user
submitting more than DAILY_QUOTA URLs was never told any were dropped.
"""

from __future__ import annotations

import os
import sys

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import indexing_notify  # noqa: E402


def _stub_notify(monkeypatch):
    # Keep batch_notify offline: never touch the Indexing API.
    monkeypatch.setattr(indexing_notify, "notify_url",
                        lambda url, action: {"url": url, "success": True})
    monkeypatch.setattr(indexing_notify.time, "sleep", lambda *_: None)


def test_over_quota_batch_keeps_the_truncation_warning(monkeypatch) -> None:
    _stub_notify(monkeypatch)
    urls = [f"https://example.com/{i}" for i in range(indexing_notify.DAILY_QUOTA + 50)]
    result = indexing_notify.batch_notify(urls, delay=0)
    assert result["quota_warning"] is not None
    # The user must be told the batch was truncated, not merely how much
    # quota the (already truncated) submission uses.
    assert "exceeds daily quota" in result["quota_warning"]
    assert str(indexing_notify.DAILY_QUOTA) in result["quota_warning"]


def test_mid_size_batch_still_reports_quota_usage(monkeypatch) -> None:
    _stub_notify(monkeypatch)
    urls = [f"https://example.com/{i}" for i in range(75)]
    result = indexing_notify.batch_notify(urls, delay=0)
    assert result["quota_warning"] is not None
    assert "will use" in result["quota_warning"]


def test_small_batch_has_no_quota_warning(monkeypatch) -> None:
    _stub_notify(monkeypatch)
    urls = [f"https://example.com/{i}" for i in range(10)]
    result = indexing_notify.batch_notify(urls, delay=0)
    assert result["quota_warning"] is None
