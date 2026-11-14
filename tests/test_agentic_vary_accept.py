"""Vary: Accept is matched as a header-name token, not a substring (issue #459).

``"accept" in vary`` let ``Vary: Accept-Encoding`` pass as ``Vary: Accept``,
so Markdown negotiation that caches would mix up with HTML was reported as
correct.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = str(ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

pytest.importorskip("requests")
pytest.importorskip("bs4")
import agentic_check as ac  # noqa: E402

URL = "https://example.com/guide"


def _audit(monkeypatch, vary):
    headers = {"content-type": "text/markdown; charset=utf-8"}
    if vary is not None:
        headers["vary"] = vary

    def fake_fetch(url, **_kwargs):
        if url == URL:
            return {"url": url, "status": 200, "headers": headers, "text": "# Guide",
                    "final_url": url, "error": None}
        return {"url": url, "status": 404, "headers": {"content-type": "text/html"},
                "text": "", "final_url": url, "error": None}

    monkeypatch.setattr(ac, "fetch", fake_fetch)
    checks, data = ac.audit_markdown(URL, {})
    [check] = [c for c in checks if c["id"] == "markdown-delivery"]
    return check, data["negotiation"]["vary_accept"]


@pytest.mark.parametrize("vary", [
    "Accept-Encoding",
    "accept-encoding, Accept-Language",
    "Accept-Encoding, User-Agent, X-Accept",
    "",
    None,
])
def test_vary_without_an_accept_token_is_flagged(monkeypatch, vary) -> None:
    check, vary_accept = _audit(monkeypatch, vary)
    assert vary_accept is False
    assert check["status"] == "warn"


@pytest.mark.parametrize("vary", [
    "Accept",
    "accept",
    "Accept-Encoding, Accept",
    "Accept-Encoding,ACCEPT ,User-Agent",
    "*",
    "Accept-Encoding, *",
])
def test_vary_with_an_accept_token_or_star_passes(monkeypatch, vary) -> None:
    check, vary_accept = _audit(monkeypatch, vary)
    assert vary_accept is True
    assert check["status"] == "pass"
