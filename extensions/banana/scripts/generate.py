#!/usr/bin/env python3
"""Claude Banana - Direct API Fallback: Image Generation

Generate images via Gemini REST API when MCP is unavailable.
Uses only Python stdlib (no pip dependencies).

Usage:
    generate.py --prompt "a cat in space" [--aspect-ratio 16:9] [--resolution 1K]
                [--model MODEL] [--api-key KEY] [--thinking LEVEL] [--image-only]

    generate.py --provider minimax --prompt "a cat in space" [--region global_en|cn_zh]
                [--model image-01|image-01-live] [--aspect-ratio 16:9 | --width W --height H]
                [--response-format url|base64] [--seed N] [--count N]
                [--prompt-optimizer|--no-prompt-optimizer] [--subject-reference SRC]
                [--api-key KEY]
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

DEFAULT_MODEL = os.environ.get("NANOBANANA_MODEL")
DEFAULT_RESOLUTION = "1K"
DEFAULT_RATIO = "1:1"
OUTPUT_DIR = Path.home() / "Documents" / "nanobanana_generated"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

VALID_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2",
                "4:5", "5:4", "1:4", "4:1", "1:8", "8:1", "21:9"}
VALID_RESOLUTIONS = {"512", "1K", "2K", "4K"}

# MiniMax image_generation direct REST fallback.
MINIMAX_DEFAULT_MODEL = "image-01"
MINIMAX_MODELS = {"image-01", "image-01-live"}
MINIMAX_ENDPOINTS = {
    "global_en": "https://api.minimax.io/v1/image_generation",
    "cn_zh": "https://api.minimaxi.com/v1/image_generation",
}
MINIMAX_DEFAULT_REGION = "global_en"
MINIMAX_RESPONSE_FORMATS = {"url", "base64"}
MINIMAX_IMAGE_MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif",
}

_GOOGLE_API_KEY_PREFIX = "AI" + "za"
_GOOGLE_API_KEY_RE = re.compile(_GOOGLE_API_KEY_PREFIX + r"[0-9A-Za-z_-]+")
_GOOGLE_KEY_QUERY_RE = re.compile(r"([?&])key=[^&\s'\"<>)]*(&?)")
_GOOGLE_KEY_BARE_RE = re.compile(r"\bkey=[^&\s'\"<>)]*")


def _redact_google_api_key(value):
    """Remove Google API keys from standalone fallback error output."""
    text = str(value)

    def drop_query_key(match):
        separator, trailing_amp = match.groups()
        if separator == "?" and trailing_amp:
            return "?"
        if separator == "&" and trailing_amp:
            return "&"
        return ""

    text = _GOOGLE_KEY_QUERY_RE.sub(drop_query_key, text)
    text = text.replace("?&", "?")
    text = _GOOGLE_KEY_BARE_RE.sub("google_api_key_redacted", text)
    return _GOOGLE_API_KEY_RE.sub("GOOGLE_API_KEY_REDACTED", text)


def generate_image(prompt, model, aspect_ratio, resolution, api_key,
                   thinking_level=None, image_only=False):
    """Call Gemini API to generate an image."""
    url = f"{API_BASE}/{model}:generateContent"

    modalities = ["IMAGE"] if image_only else ["TEXT", "IMAGE"]
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": modalities,
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": resolution,
            },
        },
    }

    if thinking_level:
        body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": thinking_level}

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = _redact_google_api_key(
            e.read().decode("utf-8", "replace") if e.fp else ""
        )
        print(json.dumps({"error": True, "status": e.code, "message": error_body}))
        sys.exit(1)
    except urllib.error.URLError as e:
        print(json.dumps({"error": True, "message": _redact_google_api_key(e.reason)}))
        sys.exit(1)

    # Extract image from response
    candidates = result.get("candidates", [])
    if not candidates:
        finish_reason = result.get("promptFeedback", {}).get("blockReason", "UNKNOWN")
        print(json.dumps({"error": True, "message": f"No candidates returned. Reason: {finish_reason}"}))
        sys.exit(1)

    parts = candidates[0].get("content", {}).get("parts", [])
    image_data = None
    text_response = ""

    for part in parts:
        if "inlineData" in part:
            image_data = part["inlineData"]["data"]
        elif "text" in part:
            text_response = part["text"]

    if not image_data:
        finish_reason = candidates[0].get("finishReason", "UNKNOWN")
        print(json.dumps({"error": True, "message": f"No image in response. finishReason: {finish_reason}"}))
        sys.exit(1)

    # Save image
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"banana_{timestamp}.png"
    output_path = (OUTPUT_DIR / filename).resolve()

    with open(output_path, "wb") as f:
        f.write(base64.b64decode(image_data))

    return {
        "path": str(output_path),
        "model": model,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "text": text_response,
    }


def _redact_secret(value, secret):
    """Strip a bearer credential from standalone fallback error output."""
    text = str(value)
    if secret:
        text = text.replace(secret, "IMAGE_API_KEY_REDACTED")
    return text


def _encode_subject_reference(reference):
    """Normalise subject references into MiniMax image_file payloads.

    Accepts an http(s) URL, an existing data URI, or a local file path
    (encoded to a base64 data URI). Returns the request-ready list or None.
    """
    if not reference:
        return None
    items = reference if isinstance(reference, (list, tuple)) else [reference]
    payload = []
    for item in items:
        item = str(item)
        if item.startswith(("http://", "https://", "data:")):
            image_file = item
        else:
            path = Path(item).expanduser().resolve()
            if not path.exists():
                raise FileNotFoundError(f"Subject reference not found: {path}")
            mime = MINIMAX_IMAGE_MIME.get(path.suffix.lower(), "image/png")
            encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
            image_file = f"data:{mime};base64,{encoded}"
        payload.append({"type": "character", "image_file": image_file})
    return payload


def build_minimax_request(prompt, model, *, aspect_ratio=None, width=None,
                          height=None, response_format="url", seed=None,
                          count=1, prompt_optimizer=None, subject_reference=None):
    """Assemble the MiniMax image_generation request body."""
    body = {"model": model, "prompt": prompt, "response_format": response_format}
    if width and height:
        body["width"] = int(width)
        body["height"] = int(height)
    elif aspect_ratio:
        body["aspect_ratio"] = aspect_ratio
    if seed is not None:
        body["seed"] = int(seed)
    if count and int(count) != 1:
        body["n"] = int(count)
    if prompt_optimizer is not None:
        body["prompt_optimizer"] = bool(prompt_optimizer)
    subject = _encode_subject_reference(subject_reference)
    if subject:
        body["subject_reference"] = subject
    return body


def parse_minimax_response(result, response_format):
    """Extract image URLs or base64 payloads from a MiniMax response.

    Raises ValueError with the upstream status message when the request was
    not accepted, mirroring the base_resp.status_code contract.
    """
    base_resp = result.get("base_resp", {})
    status_code = base_resp.get("status_code")
    if status_code not in (None, 0):
        raise ValueError(base_resp.get("status_msg") or f"status_code {status_code}")
    data = result.get("data") or {}
    if response_format == "base64":
        return "base64", list(data.get("image_base64") or [])
    return "url", list(data.get("image_urls") or [])


def generate_image_minimax(prompt, model, api_key, *, region="global_en",
                           aspect_ratio=None, width=None, height=None,
                           response_format="url", seed=None, count=1,
                           prompt_optimizer=None, subject_reference=None):
    """Call the MiniMax image_generation endpoint and save the results."""
    endpoint = MINIMAX_ENDPOINTS.get(region)
    if not endpoint:
        print(json.dumps({"error": True, "message": f"Invalid region '{region}'. Valid: {sorted(MINIMAX_ENDPOINTS)}"}))
        sys.exit(1)

    body = build_minimax_request(
        prompt, model, aspect_ratio=aspect_ratio, width=width, height=height,
        response_format=response_format, seed=seed, count=count,
        prompt_optimizer=prompt_optimizer, subject_reference=subject_reference,
    )
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = _redact_secret(e.read().decode("utf-8", "replace") if e.fp else "", api_key)
        print(json.dumps({"error": True, "status": e.code, "message": error_body}))
        sys.exit(1)
    except urllib.error.URLError as e:
        print(json.dumps({"error": True, "message": _redact_secret(e.reason, api_key)}))
        sys.exit(1)

    try:
        kind, items = parse_minimax_response(result, response_format)
    except ValueError as e:
        print(json.dumps({"error": True, "message": _redact_secret(e, api_key)}))
        sys.exit(1)

    if not items:
        metadata = result.get("metadata", {})
        print(json.dumps({"error": True, "message": f"No image returned. metadata: {metadata}"}))
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    saved = []
    for index, item in enumerate(items):
        output_path = (OUTPUT_DIR / f"banana_{timestamp}_{index}.png").resolve()
        if kind == "base64":
            output_path.write_bytes(base64.b64decode(item))
        else:
            try:
                with urllib.request.urlopen(item, timeout=120) as img_resp:
                    output_path.write_bytes(img_resp.read())
            except urllib.error.URLError as e:
                print(json.dumps({"error": True, "message": _redact_secret(e.reason, api_key)}))
                sys.exit(1)
        saved.append(str(output_path))

    metadata = result.get("metadata", {})
    return {
        "paths": saved,
        "path": saved[0],
        "model": model,
        "region": region,
        "response_format": response_format,
        "aspect_ratio": aspect_ratio,
        "image_urls": items if kind == "url" else [],
        "success_count": metadata.get("success_count"),
        "failed_count": metadata.get("failed_count"),
    }


def main():
    parser = argparse.ArgumentParser(description="Generate images via Gemini REST API")
    parser.add_argument("--prompt", required=True, help="Image generation prompt")
    parser.add_argument("--aspect-ratio", default=DEFAULT_RATIO, help=f"Aspect ratio (default: {DEFAULT_RATIO})")
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION, help=f"Resolution: 512, 1K, 2K, 4K (default: {DEFAULT_RESOLUTION})")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model ID (or set NANOBANANA_MODEL env)")
    parser.add_argument("--api-key", default=None, help="Google AI API key (or set GOOGLE_AI_API_KEY env)")
    parser.add_argument("--thinking", default=None, choices=["minimal", "low", "medium", "high"], help="Thinking level")
    parser.add_argument("--image-only", action="store_true", help="Return image only (no text)")
    parser.add_argument("--provider", default="default", choices=["default", "minimax"],
                        help="Backend provider (default: default)")
    parser.add_argument("--region", default=MINIMAX_DEFAULT_REGION, choices=sorted(MINIMAX_ENDPOINTS),
                        help=f"MiniMax region (default: {MINIMAX_DEFAULT_REGION})")
    parser.add_argument("--response-format", default="url", choices=sorted(MINIMAX_RESPONSE_FORMATS),
                        help="MiniMax response format: url or base64 (default: url)")
    parser.add_argument("--width", type=int, default=None, help="MiniMax pixel width (used with --height)")
    parser.add_argument("--height", type=int, default=None, help="MiniMax pixel height (used with --width)")
    parser.add_argument("--seed", type=int, default=None, help="MiniMax generation seed")
    parser.add_argument("--count", type=int, default=1, help="MiniMax image count (n, default: 1)")
    parser.add_argument("--subject-reference", action="append", default=None,
                        help="MiniMax subject reference: URL, data URI, or local file (repeatable)")
    parser.add_argument("--prompt-optimizer", dest="prompt_optimizer", action="store_true", default=None,
                        help="Enable MiniMax prompt_optimizer")
    parser.add_argument("--no-prompt-optimizer", dest="prompt_optimizer", action="store_false",
                        help="Disable MiniMax prompt_optimizer")

    args = parser.parse_args()

    if args.provider == "minimax":
        model = args.model if args.model in MINIMAX_MODELS else MINIMAX_DEFAULT_MODEL
        api_key = args.api_key or os.environ.get("MINIMAX_API_KEY")
        if not api_key:
            print(json.dumps({"error": True, "message": "No API key. Set MINIMAX_API_KEY env or pass --api-key"}))
            sys.exit(1)
        try:
            result = generate_image_minimax(
                prompt=args.prompt,
                model=model,
                api_key=api_key,
                region=args.region,
                aspect_ratio=args.aspect_ratio,
                width=args.width,
                height=args.height,
                response_format=args.response_format,
                seed=args.seed,
                count=args.count,
                prompt_optimizer=args.prompt_optimizer,
                subject_reference=args.subject_reference,
            )
        except FileNotFoundError as e:
            print(json.dumps({"error": True, "message": str(e)}))
            sys.exit(1)
        print(json.dumps(result, indent=2))
        return

    if args.aspect_ratio not in VALID_RATIOS:
        print(json.dumps({"error": True, "message": f"Invalid aspect ratio '{args.aspect_ratio}'. Valid: {sorted(VALID_RATIOS)}"}))
        sys.exit(1)

    if args.resolution not in VALID_RESOLUTIONS:
        print(json.dumps({"error": True, "message": f"Invalid resolution '{args.resolution}'. Valid: {sorted(VALID_RESOLUTIONS)}"}))
        sys.exit(1)

    if not args.model:
        print(json.dumps({"error": True, "message": "No model. Set NANOBANANA_MODEL or pass --model."}))
        sys.exit(1)

    api_key = args.api_key or os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print(json.dumps({"error": True, "message": "No API key. Set GOOGLE_AI_API_KEY env or pass --api-key"}))
        sys.exit(1)

    result = generate_image(
        prompt=args.prompt,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        api_key=api_key,
        thinking_level=args.thinking,
        image_only=args.image_only,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
