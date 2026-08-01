from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _get_frontend_writable_fields(self):
        return super()._get_frontend_writable_fields() | {
            "x_birthdate",
            "x_id_document_front",
        }
