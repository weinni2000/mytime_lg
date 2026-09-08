# pylint: disable=print-used
"""Standalone script to check Gemini access via OpenRouter (instead of
Google's API directly). Not part of the Odoo module - run directly:

    python3 misc/test_openrouter_gemini.py
"""

import base64
import json
from pathlib import Path

import requests

_HERE = Path(__file__).parent
_ENV_PATH = _HERE / ".env"
_IMAGE_PATH = _HERE / "img" / "7aa478f0-e862-4918-8d68-563037943e78.jpg"
_MODEL = "google/gemini-2.5-flash"
_QUESTION = "What flowers do you see in this photo? List each type and roughly how many."


def _load_api_key():
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("OPENROUTER="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"OPENROUTER key not found in {_ENV_PATH}")


def main():
    api_key = _load_api_key()
    image_b64 = base64.b64encode(_IMAGE_PATH.read_bytes()).decode()

    url = "https://openrouter.ai/api/v1/chat/completions"
    body = {
        "model": _MODEL,
        "max_tokens": 2000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _QUESTION},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                ],
            }
        ],
    }
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=60,
    )
    print("HTTP status:", response.status_code)
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except ValueError:
        print(response.text)


if __name__ == "__main__":
    main()
