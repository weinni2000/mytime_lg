from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    special_temporary_info = fields.Text(
        string="Special Temporary Information",
        translate=True,
        help="Temporary information shown on sales orders for this company.",
    )
    default_brand_id = fields.Many2one(
        comodel_name="res.brand",
        string="Default Brand for Online Orders",
        help="Brand automatically applied to sales orders created from the "
        "website or imported from an OTA/sales channel, when none is set.",
    )
