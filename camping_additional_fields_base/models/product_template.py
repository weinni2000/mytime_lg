from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    directions = fields.Text(
        translate=True,
        help="Directions to reach the camping ground for this product.",
    )
