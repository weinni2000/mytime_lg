import json
import logging
import os
import subprocess
import sys
import time

from odoo import api, fields, models
from odoo.tools import plaintext2html

_logger = logging.getLogger(__name__)


class WhatsAppAccount(models.Model):
    _inherit = "whatsapp.account"

    def _private_listener_alive(self):
        self.ensure_one()
        heartbeat = self.private_company_id._whatsapp_private_directory() / "heartbeat"
        try:
            return time.time() - heartbeat.stat().st_mtime < 20
        except OSError:
            _logger.debug("WhatsApp heartbeat file is unavailable for account %s", self.id)
        return bool(self.private_company_id._whatsapp_private_worker_pids())

    def _start_private_listener(self):
        self.ensure_one()
        if not self.private_company_id or self._private_listener_alive():
            return
        directory = self.private_company_id._whatsapp_private_directory()
        directory.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(self.private_company_id._whatsapp_private_worker()),
            "listen",
            "--directory",
            str(directory),
        ]
        log_file = (directory / "listener.log").open("ab")
        try:
            subprocess.Popen(  # pylint: disable=consider-using-with
                command,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        finally:
            log_file.close()

    def _process_private_inbox(self):
        self.ensure_one()
        directory = self.private_company_id._whatsapp_private_directory()
        inbox = directory / "inbox"
        if not inbox.exists():
            return
        for event_path in sorted(inbox.glob("*.json")):
            processing_path = event_path.with_suffix(".processing")
            try:
                os.replace(event_path, processing_path)
                event = json.loads(processing_path.read_text(encoding="utf-8"))
                message_id = event["id"]
                if self.env["whatsapp.message"].sudo().search_count([("msg_uid", "=", message_id)], limit=1):
                    processing_path.unlink(missing_ok=True)
                    continue
                phone = "+" + "".join(character for character in event["phone"] if character.isdigit())
                channel = self._find_active_channel(
                    phone,
                    sender_name=event.get("sender_name"),
                    create_if_not_found=True,
                )
                if not channel:
                    raise RuntimeError(f"Could not create a WhatsApp channel for {phone}.")
                partner = channel.whatsapp_partner_id
                if partner:
                    contact_values = {
                        "whatsapp_private_jid": event.get("jid"),
                        "whatsapp_private_company_id": self.private_company_id.id,
                        "whatsapp_private_first_name": event.get("first_name"),
                        "whatsapp_private_full_name": event.get("full_name"),
                        "whatsapp_private_push_name": event.get("push_name"),
                        "whatsapp_private_business_name": event.get("business_name"),
                        "whatsapp_private_last_sync": fields.Datetime.now(),
                        "whatsapp_private_sync_source": "inbound",
                    }
                    if (not partner.name or partner.name.strip() in {"/", "Unknown"}) and event.get("sender_name"):
                        contact_values["name"] = event["sender_name"]
                    partner.sudo().write(
                        {key: value for key, value in contact_values.items() if value is not None}
                    )
                body = plaintext2html(event["text"])
                if event.get("from_me"):
                    author = self.private_company_id.partner_id
                    mail_message = channel.message_post(
                        message_type="comment",
                        author_id=author.id,
                        body=body,
                        subtype_xmlid="mail.mt_comment",
                    )
                    self.env["whatsapp.message"].sudo().create(
                        {
                            "mail_message_id": mail_message.id,
                            "message_type": "outbound",
                            "mobile_number": phone,
                            "msg_uid": message_id,
                            "state": "sent",
                            "wa_account_id": self.id,
                        }
                    )
                else:
                    channel.message_post(
                        whatsapp_inbound_msg_uid=message_id,
                        message_type="whatsapp_message",
                        author_id=(self.private_company_id.partner_id.id if event.get("from_me") else partner.id),
                        body=body,
                        subtype_xmlid="mail.mt_comment",
                    )
                if partner:
                    partner.sudo().message_post(
                        author_id=(self.private_company_id.partner_id.id if event.get("from_me") else partner.id),
                        body=body,
                        message_type="comment",
                        subtype_xmlid="mail.mt_note",
                    )
                processing_path.unlink(missing_ok=True)
            except Exception:
                _logger.exception("Could not import private WhatsApp event %s", processing_path)
                if processing_path.exists():
                    retry_path = processing_path.with_suffix(".json")
                    os.replace(processing_path, retry_path)

    @api.model
    def _cron_private_whatsapp_listener(self):
        accounts = self.sudo().search([("connection_type", "=", "private"), ("active", "=", True)])
        # One linked private session is currently stored per company.
        seen_companies = set()
        for account in accounts:
            company_id = account.private_company_id.id
            if not company_id or company_id in seen_companies:
                continue
            seen_companies.add(company_id)
            account._start_private_listener()
            account._process_private_inbox()
