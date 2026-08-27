"""Google Search Console sitemap output regressions."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import gsc_query  # noqa: E402


class FakeExecute:
    def execute(self) -> dict:
        return {
            "sitemap": [
                {
                    "path": "https://example.com/sitemap.xml",
                    "lastSubmitted": "2026-01-01T00:00:00Z",
                    "isPending": False,
                    "isSitemapsIndex": False,
                    "type": "sitemap",
                    "warnings": 0,
                    "errors": 0,
                    "contents": [
                        {"type": "web", "submitted": 10, "indexed": 7},
                        {"type": "image", "submitted": 4},
                    ],
                }
            ]
        }


class FakeSitemaps:
    def list(self, siteUrl: str):
        return FakeExecute()


class FakeService:
    def sitemaps(self):
        return FakeSitemaps()


def test_sitemaps_strip_deprecated_indexed_counts_and_point_to_url_inspection() -> None:
    with patch.object(gsc_query, "_build_gsc_service", return_value=FakeService()):
        result = gsc_query.list_sitemaps("sc-domain:example.com")

    sitemap = result["sitemaps"][0]
    assert result["error"] is None
    assert all("indexed" not in item for item in sitemap["contents"])
    assert sitemap["contents"][0] == {"type": "web", "submitted": 10}
    assert "URL Inspection API" in sitemap["indexation_note"]


def test_seo_google_docs_identify_url_inspection_as_indexation_truth() -> None:
    text = (REPO_ROOT / "skills" / "seo-google" / "SKILL.md").read_text(encoding="utf-8")
    sitemap_section = text[text.index("### `/seo google sitemaps <property>`"):]
    assert "URL Inspection API" in sitemap_section
    assert "indexation truth" in sitemap_section
