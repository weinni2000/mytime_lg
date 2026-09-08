#!/usr/bin/env python3
# pylint: disable=print-used
"""Make a minimal Gemini request and print useful diagnostics."""

import json
import os
import socket
import sys
import urllib.error
import urllib.request

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def force_ip_family(family):
    """Make urllib resolve remote hosts to one IP address family only."""
    original_getaddrinfo = socket.getaddrinfo

    def getaddrinfo(host, port, family=0, socktype=0, proto=0, flags=0):
        return original_getaddrinfo(host, port, selected_family, socktype, proto, flags)

    selected_family = family
    socket.getaddrinfo = getaddrinfo


def main():
    ip_version = os.getenv("GEMINI_IP_VERSION")
    if not ip_version and os.getenv("GEMINI_FORCE_IPV4") == "1":
        ip_version = "4"
    if ip_version in ("4", "6"):
        force_ip_family(socket.AF_INET if ip_version == "4" else socket.AF_INET6)
        print(f"Network mode: IPv{ip_version} only")
    elif ip_version:
        print("GEMINI_IP_VERSION must be 4 or 6.", file=sys.stderr)
        return 2

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not set.", file=sys.stderr)
        print("Run: GEMINI_API_KEY='your-key' python3 misc/test_gemini.py", file=sys.stderr)
        return 2

    payload = json.dumps({"contents": [{"parts": [{"text": "Reply with exactly: OK"}]}]}).encode()
    request = urllib.request.Request(
        URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(f"HTTP {response.status}")
            print(json.dumps(json.loads(body), indent=2))
            return 0
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code} {error.reason}", file=sys.stderr)
        try:
            print(json.dumps(json.loads(body), indent=2), file=sys.stderr)
        except json.JSONDecodeError:
            print(body, file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"Connection failed: {error.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
