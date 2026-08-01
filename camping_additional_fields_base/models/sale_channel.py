from odoo import fields, models


class SaleChannel(models.Model):
    _inherit = "sale.channel"

    ota = fields.Boolean(string="OTA")
    ota_payment = fields.Boolean(
        string="OTA Payment",
        help="The OTA collects the payment for orders from this channel.",
    )
