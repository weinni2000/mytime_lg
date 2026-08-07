from odoo import api, fields, models


class MailToBookingProductMappingWizard(models.TransientModel):
    _name = "mail.to.booking.product.mapping.wizard"
    _description = "Choose Product for Mail to Booking"

    mail_to_booking_id = fields.Many2one("mail.to.booking", required=True, readonly=True)
    sale_channel_id = fields.Many2one("sale.channel", required=True, readonly=True)
    product_hint = fields.Char(readonly=True)
    product_id = fields.Many2one(
        "product.product",
        required=True,
        domain=[("x_is_a_room_offer", "=", True)],
    )
    force_single_product = fields.Boolean(
        string="Immer für diesen Kanal verwenden",
        help="Statt nur diesen Hinweistext zuzuordnen, wird dieses Produkt für "
        "jede zukünftige Buchung des Kanals verwendet (produkt_hint-Zuordnung "
        "wird dann übersprungen).",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        booking_id = self.env["mail.to.booking"].browse(self.env.context.get("active_id"))
        if booking_id:
            values["mail_to_booking_id"] = booking_id.id
            values["sale_channel_id"] = booking_id.sale_channel_id.id
            values["product_hint"] = booking_id.product_hint
        return values

    def action_confirm(self):
        self.ensure_one()
        if self.force_single_product:
            self.sale_channel_id.write(
                {
                    "force_single_product": True,
                    "default_product_id": self.product_id.id,
                }
            )
        elif self.product_hint:
            # Without a hint there is nothing to key a mapping row on, so
            # only save one for future automatic matches when a hint exists.
            self.env["mail.to.booking.product.mapping"].create(
                {
                    "sale_channel_id": self.sale_channel_id.id,
                    "product_hint": self.product_hint,
                    "product_id": self.product_id.id,
                    "company_id": self.mail_to_booking_id.company_id.id,
                }
            )
        self.mail_to_booking_id.action_process(product_id=self.product_id)
        return True
