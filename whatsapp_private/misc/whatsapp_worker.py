#!/usr/bin/env python3
"""Persistent linked-device worker for the Odoo Private WhatsApp addon."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

import qrcode
from neonize.aioze.client import ClientFactory, NewAClient
from neonize.aioze.events import ConnectedEv, MessageEv
from neonize.proto.Neonize_pb2 import ContactEntry
from neonize.utils import build_jid

_logger = logging.getLogger(__name__)


class OperationAlreadyRunning(RuntimeError):
    """Raised when another worker already owns the company session."""


def user_facing_error(error: BaseException) -> str:
    """Translate protocol errors into an actionable message for Odoo users."""
    detail = str(error)
    if "error 463" in detail.lower():
        return (
            "WhatsApp temporarily prevents this linked number from starting a chat "
            "with a new contact (error 463). Ask the recipient to message this "
            "WhatsApp number first, or retry later. Reconnecting the QR code will "
            "not remove this WhatsApp restriction."
        )
    return detail


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def write_json(path: Path, payload: dict) -> None:
    atomic_write(path, json.dumps(payload, ensure_ascii=False).encode())


def write_state(directory: Path, status: str, detail: str) -> None:
    write_json(
        directory / "state.json",
        {"status": status, "detail": detail, "updated_at": time.time()},
    )


def remove_qr(directory: Path) -> None:
    (directory / "qr.png").unlink(missing_ok=True)


def save_qr(directory: Path, qr_data: bytes) -> None:
    image = qrcode.make(qr_data)
    temporary = directory / "qr.png.tmp"
    image.save(temporary, format="PNG")
    os.replace(temporary, directory / "qr.png")
    write_state(directory, "waiting_for_qr", "Scan the QR code in WhatsApp Linked Devices.")


def acquire_lock(directory: Path, name: str = "worker.lock"):
    lock_file = (directory / name).open("a+")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        _logger.warning("Lock %s in %s is already held by another process.", name, directory)
        raise OperationAlreadyRunning("Another WhatsApp operation is already running.") from None
    return lock_file


def message_text(event: MessageEv) -> str:
    message = event.Message
    if message.conversation:
        return message.conversation
    if message.HasField("extendedTextMessage"):
        return message.extendedTextMessage.text
    return ""


async def queue_inbound(directory: Path, client: NewAClient, event: MessageEv) -> None:
    source = event.Info.MessageSource
    sender = source.Chat if source.IsFromMe else source.Sender
    if sender.Server == "lid":
        try:
            sender = await client.get_pn_from_lid(sender)
        except Exception as exc:
            # Preserve the event even if WhatsApp local LID mapping is
            # temporarily unavailable; diagnostics retain the lookup error.
            sender_resolution_error = str(exc)
        else:
            sender_resolution_error = ""
    else:
        sender_resolution_error = ""
    audit = {
        "received_at": time.time(),
        "id": event.Info.ID,
        "sender": source.Sender.User,
        "sender_server": source.Sender.Server,
        "resolved_phone": sender.User if sender.Server != "lid" else "",
        "sender_resolution_error": sender_resolution_error,
        "chat": source.Chat.User,
        "from_me": source.IsFromMe,
        "is_group": source.IsGroup,
        "pushname": event.Info.Pushname,
        "has_text": bool(message_text(event)),
    }
    with (directory / "events.log").open("a", encoding="utf-8") as event_log:
        event_log.write(json.dumps(audit, ensure_ascii=False) + "\n")
    if sender.Server == "lid":
        return
    if source.IsGroup:
        return
    contact_data = {}
    try:
        contact_info = await client.contact.get_contact(sender)
        contact_data = {
            "first_name": contact_info.FirstName,
            "full_name": contact_info.FullName,
            "push_name": contact_info.PushName or event.Info.Pushname,
            "business_name": contact_info.BusinessName,
        }
    except Exception as exc:
        _logger.debug("Could not enrich inbound WhatsApp contact %s: %s", sender.User, exc)
        contact_data = {"push_name": event.Info.Pushname}
    text = message_text(event).strip()
    if not text:
        return
    message_id = event.Info.ID or uuid.uuid4().hex
    write_json(
        directory / "inbox" / f"{message_id}.json",
        {
            "id": message_id,
            "jid": f"{sender.User}@{sender.Server}",
            "phone": sender.User or source.Chat.User,
            "from_me": source.IsFromMe,
            "sender_name": contact_data.get("full_name")
            or contact_data.get("business_name")
            or contact_data.get("push_name"),
            "first_name": contact_data.get("first_name", ""),
            "full_name": contact_data.get("full_name", ""),
            "push_name": contact_data.get("push_name", ""),
            "business_name": contact_data.get("business_name", ""),
            "text": text,
            "timestamp": event.Info.Timestamp,
        },
    )
    _logger.info(
        "Queued %s WhatsApp message %s for %s",
        "linked-device outbound" if source.IsFromMe else "inbound",
        message_id,
        sender.User or source.Chat.User,
    )


async def link(directory: Path, timeout: float) -> None:
    client = ClientFactory(str(directory / "session.db")).new_client(uuid="odoo-private-whatsapp")
    connected = asyncio.Event()

    @client.event.qr
    async def on_qr(_: NewAClient, qr_data: bytes) -> None:
        _logger.info("Received a new QR code for linking in %s.", directory)
        save_qr(directory, qr_data)

    @client.event(ConnectedEv)
    async def on_connected(_: NewAClient, __: ConnectedEv) -> None:
        _logger.info("WhatsApp linking succeeded in %s.", directory)
        remove_qr(directory)
        write_state(directory, "connected", "WhatsApp is linked and ready.")
        connected.set()

    _logger.info("Starting WhatsApp linking process in %s (timeout=%ss).", directory, timeout)
    write_state(directory, "starting", "Starting WhatsApp linking process.")
    atomic_write(directory / "link.pid", str(os.getpid()).encode())
    try:
        await client.connect()
        await asyncio.wait_for(connected.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        _logger.warning("WhatsApp QR login timed out after %ss in %s.", timeout, directory)
        write_state(directory, "timeout", "The QR login timed out. Start linking again.")
        raise
    finally:
        (directory / "link.pid").unlink(missing_ok=True)
        await client.disconnect()


async def direct_send(directory: Path, phone: str, message: str, timeout: float) -> None:
    client = ClientFactory(str(directory / "session.db")).new_client(uuid="odoo-private-whatsapp")
    completed = asyncio.Event()
    failure: list[BaseException] = []

    @client.event(ConnectedEv)
    async def on_connected(connected_client: NewAClient, _: ConnectedEv) -> None:
        try:
            _logger.info("Connected; sending direct WhatsApp message to %s.", phone)
            write_state(directory, "sending", f"Sending to +{phone}.")
            response = await connected_client.send_message(build_jid(phone), message)
            message_id = getattr(response, "ID", None) or getattr(response, "id", None)
            _logger.info("Direct WhatsApp message sent to %s (message id: %s).", phone, message_id)
            write_state(directory, "sent", f"Message sent to +{phone}.")
        except BaseException as exc:
            _logger.exception("Failed to send direct WhatsApp message to %s.", phone)
            failure.append(exc)
        finally:
            completed.set()

    try:
        _logger.info("Connecting to WhatsApp to send a direct message to %s.", phone)
        await client.connect()
        await asyncio.wait_for(completed.wait(), timeout=timeout)
        if failure:
            raise failure[0]
    finally:
        await client.disconnect()


def listener_alive(directory: Path) -> bool:
    try:
        return time.time() - (directory / "heartbeat").stat().st_mtime < 20
    except OSError:
        return False


def queued_send(directory: Path, phone: str, message: str, timeout: float) -> None:
    request_id = uuid.uuid4().hex
    request_path = directory / "outbox" / f"{request_id}.json"
    result_path = directory / "results" / f"{request_id}.json"
    write_json(request_path, {"id": request_id, "phone": phone, "message": message})
    _logger.info("Queued WhatsApp send request %s to %s for the persistent listener.", request_id, phone)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.2)
            continue
        result_path.unlink(missing_ok=True)
        if result.get("error"):
            detail = user_facing_error(RuntimeError(result["error"]))
            _logger.error("WhatsApp send request %s to %s failed: %s", request_id, phone, detail)
            raise RuntimeError(detail)
        _logger.info(
            "WhatsApp send request %s to %s confirmed by the listener (message id: %s).",
            request_id,
            phone,
            result.get("id"),
        )
        return
    request_path.unlink(missing_ok=True)
    _logger.error(
        "WhatsApp send request %s to %s timed out after %ss waiting for the listener.",
        request_id,
        phone,
        timeout,
    )
    raise TimeoutError("The persistent WhatsApp listener did not complete the send request.")


async def heartbeat_loop(directory: Path) -> None:
    while True:
        atomic_write(directory / "heartbeat", str(time.time()).encode())
        await asyncio.sleep(5)


async def outbox_loop(directory: Path, client: NewAClient) -> None:
    outbox = directory / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    while True:
        for path in sorted(outbox.glob("*.json")):
            processing = path.with_suffix(".processing")
            try:
                os.replace(path, processing)
                request = json.loads(processing.read_text(encoding="utf-8"))
                _logger.info("Sending queued WhatsApp message %s to %s.", request["id"], request["phone"])
                response = await client.send_message(build_jid(request["phone"]), request["message"])
                message_id = getattr(response, "ID", None) or getattr(response, "id", None)
                _logger.info(
                    "Queued WhatsApp message %s to %s sent (message id: %s).",
                    request["id"],
                    request["phone"],
                    message_id,
                )
                write_json(
                    directory / "results" / f"{request['id']}.json",
                    {"id": message_id or request["id"]},
                )
            except Exception as exc:
                request_id = locals().get("request", {}).get("id") or processing.stem
                _logger.exception("Failed to send queued WhatsApp message %s.", request_id)
                write_json(
                    directory / "results" / f"{request_id}.json",
                    {"error": str(exc)},
                )
            finally:
                processing.unlink(missing_ok=True)
        await asyncio.sleep(0.2)


async def contact_export_loop(directory: Path, client: NewAClient) -> None:
    """Export the live WhatsApp contact store when requested by Odoo."""
    request_path = directory / "contact_export.request"
    while True:
        if not request_path.exists():
            await asyncio.sleep(1)
            continue
        processing = request_path.with_suffix(".processing")
        try:
            os.replace(request_path, processing)
            request = json.loads(processing.read_text(encoding="utf-8"))
            exported = {}
            for contact in await client.contact.get_all_contacts():
                jid = contact.JID
                if jid.Server != "s.whatsapp.net" or not jid.User.isdigit():
                    continue
                info = contact.Info
                key = f"{jid.User}@{jid.Server}"
                exported[key] = {
                    "jid": key,
                    "phone": jid.User,
                    "first_name": info.FirstName,
                    "full_name": info.FullName,
                    "push_name": info.PushName,
                    "business_name": info.BusinessName,
                }
            write_json(
                directory / "contacts_snapshot.json",
                {
                    "request_id": request.get("request_id"),
                    "exported_at": time.time(),
                    "contacts": list(exported.values()),
                    "error": "",
                },
            )
            _logger.info("Exported %s WhatsApp contacts in %s.", len(exported), directory)
        except Exception as exc:
            _logger.exception("Could not export WhatsApp contacts in %s.", directory)
            write_json(
                directory / "contacts_snapshot.json",
                {"exported_at": time.time(), "contacts": [], "error": str(exc)},
            )
        finally:
            processing.unlink(missing_ok=True)
        await asyncio.sleep(1)


async def contact_update_loop(directory: Path, client: NewAClient) -> None:
    """Apply Odoo contact names to the linked WhatsApp contact store."""
    request_path = directory / "contact_update.request"
    while True:
        if not request_path.exists():
            await asyncio.sleep(1)
            continue
        processing = request_path.with_suffix(".processing")
        request = {}
        try:
            os.replace(request_path, processing)
            request = json.loads(processing.read_text(encoding="utf-8"))
            entries = [
                ContactEntry(
                    JID=build_jid(contact["phone"]),
                    FirstName=contact.get("first_name") or contact["name"].split()[0],
                    FullName=contact["name"],
                )
                for contact in request.get("contacts", [])
                if contact.get("phone") and contact.get("name")
            ]
            if entries:
                await client.contact.put_all_contact_name(entries)
            write_json(
                directory / "contact_update_result.json",
                {
                    "request_id": request.get("request_id"),
                    "updated_at": time.time(),
                    "count": len(entries),
                    "error": "",
                },
            )
            _logger.info("Updated %s WhatsApp contact names from Odoo in %s.", len(entries), directory)
        except Exception as exc:
            _logger.exception("Could not update WhatsApp contact names in %s.", directory)
            write_json(
                directory / "contact_update_result.json",
                {"request_id": request.get("request_id"), "count": 0, "error": str(exc)},
            )
        finally:
            processing.unlink(missing_ok=True)
        await asyncio.sleep(1)


async def listen(directory: Path) -> None:
    client = ClientFactory(str(directory / "session.db")).new_client(uuid="odoo-private-whatsapp")
    connected = asyncio.Event()

    @client.event.qr
    async def on_qr(_: NewAClient, qr_data: bytes) -> None:
        _logger.info("Received a new QR code for linking in %s.", directory)
        save_qr(directory, qr_data)

    @client.event(ConnectedEv)
    async def on_connected(_: NewAClient, __: ConnectedEv) -> None:
        _logger.info("WhatsApp listener connected in %s.", directory)
        remove_qr(directory)
        write_state(directory, "connected", "WhatsApp listener is connected.")
        connected.set()

    @client.event(MessageEv)
    async def on_message(_: NewAClient, event: MessageEv) -> None:
        await queue_inbound(directory, client, event)

    _logger.info("Starting persistent WhatsApp listener in %s.", directory)
    atomic_write(directory / "listener.pid", str(os.getpid()).encode())
    try:
        await client.connect()
        await connected.wait()
        await asyncio.gather(
            heartbeat_loop(directory),
            outbox_loop(directory, client),
            contact_export_loop(directory, client),
            contact_update_loop(directory, client),
        )
    finally:
        _logger.info("WhatsApp listener stopping in %s.", directory)
        (directory / "heartbeat").unlink(missing_ok=True)
        (directory / "listener.pid").unlink(missing_ok=True)
        await client.disconnect()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("link", "listen", "send"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--phone")
    parser.add_argument("--message")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args.directory.mkdir(parents=True, exist_ok=True)
    try:
        if args.operation == "send" and listener_alive(args.directory):
            if not args.phone or not args.message:
                raise ValueError("Phone and message are required.")
            queued_send(args.directory, args.phone, args.message, args.timeout)
            return 0
        lock_name = "listener.lock" if args.operation in {"link", "listen"} else "worker.lock"
        lock_file = acquire_lock(args.directory, lock_name)
        with lock_file:
            if args.operation == "link":
                asyncio.run(link(args.directory, args.timeout))
            elif args.operation == "listen":
                asyncio.run(listen(args.directory))
            else:
                if not args.phone or not args.message:
                    raise ValueError("Phone and message are required.")
                asyncio.run(direct_send(args.directory, args.phone, args.message, args.timeout))
    except OperationAlreadyRunning as exc:
        _logger.warning(
            "WhatsApp worker operation %r skipped in %s: %s",
            args.operation,
            args.directory,
            exc,
        )
        return 2
    except Exception as exc:
        _logger.exception("WhatsApp worker operation %r failed in %s.", args.operation, args.directory)
        detail = user_facing_error(exc)
        if args.operation == "send" and listener_alive(args.directory):
            write_state(
                args.directory,
                "connected",
                f"WhatsApp listener is connected. Last send failed: {detail}",
            )
        else:
            write_state(args.directory, "error", detail)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
