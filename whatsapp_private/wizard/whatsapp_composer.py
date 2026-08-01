from odoo import _, api, fields, models
from odoo.tools import html2plaintext, plaintext2html


class WhatsappComposer(models.TransientModel):
    _inherit = "whatsapp.composer"

    is_private_whatsapp = fields.Boolean(
        compute="_compute_is_private_whatsapp",
    )
    is_individual = fields.Boolean(
        string="Individual Message",
        help="Edit the message manually before sending instead of using the template as-is.",
    )
    individual_message = fields.Text(
        string="Message",
        compute="_compute_individual_message",
        readonly=False,
        store=True,
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        model = values.get("res_model") or self.env.context.get("active_model")
        if model and not self.env.context.get("default_wa_template_id"):
            private_template = self.env["whatsapp.template"].search(
                [
                    ("model", "=", model),
                    ("status", "=", "approved"),
                    ("wa_account_id.connection_type", "=", "private"),
                    ("wa_account_id.private_company_id", "=", self.env.company.id),
                ],
                order="id",
                limit=1,
            )
            if private_template:
                values["wa_template_id"] = private_template.id
        return values

    @api.depends("wa_template_id")
    def _compute_is_private_whatsapp(self):
        for composer in self:
            composer.is_private_whatsapp = composer.wa_template_id.wa_account_id.connection_type == "private"

    @api.depends(
        "is_individual",
        "wa_template_id",
        "header_text_1",
        "button_dynamic_url_1",
        "button_dynamic_url_2",
        *(f"free_text_{i}" for i in range(1, 11)),
    )
    def _compute_individual_message(self):
        for composer in self:
            if not composer.is_individual:
                continue
            records = composer._get_active_records()
            if composer.wa_template_id and records:
                composer.individual_message = html2plaintext(composer._get_template_whatsapp_body(records[0]))

    def _get_free_text_fields(self):
        return super()._get_free_text_fields() + ["is_individual", "individual_message"]

    def _get_template_whatsapp_body(self, rec):
        """Render the message from the template only, ignoring any manual edit."""
        return super()._get_html_preview_whatsapp(rec=rec)

    def _get_html_preview_whatsapp(self, rec):
        if self.is_individual and self.individual_message:
            return plaintext2html(self.individual_message)
        return super()._get_html_preview_whatsapp(rec=rec)

    def action_send_whatsapp_template(self):
        result = super().action_send_whatsapp_template()
        if (
            self.is_private_whatsapp
            and result
            and getattr(result, "_name", None) == "whatsapp.message"
            and any(message.state == "error" for message in result)
        ):
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("WhatsApp message was not sent"),
                    "message": _(
                        "The private WhatsApp connection failed. A note with the error and "
                        "reconnect link was added to the chatter."
                    ),
                    "type": "danger",
                    "sticky": True,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        return result
