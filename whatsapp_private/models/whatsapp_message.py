import logging
import re
import uuid

from markupsafe import Markup, escape

from odoo import _, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class WhatsAppMessage(models.Model):
    _inherit = "whatsapp.message"

    def _post_private_failure_on_source(self, error):
        """Leave an actionable failure note on the originating business record."""
        self.ensure_one()
        mail_message = self.mail_message_id
        if not mail_message.model or not mail_message.res_id:
            return
        source = self.env[mail_message.model].browse(mail_message.res_id).exists()
        if not source or not hasattr(source, "message_post"):
            return

        error_text = str(error)
        reconnect_required = True
        if "timed out after" in error_text:
            error_text = _(
                "The private WhatsApp connection timed out. The linked device may need to be reconnected."
            )
        elif "error 463" in error_text:
            reconnect_required = False
            error_text = _(
                "WhatsApp temporarily prevents this number from starting a chat with a new "
                "contact (error 463). Ask the recipient to message this WhatsApp number "
                "first, or retry later. Reconnecting the QR code will not remove this "
                "WhatsApp restriction."
            )
        try:
            if reconnect_required:
                instruction = Markup("%s %s") % (
                    escape(_("Reconnect the private WhatsApp account and retry the message:")),
                    self.wa_account_id._get_html_link(title=_("Reconnect WhatsApp / show QR code")),
                )
            else:
                instruction = escape(_("The WhatsApp connection itself is still active; no QR action is needed."))
            source.message_post(
                body=Markup(
                    "<p><strong>%(title)s</strong></p>" "<p>%(error_label)s %(error)s</p>" "<p>%(instruction)s</p>"
                )
                % {
                    "title": escape(_("WhatsApp message was not sent.")),
                    "error_label": escape(_("Error:")),
                    "error": escape(error_text),
                    "instruction": instruction,
                },
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        except Exception:  # pylint: disable=broad-exception-caught
            _logger.exception(
                "Could not post private WhatsApp failure for message %s on %s,%s.",
                self.id,
                mail_message.model,
                mail_message.res_id,
            )

    def _send_private_message(self, with_commit=False):
        self.ensure_one()
        if self.state != "outgoing":
            return

        account = self.wa_account_id
        try:
            if not account.private_company_id:
                raise ValidationError(_("No company is configured for this Private Business account."))
            phone = re.sub(r"\D", "", self.mobile_number_formatted or self.mobile_number or "")
            if not 7 <= len(phone) <= 15:
                raise ValidationError(_("The WhatsApp recipient number is invalid."))
            message = html2plaintext(self.body or "", include_references=False).strip()
            if not message:
                raise ValidationError(_("The WhatsApp message is empty."))

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
            self._post_private_failure_on_source(error)
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
            self.env.cr.commit()  # pylint: disable=invalid-commit

    def _send_message(self, with_commit=False):
        private_messages = self.filtered(lambda message: message.wa_account_id.connection_type == "private")
        cloud_messages = self - private_messages

        for message in private_messages:
            message._send_private_message(with_commit=with_commit)
        if cloud_messages:
            return super(WhatsAppMessage, cloud_messages)._send_message(with_commit=with_commit)
        return None
