from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    deepseek_api_key = fields.Char(
        string="DeepSeek API Key",
        copy=False,
        groups="base.group_system",
    )
