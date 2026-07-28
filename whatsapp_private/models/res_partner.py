from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    whatsapp_private_jid = fields.Char(
        string="WhatsApp JID",
        index=True,
        copy=False,
        help="Technical WhatsApp linked-device identifier for this contact.",
    )
