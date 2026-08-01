from odoo import fields, models


class MailToBookingExcludedEmail(models.Model):
    _name = "mail.to.booking.excluded.email"
    _description = "Mail to Booking Excluded Email"
    _order = "email"

    email = fields.Char(
        required=True,
        help="A shared/forwarding mailbox address (e.g. the address a booking "
        "platform notification is forwarded through). Emails extracted from the "
        "message that match this address are never used to look up an existing "
        "res.partner - only the guest name found in the message is used.",
    )
    note = fields.Char(help="Why this address is excluded, e.g. which forwarding inbox it is.")
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
