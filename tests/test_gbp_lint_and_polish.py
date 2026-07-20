"""
Tests for v2 Checkpoint 6 (Phase F — local + international + privacy polish):
    scripts/gbp_deprecation_lint.py
    skills/seo-google/references/dma-consent-mode-v2.md
    skills/seo-hreflang/references/machine-translation-qa.md
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import gbp_deprecation_lint as gbp  # noqa: E402


# ---------------------------------------------------------------------------
# gbp_deprecation_lint
# ---------------------------------------------------------------------------


def test_clean_page_returns_ok() -> None:
    result = gbp.scan("<html><body>Contact us at +1-555-1234.</body></html>")
    assert result["ok"] is True
    assert result["findings"] == []


def test_detects_gbp_chat_cta() -> None:
    html = '<a class="cta">Message us on Google</a>'
    result = gbp.scan(html)
    assert result["ok"] is False
    feats = {f["feature"] for f in result["findings"]}
    assert "gbp-chat" in feats
    assert result["summary"]["critical"] >= 1


def test_treats_business_site_url_as_manual_verification() -> None:
    html = '<a href="https://shopname-456.business.site/menu">our menu</a>'
    result = gbp.scan(html)
    feats = {f["feature"] for f in result["findings"]}
    assert "business-site-url" in feats
    assert result["summary"]["medium"] >= 1
    assert result["summary"]["high"] == 0


def test_does_not_flag_gbp_qa_embed() -> None:
    html = '<div data-google-business-qa>...</div>'
    result = gbp.scan(html)
    assert result["findings"] == []
    assert result["ok"] is True


def test_does_not_flag_generic_chat_widget() -> None:
    """Intercom / drift / custom chat widgets are fine — we only flag GBP-chat."""
    html = '<div id="intercom"><button>Message us</button></div>'
    result = gbp.scan(html)
    feats = {f["feature"] for f in result["findings"]}
    assert "gbp-chat" not in feats


def test_summary_counts_match_findings() -> None:
    html = (
        '<a href="https://x.business.site/">a</a>'
        '<a href="https://y.business.site/">b</a>'
        '<span>Message us on Google</span>'
    )
    result = gbp.scan(html)
    s = result["summary"]
    assert s["critical"] + s["high"] + s["medium"] == len(result["findings"])
    assert s["critical"] >= 1
    assert s["medium"] >= 2  # both .business.site URLs need manual verification


# ---------------------------------------------------------------------------
# DMA + consent-mode v2 reference
# ---------------------------------------------------------------------------


def test_dma_reference_exists_and_cites_primary_sources() -> None:
    path = _REPO / "skills" / "seo-google" / "references" / "dma-consent-mode-v2.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "DMA" in text
    assert "consent" in text.lower()
    assert "third-party cookie" in text.lower()
    assert "2024-03-07" in text or "Mar" in text
    # Must cite an official EC URL.
    assert "digital-markets-act.ec.europa.eu" in text
    # Must explicitly soften cookieless framing per the gap analysis.
    assert "abandoned" in text.lower() or "reversal" in text.lower() or \
           "no longer urgent" in text.lower()


# ---------------------------------------------------------------------------
# Machine-translation QA reference
# ---------------------------------------------------------------------------


def test_mt_qa_reference_exists_and_cites_qrg() -> None:
    path = _REPO / "skills" / "seo-hreflang" / "references" / "machine-translation-qa.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "Jan" in text and "2025" in text
    assert "§4.6.5" in text or "4.6.5" in text
    # Primary source link must point at Google.
    assert "services.google.com" in text
    # Must list at least one signal table.
    assert "hreflang" in text.lower()
    assert "scaled content abuse" in text.lower()
