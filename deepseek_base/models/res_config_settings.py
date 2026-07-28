from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    deepseek_api_key = fields.Char(
        string="DeepSeek API Key",
        config_parameter="deepseek.api_key",
        groups="base.group_system",
    )
