"""Exact and near-duplicate image groups. Issue #255.

Called by pytest. Synthetic PNGs only: no production images, no dates.
The user asked to solve the issue locally and not to commit or push.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

pytest.importorskip("PIL")
import image_duplicates  # noqa: E402
from PIL import Image  # noqa: E402


def _png(paint) -> bytes:
    img = Image.new("RGB", (32, 32))
    pixels = img.load()
    for y in range(32):
        for x in range(32):
            pixels[x, y] = paint(x, y)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    assert len(data) >= image_duplicates.MIN_CONTENT_BYTES
    return data


def _gradient(shift: int = 0):
    return _png(lambda x, y: ((x * 8 + shift) % 256, (y * 8) % 256, 80))


def _checker() -> bytes:
    return _png(lambda x, y: (255, 255, 255) if (x // 4 + y // 4) % 2 == 0 else (0, 0, 0))


def _fetched(url: str, body: bytes | None = None, error: str | None = None) -> dict:
    item = {"url": url, "references": 1}
    if error:
        item["error"] = error
    else:
        item["body"] = body
    return item


def test_identical_bytes_are_exact_and_not_also_near() -> None:
    body = _gradient()
    result = image_duplicates.report([
        _fetched("https://cdn.example/a.png", body),
        _fetched("https://cdn.example/b.png", body),
    ])
    assert result["checked"] == 2
    assert len(result["exact_duplicates"]) == 1
    assert result["exact_duplicates"][0]["urls"] == [
        "https://cdn.example/a.png",
        "https://cdn.example/b.png",
    ]
    assert result["near_duplicates"] == []
    assert result["indexed_image_search"] == "not performed"
    assert result["near_status"] == "checked"


def test_a_one_pixel_change_is_near_not_exact() -> None:
    original = _gradient(0)
    changed = _png(lambda x, y: ((x * 8) % 256, (y * 8) % 256, 80 if (x, y) != (3, 3) else 90))
    assert original != changed
    result = image_duplicates.report([
        _fetched("https://cdn.example/original.png", original),
        _fetched("https://cdn.example/changed.png", changed),
    ])
    assert result["exact_duplicates"] == []
    assert len(result["near_duplicates"]) == 1
    assert result["near_duplicates"][0]["distance"] <= image_duplicates.NEAR_DISTANCE
    assert set(result["near_duplicates"][0]["urls"]) == {
        "https://cdn.example/original.png",
        "https://cdn.example/changed.png",
    }


def test_a_different_picture_is_not_a_near_duplicate() -> None:
    result = image_duplicates.report([
        _fetched("https://cdn.example/gradient.png", _gradient()),
        _fetched("https://cdn.example/checker.png", _checker()),
    ])
    assert result["exact_duplicates"] == []
    assert result["near_duplicates"] == []
    assert "No exact or near-duplicate" in result["presentation"]


def test_flat_colors_are_not_called_lookalikes() -> None:
    red = _png(lambda _x, _y: (220, 20, 20))
    blue = _png(lambda _x, _y: (20, 20, 220))
    result = image_duplicates.report([
        _fetched("https://cdn.example/red.png", red),
        _fetched("https://cdn.example/blue.png", blue),
    ])
    assert result["exact_duplicates"] == []
    assert result["near_duplicates"] == []


def test_skips_decorative_pixels_data_urls_and_the_limit() -> None:
    images = [
        {"resolved_src": "https://cdn.example/hero.png"},
        {"resolved_src": "https://cdn.example/hero.png"},
        {"src": "https://cdn.example/icon.png", "decorative": True},
        {"src": "https://cdn.example/pixel.gif", "width": "1", "height": "1px"},
        {"src": "data:image/png;base64,aaaa"},
        {"src": "https://cdn.example/second.png"},
        "nope",
    ]
    chosen, skipped = image_duplicates.collect_candidates(images, limit=1)
    assert [item["url"] for item in chosen] == ["https://cdn.example/hero.png"]
    assert chosen[0]["references"] == 2
    reasons = {item["reason"] for item in skipped}
    assert reasons == {
        "decorative",
        "tracking pixel",
        "data url",
        "limit of 1 images",
        "not an image object",
    }


def test_non_images_tiny_bodies_and_fetch_errors_are_not_duplicates() -> None:
    tiny = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    assert len(tiny) < image_duplicates.MIN_CONTENT_BYTES
    result = image_duplicates.report([
        _fetched("https://cdn.example/tiny.png", tiny),
        _fetched("https://cdn.example/page.html", b"<html>not an image</html>" * 10),
        _fetched("https://cdn.example/missing.png", error="HTTP 404"),
    ])
    assert result["checked"] == 0
    assert result["exact_duplicates"] == []
    assert {item["reason"] for item in result["skipped"]} == {"smaller than a content image"}
    assert {item["error"] for item in result["failed"]} == {"not a recognized image", "HTTP 404"}


def test_private_url_is_refused_before_a_connection() -> None:
    result = image_duplicates.fetch_image("http://127.0.0.1/secret.png")
    assert result["error"].startswith("url_safety:")
    assert "body" not in result


def test_oversized_body_is_not_hashed(monkeypatch) -> None:
    class _Response:
        status_code = 200
        headers: dict = {}

        def iter_content(self, chunk_size):
            yield b"x" * 30

        def close(self):
            return None

    monkeypatch.setattr(image_duplicates, "MAX_IMAGE_BYTES", 16)
    monkeypatch.setattr(
        "url_safety.safe_requests_get",
        lambda *args, **kwargs: _Response(),
    )
    result = image_duplicates.fetch_image("https://cdn.example/huge.png")
    assert "body" not in result
    assert "larger than 16 bytes" in result["error"]


def test_cli_reports_exact_duplicates_without_a_network(tmp_path: Path, monkeypatch, capsys) -> None:
    body = _gradient()
    monkeypatch.setattr(image_duplicates, "fetch_image", lambda url, timeout: {"body": body})
    path = tmp_path / "images.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps({
        "images": [
            {"resolved_src": "https://cdn.example/a.png"},
            {"resolved_src": "https://cdn.example/b.png"},
        ]
    }).encode("utf-8"))
    assert image_duplicates.main(["--images", str(path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["exact_duplicates"][0]["urls"] == [
        "https://cdn.example/a.png",
        "https://cdn.example/b.png",
    ]


def test_cli_errors_are_json_and_do_not_fetch(tmp_path: Path, capsys) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    assert image_duplicates.main(["--images", str(broken)]) == 2
    assert "invalid JSON" in json.loads(capsys.readouterr().out)["error"]

    missing = tmp_path / "missing.json"
    assert image_duplicates.main(["--images", str(missing)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"

    assert image_duplicates.main(["--images", str(broken), "--limit", "0"]) == 2


def test_skill_delegates_duplicates_to_the_script() -> None:
    text = (REPO_ROOT / "skills" / "seo-images" / "SKILL.md").read_text(encoding="utf-8")
    section = text[text.index("### Duplicate content"):text.index("## Output")]
    assert "run image_duplicates.py --url <url> --json" in section
    assert "claude-seo" in section
    assert "python image_duplicates.py" not in section
    assert "python3" not in section
    assert "indexed_image_search" in section
    assert "Do not decide that two images are duplicates by looking at them." in section


def test_hamming_counts_bits() -> None:
    assert image_duplicates.hamming(0b1011, 0b1001) == 1
