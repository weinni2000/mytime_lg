from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    camping_confirmation_text = fields.Text(
        translate=True,
        help="Text inserted into the camping confirmation email when this product is sold.",
    )
