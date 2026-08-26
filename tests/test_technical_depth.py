"""
Tests for the v2 Checkpoint 3 technical-depth scripts.

Coverage:
    scripts/preload_check.py — Speculation Rules / bfcache / preload
    scripts/indexnow_submit.py — payload validation + key verification
    scripts/lcp_subparts.py — pure SSRF guard + result-shape (no live CrUX)
    scripts/unlighthouse_run.py — SSRF guard + Node-availability check

lcp_subparts and unlighthouse are heavy network/process integrations;
we test their non-network paths only. Real-API integration is
deferred to manual smoke tests.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import indexnow_submit  # noqa: E402
import lcp_subparts  # noqa: E402
import preload_check  # noqa: E402
import unlighthouse_run  # noqa: E402

# ---------------------------------------------------------------------------
# preload_check
# ---------------------------------------------------------------------------


def test_preload_detects_speculation_rules_inline_block() -> None:
    html = '<script type="speculationrules">{"prefetch":[{"urls":["/next"]}]}</script>'
    result = preload_check.analyse(html, {})
    assert result["speculation_rules"]["inline_blocks"] == 1
    assert "prefetch" in result["speculation_rules"]["actions"]


def test_preload_detects_speculation_rules_header() -> None:
    result = preload_check.analyse("", {"Speculation-Rules": "/rules.json"})
    assert result["speculation_rules"]["header_present"] is True


def test_preload_detects_deprecated_prerender_link() -> None:
    html = '<link rel="prerender" href="/next">'
    result = preload_check.analyse(html, {})
    assert result["prerender_links"] == 1
    assert any("deprecated" in r.lower() for r in result["recommendations"])


def test_preload_detects_bfcache_killer_no_store() -> None:
    result = preload_check.analyse("<html></html>", {"Cache-Control": "no-store"})
    assert result["bfcache_signals"]["cache_control_no_store"] is True
    assert any("no-store" in r for r in result["recommendations"])


def test_preload_detects_bfcache_killer_unload_listener() -> None:
    html = "<script>addEventListener('unload', () => {});</script>"
    result = preload_check.analyse(html, {})
    assert result["bfcache_signals"]["unload_listener"] is True


def test_preload_detects_lcp_fetchpriority_high() -> None:
    html = '<img src="/hero.webp" fetchpriority="high">'
    result = preload_check.analyse(html, {})
    assert result["lcp_resource_hints"]["preload_lcp_candidate"] is True
    assert result["lcp_resource_hints"]["fetchpriority_high"] >= 1


def test_preload_score_100_on_well_optimised_page() -> None:
    html = (
        '<script type="speculationrules">{"prefetch":[{"urls":["/next"]}]}</script>'
        '<link rel="preload" as="image" href="/hero.webp" fetchpriority="high">'
        '<img src="/hero.webp" fetchpriority="high">'
    )
    result = preload_check.analyse(html, {})
    assert result["score"] == 100
    assert result["recommendations"] == []


def test_preload_score_low_on_bfcache_killer() -> None:
    html = "<script>addEventListener('unload', () => {});</script>"
    result = preload_check.analyse(html, {"Cache-Control": "no-store"})
    # Loses points for: no speculation rules, no fetchpriority, two bfcache
    # killers, but gains 25 for no deprecated prerender = ~25/100.
    assert result["score"] <= 50


# ---------------------------------------------------------------------------
# indexnow_submit — validation only (no network)
# ---------------------------------------------------------------------------


def test_indexnow_rejects_empty_url_list() -> None:
    result = indexnow_submit.submit("example.com", "k" * 32,
                                    "https://example.com/k.txt", [])
    assert result["ok"] is False
    assert "empty" in result["error"]


def test_indexnow_rejects_key_too_short() -> None:
    result = indexnow_submit.submit("example.com", "short",
                                    "https://example.com/k.txt",
                                    ["https://example.com/a"])
    assert result["ok"] is False
    assert "key must be" in result["error"]


def test_indexnow_rejects_cross_host_urls() -> None:
    result = indexnow_submit.submit(
        "example.com", "k" * 32, "https://example.com/k.txt",
        ["https://example.com/ok", "https://other.example/bad"],
    )
    assert result["ok"] is False
    assert "host" in result["error"]


def test_indexnow_rejects_batch_above_spec_cap() -> None:
    big = [f"https://example.com/p{i}" for i in range(10001)]
    result = indexnow_submit.submit(
        "example.com", "k" * 32, "https://example.com/k.txt", big,
    )
    assert result["ok"] is False
    assert "10000" in result["error"]


def test_indexnow_rejects_private_ip_in_url_list() -> None:
    result = indexnow_submit.submit(
        "10.0.0.1", "k" * 32, "https://10.0.0.1/k.txt",
        ["http://10.0.0.1/admin"],
    )
    assert result["ok"] is False
    assert "url_safety" in result["error"]


# ---------------------------------------------------------------------------
# lcp_subparts — SSRF + missing-key paths
# ---------------------------------------------------------------------------


def test_lcp_subparts_blocks_ssrf() -> None:
    result = lcp_subparts.analyse("http://10.0.0.1/")
    assert "error" in result
    assert "url_safety" in result["error"]


def test_lcp_subparts_reports_missing_api_key() -> None:
    with patch.object(lcp_subparts, "get_api_key", return_value=None):
        result = lcp_subparts.analyse("https://example.com/")
    assert "error" in result
    assert "API key" in result["error"]


# ---------------------------------------------------------------------------
# unlighthouse_run — SSRF + Node-missing paths
# ---------------------------------------------------------------------------


def test_unlighthouse_blocks_ssrf() -> None:
    result = unlighthouse_run.run("http://192.168.1.1/")
    assert result["ok"] is False
    assert "url_safety" in result["error"]


def test_unlighthouse_reports_missing_node(monkeypatch) -> None:
    monkeypatch.setattr(unlighthouse_run.shutil, "which", lambda _name: None)
    result = unlighthouse_run.run("https://example.com/")
    assert result["ok"] is False
    assert "npx" in result["error"].lower() or "node" in result["error"].lower()
