from odoo import api, fields, models


class MailToBookingNotBookingWizard(models.TransientModel):
    _name = "mail.to.booking.not.booking.wizard"
    _description = "Mark Mail to Booking as Not a Booking"

    mail_to_booking_id = fields.Many2one("mail.to.booking", required=True, readonly=True)
    subject = fields.Char(readonly=True)
    sale_channel_id = fields.Many2one("sale.channel", required=True)
    subject_keyword = fields.Char(
        required=True,
        string="Blocker Text",
        help="If a future email's subject contains this text (case-insensitive) for this "
        "sales channel, it will automatically be marked as 'Not a Booking'.",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        booking_id = self.env["mail.to.booking"].browse(self.env.context.get("active_id"))
        if booking_id:
            values["mail_to_booking_id"] = booking_id.id
            values["subject"] = booking_id.subject
            values["sale_channel_id"] = booking_id.sale_channel_id.id
            values["subject_keyword"] = booking_id.subject
        return values

    def action_confirm(self):
        self.ensure_one()
        self.env["mail.to.booking.subject.blocklist"].create(
            {
                "sale_channel_id": self.sale_channel_id.id,
                "subject_keyword": self.subject_keyword,
                "company_id": self.mail_to_booking_id.company_id.id,
            }
        )
        booking_id = self.mail_to_booking_id
        booking_id._remove_sale_order()
        booking_id.write(
            {
                "sale_channel_id": self.sale_channel_id.id,
                "is_booking": False,
                "state": "skipped",
                "error_message": False,
                "confirm_warning": False,
            }
        )
        return True
