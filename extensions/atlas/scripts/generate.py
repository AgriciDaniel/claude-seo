#!/usr/bin/env python3
"""Generate SEO images through the Atlas Cloud asynchronous image API.

The client uses one POST per invocation, bounded GET polling, and a
credential-free download request. It intentionally depends only on the Python
standard library so it can run inside the managed Claude SEO runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

API_BASE = "https://api.atlascloud.ai/api/v1"
USER_AGENT = "claude-seo-atlas-extension/2.2.4"
DEFAULT_MODEL = "qwen-image-3.0/text-to-image"
DEFAULT_SIZE = "1024*1024"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 30 * 1024 * 1024
TERMINAL_SUCCESS = {"completed", "succeeded", "success"}
TERMINAL_FAILURE = {"failed", "canceled", "cancelled", "error"}
ALLOWED_OUTPUT_HOSTS = {
    "atlas-img.oss-accelerate-overseas.aliyuncs.com",
    "cdn.atlascloud.ai",
    "dashscope-a717.oss-accelerate.aliyuncs.com",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Reject redirects so credentials and download policy cannot drift."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urllib.error.HTTPError(req.full_url, code, "redirect blocked", headers, fp)


_OPENER = urllib.request.build_opener(NoRedirect)


def _urlopen(request: urllib.request.Request, timeout: float):
    return _OPENER.open(request, timeout=timeout)


def _emit_error(
    message: str,
    *,
    status: int | None = None,
    prediction_id: str | None = None,
) -> None:
    payload: dict[str, Any] = {"error": True, "message": message}
    if status is not None:
        payload["status"] = status
    if prediction_id is not None:
        payload["prediction_id"] = prediction_id
    print(json.dumps(payload, sort_keys=True))


def _read_limited(response, limit: int) -> bytes:  # noqa: ANN001
    data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"response exceeds {limit} bytes")
    return data


def _request_json(
    method: str,
    url: str,
    *,
    api_key: str,
    body: dict[str, Any] | None = None,
    timeout: float = 60,
) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with _urlopen(request, timeout) as response:
            raw = _read_limited(response, MAX_RESPONSE_BYTES)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Atlas Cloud returned HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Atlas Cloud request failed: {exc.reason}") from None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Atlas Cloud returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Atlas Cloud returned an unexpected response")
    if value.get("code") not in (None, 0, 200):
        raise RuntimeError(f"Atlas Cloud request failed with code {value.get('code')}")
    data_value = value.get("data", value)
    if not isinstance(data_value, dict):
        raise RuntimeError("Atlas Cloud response data is not an object")
    return data_value


def _prediction_id(value: dict[str, Any]) -> str:
    prediction_id = value.get("id") or value.get("prediction_id")
    if not isinstance(prediction_id, str) or not prediction_id.strip():
        raise RuntimeError("Atlas Cloud response did not include a prediction id")
    return prediction_id.strip()


def submit_prediction(api_key: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """Submit exactly one generation request."""
    return _request_json(
        "POST",
        f"{API_BASE}/model/generateImage",
        api_key=api_key,
        body=payload,
        timeout=timeout,
    )


def poll_prediction(
    api_key: str,
    prediction_id: str,
    *,
    max_polls: int,
    poll_seconds: float,
    timeout: float,
) -> dict[str, Any]:
    encoded_id = quote(prediction_id, safe="")
    for attempt in range(max_polls):
        if attempt:
            time.sleep(min(poll_seconds * (1.5 ** min(attempt - 1, 4)), 15.0))
        value = _request_json(
            "GET",
            f"{API_BASE}/model/prediction/{encoded_id}",
            api_key=api_key,
            timeout=timeout,
        )
        status = str(value.get("status", "")).lower()
        if status in TERMINAL_SUCCESS:
            return value
        if status in TERMINAL_FAILURE:
            raise RuntimeError(f"Atlas Cloud prediction ended with status {status}")
    raise TimeoutError(f"prediction did not complete after {max_polls} polls")


def _validate_output_url(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise ValueError("output URL must use HTTPS")
    if host not in ALLOWED_OUTPUT_HOSTS and not host.endswith(".atlascloud.ai"):
        raise ValueError(f"output host is not allowed: {host}")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("output URL contains disallowed authority components")
    return value


def _image_extension(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if len(data) >= 12 and data[4:12] in {b"ftypavif", b"ftypavis"}:
        return ".avif"
    raise ValueError("downloaded output is not a supported image")


def download_image(url: str, destination: Path, timeout: float) -> Path:
    safe_url = _validate_output_url(url)
    request = urllib.request.Request(
        safe_url,
        headers={
            "Accept": "image/avif,image/webp,image/png,image/jpeg",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    try:
        with _urlopen(request, timeout) as response:
            data = _read_limited(response, MAX_IMAGE_BYTES)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"image download returned HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"image download failed: {exc.reason}") from None
    extension = _image_extension(data)
    output = destination.with_suffix(extension)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    try:
        temp.write_bytes(data)
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    return output.resolve()


def _output_base(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return Path.home() / "Documents" / "claude-seo" / "atlas-generated" / f"atlas-{timestamp}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an SEO image with Atlas Cloud")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default=DEFAULT_SIZE, help="Width*height, for example 1200*630")
    parser.add_argument("--count", type=int, default=1, choices=range(1, 5), metavar="1-4")
    parser.add_argument("--negative-prompt")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--no-prompt-extend", action="store_true")
    parser.add_argument("--output", help="Output file base or path")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--max-polls", type=int, default=30)
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    api_key = os.environ.get("ATLASCLOUD_API_KEY", "").strip()
    if not api_key:
        _emit_error("ATLASCLOUD_API_KEY is not set")
        return 2
    if not 1 <= args.max_polls <= 60:
        _emit_error("--max-polls must be between 1 and 60")
        return 2
    if not 0 <= args.poll_seconds <= 30:
        _emit_error("--poll-seconds must be between 0 and 30")
        return 2
    if not 1 <= args.timeout <= 180:
        _emit_error("--timeout must be between 1 and 180 seconds")
        return 2

    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": args.prompt,
        "size": args.size,
        "n": args.count,
        "prompt_extend": not args.no_prompt_extend,
    }
    if args.negative_prompt:
        payload["negative_prompt"] = args.negative_prompt
    if args.seed is not None:
        if not 0 <= args.seed <= 2_147_483_647:
            _emit_error("--seed must be between 0 and 2147483647")
            return 2
        payload["seed"] = args.seed

    prediction_id: str | None = None
    try:
        submitted = submit_prediction(api_key, payload, args.timeout)
        prediction_id = _prediction_id(submitted)
        completed = poll_prediction(
            api_key,
            prediction_id,
            max_polls=args.max_polls,
            poll_seconds=args.poll_seconds,
            timeout=args.timeout,
        )
        outputs = completed.get("outputs")
        if (
            not isinstance(outputs, list)
            or not outputs
            or not all(isinstance(x, str) for x in outputs)
        ):
            raise RuntimeError("completed prediction did not include output URLs")
        safe_outputs = [_validate_output_url(value) for value in outputs]
        paths: list[str] = []
        if not args.no_download:
            base = _output_base(args.output)
            for index, url in enumerate(safe_outputs, start=1):
                target = base if len(safe_outputs) == 1 else base.with_name(f"{base.name}-{index}")
                paths.append(str(download_image(url, target, args.timeout)))
        result = {
            "prediction_id": prediction_id,
            "status": str(completed.get("status", "completed")),
            "model": args.model,
            "size": args.size,
            "outputs": safe_outputs,
            "paths": paths,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (RuntimeError, TimeoutError, ValueError, OSError) as exc:
        _emit_error(str(exc), prediction_id=prediction_id)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
