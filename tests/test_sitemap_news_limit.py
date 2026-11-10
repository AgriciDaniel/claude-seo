"""News sitemap limit: the 1,000 cap counts news:news tags, not every URL (#335).

Google: a sitemap may have up to 1,000 news:news tags, and general sitemap
limits still apply, including when news tags extend an existing sitemap.
https://developers.google.com/search/docs/crawling-indexing/sitemaps/news-sitemap
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "seo-sitemap" / "SKILL.md"


def test_news_cap_does_not_replace_the_url_limit() -> None:
    folded = " ".join(SKILL.read_text(encoding="utf-8").split())
    assert "override the generic 50k check with the 1,000 cap" not in folded
    assert "do not replace them when the `news:` namespace is present" in folded
    assert "max **1,000** `<news:news>` tags per file" in folded
    assert "50,000 URL and 50 MB checks" in folded
