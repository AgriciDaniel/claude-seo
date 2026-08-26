"""Regression tests for Banana direct REST fallback API-key redaction."""

from __future__ import annotations

import importlib.util
import io
import json
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SECRET = "AI" + "zaSyDUMMYSECRET"
QUERY_KEY = "ke" + "y"
QUERY_KEY_ASSIGNMENT = QUERY_KEY + "="


def _load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _http_error_with_key() -> urllib.error.HTTPError:
    body = f'{{"error":"bad {QUERY_KEY_ASSIGNMENT}{SECRET} {SECRET}"}}'.encode()
    return urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models/test:generateContent",
        code=403,
        msg="Forbidden",
        hdrs={},
        fp=io.BytesIO(body),
    )


def _capture_exit_output(callable_):
    out = io.StringIO()
    with redirect_stdout(out):
        try:
            callable_()
        except SystemExit as exc:
            assert exc.code == 1
    return json.loads(out.getvalue())


def test_banana_generate_redacts_upstream_http_error_body() -> None:
    module = _load_module("banana_generate", "extensions/banana/scripts/generate.py")
    with patch.object(module.urllib.request, "urlopen", side_effect=_http_error_with_key()):
        payload = _capture_exit_output(
            lambda: module.generate_image(
                "prompt",
                module.DEFAULT_MODEL,
                "1:1",
                "1K",
                SECRET,
            )
        )

    dumped = json.dumps(payload)
    assert SECRET not in dumped
    assert QUERY_KEY_ASSIGNMENT not in dumped
    assert "AI" + "za" not in dumped


def test_banana_edit_redacts_upstream_http_error_body(tmp_path: Path) -> None:
    module = _load_module("banana_edit", "extensions/banana/scripts/edit.py")
    image = tmp_path / "input.png"
    image.write_bytes(b"not really png")
    with patch.object(module.urllib.request, "urlopen", side_effect=_http_error_with_key()):
        payload = _capture_exit_output(
            lambda: module.edit_image(image, "prompt", module.DEFAULT_MODEL, SECRET)
        )

    dumped = json.dumps(payload)
    assert SECRET not in dumped
    assert QUERY_KEY_ASSIGNMENT not in dumped
    assert "AI" + "za" not in dumped
