from odoo import fields, models

DEFAULT_PITCH_NO_AVAILABILITY_MESSAGE = (
    "For the Type of vehicle we don't have an available space for this duration. "
    "Sometimes we have additional spaces please call +436502728225 or change your "
    "vehicle type or stay time"
)


class ResCompany(models.Model):
    _inherit = "res.company"

    x_local_tax_product_id = fields.Many2one("product.product", string="Local Tax Product")
    x_use_camping_pitch_map = fields.Boolean(
        string="Use Pitch Map in Checkout",
        help="Let website customers select an available campsite pitch before reviewing the order.",
    )
    x_pitch_no_availability_message = fields.Text(
        string="Pitch No Availability Message",
        translate=True,
        default=DEFAULT_PITCH_NO_AVAILABILITY_MESSAGE,
        help="Shown as a popup on the pitch step when no pitch is available for the "
        "selected vehicle type and stay.",
    )
