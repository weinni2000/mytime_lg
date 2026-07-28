from odoo import api, fields, models
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
