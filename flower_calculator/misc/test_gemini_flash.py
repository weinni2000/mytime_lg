# pylint: disable=print-used
"""Standalone script to check whether the Gemini API is reachable from this
server. Not part of the Odoo module - run directly:

    python3 misc/test_gemini_flash.py
"""

import base64
import json
from pathlib import Path

import requests

_HERE = Path(__file__).parent
_ENV_PATH = _HERE / ".env"
_IMAGE_PATH = _HERE / "img" / "7aa478f0-e862-4918-8d68-563037943e78.jpg"
_MODEL = "gemini-3.6-flash"
_QUESTION = "What flowers do you see in this photo? List each type and roughly how many."


def _load_api_key():
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"GEMINI_API_KEY not found in {_ENV_PATH}")


def main():
    api_key = _load_api_key()
    image_b64 = base64.b64encode(_IMAGE_PATH.read_bytes()).decode()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": _QUESTION},
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                ],
            }
        ],
    }
    response = requests.post(
        url,
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    print("HTTP status:", response.status_code)
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except ValueError:
        print(response.text)


if __name__ == "__main__":
    main()
