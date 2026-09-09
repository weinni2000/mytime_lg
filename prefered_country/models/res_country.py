from odoo import api, fields, models

_NO_PRIORITY_RANK = 999999


class ResCountry(models.Model):
    _inherit = "res.country"
    _order = "x_country_sort_priority, name"

    x_country_sort_priority = fields.Integer(
        compute="_compute_x_country_sort_priority",
        store=True,
        help=(
            "Mirrors x_checkout_priority_sequence (from camping_checkout), "
            "but pushes countries without a priority to the end instead of "
            "the start, so the standard country selection field shows "
            "priority countries first everywhere, not just on the website "
            "checkout."
        ),
    )

    @api.depends("x_checkout_priority_sequence")
    def _compute_x_country_sort_priority(self):
        for record in self:
            record.x_country_sort_priority = record.x_checkout_priority_sequence or _NO_PRIORITY_RANK
