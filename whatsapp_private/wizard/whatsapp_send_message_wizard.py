import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WhatsAppSendMessageWizard(models.TransientModel):
    _name = "whatsapp.send.message.wizard"
    _description = "Send Private WhatsApp Message"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        required=True,
        domain="[('is_company', '=', False)]",
    )
    phone = fields.Char(
        string="WhatsApp Number",
        required=True,
        help="International format including country code, for example +436641234567.",
    )
    message = fields.Text(required=True)

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.phone = (
                self.partner_id["mobile"]
                if "mobile" in self.partner_id._fields and self.partner_id["mobile"]
                else self.partner_id.phone
            )

    @api.constrains("message")
    def _check_message(self):
        for wizard in self:
            if not wizard.message or not wizard.message.strip():
                raise ValidationError(_("The message must not be empty."))

    def _normalize_phone(self):
        self.ensure_one()
        value = (self.phone or "").strip()
        phone = re.sub(r"\D", "", value)
        if value.startswith("00"):
            phone = phone[2:]
        if not 7 <= len(phone) <= 15:
            raise ValidationError(
                _(
                    "Use an international phone number with country code "
                    "(7 to 15 digits), for example +436641234567."
                )
            )
        return phone

    def action_send(self):
        self.ensure_one()
        self.company_id._send_private_whatsapp_message(
            self._normalize_phone(),
            self.message,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("WhatsApp"),
                "message": _("Message sent to %s.", self.partner_id.display_name),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
