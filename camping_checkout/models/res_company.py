from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    x_local_tax_product_id = fields.Many2one("product.product", string="Local Tax Product")
    x_use_camping_pitch_map = fields.Boolean(
        string="Use Pitch Map in Checkout",
        help="Let website customers select an available campsite pitch before reviewing the order.",
    )
