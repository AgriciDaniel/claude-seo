"""Sitemap expansion: sitemap_discovery.py --expand reads what discovery found.

All fetches are mocked at ``_bounded_fetch``, the single request path of the
script, so the tests also prove that no child sitemap is fetched another way.
"""

from __future__ import annotations

import gzip
import json
import sys
import tracemalloc
import zlib
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

pytest.importorskip("lxml")

import sitemap_discovery as discovery  # noqa: E402

SITE = "https://example.com"
NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
BASE_KEYS = {"target", "robots_url", "declared", "found", "checked", "warnings", "error"}


def urlset(*entries) -> bytes:
    """Entries are a loc, or a (loc, lastmod) pair."""
    rows = []
    for entry in entries:
        loc, lastmod = entry if isinstance(entry, tuple) else (entry, None)
        stamp = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
        rows.append(f"<url><loc>{loc}</loc>{stamp}</url>")
    return f'<?xml version="1.0"?><urlset {NS}>{"".join(rows)}</urlset>'.encode()


def index(*locs) -> bytes:
    rows = "".join(f"<sitemap><loc>{loc}</loc></sitemap>" for loc in locs)
    return f'<?xml version="1.0"?><sitemapindex {NS}>{rows}</sitemapindex>'.encode()


def response(content=b"", url=SITE + "/", status=200, content_type="application/xml", too_large=False):
    return {
        "status_code": status,
        "content": content,
        "content_type": content_type,
        "final_url": url,
        "too_large": too_large,
        "error": None,
    }


def run(routes, robots=b"", **options):
    """Run discovery against a route table. Returns (result, fetched URLs).

    A route value is a body (served at its own URL), a full response dict, or
    a callable taking the URL. Unlisted URLs answer 404.
    """
    fetched = []

    def fake_fetch(url, _limit):
        fetched.append(url)
        if url == SITE + "/robots.txt":
            return response(robots, url, content_type="text/plain")
        route = routes.get(url)
        if route is None:
            return response(url=url, status=404)
        if callable(route):
            return route(url)
        return route if isinstance(route, dict) else response(route, url)

    options.setdefault("expand", True)
    with patch.object(discovery, "_bounded_fetch", side_effect=fake_fetch):
        result = discovery.discover_sitemaps(SITE, **options)
    json.dumps(result)  # The whole result must stay JSON serialisable.
    return result, fetched


def file_for(result, suffix):
    return next(item for item in result["expanded"]["files"] if item["url"].endswith(suffix))


def test_output_without_expand_keeps_its_keys():
    result, _ = run({SITE + "/sitemap.xml": urlset(SITE + "/a")}, expand=False)
    assert set(result) == BASE_KEYS
    assert set(result["found"][0]) == {
        "url", "query_redacted", "source", "status_code", "kind", "valid", "error",
    }


def test_expand_adds_one_key_and_leaves_discovery_keys_alone():
    routes = {SITE + "/sitemap.xml": urlset(SITE + "/a")}
    plain, _ = run(routes, expand=False)
    expanded, _ = run(routes)
    assert set(expanded) == BASE_KEYS | {"expanded"}
    assert {key: expanded[key] for key in BASE_KEYS} == plain


def test_index_children_are_fetched_once_and_totalled():
    routes = {
        SITE + "/sitemap_index.xml": index(SITE + "/posts.xml", SITE + "/pages.xml", SITE + "/posts.xml"),
        SITE + "/posts.xml": urlset(SITE + "/p1", SITE + "/p2"),
        SITE + "/pages.xml": urlset(SITE + "/about"),
    }
    result, fetched = run(routes)
    top = file_for(result, "/sitemap_index.xml")
    assert (top["kind"], top["child_count"], top["url_count"], top["duplicate_count"]) == ("sitemapindex", 3, 0, 1)
    posts = file_for(result, "/posts.xml")
    assert (posts["source"], posts["parent"], posts["url_count"]) == ("sitemapindex", top["url"], 2)
    assert fetched.count(SITE + "/posts.xml") == 1
    assert result["expanded"]["totals"] == {
        "sitemap_files": 3,
        "total_urls": 3,
        "unique_urls": 3,
        "duplicates_within_files": 0,
        "duplicates_across_files": 0,
        "invalid_locs": 0,
    }
    assert result["expanded"]["children"] == {"limit": 50, "listed": 2, "fetched": 2, "skipped": 0}
    assert result["expanded"]["truncated"] is False
    # Children are reported under "expanded" only; "found" still means discovery.
    assert [item["url"] for item in result["found"]] == [SITE + "/sitemap_index.xml"]


def test_child_limit_stops_fetching_and_says_so():
    children = [f"{SITE}/c{number}.xml" for number in range(4)]
    routes = {SITE + "/sitemap.xml": index(*children)}
    routes.update({child: urlset(child + "/page") for child in children})
    result, fetched = run(routes, max_children=1)
    assert [url for url in fetched if url in children] == [children[0]]
    assert result["expanded"]["children"] == {"limit": 1, "listed": 4, "fetched": 1, "skipped": 3}
    assert result["expanded"]["truncated"] is True
    assert sum("Child sitemap limit reached (1)" in warning for warning in result["warnings"]) == 1
    assert result["expanded"]["totals"]["total_urls"] == 1


def test_nested_index_is_a_finding_and_is_not_followed():
    routes = {
        SITE + "/sitemap.xml": index(SITE + "/nested.xml"),
        SITE + "/nested.xml": index(SITE + "/grandchild.xml"),
        SITE + "/grandchild.xml": urlset(SITE + "/deep"),
    }
    result, fetched = run(routes)
    assert SITE + "/grandchild.xml" not in fetched
    assert file_for(result, "/sitemap.xml")["findings"] == ["nested_sitemap_index"]
    nested = file_for(result, "/nested.xml")
    assert (nested["kind"], nested["child_count"]) == ("sitemapindex", 1)
    assert any("Nested sitemap index was not followed" in warning for warning in result["warnings"])
    assert result["expanded"]["totals"]["total_urls"] == 0


def test_index_that_lists_itself_is_not_refetched():
    routes = {SITE + "/sitemap.xml": index(SITE + "/sitemap.xml")}
    result, fetched = run(routes)
    assert fetched.count(SITE + "/sitemap.xml") == 1
    assert file_for(result, "/sitemap.xml")["findings"] == ["nested_sitemap_index"]


def test_paths_redirecting_to_one_file_are_reported_and_counted_once():
    final = SITE + "/sitemap_index.xml"
    body = index(SITE + "/posts.xml")
    routes = {
        SITE + "/sitemap.xml": response(body, final),
        final: body,
        SITE + "/posts.xml": urlset(SITE + "/p1"),
    }
    result, fetched = run(routes, robots=f"Sitemap: {SITE}/posts.xml\n".encode())
    assert [item["url"] for item in result["found"]] == [SITE + "/posts.xml", final]
    assert [item["url"] for item in result["expanded"]["files"]] == [SITE + "/posts.xml", final]
    # posts.xml was declared in robots.txt and listed in the index: read once.
    assert fetched.count(SITE + "/posts.xml") == 1
    assert result["expanded"]["totals"]["total_urls"] == 1


def test_child_redirecting_to_a_known_file_is_counted_once():
    routes = {
        SITE + "/sitemap.xml": index(SITE + "/posts.xml", SITE + "/old-posts.xml"),
        SITE + "/posts.xml": urlset(SITE + "/p1"),
        SITE + "/old-posts.xml": response(urlset(SITE + "/p1"), SITE + "/posts.xml"),
    }
    result, _ = run(routes)
    assert [item["url"] for item in result["expanded"]["files"]].count(SITE + "/posts.xml") == 1
    assert result["expanded"]["totals"]["total_urls"] == 1


def test_gzip_sitemap_is_inflated_by_magic_bytes():
    plain = urlset(SITE + "/a", SITE + "/b")
    packed = gzip.compress(plain)
    # The second URL has no .gz suffix: detection is by content, not by name.
    routes = {SITE + "/sitemap.xml": index(SITE + "/posts.xml.gz", SITE + "/pages"),
              SITE + "/posts.xml.gz": response(packed, SITE + "/posts.xml.gz", content_type="application/gzip"),
              SITE + "/pages": response(packed, SITE + "/pages", content_type="application/octet-stream")}
    result, _ = run(routes)
    for suffix in ("/posts.xml.gz", "/pages"):
        item = file_for(result, suffix)
        assert (item["kind"], item["valid"], item["gzip"], item["url_count"]) == ("urlset", True, True, 2)
        assert (item["bytes"], item["decompressed_bytes"]) == (len(packed), len(plain))
    assert file_for(result, "/sitemap.xml")["gzip"] is False
    assert file_for(result, "/sitemap.xml")["decompressed_bytes"] is None


def test_gzip_is_classified_the_same_with_and_without_expand():
    packed = gzip.compress(urlset(SITE + "/a"))
    routes = {SITE + "/sitemap.xml": response(packed, SITE + "/sitemap.xml", content_type="application/gzip")}
    plain, _ = run(routes, expand=False)
    expanded, _ = run(routes)
    assert [(item["kind"], item["gzip"]) for item in plain["found"]] == [("urlset", True)]
    assert {key: expanded[key] for key in BASE_KEYS} == plain


def test_gzip_text_sitemap_is_classified_by_its_inner_name():
    packed = gzip.compress(f"{SITE}/one\n{SITE}/two\n".encode())
    routes = {SITE + "/sitemap.xml": index(SITE + "/urls.txt.gz"),
              SITE + "/urls.txt.gz": response(packed, SITE + "/urls.txt.gz", content_type="application/gzip")}
    result, _ = run(routes)
    item = file_for(result, "/urls.txt.gz")
    assert (item["kind"], item["url_count"], item["lastmod_count"]) == ("text", 2, 0)


def bomb(megabytes: int) -> bytes:
    """A small gzip stream that inflates to the given size, built in pieces."""
    packer = zlib.compressobj(9, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
    piece = b" " * (1024 * 1024)
    return b"".join(packer.compress(piece) for _ in range(megabytes)) + packer.flush()


def test_gunzip_stops_at_the_cap_without_inflating_the_rest():
    data = bomb(64)
    assert len(data) < 200 * 1024
    tracemalloc.start()
    try:
        assert discovery._gunzip_bounded(data, 1024 * 1024) == (b"", True)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    # 64 MiB would be needed to inflate it all; the capped read stays near 2 MiB.
    assert peak < 8 * 1024 * 1024


def test_gunzip_reads_exactly_up_to_the_cap():
    body = b"x" * 5000
    assert discovery._gunzip_bounded(gzip.compress(body), 5000) == (body, False)
    assert discovery._gunzip_bounded(gzip.compress(body), 4999) == (b"", True)
    # Concatenated gzip members are one file.
    assert discovery._gunzip_bounded(gzip.compress(b"ab") + gzip.compress(b"cd"), 10) == (b"abcd", False)


def test_gzip_over_the_uncompressed_limit_is_a_finding_not_a_parse():
    packed = gzip.compress(urlset(*[f"{SITE}/{'x' * 200}{number}" for number in range(50)]))
    routes = {SITE + "/sitemap.xml": index(SITE + "/big.xml.gz"),
              SITE + "/big.xml.gz": response(packed, SITE + "/big.xml.gz")}
    with patch.object(discovery, "MAX_SITEMAP_BYTES", 1024):
        result, _ = run(routes)
    item = file_for(result, "/big.xml.gz")
    assert (item["valid"], item["kind"], item["url_count"]) == (False, None, None)
    assert item["findings"] == ["over_50mib_uncompressed"]
    assert "50 MiB" in item["error"]


@pytest.mark.parametrize("damage", [lambda data: data[:-12], lambda data: data[:20] + b"\xff" * 20 + data[40:]])
def test_truncated_or_corrupt_gzip_is_an_error(damage):
    packed = damage(gzip.compress(urlset(*[f"{SITE}/page-{number}" for number in range(200)]), mtime=0))
    routes = {SITE + "/sitemap.xml": index(SITE + "/broken.xml.gz"),
              SITE + "/broken.xml.gz": response(packed, SITE + "/broken.xml.gz")}
    result, _ = run(routes)
    item = file_for(result, "/broken.xml.gz")
    assert (item["valid"], item["error"]) == (False, "invalid gzip data")


def test_oversized_body_is_reported_as_a_limit_finding():
    routes = {SITE + "/sitemap.xml": response(b"<urlset>", SITE + "/sitemap.xml", too_large=True)}
    result, _ = run(routes)
    item = file_for(result, "/sitemap.xml")
    assert (item["valid"], item["bytes"], item["findings"]) == (False, None, ["over_50mib_uncompressed"])
    assert result["found"] == []


def test_more_than_50000_urls_is_a_finding_and_the_sample_stays_bounded():
    locs = [f"{SITE}/p{number}" for number in range(50001)]
    result, _ = run({SITE + "/sitemap.xml": urlset(*locs)}, sample_size=3)
    item = file_for(result, "/sitemap.xml")
    assert item["url_count"] == 50001
    assert item["findings"] == ["over_50000_urls"]
    assert item["sample_urls"] == locs[:3]
    assert result["expanded"]["sample_size"] == 3
    assert result["expanded"]["totals"]["unique_urls"] == 50001
    assert len(json.dumps(result)) < 5000


def test_exactly_50000_urls_is_within_the_limit():
    result, _ = run({SITE + "/sitemap.xml": urlset(*[f"{SITE}/p{number}" for number in range(50000)])}, sample_size=0)
    item = file_for(result, "/sitemap.xml")
    assert (item["url_count"], item["findings"], item["sample_urls"]) == (50000, [], [])


def test_oversized_text_sitemap_keeps_its_count():
    body = "\n".join(f"{SITE}/p{number}" for number in range(50001)).encode()
    routes = {SITE + "/sitemap.xml": index(SITE + "/urls.txt"),
              SITE + "/urls.txt": response(body, SITE + "/urls.txt", content_type="text/plain")}
    result, _ = run(routes)
    item = file_for(result, "/urls.txt")
    assert (item["valid"], item["url_count"], item["findings"]) == (False, 50001, ["over_50000_urls"])


def test_lastmod_statistics():
    result, _ = run({SITE + "/sitemap.xml": urlset(
        (SITE + "/a", "2026-03-01T00:30:00+02:00"),  # 2026-02-28 22:30 UTC: the oldest
        (SITE + "/b", "2026-03-01"),
        (SITE + "/c", "2026-03-01"),
        (SITE + "/d", "2026-03-01"),
        (SITE + "/e", "2026-03-01T01:00:00Z"),  # the newest
        (SITE + "/f", "yesterday"),
        (SITE + "/g", "2026-13-01"),
        SITE + "/h",
    )})
    item = file_for(result, "/sitemap.xml")
    assert (item["url_count"], item["lastmod_count"], item["lastmod_invalid_count"]) == (8, 7, 2)
    assert item["lastmod_oldest"] == "2026-03-01T00:30:00+02:00"
    assert item["lastmod_newest"] == "2026-03-01T01:00:00Z"
    assert item["lastmod_most_common"] == "2026-03-01"
    assert item["lastmod_identical_share"] == round(3 / 7, 4)


def test_auto_stamped_lastmod_shows_as_a_full_share():
    stamp = "2026-11-10T03:00:00+00:00"
    result, _ = run({SITE + "/sitemap.xml": urlset(*[(f"{SITE}/p{number}", stamp) for number in range(40)])})
    item = file_for(result, "/sitemap.xml")
    assert (item["lastmod_identical_share"], item["lastmod_oldest"], item["lastmod_newest"]) == (1.0, stamp, stamp)


def test_file_without_lastmod_reports_no_share():
    result, _ = run({SITE + "/sitemap.xml": urlset(SITE + "/a")})
    item = file_for(result, "/sitemap.xml")
    assert (item["lastmod_count"], item["lastmod_oldest"], item["lastmod_identical_share"]) == (0, None, None)


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("2026", True),
        ("2026-02", True),
        ("2026-02-07", True),
        ("2026-02-07T10:15Z", True),
        ("2026-02-07T10:15:30+01:00", True),
        ("2026-02-07T10:15:30.25-08:00", True),
        ("2026-02-07T10:15:30", False),  # A time needs a zone.
        ("2026-02-30", False),
        ("2026-02-07 10:15:30Z", False),
        ("07/02/2026", False),
        ("2026-02-07T10:15:30+25:00", False),
        ("", False),
    ],
)
def test_w3c_datetime_validation(value, valid):
    assert (discovery._parse_w3c_datetime(value) is not None) is valid


def test_entries_on_another_host_are_counted_with_redacted_examples():
    locs = [SITE + "/home", "https://www.example.com/a?token=keep-out"]
    locs += [f"https://other.example.net/p{number}" for number in range(8)]
    result, _ = run({SITE + "/sitemap.xml": urlset(*locs)})
    item = file_for(result, "/sitemap.xml")
    assert item["cross_host_url_count"] == 9
    assert len(item["cross_host_url_examples"]) == discovery.MAX_EXAMPLES
    assert item["cross_host_url_examples"][0] == "https://www.example.com/a"
    assert "keep-out" not in json.dumps(result)


def test_duplicates_within_and_across_files_after_normalisation():
    routes = {
        SITE + "/sitemap.xml": index(SITE + "/one.xml", SITE + "/two.xml"),
        SITE + "/one.xml": urlset(
            SITE + "/a",
            "HTTPS://EXAMPLE.com:443/a?utm_source=news#top",  # same as /a
            SITE + "/a/",  # the trailing slash is a different address
            SITE + "/b?id=1",
        ),
        SITE + "/two.xml": urlset(SITE + "/a", SITE + "/b?id=2", SITE + "/c"),
    }
    result, _ = run(routes)
    assert file_for(result, "/one.xml")["duplicate_count"] == 1
    assert file_for(result, "/two.xml")["duplicate_count"] == 0
    assert result["expanded"]["totals"] == {
        "sitemap_files": 3,
        "total_urls": 7,
        "unique_urls": 5,
        "duplicates_within_files": 1,
        "duplicates_across_files": 1,
        "invalid_locs": 0,
    }


def test_duplicate_totals_are_withheld_when_tracking_is_full():
    locs = [f"{SITE}/p{number}" for number in range(5)]
    with patch.object(discovery, "MAX_TRACKED_URLS", 2):
        result, _ = run({SITE + "/sitemap.xml": urlset(*locs)})
    totals = result["expanded"]["totals"]
    assert (totals["total_urls"], totals["unique_urls"], totals["duplicates_across_files"]) == (5, None, None)
    assert file_for(result, "/sitemap.xml")["duplicate_count"] is None
    assert any("unique and duplicate totals are not reported" in warning for warning in result["warnings"])


def test_invalid_locs_are_counted_and_never_printed():
    body = urlset("/relative", "javascript:alert(1)", "https://user:secret@example.com/x", SITE + "/" + "a" * 2048, SITE + "/ok")
    body = body.replace(b"</urlset>", b"<url></url></urlset>")
    result, _ = run({SITE + "/sitemap.xml": body})
    item = file_for(result, "/sitemap.xml")
    assert (item["url_count"], item["invalid_loc_count"], item["sample_urls"]) == (6, 5, [SITE + "/ok"])
    assert "secret" not in json.dumps(result)


def test_child_urls_are_validated_like_any_other_url():
    """A child loc is untrusted: bad syntax is never fetched, a private target is refused."""
    private = "http://127.0.0.1/internal.xml"
    real_fetch = discovery._bounded_fetch
    routes = {
        SITE + "/sitemap.xml": index(
            private,
            "file:///etc/passwd",
            "https://user:pw@example.com/a.xml",
            "//example.com/b.xml",
            "https://exa mple.com/c.xml",
        ),
        # The real fetch path: url_safety refuses the literal before any request.
        private: lambda url: real_fetch(url, 100),
    }
    result, fetched = run(routes)
    assert [url for url in fetched if "sitemap" not in url and "robots" not in url] == [private]
    top = file_for(result, "/sitemap.xml")
    assert (top["child_count"], top["invalid_loc_count"]) == (5, 4)
    refused = file_for(result, "/internal.xml")
    assert (refused["valid"], refused["error"], refused["status_code"]) == (False, "URL safety validation failed", None)
    assert refused["cross_host"] is True


def test_cross_host_child_is_flagged_and_uses_the_same_fetch():
    child = "https://cdn.example.net/posts.xml?sig=private-value"
    routes = {SITE + "/sitemap.xml": index(child.replace("&", "&amp;")), child: urlset("https://cdn.example.net/p1")}
    result, fetched = run(routes)
    assert child in fetched
    item = file_for(result, "/posts.xml")
    assert (item["cross_host"], item["valid"], item["query_redacted"]) == (True, True, True)
    assert item["cross_host_url_count"] == 0  # Entries match the host of their own file.
    top = file_for(result, "/sitemap.xml")
    assert (top["cross_host_url_count"], top["cross_host_url_examples"]) == (1, ["https://cdn.example.net/posts.xml"])
    assert "private-value" not in json.dumps(result)


def test_same_host_child_has_no_cross_host_flag():
    routes = {SITE + "/sitemap.xml": index(SITE + "/posts.xml"), SITE + "/posts.xml": urlset(SITE + "/p1")}
    result, _ = run(routes)
    assert "cross_host" not in file_for(result, "/posts.xml")


def test_xml_hardening_applies_to_children_and_inside_gzip():
    hostile = b'<!DOCTYPE urlset [<!ENTITY x SYSTEM "file:///etc/passwd">]><urlset><url><loc>&x;</loc></url></urlset>'
    routes = {
        SITE + "/sitemap.xml": index(SITE + "/plain.xml", SITE + "/packed.xml.gz", SITE + "/broken.xml", SITE + "/gone.xml"),
        SITE + "/plain.xml": hostile,
        SITE + "/packed.xml.gz": gzip.compress(hostile),
        SITE + "/broken.xml": b"<urlset><url>",
    }
    result, _ = run(routes)
    for suffix in ("/plain.xml", "/packed.xml.gz"):
        item = file_for(result, suffix)
        assert (item["valid"], item["error"], item["url_count"]) == (False, "DOCTYPE is not allowed in sitemap XML", None)
    assert file_for(result, "/broken.xml")["error"] == "invalid XML"
    assert (file_for(result, "/gone.xml")["error"], file_for(result, "/gone.xml")["status_code"]) == ("HTTP 404", 404)
    assert result["expanded"]["totals"]["sitemap_files"] == 1


def test_extension_tags_are_not_mistaken_for_entries():
    body = (
        f'<urlset {NS} xmlns:image="http://www.google.com/schemas/sitemap-image/1.1" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml"><!-- note -->'
        f"<url><loc>{SITE}/a</loc>"
        '<xhtml:link rel="alternate" hreflang="de" href="https://example.de/a"/>'
        "<image:image><image:loc>https://cdn.example.net/a.png</image:loc></image:image></url></urlset>"
    ).encode()
    result, _ = run({SITE + "/sitemap.xml": body})
    item = file_for(result, "/sitemap.xml")
    assert (item["url_count"], item["cross_host_url_count"], item["sample_urls"]) == (1, 0, [SITE + "/a"])


def test_feeds_count_their_item_links():
    rss = f"<rss><channel><link>{SITE}/</link><item><link>{SITE}/one</link></item><item><link>{SITE}/two</link></item></channel></rss>"
    atom = (
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        f'<link href="{SITE}/"/><entry><link rel="self" href="{SITE}/feed/1"/>'
        f'<link href="{SITE}/one"/><updated>2026-02-07T10:00:00Z</updated></entry></feed>'
    )
    routes = {SITE + "/sitemap.xml": rss.encode(), SITE + "/wp-sitemap.xml": atom.encode()}
    result, _ = run(routes)
    assert (file_for(result, "/sitemap.xml")["kind"], file_for(result, "/sitemap.xml")["url_count"]) == ("rss", 2)
    feed = file_for(result, "/wp-sitemap.xml")
    assert (feed["kind"], feed["url_count"], feed["sample_urls"], feed["lastmod_count"]) == ("feed", 1, [SITE + "/one"], 1)


def test_cli_prints_expanded_json_and_validates_flags(capsys):
    routes = {SITE + "/sitemap.xml": urlset(SITE + "/a", SITE + "/b")}

    def fake_fetch(url, _limit):
        return response(routes[url], url) if url in routes else response(url=url, status=404)

    with patch.object(discovery, "_bounded_fetch", side_effect=fake_fetch):
        with patch.object(sys, "argv", ["sitemap_discovery.py", SITE, "--expand", "--sample", "1", "--json"]):
            assert discovery.main() == 0
        printed = json.loads(capsys.readouterr().out)
        assert printed["expanded"]["files"][0]["sample_urls"] == [SITE + "/a"]
        assert printed["expanded"]["totals"]["total_urls"] == 2

        with patch.object(sys, "argv", ["sitemap_discovery.py", SITE, "--expand"]):
            assert discovery.main() == 0
        text = capsys.readouterr().out
        assert f"{SITE}/sitemap.xml (urlset, 2 URLs)" in text
        assert "Total: 2 URLs in 1 files, 2 unique" in text

        with patch.object(sys, "argv", ["sitemap_discovery.py", SITE, "--json"]):
            assert discovery.main() == 0
        assert "expanded" not in json.loads(capsys.readouterr().out)

    with patch.object(sys, "argv", ["sitemap_discovery.py", SITE, "--expand", "--max-children", "-1"]):
        with pytest.raises(SystemExit) as stop:
            discovery.main()
    assert stop.value.code == 2


def test_sample_urls_keep_their_query_so_they_can_be_checked():
    locs = [f"{SITE}/product?id={number}" for number in range(5)]
    result, _ = run({SITE + "/sitemap.xml": urlset(*locs)})
    item = file_for(result, "/sitemap.xml")
    assert item["sample_urls"] == locs
    assert (item["redacted_url_count"], item["redacted_url_examples"]) == (0, [])


def test_sample_urls_are_unique_and_drop_only_the_fragment():
    body = urlset(SITE + "/a?page=2#top", SITE + "/a?page=2", SITE + "/a?page=2#end", SITE + "/b", SITE + "/b")
    result, _ = run({SITE + "/sitemap.xml": body}, sample_size=2)
    assert file_for(result, "/sitemap.xml")["sample_urls"] == [SITE + "/a?page=2", SITE + "/b"]


def test_urls_with_token_parameters_are_listed_apart_and_never_sampled():
    body = urlset(
        SITE + "/account?token=abc123SECRET&amp;id=1",
        SITE + "/cart?PHPSESSID=deadbeefSECRET",
        SITE + "/dl?file=a.pdf&amp;X-Amz-Signature=feedSECRET",
        SITE + "/blog?author=jane",  # "author" is not "auth"
        SITE + "/search?keyword=shoes",  # "keyword" is not "key"
    )
    result, _ = run({SITE + "/sitemap.xml": body})
    item = file_for(result, "/sitemap.xml")
    assert item["sample_urls"] == [SITE + "/blog?author=jane", SITE + "/search?keyword=shoes"]
    assert item["redacted_url_count"] == 3
    assert item["redacted_url_examples"] == [
        SITE + "/account?token=REDACTED&id=1",
        SITE + "/cart?PHPSESSID=REDACTED",
        SITE + "/dl?file=a.pdf&X-Amz-Signature=REDACTED",
    ]
    assert "SECRET" not in json.dumps(result)
    assert (item["url_count"], result["expanded"]["totals"]["unique_urls"]) == (5, 5)


def test_a_url_repeated_in_one_file_and_listed_in_an_earlier_file_is_counted_once_each_way():
    """The reviewer's case: c.xml lists p0 twice, and a.xml already listed p0."""
    routes = {
        SITE + "/sitemap.xml": index(SITE + "/a.xml", SITE + "/b.xml", SITE + "/c.xml"),
        SITE + "/a.xml": urlset(SITE + "/p0", SITE + "/p1", SITE + "/p2"),
        SITE + "/b.xml": urlset(SITE + "/p2", SITE + "/p3", SITE + "/p4"),
        SITE + "/c.xml": urlset(SITE + "/p0", SITE + "/p0", SITE + "/zz", SITE + "/p2", SITE + "/zz", SITE + "/zz"),
    }
    result, _ = run(routes)
    assert [file_for(result, name)["duplicate_count"] for name in ("/a.xml", "/b.xml", "/c.xml")] == [0, 0, 3]
    totals = result["expanded"]["totals"]
    # b repeats p2 from a; c repeats p0 and p2 from earlier files.
    assert (totals["duplicates_within_files"], totals["duplicates_across_files"]) == (3, 3)
    assert (totals["total_urls"], totals["unique_urls"]) == (12, 6)
    assert totals["total_urls"] == (
        totals["unique_urls"] + totals["duplicates_within_files"] + totals["duplicates_across_files"]
    )


MALFORMED = [
    "http://[bad/sitemap.xml",
    "http://[::1/sitemap.xml",
    "https://exa\u2100mple.com/sitemap.xml",
    "http://user:hunter2@[bad/sitemap.xml?token=hunter2",
]


@pytest.mark.parametrize("bad", MALFORMED)
@pytest.mark.parametrize("expand", [False, True])
def test_malformed_robots_sitemap_line_is_recorded_and_the_run_continues(bad, expand):
    good = SITE + "/good.xml"
    robots = f"Sitemap: {bad}\nSitemap: {good}\n".encode()
    result, fetched = run({good: urlset(SITE + "/a")}, robots=robots, expand=expand)
    assert bad not in fetched
    assert [item["url"] for item in result["found"]] == [good]
    skipped = result["checked"][0]
    assert (skipped["source"], skipped["valid"], skipped["error"]) == ("robots.txt", False, "Malformed sitemap URL")
    assert len(result["declared"]) == 2
    assert "hunter2" not in json.dumps(result)


@pytest.mark.parametrize("bad", MALFORMED)
def test_malformed_urls_inside_sitemaps_are_counted_invalid(bad):
    routes = {
        SITE + "/sitemap.xml": index(bad, SITE + "/posts.xml", SITE + "/urls.txt"),
        SITE + "/posts.xml": urlset(bad, SITE + "/a"),
        SITE + "/urls.txt": response(f"{SITE}/b\n{bad}\n".encode(), SITE + "/urls.txt", content_type="text/plain"),
    }
    result, fetched = run(routes)
    assert bad not in fetched
    assert file_for(result, "/sitemap.xml")["invalid_loc_count"] == 1
    assert (file_for(result, "/posts.xml")["url_count"], file_for(result, "/posts.xml")["invalid_loc_count"]) == (2, 1)
    assert file_for(result, "/urls.txt")["error"] == "invalid text sitemap"
    assert "hunter2" not in json.dumps(result)


@pytest.mark.parametrize("bad", MALFORMED)
def test_malformed_url_never_raises_from_the_helpers(bad):
    assert discovery._bounded_fetch(bad, 100)["error"] is not None
    shown, redacted = discovery._display_url(bad)
    assert redacted is True and "hunter2" not in shown
    assert discovery._host(bad) == ""
    assert discovery.discover_sitemaps(bad)["error"] is not None
    # A redirect target or content type check on an unparsable final URL.
    assert discovery._sitemap_kind(b"https://example.com/a\n", "application/octet-stream", bad)[0] is None
    body = discovery._read_body(response(gzip.compress(urlset(SITE + "/a")), bad))
    assert body["kind"] == "urlset"
