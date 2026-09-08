from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    kleinstunternehmer = fields.Boolean(
        help="If enabled, detailed digitalization multiplies extracted bill prices by 1.2.",
    )
