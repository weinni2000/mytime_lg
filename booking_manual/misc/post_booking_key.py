#!/usr/bin/env python3
# pylint: disable=print-used
"""Send a test SMS payload to the Booking webhook."""

import argparse
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description="POST a test message to the /booking/key endpoint.")
    parser.add_argument(
        "--url",
        default=os.getenv("BOOKING_KEY_ENDPOINT", "https://camping.unternhub.at/booking/key"),
        help="Webhook URL (default: %(default)s)",
    )
    parser.add_argument(
        "--key",
        default=os.getenv("BOOKING_WEBHOOK_KEY"),
        help="Webhook key (or set BOOKING_WEBHOOK_KEY)",
    )
    parser.add_argument(
        "--message",
        default=os.getenv("BOOKING_SMS_MESSAGE"),
        help="SMS text sent as 'nachricht' (or set BOOKING_SMS_MESSAGE)",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    if not args.key:
        parser.error("--key or BOOKING_WEBHOOK_KEY is required")
    if not args.message:
        parser.error("--message or BOOKING_SMS_MESSAGE is required")

    body = urlencode({"key": args.key, "nachricht": args.message}).encode()
    request = Request(
        args.url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urlopen(request, timeout=args.timeout) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            print(f"HTTP {response.status}")
            print(response_body)
    except HTTPError as error:
        response_body = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code}", file=sys.stderr)
        print(response_body, file=sys.stderr)
        return 1
    except URLError as error:
        print(f"Request failed: {error.reason}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
