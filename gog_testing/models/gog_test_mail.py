from odoo import fields, models


class GogTestMail(models.Model):
    _name = "gog.test.mail"
    _description = "GOG Test Mail Result"
    _order = "mail_date desc"

    message_id = fields.Char(required=True)
    subject = fields.Char()
    sender = fields.Char()
    mail_date = fields.Char(string="Date")
