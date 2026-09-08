from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    flower_openrouter_key_enabled = fields.Boolean(
        string="Enable custom OpenRouter API key",
        compute="_compute_flower_openrouter_key_enabled",
        readonly=False,
        groups="base.group_system",
    )
    flower_openrouter_key = fields.Char(
        string="OpenRouter API key",
        config_parameter="flower_calculator.openrouter_api_key",
        readonly=False,
        groups="base.group_system",
    )

    def _compute_flower_openrouter_key_enabled(self):
        for record in self:
            record.flower_openrouter_key_enabled = bool(record.flower_openrouter_key)
