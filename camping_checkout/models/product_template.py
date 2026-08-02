from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_max_guest = fields.Integer(string="Max Guests", default=2)
    x_additional_guest_product_id = fields.Many2one("product.product", string="Additional Guest Product")
    x_electricity_product_id = fields.Many2one("product.product", string="Electricity")
