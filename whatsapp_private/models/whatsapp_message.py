import logging
import re
import uuid

from odoo import models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class WhatsAppMessage(models.Model):
    _inherit = "whatsapp.message"

    def _send_private_message(self, with_commit=False):
        self.ensure_one()
        if self.state != "outgoing":
            return

        account = self.wa_account_id
        try:
            if not account.private_company_id:
                raise ValidationError("No company is configured for this Private Business account.")
            phone = re.sub(r"\D", "", self.mobile_number_formatted or self.mobile_number or "")
            if not 7 <= len(phone) <= 15:
                raise ValidationError("The WhatsApp recipient number is invalid.")
            message = html2plaintext(self.body or "", include_references=False).strip()
            if not message:
                raise ValidationError("The WhatsApp message is empty.")

            _logger.info(
                "Sending private WhatsApp message %s to %s via account %s.",
                self.id,
                phone,
                account.id,
            )
            account.private_company_id._send_private_whatsapp_message(phone, message)
        except (UserError, ValidationError) as error:
            _logger.warning("Private WhatsApp message %s failed: %s", self.id, error)
            self._handle_error(failure_type="unknown", error_message=str(error))
        else:
            _logger.info("Private WhatsApp message %s marked as sent.", self.id)
            self.write(
                {
                    "message_type": "outbound",
                    "state": "sent",
                    "msg_uid": f"private-{uuid.uuid4().hex}",
                }
            )
            if self.wa_template_id and self.wa_template_id.model != "discuss.channel":
                self._post_message_in_active_channel()
        if with_commit:
            self.env.cr.commit()

    def _send_message(self, with_commit=False):
        private_messages = self.filtered(lambda message: message.wa_account_id.connection_type == "private")
        cloud_messages = self - private_messages

        for message in private_messages:
            message._send_private_message(with_commit=with_commit)
        if cloud_messages:
            return super(WhatsAppMessage, cloud_messages)._send_message(with_commit=with_commit)
        return None
