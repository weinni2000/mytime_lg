from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    validate_locations = fields.Boolean(
        default=False,
        help="When enabled, partners and companies must have a country, "
        "state, city and zip matching their selected ZIP Location "
        "(base_location's zip_id), otherwise saving raises a validation "
        "error. Disabled by default so mismatching addresses can be saved.",
    )
