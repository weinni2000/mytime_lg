from odoo import fields, models


class ResCountry(models.Model):
    _inherit = "res.country"

    x_checkout_priority_sequence = fields.Integer(
        string="Checkout Priority",
        default=0,
        help="Countries with a non-zero value are pinned to the top of the "
        "website checkout country dropdown, ordered by this value (lowest "
        "first). Leave at 0 to keep the country in the regular alphabetical "
        "list.",
    )
