# pylint: disable=print-used
"""Standalone script to check Gemini Flash using user ADC credentials.

This is not part of the Odoo module. Authenticate first with
``gcloud auth application-default login``, then run directly:

    python3 misc/test_gemini_enterprise.py
"""

import base64
import json
import os
from pathlib import Path

import google.auth
from google.auth.transport.requests import AuthorizedSession

_HERE = Path(__file__).parent
_IMAGE_PATH = _HERE / "img" / "7aa478f0-e862-4918-8d68-563037943e78.jpg"
_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "theta-inkwell-504108-q4")
_LOCATION = "global"
_MODEL = "gemini-2.5-flash"
_QUESTION = "What flowers do you see in this photo? List each type and roughly how many."


def main():
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=_PROJECT_ID,
    )
    session = AuthorizedSession(credentials)
    image_b64 = base64.b64encode(_IMAGE_PATH.read_bytes()).decode()

    url = (
        "https://aiplatform.googleapis.com/v1/"
        f"projects/{_PROJECT_ID}/locations/{_LOCATION}/publishers/google/"
        f"models/{_MODEL}:generateContent"
    )
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
    response = session.post(
        url,
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
