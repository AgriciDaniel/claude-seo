"""Expanded page-URL totals do not include invalid child-sitemap locations."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sitemap_discovery as discovery  # noqa: E402

SITE = "https://example.com"


@pytest.mark.parametrize("bad_child", ["", "/relative.xml", "javascript:missing"])
@pytest.mark.parametrize("with_pages", [False, True])
def test_page_totals_keep_index_locations_separate(monkeypatch, bad_child, with_pages):
    child = f"<sitemap><loc>{SITE}/pages.xml</loc></sitemap>" if with_pages else ""
    routes = {
        SITE + "/sitemap.xml": (
            "<sitemapindex>" + child
            + f"<sitemap><loc>{bad_child}</loc></sitemap></sitemapindex>"
        ).encode(),
        SITE + "/pages.xml": (
            f"<urlset><url><loc>{SITE}/a</loc></url>"
            f"<url><loc>{SITE}/a</loc></url>"
            "<url><loc>/invalid-page</loc></url></urlset>"
        ).encode(),
    }

    def fetch(url, _limit):
        is_robots = url.endswith("/robots.txt")
        return {
            "status_code": 200 if is_robots or url in routes else 404,
            "content": routes.get(url, b""),
            "content_type": "text/plain" if is_robots else "application/xml",
            "final_url": url, "too_large": False, "error": None,
        }

    monkeypatch.setattr(discovery, "_bounded_fetch", fetch)
    result = discovery.discover_sitemaps(SITE, expand=True)
    files = result["expanded"]["files"]
    index = next(item for item in files if item["kind"] == "sitemapindex")
    assert index["invalid_loc_count"] == 1

    totals = result["expanded"]["totals"]
    assert totals["invalid_locs"] == (1 if with_pages else 0)
    assert totals["total_urls"] == (3 if with_pages else 0)
    assert totals["total_urls"] == sum(
        totals[key] for key in (
            "unique_urls", "duplicates_within_files",
            "duplicates_across_files", "invalid_locs",
        )
    )
