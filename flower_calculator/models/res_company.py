from odoo import fields, models

from ._const import DEFAULT_FLOWER_LARGE_PRICE, DEFAULT_FLOWER_SMALL_PRICE


class ResCompany(models.Model):
    _inherit = "res.company"

    default_flower_small = fields.Monetary(
        string="Default Small Flower Price",
        default=DEFAULT_FLOWER_SMALL_PRICE,
    )
    default_flower_large = fields.Monetary(
        string="Default Large Flower Price",
        default=DEFAULT_FLOWER_LARGE_PRICE,
    )
