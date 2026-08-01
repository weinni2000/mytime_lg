from odoo import fields, models


class Animal(models.Model):
    _inherit = "animal"

    product_id = fields.Many2one("product.product", string="Product")
    sale_order_id = fields.Many2one("sale.order", ondelete="cascade", index=True)
