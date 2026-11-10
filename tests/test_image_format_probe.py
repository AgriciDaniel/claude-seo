"""
Tests for the served-format probe in scripts/parse_html.py.

Background: closes issue #331. Sites that negotiate image formats (WordPress
WebP plugins, Cloudflare Polish, image CDNs) serve WebP or AVIF from a
`.jpg`/`.png` URL, so judging format by the URL extension produced false
"convert to WebP" recommendations. The probe reads the served format instead.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

pytest.importorskip("bs4")
pytest.importorskip("requests")
import parse_html  # noqa: E402
from parse_html import (  # noqa: E402
    IMAGE_ACCEPT,
    _sniff_image_format,
    probe_image_format,
    probe_images,
)

JPEG = b"\xff\xd8\xff\xdb\x00\x84" + b"\x00" * 26
WEBP = b"RIFF\x20\x40\x00\x00WEBPVP8 " + b"\x00" * 16
AVIF = b"\x00\x00\x00\x1cftypavif" + b"\x00" * 20


class _FakeResponse:
    def __init__(self, body: bytes, headers: dict, status_code: int = 200):
        self._body = body
        self.headers = headers
        self.status_code = status_code
        self.closed = False

    def iter_content(self, chunk_size):
        yield self._body[:chunk_size]

    def close(self):
        self.closed = True


@pytest.fixture
def fake_get(monkeypatch):
    """Patch safe_requests_get; record each call and return the queued response."""
    calls = []
    responses = {}

    def _get(url, **kwargs):
        calls.append((url, kwargs))
        return responses[url]

    monkeypatch.setattr(parse_html, "safe_requests_get", _get)
    return calls, responses


@pytest.mark.parametrize(
    "head, expected",
    [
        (JPEG, "jpeg"),
        (WEBP, "webp"),
        (AVIF, "avif"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, "png"),
        (b"GIF89a" + b"\x00" * 8, "gif"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'>", "svg"),
        (b'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg">', "svg"),
        (
            b'\xef\xbb\xbf<?xml version="1.0"?><!-- Generator: Illustrator -->'
            b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "svg11.dtd"><svg>',
            "svg",
        ),
        (b'<?xml version="1.0" encoding="UTF-8"?><urlset><url></url></urlset>', None),
        (b'<?xml version="1.0"?><!DOCTYPE html><html><body><svg>', None),
        (b'<?xml version="1.0" encoding="UTF-8"', None),
        (b"<!DOCTYPE html><html><body><svg>", None),
        (b"not an image", None),
    ],
)
def test_sniff_image_format(head, expected):
    assert _sniff_image_format(head) == expected


def test_jpeg_url_serving_webp_reports_webp(fake_get):
    calls, responses = fake_get
    url = "https://example.com/uploads/photo.jpeg"
    responses[url] = _FakeResponse(
        WEBP, {"Content-Type": "image/webp", "Content-Length": "16424", "Vary": "Accept, Accept-Encoding"}
    )

    result = probe_image_format(url)

    assert result == {
        "served_format": "webp",
        "served_bytes": 16424,
        "negotiated": True,
        "probe_error": None,
    }
    assert calls[0][1]["headers"]["Accept"] == IMAGE_ACCEPT
    assert responses[url].closed


def test_magic_bytes_win_over_a_wrong_content_type(fake_get):
    _, responses = fake_get
    url = "https://example.com/photo.png"
    responses[url] = _FakeResponse(AVIF, {"Content-Type": "image/png"})

    result = probe_image_format(url)

    assert result["served_format"] == "avif"
    assert result["served_bytes"] is None
    assert result["negotiated"] is False


def test_content_type_used_when_bytes_are_unknown(fake_get):
    _, responses = fake_get
    url = "https://example.com/photo.jpg"
    responses[url] = _FakeResponse(b"\x00" * 32, {"Content-Type": "image/jpeg; charset=binary"})

    assert probe_image_format(url)["served_format"] == "jpeg"


def test_http_error_is_reported_not_guessed(fake_get):
    _, responses = fake_get
    url = "https://example.com/missing.webp"
    responses[url] = _FakeResponse(b"<html>", {"Content-Type": "text/html"}, status_code=404)

    result = probe_image_format(url)

    assert result["served_format"] is None
    assert result["probe_error"] == "HTTP 404"


def test_data_uri_is_not_fetched(fake_get):
    calls, _ = fake_get

    result = probe_image_format("data:image/svg+xml;base64,PHN2Zz4=")

    assert result["probe_error"] == "not an http(s) URL"
    assert calls == []


def test_url_safety_rejection_is_reported(monkeypatch):
    def _blocked(url, **kwargs):
        raise parse_html.URLSafetyError("blocked private IP")

    monkeypatch.setattr(parse_html, "safe_requests_get", _blocked)

    result = probe_image_format("https://internal.example/photo.jpg")

    assert result["served_format"] is None
    assert result["probe_error"].startswith("url_safety:")


def test_probe_images_dedupes_and_respects_limit(fake_get):
    calls, responses = fake_get
    a, b = "https://example.com/a.jpg", "https://example.com/b.jpg"
    responses[a] = _FakeResponse(WEBP, {"Content-Type": "image/webp"})
    images = [{"src": a}, {"src": a}, {"src": b}]

    probe_images(images, limit=1)

    assert len(calls) == 1
    assert images[0]["served_format"] == images[1]["served_format"] == "webp"
    assert images[2]["served_format"] is None
    assert "probe limit" in images[2]["probe_error"]


def test_parse_html_alone_makes_no_requests(fake_get):
    calls, _ = fake_get

    result = parse_html.parse_html('<img src="photo.jpg" alt="x">', "https://example.com/")

    assert calls == []
    assert "served_format" not in result["images"][0]


def test_malformed_src_is_reported_not_raised(fake_get):
    calls, _ = fake_get

    result = probe_image_format("http://[bad/a.jpg")

    assert result["served_format"] is None
    assert result["probe_error"].startswith("malformed URL")
    assert calls == []


def test_probe_images_survives_a_malformed_src(fake_get):
    calls, responses = fake_get
    good = "https://example.com/a.jpg"
    responses[good] = _FakeResponse(WEBP, {"Content-Type": "image/webp"})
    images = [{"src": "http://[bad/a.jpg"}, {"src": good}]

    probe_images(images)

    assert images[0]["probe_error"].startswith("malformed URL")
    assert images[1]["served_format"] == "webp"
    assert [url for url, _ in calls] == [good]


@pytest.mark.parametrize(
    "body, content_type",
    [
        (b"<!DOCTYPE html><html><head><title>Not found</title>", "text/html; charset=utf-8"),
        (b"Hotlinking is not allowed", "text/plain"),
        (b"\x00" * 32, ""),
    ],
)
def test_non_image_200_sets_probe_error(fake_get, body, content_type):
    _, responses = fake_get
    url = "https://example.com/photo.jpg"
    headers = {"Content-Type": content_type} if content_type else {}
    responses[url] = _FakeResponse(body, headers)

    result = probe_image_format(url)

    assert result["served_format"] is None
    assert result["probe_error"].startswith("not a recognized image")
    assert responses[url].closed


def test_xml_that_is_not_svg_is_not_labelled_svg(fake_get):
    _, responses = fake_get
    url = "https://example.com/logo.svg"
    responses[url] = _FakeResponse(
        b'<?xml version="1.0" encoding="UTF-8"?><urlset><url></url></urlset>',
        {"Content-Type": "application/xml"},
    )

    result = probe_image_format(url)

    assert result["served_format"] is None
    assert "application/xml" in result["probe_error"]


def test_svg_content_type_is_trusted_when_the_root_is_past_the_sniffed_bytes(fake_get):
    _, responses = fake_get
    url = "https://example.com/logo.svg"
    body = b'<?xml version="1.0"?><!-- ' + b"x" * 2000 + b" --><svg></svg>"
    responses[url] = _FakeResponse(body, {"Content-Type": "image/svg+xml"})

    result = probe_image_format(url)

    assert result["served_format"] == "svg"
    assert result["probe_error"] is None
