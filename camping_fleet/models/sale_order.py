from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    vehicle_ids = fields.One2many("camping.fleet.vehicle", "sale_order_id", string="Vehicles")
