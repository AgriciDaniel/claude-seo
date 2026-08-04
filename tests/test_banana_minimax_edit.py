"""Tests for the Banana direct REST fallback MiniMax image-to-image path."""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SECRET = "sk-" + "DUMMYMINIMAXKEY0000000000"


def _load_edit():
    spec = importlib.util.spec_from_file_location(
        "banana_edit_minimax", REPO_ROOT / "extensions/banana/scripts/edit.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, payload):
        if isinstance(payload, bytes):
            self._body = payload
        else:
            self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _capture_exit_output(callable_):
    out = io.StringIO()
    with redirect_stdout(out):
        try:
            callable_()
        except SystemExit as exc:
            assert exc.code == 1
    return json.loads(out.getvalue())


def test_endpoints_cover_global_and_cn_regions():
    module = _load_edit()
    assert module.MINIMAX_ENDPOINTS["global_en"] == "https://api.minimax.io/v1/image_generation"
    assert module.MINIMAX_ENDPOINTS["cn_zh"] == "https://api.minimaxi.com/v1/image_generation"
    assert module.MINIMAX_MODELS == {"image-01", "image-01-live"}
    assert module.MINIMAX_DEFAULT_MODEL == "image-01"


def test_build_request_uses_aspect_ratio_and_controls():
    module = _load_edit()
    body = module.build_minimax_request(
        "make it sunset", "image-01", aspect_ratio="16:9", response_format="url",
        seed=7, count=3, prompt_optimizer=True,
    )
    assert body["model"] == "image-01"
    assert body["prompt"] == "make it sunset"
    assert body["aspect_ratio"] == "16:9"
    assert body["response_format"] == "url"
    assert body["seed"] == 7
    assert body["n"] == 3
    assert body["prompt_optimizer"] is True
    assert "width" not in body and "height" not in body


def test_build_request_prefers_pixel_dimensions_and_subject_reference():
    module = _load_edit()
    body = module.build_minimax_request(
        "make it sunset", "image-01-live", aspect_ratio="1:1", width=1024, height=768,
        response_format="base64", subject_reference="https://example.com/ref.png",
    )
    assert body["width"] == 1024
    assert body["height"] == 768
    assert "aspect_ratio" not in body
    assert body["response_format"] == "base64"
    assert body["subject_reference"] == [
        {"type": "character", "image_file": "https://example.com/ref.png"}
    ]


def test_subject_reference_local_file_becomes_data_uri(tmp_path):
    module = _load_edit()
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"pixels")
    payload = module._encode_subject_reference([str(ref)])
    assert payload[0]["type"] == "character"
    assert payload[0]["image_file"].startswith("data:image/png;base64,")


def test_parse_response_extracts_urls_and_base64():
    module = _load_edit()
    kind, urls = module.parse_minimax_response(
        {"data": {"image_urls": ["https://cdn/img.png"]}, "base_resp": {"status_code": 0}},
        "url",
    )
    assert kind == "url" and urls == ["https://cdn/img.png"]

    kind, payloads = module.parse_minimax_response(
        {"data": {"image_base64": ["QUJD"]}, "base_resp": {"status_code": 0}},
        "base64",
    )
    assert kind == "base64" and payloads == ["QUJD"]


def test_parse_response_raises_on_upstream_error():
    module = _load_edit()
    with pytest.raises(ValueError, match="insufficient balance"):
        module.parse_minimax_response(
            {"base_resp": {"status_code": 1008, "status_msg": "insufficient balance"}},
            "url",
        )


def test_edit_minimax_sends_input_image_as_subject_reference(tmp_path):
    module = _load_edit()
    image = tmp_path / "input.png"
    image.write_bytes(b"not really png")
    captured = {}

    def _fake_urlopen(req, timeout=120):
        if isinstance(req, str):
            return _FakeResponse(b"png-bytes")
        captured["body"] = req.data.decode("utf-8")
        return _FakeResponse(
            {
                "data": {"image_urls": ["https://cdn/out.png"]},
                "metadata": {"success_count": "1", "failed_count": "0"},
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        )

    with patch.object(module, "OUTPUT_DIR", tmp_path), \
            patch.object(module.urllib.request, "urlopen", side_effect=_fake_urlopen):
        result = module.edit_image_minimax(
            [str(image)], "make it sunset", "image-01", SECRET,
            region="global_en", response_format="url",
        )

    body = json.loads(captured["body"])
    assert body["model"] == "image-01"
    assert body["prompt"] == "make it sunset"
    refs = body["subject_reference"]
    assert len(refs) == 1
    assert refs[0]["type"] == "character"
    assert refs[0]["image_file"].startswith("data:image/png;base64,")
    assert result["region"] == "global_en"
    assert result["image_urls"] == ["https://cdn/out.png"]
    assert len(result["paths"]) == 1
    saved = Path(result["paths"][0])
    assert saved.exists()
    assert saved.read_bytes() == b"png-bytes"


def test_edit_base64_saves_file(tmp_path):
    module = _load_edit()
    image = tmp_path / "input.png"
    image.write_bytes(b"input pixels")
    encoded = base64.b64encode(b"fake-png-bytes").decode("utf-8")
    payload = {
        "data": {"image_base64": [encoded]},
        "metadata": {"success_count": "1", "failed_count": "0"},
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }
    with patch.object(module, "OUTPUT_DIR", tmp_path), \
            patch.object(module.urllib.request, "urlopen", return_value=_FakeResponse(payload)):
        result = module.edit_image_minimax(
            [str(image)], "make it sunset", "image-01", SECRET,
            region="cn_zh", response_format="base64",
        )
    assert result["region"] == "cn_zh"
    assert result["success_count"] == "1"
    assert len(result["paths"]) == 1
    saved = Path(result["paths"][0])
    assert saved.exists()
    assert saved.read_bytes() == b"fake-png-bytes"


def test_edit_redacts_api_key_in_http_error(tmp_path):
    module = _load_edit()
    image = tmp_path / "input.png"
    image.write_bytes(b"input pixels")
    body = ('{"message":"bad request with ' + SECRET + '"}').encode()
    err = urllib.error.HTTPError(
        url=module.MINIMAX_ENDPOINTS["global_en"], code=401, msg="Unauthorized",
        hdrs={}, fp=io.BytesIO(body),
    )
    with patch.object(module, "OUTPUT_DIR", tmp_path), \
            patch.object(module.urllib.request, "urlopen", side_effect=err):
        out = _capture_exit_output(
            lambda: module.edit_image_minimax([str(image)], "make it sunset", "image-01", SECRET)
        )
    assert SECRET not in json.dumps(out)
