from odoo import fields, models


class ResourceResource(models.Model):
    _inherit = "resource.resource"

    vehicle_type_ids = fields.Many2many(
        "camping.vehicle.type",
        string="Allowed Vehicles",
        help="Vehicle types allowed on this pitch. Leave empty to allow any vehicle.",
    )
