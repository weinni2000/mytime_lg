from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    x_local_tax_product_id = fields.Many2one("product.product", string="Local Tax Product")
