from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    id_scan_provider = fields.Selection(
        selection=[
            ("anthropic", "Claude"),
            ("google", "Google Gemini"),
            ("openai", "OpenAI"),
        ],
        string="ID Scan Provider",
        required=True,
        default="anthropic",
        help="AI provider used to extract identity document data.",
    )
