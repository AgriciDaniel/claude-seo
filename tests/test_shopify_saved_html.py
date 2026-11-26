"""Saved HTML must not collapse distinct crawl URLs onto one filename."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
pytest.importorskip("lxml")
pytest.importorskip("requests")

import shopify_crawl as crawl  # noqa: E402

ORIGIN = crawl.Origin("https", "shop.example")


class PageResponse:
    status_code = 200
    headers = {"Content-Type": "text/html"}
    encoding = "utf-8"

    def __init__(self, body: str):
        self.body = body.encode("utf-8")

    def iter_content(self, chunk_size=65536):
        yield self.body

    def close(self):
        pass


class Session:
    def __init__(self, body: str):
        self.body = body

    def get(self, url, **kwargs):
        return PageResponse(self.body)


def _crawl(url: str, body: str, directory: Path | None):
    session = Session(body)
    return crawl.crawl_one(
        lambda: session, url, ORIGIN, None, crawl.RateLimitGovernor(0),
        timeout=5, save_html_dir=directory,
    )


@pytest.mark.parametrize("paths", [
    ("/products/a-b", "/products/a/b", "/products/a_b"),
    ("/products/a?variant=1", "/products/a?variant=2"),
    ("/products/" + "a" * 150 + "1", "/products/" + "a" * 150 + "2"),
    ("/collections/Tea", "/collections/tea"),
    ("/products/红茶", "/products/绿茶"),
])
def test_distinct_pages_keep_their_own_content(paths, tmp_path):
    bodies = [f"<html><title>Product {i}</title></html>" for i in range(len(paths))]
    records = [_crawl(ORIGIN.root + path, body, tmp_path) for path, body in zip(paths, bodies)]
    files = list(tmp_path.glob("*.html"))

    assert len(files) == len(paths)
    assert len({p.name.casefold() for p in files}) == len(paths)
    assert {p.read_text(encoding="utf-8") for p in files} == set(bodies)
    for record, body in zip(records, bodies):
        assert (tmp_path / record["html_file"]).read_text(encoding="utf-8") == body


def test_same_url_reuses_its_artifact_and_replaces_old_content(tmp_path):
    url = ORIGIN.root + "/products/a?variant=1"
    first = _crawl(url, "<title>Before</title>", tmp_path)
    second = _crawl(url, "<title>After</title>", tmp_path)

    assert first["html_file"] == second["html_file"]
    assert len(list(tmp_path.iterdir())) == 1
    assert (tmp_path / second["html_file"]).read_text(encoding="utf-8") == "<title>After</title>"


@pytest.mark.parametrize("path", ["/", "/products/a" * 30, "/../x:y*?secret=private-token", "/产品/茶"])
def test_artifact_names_are_bounded_and_portable(path, tmp_path):
    record = _crawl(ORIGIN.root + path, "<title>Product</title>", tmp_path)
    filename = record["html_file"]

    assert filename.endswith(".html")
    assert len(filename) <= 125
    assert filename.isascii()
    assert all(char.isalnum() or char in "_.-" for char in filename)
    assert "private-token" not in filename
    assert (tmp_path / filename).is_file()


def test_disabled_saving_leaves_no_file_reference(tmp_path):
    result = _crawl(ORIGIN.root + "/products/a", "<title>Product</title>", None)

    assert "html_file" not in result
    assert not list(tmp_path.iterdir())
