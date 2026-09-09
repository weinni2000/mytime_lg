from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    validate_locations = fields.Boolean(
        related="company_id.validate_locations",
        readonly=False,
    )
