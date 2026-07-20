#!/usr/bin/env python3
"""Claude Banana - Direct API Fallback: Image Editing

Edit images via Gemini REST API when MCP is unavailable.
Uses only Python stdlib (no pip dependencies).

Usage:
    edit.py --image path/to/image.png --prompt "remove the background"
            [--model MODEL] [--api-key KEY]
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
OUTPUT_DIR = Path.home() / "Documents" / "nanobanana_generated"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
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


def edit_image(image_path, prompt, model, api_key):
    """Call Gemini API to edit an image."""
    image_path = Path(image_path).resolve()
    if not image_path.exists():
        print(json.dumps({"error": True, "message": f"Image not found: {image_path}"}))
        sys.exit(1)

    # Read and encode image
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    # Determine MIME type
    suffix = image_path.suffix.lower()
    mime_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                  ".webp": "image/webp", ".gif": "image/gif"}
    mime_type = mime_types.get(suffix, "image/png")

    url = f"{API_BASE}/{model}:generateContent"

    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": mime_type, "data": image_b64}},
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

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
    filename = f"banana_edit_{timestamp}.png"
    output_path = (OUTPUT_DIR / filename).resolve()

    with open(output_path, "wb") as f:
        f.write(base64.b64decode(image_data))

    return {
        "path": str(output_path),
        "model": model,
        "source": str(image_path),
        "text": text_response,
    }


def main():
    parser = argparse.ArgumentParser(description="Edit images via Gemini REST API")
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument("--prompt", required=True, help="Edit instruction")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model ID (or set NANOBANANA_MODEL env)")
    parser.add_argument("--api-key", default=None, help="Google AI API key (or set GOOGLE_AI_API_KEY env)")

    args = parser.parse_args()

    if not args.model:
        print(json.dumps({"error": True, "message": "No model. Set NANOBANANA_MODEL or pass --model."}))
        sys.exit(1)

    api_key = args.api_key or os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print(json.dumps({"error": True, "message": "No API key. Set GOOGLE_AI_API_KEY env or pass --api-key"}))
        sys.exit(1)

    result = edit_image(
        image_path=args.image,
        prompt=args.prompt,
        model=args.model,
        api_key=api_key,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
