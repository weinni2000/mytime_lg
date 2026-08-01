from odoo import fields, models


class CampingFleetVehicle(models.Model):
    _name = "camping.fleet.vehicle"
    _description = "Camping Vehicle"
    _rec_name = "license_plate"
    _order = "license_plate, id"

    license_plate = fields.Char(string="Plate")
    category_id = fields.Many2one(
        "fleet.vehicle.model.category",
        string="Category",
        required=True,
        ondelete="restrict",
    )
    sale_order_id = fields.Many2one("sale.order", required=True, ondelete="cascade", index=True)


class FleetVehicleModelCategory(models.Model):
    _inherit = "fleet.vehicle.model.category"

    active = fields.Boolean(default=True)
