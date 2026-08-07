from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    no_dropped_mail_enabled = fields.Boolean(
        related="company_id.no_dropped_mail_enabled",
        readonly=False,
    )
    no_dropped_mail_channel_id = fields.Many2one(
        related="company_id.no_dropped_mail_channel_id",
        readonly=False,
    )
