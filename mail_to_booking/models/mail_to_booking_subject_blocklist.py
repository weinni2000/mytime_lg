from odoo import fields, models


class MailToBookingSubjectBlocklist(models.Model):
    _name = "mail.to.booking.subject.blocklist"
    _description = "Mail to Booking Subject Blocklist"
    _order = "sale_channel_id, subject_keyword"

    sale_channel_id = fields.Many2one("sale.channel", required=True, ondelete="cascade")
    subject_keyword = fields.Char(
        required=True,
        help="If a future email's subject contains this text (case-insensitive) for this "
        "sales channel, it is automatically marked as 'Not a Booking' without calling "
        "the extraction API.",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
