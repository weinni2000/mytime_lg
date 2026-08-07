from odoo import fields, models


class CampingVehicleType(models.Model):
    _name = "camping.vehicle.type"
    _description = "Camping Vehicle Type"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
