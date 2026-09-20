from odoo import fields, models


class VoipCall(models.Model):
    _inherit = "voip.call"

    comment = fields.Text()
