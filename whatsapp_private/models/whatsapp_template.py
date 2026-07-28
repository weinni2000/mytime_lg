from odoo import _, api, fields, models


class WhatsAppTemplate(models.Model):
    _inherit = "whatsapp.template"

    is_private_whatsapp = fields.Boolean(
        related="wa_account_id.is_private_whatsapp",
    )

    def _approve_private_templates(self):
        private_templates = self.filtered(
            lambda template: template.wa_account_id.connection_type == "private" and template.status != "approved"
        )
        if private_templates:
            private_templates.with_context(skip_private_template_auto_approval=True).write({"status": "approved"})

    @api.onchange("wa_account_id")
    def _onchange_wa_account_id(self):
        result = super()._onchange_wa_account_id()
        if self.wa_account_id.connection_type == "private":
            self.status = "approved"
        return result

    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        templates._approve_private_templates()
        return templates

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("skip_private_template_auto_approval"):
            self._approve_private_templates()
        return result

    def button_submit_template(self):
        self.ensure_one()
        if self.wa_account_id.connection_type == "private":
            self.status = "approved"
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("WhatsApp Template"),
                    "message": _("Private Business templates are approved immediately."),
                    "type": "success",
                    "sticky": False,
                },
            }
        return super().button_submit_template()
