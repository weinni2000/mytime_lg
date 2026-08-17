from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_max_guest = fields.Integer(string="Max Guests", default=2)
    x_included_persons = fields.Integer(
        string="Included Persons",
        default=2,
        help="Guests already covered by the accommodation price. The included "
        "headcount scales with the quantity, so with several pitches it is "
        "included_persons x quantity (e.g. 2 pitches x 2 = 4). Every guest "
        "beyond that total is billed the additional-guest product.",
    )
    x_additional_guest_product_id = fields.Many2one("product.product", string="Additional Guest Product")
    x_electricity_product_id = fields.Many2one("product.product", string="Electricity")
