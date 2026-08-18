from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "extensions" / "atlas" / "scripts" / "generate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("atlas_generate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, data: bytes):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size: int = -1) -> bytes:
        return self.data if size < 0 else self.data[:size]


def test_payload_matches_live_qwen_image_schema(monkeypatch, capsys, tmp_path: Path) -> None:
    module = _load_module()
    requests = []

    def fake_urlopen(request, _timeout):
        requests.append(request)
        if request.get_method() == "POST":
            return _Response(json.dumps({"code": 200, "data": {"id": "pred-1"}}).encode())
        if "/prediction/" in request.full_url:
            payload = {
                "code": 200,
                "data": {"status": "completed", "outputs": ["https://cdn.atlascloud.ai/a.png"]},
            }
            return _Response(json.dumps(payload).encode())
        return _Response(b"\x89PNG\r\n\x1a\nimage")

    monkeypatch.setenv("ATLASCLOUD_API_KEY", "test-key")
    monkeypatch.setattr(module, "_urlopen", fake_urlopen)
    rc = module.main(
        ["--prompt", "SEO hero", "--size", "1200*630", "--output", str(tmp_path / "hero")]
    )
    assert rc == 0
    body = json.loads(requests[0].data)
    assert body == {
        "model": "qwen-image-3.0/text-to-image",
        "prompt": "SEO hero",
        "size": "1200*630",
        "n": 1,
        "prompt_extend": True,
    }
    assert requests[0].get_header("User-agent") == module.USER_AGENT
    assert json.loads(capsys.readouterr().out)["prediction_id"] == "pred-1"


def test_generation_post_occurs_exactly_once(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    methods = []
    polls = iter(["processing", "completed"])

    def fake_urlopen(request, _timeout):
        methods.append(request.get_method())
        if request.get_method() == "POST":
            return _Response(b'{"data":{"id":"pred-2"}}')
        if "/prediction/" in request.full_url:
            status = next(polls)
            outputs = ["https://cdn.atlascloud.ai/a.png"] if status == "completed" else None
            return _Response(json.dumps({"data": {"status": status, "outputs": outputs}}).encode())
        return _Response(b"\x89PNG\r\n\x1a\nimage")

    monkeypatch.setenv("ATLASCLOUD_API_KEY", "test-key")
    monkeypatch.setattr(module, "_urlopen", fake_urlopen)
    monkeypatch.setattr(module.time, "sleep", lambda _value: None)
    assert (
        module.main(["--prompt", "x", "--poll-seconds", "0", "--output", str(tmp_path / "x")]) == 0
    )
    assert methods.count("POST") == 1


def test_download_never_receives_authorization(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    seen_download_headers = None

    def fake_urlopen(request, _timeout):
        nonlocal seen_download_headers
        if request.get_method() == "POST":
            return _Response(b'{"data":{"id":"pred-3"}}')
        if "/prediction/" in request.full_url:
            return _Response(
                b'{"data":{"status":"completed","outputs":["https://cdn.atlascloud.ai/a.png"]}}'
            )
        seen_download_headers = dict(request.header_items())
        return _Response(b"\x89PNG\r\n\x1a\nimage")

    monkeypatch.setenv("ATLASCLOUD_API_KEY", "test-key")
    monkeypatch.setattr(module, "_urlopen", fake_urlopen)
    assert module.main(["--prompt", "x", "--output", str(tmp_path / "x")]) == 0
    assert seen_download_headers is not None
    assert "Authorization" not in seen_download_headers


def test_polling_is_bounded(monkeypatch) -> None:
    module = _load_module()
    calls = 0

    def fake_request(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return {"status": "processing"}

    monkeypatch.setattr(module, "_request_json", fake_request)
    monkeypatch.setattr(module.time, "sleep", lambda _value: None)
    with pytest.raises(TimeoutError):
        module.poll_prediction("key", "id", max_polls=3, poll_seconds=0, timeout=1)
    assert calls == 3


@pytest.mark.parametrize(
    "url",
    [
        "http://cdn.atlascloud.ai/a.png",
        "https://example.com/a.png",
        "https://user:pass@cdn.atlascloud.ai/a.png",
        "https://cdn.atlascloud.ai:444/a.png",
    ],
)
def test_output_url_policy_rejects_unsafe_urls(url: str) -> None:
    module = _load_module()
    with pytest.raises(ValueError):
        module._validate_output_url(url)


def test_live_provider_output_host_is_allowlisted() -> None:
    module = _load_module()
    url = "https://dashscope-a717.oss-accelerate.aliyuncs.com/generated/a.png"
    assert module._validate_output_url(url) == url


def test_image_signature_validation() -> None:
    module = _load_module()
    assert module._image_extension(b"\x89PNG\r\n\x1a\nrest") == ".png"
    assert module._image_extension(b"\xff\xd8\xffrest") == ".jpg"
    with pytest.raises(ValueError):
        module._image_extension(b"<html>not an image</html>")


def test_download_uses_detected_image_extension(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_urlopen",
        lambda _request, _timeout: _Response(b"RIFF\x00\x00\x00\x00WEBPimage"),
    )
    output = module.download_image(
        "https://cdn.atlascloud.ai/a.png",
        tmp_path / "seo-image.png",
        1,
    )
    assert output.suffix == ".webp"
    assert output.read_bytes().startswith(b"RIFF")


def test_http_error_body_is_not_exposed(monkeypatch) -> None:
    module = _load_module()

    def fake_urlopen(request, _timeout):
        raise HTTPError(request.full_url, 401, "denied secret-body", {}, None)

    monkeypatch.setattr(module, "_urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="HTTP 401") as exc:
        module._request_json("GET", module.API_BASE, api_key="secret-key")
    assert "secret" not in str(exc.value)


def test_missing_key_fails_before_network(monkeypatch, capsys) -> None:
    module = _load_module()
    monkeypatch.delenv("ATLASCLOUD_API_KEY", raising=False)
    monkeypatch.setattr(module, "_urlopen", lambda *_args: pytest.fail("network called"))
    assert module.main(["--prompt", "x"]) == 2
    assert json.loads(capsys.readouterr().out)["message"] == "ATLASCLOUD_API_KEY is not set"


def test_extension_layout_and_runtime_fallback() -> None:
    skill = ROOT / "extensions" / "atlas" / "skills" / "seo-atlas-image-gen" / "SKILL.md"
    assert skill.is_file()
    assert "original_author:" in skill.read_text(encoding="utf-8")
    assert (ROOT / "extensions" / "atlas" / "docs" / "ATLAS-SETUP.md").is_file()
    installer = (ROOT / "extensions" / "atlas" / "install.sh").read_text(encoding="utf-8")
    assert 'mkdir -p "${SKILL_DIR}/scripts" "${SKILL_DIR}/references"' in installer
    runtime = (ROOT / "scripts" / "runtime.py").read_text(encoding="utf-8")
    assert '"atlas": "seo-atlas-image-gen"' in runtime
