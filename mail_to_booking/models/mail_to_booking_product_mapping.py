from odoo import fields, models


class MailToBookingProductMapping(models.Model):
    _name = "mail.to.booking.product.mapping"
    _description = "Mail to Booking Product Mapping"
    _order = "sale_channel_id, product_hint"

    sale_channel_id = fields.Many2one("sale.channel", required=True, ondelete="cascade")
    product_hint = fields.Char(required=True)
    product_id = fields.Many2one("product.product", required=True, ondelete="cascade")
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
