from odoo import fields, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    checked_by_id = fields.Many2one(
        "res.users",
        string="Geprüft von",
    )

    def action_open_related_document(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }
