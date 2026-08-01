from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    animal_ids = fields.One2many("animal", "sale_order_id", string="Dogs")
