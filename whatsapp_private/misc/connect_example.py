#!/usr/bin/env python3
"""Minimal example: connect a private WhatsApp account with Neonize.

Run it, scan the QR code shown in the terminal with WhatsApp's
"Linked devices" screen, then press Ctrl+C once connected. The session
is stored in whatsapp_session.db and reused on the next run, so later
runs connect without a new QR scan.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from neonize.aioze.client import ClientFactory, NewAClient
from neonize.aioze.events import ConnectedEv, DisconnectedEv, LoggedOutEv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

SESSION_PATH = Path(__file__).with_name("whatsapp_session.db")


async def main() -> None:
    factory = ClientFactory(str(SESSION_PATH))
    client = factory.new_client(uuid="connect-example")

    @client.event(ConnectedEv)
    async def on_connected(_: NewAClient, __: ConnectedEv) -> None:
        log.info("Connected to WhatsApp.")

    @client.event(DisconnectedEv)
    async def on_disconnected(_: NewAClient, __: DisconnectedEv) -> None:
        log.info("Disconnected from WhatsApp.")

    @client.event(LoggedOutEv)
    async def on_logged_out(_: NewAClient, __: LoggedOutEv) -> None:
        log.warning("Logged out - delete %s and scan the QR code again.", SESSION_PATH.name)

    await client.connect()
    try:
        await asyncio.Event().wait()  # keep the script alive until Ctrl+C
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped.")
