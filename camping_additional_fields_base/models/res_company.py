from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    special_temporary_info = fields.Text(
        string="Special Temporary Information",
        translate=True,
        help="Temporary information shown on sales orders for this company.",
    )
