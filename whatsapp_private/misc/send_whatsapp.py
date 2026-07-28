#!/usr/bin/env python3
"""Send one WhatsApp message through a linked private WhatsApp account.

Neonize uses WhatsApp's unofficial multi-device protocol. The first run shows a
QR code that must be scanned in WhatsApp under "Linked devices". The linked
session is stored locally and reused on subsequent runs.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

from neonize.aioze.client import ClientFactory, NewAClient
from neonize.aioze.events import ConnectedEv
from neonize.utils import build_jid

DEFAULT_SESSION = Path(__file__).with_name("whatsapp_session.db")


def normalize_phone(value: str) -> str:
    """Return an international phone number containing digits only."""
    phone = re.sub(r"\D", "", value)
    if value.strip().startswith("00"):
        phone = phone[2:]
    if not 7 <= len(phone) <= 15:
        raise argparse.ArgumentTypeError(
            "Use an international number with country code, for example " "+436641234567 (7 to 15 digits)."
        )
    return phone


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a message from a linked private WhatsApp account.")
    parser.add_argument(
        "phone",
        type=normalize_phone,
        help="Recipient in international format, e.g. +436641234567",
    )
    message = parser.add_mutually_exclusive_group(required=True)
    message.add_argument("--message", "-m", help="Message text")
    message.add_argument(
        "--message-file",
        type=Path,
        help="UTF-8 text file containing the message",
    )
    parser.add_argument(
        "--session",
        type=Path,
        default=DEFAULT_SESSION,
        help=f"Session database (default: {DEFAULT_SESSION})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180,
        help="Seconds to wait for login and sending (default: 180)",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def get_message(args: argparse.Namespace) -> str:
    text = args.message_file.read_text(encoding="utf-8") if args.message_file else args.message
    if not text or not text.strip():
        raise ValueError("The message must not be empty.")
    return text


async def send_message(
    phone: str,
    text: str,
    session_path: Path,
    timeout: float,
) -> None:
    session_path = session_path.expanduser().resolve()
    session_path.parent.mkdir(parents=True, exist_ok=True)

    factory = ClientFactory(str(session_path))
    client = factory.new_client(uuid="private-whatsapp-sender")
    sent = asyncio.Event()
    failure: list[BaseException] = []

    @client.event(ConnectedEv)
    async def on_connected(connected_client: NewAClient, _: ConnectedEv) -> None:
        if sent.is_set():
            return
        try:
            result = await connected_client.send_message(
                build_jid(phone),
                text,
            )
            message_id = getattr(result, "ID", None) or getattr(result, "id", None)
            detail = f" (message ID: {message_id})" if message_id else ""
            sys.stdout.write(f"Message sent to +{phone}{detail}.\n")
        except BaseException as exc:
            failure.append(exc)
        finally:
            sent.set()

    try:
        await client.connect()
        await asyncio.wait_for(sent.wait(), timeout=timeout)
        if failure:
            raise failure[0]
    finally:
        await client.disconnect()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    try:
        text = get_message(args)
        asyncio.run(
            send_message(
                phone=args.phone,
                text=text,
                session_path=args.session,
                timeout=args.timeout,
            )
        )
    except KeyboardInterrupt:
        sys.stderr.write("Cancelled.\n")
        return 130
    except Exception as exc:
        sys.stderr.write(f"WhatsApp message failed: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
