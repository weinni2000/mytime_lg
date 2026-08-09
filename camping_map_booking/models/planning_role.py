from odoo import fields, models


class PlanningRole(models.Model):
    _inherit = "planning.role"

    allowed_vehicle_type_ids = fields.Many2many(
        "camping.vehicle.type",
        string="Allowed Vehicles",
        help="Vehicle types allowed for this role. Leave empty to allow any vehicle.",
    )
